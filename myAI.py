"""Equity/pot-odds bot for the WAI engine. Entry points: myAI and defaultAI.

Optional classifier: put opponent_best.pth beside this file, or set
POKER_OPPONENT_MODEL to an opponent-v1 checkpoint. Without one, legal ranges
use a soft Chen preflop prior. No SR4/SR5 binary checkpoint is compatible.
The classifier architecture and 1,369 features match the opponent collector.
Raises assume all live opponents call what they can: no invented fold equity.
No files are written, and the existing myAI bot and engine are not imported.
"""
from collections import Counter, OrderedDict
from functools import lru_cache
from itertools import combinations
from pathlib import Path
import hashlib
import math
import os
import random
import time

import numpy as np
import treys
from poker.action import Action
from poker.card import Rank, Suit
from poker.game_state import GameState
from poker.player import Blind

CLASSES = ('high_card', 'pair', 'two_pair', 'three_of_a_kind', 'straight',
           'flush', 'full_house', 'four_of_a_kind', 'straight_flush', 'royal_flush')
DECK = tuple(r+s for r in '23456789TJQKA' for s in 'shdc')
CARD_INDEX = {card: i for i, card in enumerate(DECK)}
TREYS = tuple(treys.Card.new(card) for card in DECK)
RANK_TEXT = dict(zip(Rank, '23456789TJQKA'))
SUIT_TEXT = dict(zip(Suit, 'shdc'))
BASE_SIZE, SLOT_SIZE, INPUT_SIZE = 295, 358, 1369
SIMULATIONS = 320
DECISION_SECONDS = 0.65  # Leave room inside the engine's one-second alarm.
EVALUATOR = treys.Evaluator()


def card_text(card):
    return RANK_TEXT[card.rank] + SUIT_TEXT[card.suit]


def _straight(mask):
    return bool(mask & (mask >> 1) & (mask >> 2) & (mask >> 3) & (mask >> 4)
                or mask & 0x100F == 0x100F)


def _category(indices):
    counts, suits, mask = [0]*13, [0]*4, 0
    for index in indices:
        rank, suit = divmod(index, 4)
        counts[rank] += 1
        suits[suit] |= 1 << rank
        mask |= 1 << rank
    for suited in suits:
        if suited.bit_count() >= 5:
            if _straight(suited):
                return 9 if suited & 0x1F00 == 0x1F00 else 8
            return 5
    groups = sorted(counts, reverse=True)
    if groups[0] == 4:
        return 7
    if groups[0] == 3 and groups[1] >= 2:
        return 6
    if _straight(mask):
        return 4
    if groups[0] == 3:
        return 3
    if groups[0] == 2:
        return 2 if groups[1] == 2 else 1
    return 0


@lru_cache(maxsize=128)
def board_holdings(board):
    """All board-legal pairs, category counts, and board-only priors."""
    remaining = [i for i in range(52) if i not in board]
    pairs, labels, counts = [], [], [0]*10
    for a, b in combinations(remaining, 2):
        label = _category((*board, a, b)) if board else 0
        pairs.append((a, b))
        labels.append(label)
        counts[label] += 1
    odds = tuple(n/len(pairs) for n in counts)
    return tuple(pairs), tuple(labels), tuple(counts), odds


def _ordered(players):
    blind = Blind.BIG if len(players) == 2 else Blind.SMALL
    first = next((i for i, p in enumerate(players) if p.blind is blind), 0)
    return players[first:] + players[:first]


def _blinds(players, small, big):
    return [float(small if p.blind is Blind.SMALL else big if p.blind is Blind.BIG else 0)
            for p in players]


def _replay(players, stacks, blinds, ante, actions, street, bb, finish=False):
    """Match the collector's incremental contributions and boundary refunds."""
    n = len(players)
    seats = {p.id: i for i, p in enumerate(players)}
    bets = [min(b, max(0., s-ante)) for s, b in zip(stacks, blinds)]
    remaining = [s-min(s, ante)-b for s, b in zip(stacks, bets)]
    paid = [s-r for s, r in zip(stacks, remaining)]
    folded = [False]*n
    summaries = np.zeros((4, 8, 5), dtype=np.float32)
    current = 0

    def refund():
        top = max(range(n), key=bets.__getitem__)
        excess = max(0., bets[top]-max(b for i, b in enumerate(bets) if i != top))
        bets[top] -= excess
        remaining[top] += excess
        paid[top] -= excess

    for action in actions:
        while current < action.street:
            refund()
            bets = [0.]*n
            current += 1
        seat = seats[action.id]
        if action.kind is Action.Kind.FOLD:
            folded[seat] = True
            summaries[current, seat, 3] += 1
            continue
        call = max(0., max(bets)-bets[seat])
        amount = min(remaining[seat], max(0., action.chips_bet-bets[seat]))
        # CHECK/CALL are identical in PHH, so classify by outstanding call.
        kind = 2 if action.kind is Action.Kind.RAISE else int(call > 0)
        summaries[current, seat, kind] += 1
        summaries[current, seat, 4] += amount/bb
        bets[seat] += amount
        remaining[seat] -= amount
        paid[seat] += amount
    while current < street:
        refund()
        bets = [0.]*n
        current += 1
    if finish:
        refund()
    return remaining, bets, folded, paid, summaries


def _starting_stacks(state, players):
    """Recover contributions from public raise-to history, including refunds."""
    if not state.history:
        # On an actual first preflop turn, these are exactly the forced posts.
        # Synthetic postflop score states lack earlier contributions; keep that
        # unknown money in the shared main pot rather than invent side pots.
        paid = [float(state.ante+p.chips_bet) for p in players]
        return [p.chips_in_stack+c for p, c in zip(players, paid)], paid
    n = len(players)
    seats = {p.id: i for i, p in enumerate(players)}
    street = max(0, len(state.community_cards)-2)
    bets = _blinds(players, state.small_blind, state.big_blind)
    # Short blinds can be inferred directly on preflop score/test states.
    if street == 0:
        for i, player in enumerate(players):
            if player.chips_in_stack == 0:
                bets[i] = min(bets[i], player.chips_bet)
    paid = [state.ante+b for b in bets]
    current = 0
    for action in state.history:
        if action.street != current:
            top = max(range(n), key=bets.__getitem__)
            paid[top] -= max(0., bets[top]-max(b for i, b in enumerate(bets) if i != top))
            bets = [0.]*n
            current = action.street
        seat = seats[action.id]
        if action.kind is not Action.Kind.FOLD:
            paid[seat] += max(0., action.chips_bet-bets[seat])
            bets[seat] = action.chips_bet
    if current < street:
        top = max(range(n), key=bets.__getitem__)
        paid[top] -= max(0., bets[top]-max(b for i, b in enumerate(bets) if i != top))
        bets = [0.]*n
    # This also supports the engine's synthetic score states with no history.
    for i, player in enumerate(players):
        paid[i] += player.chips_bet-bets[i]
    # Correct inferable short blind/ante posts by inactive all-in players.
    surplus = max(0., sum(paid)-state.chips_in_pot)
    for i, player in enumerate(players):
        if surplus and not player.chips_in_stack and not any(a.id == player.id for a in state.history):
            reduction = min(surplus, max(0., paid[i]-player.chips_bet))
            paid[i] -= reduction
            surplus -= reduction
    return [p.chips_in_stack+max(0., paid[i]) for i, p in enumerate(players)], paid


def _public(players, stacks, blinds, ante, actions, street, board, target, bb, finish=False):
    remaining, bets, folded, paid, summaries = _replay(
        players, stacks, blinds, ante, actions, street, bb, finish)
    n = len(players)
    pad = lambda values: list(values)+[0.]*(8-n)
    odds = board_holdings(tuple(sorted(board)))[3]
    features = ([float(i == street) for i in range(4)]
                + [float(i == target) for i in range(8)]
                + [float(i < n) for i in range(8)]
                + pad(s/bb for s in stacks) + pad(r/bb for r in remaining)
                + pad(b/bb for b in bets) + pad(map(float, folded))
                + pad(b/bb for b in blinds)
                + [sum(paid)/bb, max(0., max(bets)-bets[target])/bb, n/8]
                + [float(i in board) for i in range(52)]
                + [float(p > 0) for p in odds] + list(odds)
                + summaries.reshape(-1).tolist())
    if len(features) != BASE_SIZE:
        raise ValueError('Opponent feature layout mismatch')
    return features


def _context(public, previous):
    features = list(public)
    for record in previous[-3:][::-1]:
        features += [1.] + list(record)
    return features + [0.]*(INPUT_SIZE-len(features))


_MODEL, _MEAN, _STD = None, None, None
MODEL_PATH = Path(os.environ.get('POKER_OPPONENT_MODEL',
                                str(Path(__file__).with_name('opponent_best.pth'))))
MODEL_STATUS = 'No checkpoint: using Chen-weighted legal ranges'
if MODEL_PATH.is_file():
    import torch
    from torch import nn
    torch.set_num_threads(1)
    checkpoint = torch.load(MODEL_PATH, map_location='cpu', weights_only=True)
    if (checkpoint.get('schema') != 'opponent-v1'
            or checkpoint.get('input_features') != INPUT_SIZE
            or tuple(checkpoint.get('classes', ())) != CLASSES):
        raise ValueError('Expected an opponent-v1 ten-class checkpoint, not an SR4/SR5 model')
    _MODEL = nn.Sequential(nn.Linear(INPUT_SIZE, 256), nn.ReLU(), nn.Dropout(.15),
                           nn.Linear(256, 128), nn.ReLU(), nn.Dropout(.15), nn.Linear(128, 10))
    _MODEL.load_state_dict(checkpoint['model_state_dict'])
    _MODEL.eval()
    _MEAN, _STD = checkpoint['mean'].float(), checkpoint['std'].float()
    if (_MEAN.shape != (INPUT_SIZE,) or _STD.shape != (INPUT_SIZE,)
            or not torch.isfinite(_MEAN).all() or not torch.isfinite(_STD).all()
            or not (_STD > 0).all()):
        raise ValueError('Invalid opponent checkpoint normalization')
    MODEL_STATUS = f'Using opponent classifier: {MODEL_PATH.name}'


class Memory:
    def __init__(self):
        self.history = {}
        self.seen = OrderedDict()
        self.hand_key = None
        self.latest_hand = 0
        self.ranges = {}
        self.last_decision = {}


_MEMORIES = OrderedDict()


def _learn(state, memory, deadline):
    if _MODEL is None:
        return
    # Only public shown cards populate context. Re-delivered records are ignored.
    for record in state.previous_hands:
        signature = (record.number, tuple(p.id for p in record.players),
                     tuple(record.actions), tuple(sorted(card_text(c) for c in record.board)))
        if signature in memory.seen:
            continue
        if time.perf_counter() > deadline - .15:
            break
        players = _ordered(record.players)
        stacks = [p.chips_in_stack+p.chips_bet-record.won.get(p.id, 0) for p in players]
        blinds = _blinds(players, record.small_blind, record.big_blind)
        board = tuple(sorted(CARD_INDEX[card_text(c)] for c in record.board))
        if len(board) >= 3 and 2 <= len(players) <= 8:
            street = len(board)-2
            for target, player in enumerate(players):
                if player.id not in record.shown:
                    continue
                hole = {CARD_INDEX[card_text(c)] for c in record.shown[player.id]}
                public = _public(players, stacks, blinds, record.ante, record.actions,
                                 street, board, target, record.big_blind, finish=True)
                label = _category((*board, *hole))
                previous = public + [float(i in hole) for i in range(52)] + [float(i == label) for i in range(10)]
                memory.history.setdefault(player.id, []).append(previous)
                memory.history[player.id] = memory.history[player.id][-3:]
        memory.seen[signature] = None
        if len(memory.seen) > 256:
            memory.seen.popitem(last=False)


def _chen(pair):
    high, low = sorted((pair[0]//4+2, pair[1]//4+2), reverse=True)
    score = {14: 10, 13: 8, 12: 7, 11: 6}.get(high, high/2)
    gap = high-low-1
    if gap < 0:
        return max(2*score, 5)+(high == 5)
    return score-min(gap, 4)-(gap >= 3)+2*(pair[0] % 4 == pair[1] % 4)+(gap <= 1 and high < 12)


def opponent_ranges(state, opponents, memory, board, hole):
    pairs, labels, counts, prior = board_holdings(board)
    hero_dead = set(hole)
    players = _ordered(state.players)
    stacks, _ = _starting_stacks(state, players)
    blinds = _blinds(players, state.small_blind, state.big_blind)
    seats = {p.id: i for i, p in enumerate(players)}
    street = max(0, len(board)-2)
    result = []
    for opponent in opponents:
        last = next((i for i in range(len(state.history)-1, -1, -1)
                     if state.history[i].id == opponent.id), None)
        action_key = tuple(state.history[:last+1]) if last is not None else ()
        saved = memory.ranges.get(opponent.id)
        if (board and _MODEL is not None and last is not None
                and state.history[last].street == street
                and (saved is None or saved[0] != (board, action_key))):
            public = _public(players, stacks, blinds, state.ante, state.history[:last+1],
                             street, board, seats[opponent.id], state.big_blind)
            features = _context(public, memory.history.get(opponent.id, []))
            with torch.inference_mode():
                tensor = torch.tensor(features, dtype=torch.float32)
                probabilities = _MODEL(((tensor-_MEAN)/_STD).unsqueeze(0)).softmax(-1)[0].tolist()
            probabilities = [.85*p+.15*q for p, q in zip(probabilities, prior)]
            weighted = [(pair, probabilities[label]/counts[label])
                        for pair, label in zip(pairs, labels) if not hero_dead.intersection(pair)]
            saved = ((board, action_key), weighted)
            memory.ranges[opponent.id] = saved
        if saved is not None:
            # Carry a hole-card distribution across streets, conditioning on new cards.
            weighted = [(pair, weight) for pair, weight in saved[1]
                        if not set(pair).intersection((*board, *hole))]
        else:
            preflop = [a.kind for a in state.history if a.id == opponent.id and a.street == 0]
            strength = .22 if Action.Kind.RAISE in preflop else .12 if Action.Kind.CALL in preflop else 0.
            weighted = [(pair, math.exp(strength*_chen(pair))) for pair in pairs
                        if not hero_dead.intersection(pair)]
        if not weighted:
            weighted = [(pair, 1.) for pair in pairs if not hero_dead.intersection(pair)]
        holdings = [pair for pair, _ in weighted]
        cumulative, total = [], 0.
        for _, weight in weighted:
            total += weight
            cumulative.append(total)
        result.append((holdings, cumulative))
    return result


def _pots(contributions, folded, hero):
    """Hero-eligible side pots; uncalled excess is a one-player refund pot."""
    result, previous = [], 0.
    for level in sorted({c for c in contributions if c > 0}):
        amount = sum(min(c, level)-min(c, previous) for c in contributions)
        eligible = tuple(i for i, c in enumerate(contributions) if c >= level and not folded[i])
        if result and (not eligible or eligible == result[-1][1]):
            result[-1] = (result[-1][0]+amount, result[-1][1])
        else:
            result.append((amount, eligible))
        previous = level
    return [(amount, eligible) for amount, eligible in result if hero in eligible]


def _scenarios(state, players, hero, paid):
    me = state.my_player
    outstanding = max(p.chips_bet for p in players)-me.chips_bet
    call = min(me.chips_in_stack, max(0, outstanding))
    left = me.chips_in_stack-outstanding
    sizes = [0]
    if left > 0 and any(p.id != me.id and not p.has_folded and p.chips_in_stack > 0 for p in players):
        for fraction in (.5, 1.):
            sizes.append(int(min(left, max(state.min_raise, int(fraction*(state.chips_in_pot+call))))))
    scenarios = []
    for size in sorted(set(sizes)):
        contributions = list(paid)
        cost = call+size
        contributions[hero] += cost
        if size:
            target = me.chips_bet+outstanding+size
            for i, p in enumerate(players):
                if i != hero and not p.has_folded:
                    contributions[i] += min(p.chips_in_stack, max(0, target-p.chips_bet))
        pots = _pots(contributions, [p.has_folded for p in players], hero)
        scenarios.append((size, cost, pots))
    return scenarios


def estimate_actions(state, memory, deadline):
    """Monte Carlo chip EV; independent ranges conditioned on no card collisions."""
    players = _ordered(state.players)
    hero = next(i for i, p in enumerate(players) if p.id == state.my_player.id)
    opponents = [p for p in players if p.id != state.my_player.id and not p.has_folded]
    opponent_seats = [i for i, p in enumerate(players) if p.id != state.my_player.id and not p.has_folded]
    hole = tuple(sorted(CARD_INDEX[card_text(c)] for c in state.my_player.hole_cards))
    board = tuple(sorted(CARD_INDEX[card_text(c)] for c in state.community_cards))
    ranges = opponent_ranges(state, opponents, memory, board, hole)
    _, paid = _starting_stacks(state, players)
    # Preserve unassigned dead money in synthetic states (real histories sum exactly).
    extra_pot = max(0., state.chips_in_pot-sum(paid))
    scenarios = _scenarios(state, players, hero, paid)
    if extra_pot:
        for _, _, pots in scenarios:
            pots.append((extra_pot, (hero, *opponent_seats)))
    seed = hashlib.sha256(repr((tuple((p.id, p.chips_bet, p.chips_in_stack) for p in players),
                                hole, board, tuple(state.history))).encode()).digest()
    rng = random.Random(int.from_bytes(seed[:8], 'big'))
    sums, squares = [0.]*len(scenarios), [0.]*len(scenarios)
    count = 0
    while count < SIMULATIONS and time.perf_counter() < deadline:
        # Reject the WHOLE joint draw when two opponents overlap, avoiding
        # order-dependent sequential range sampling and impossible deals.
        for _ in range(64):
            dead, hands = set((*hole, *board)), []
            for holdings, cumulative in ranges:
                pair = rng.choices(holdings, cum_weights=cumulative, k=1)[0]
                if dead.intersection(pair):
                    break
                dead.update(pair)
                hands.append(pair)
            else:
                break
        else:
            continue
        full = (*board, *rng.sample([i for i in range(52) if i not in dead], 5-len(board)))
        full_treys = [TREYS[i] for i in full]
        scores = {hero: EVALUATOR.evaluate(full_treys, [TREYS[i] for i in hole])}
        for seat, hand in zip(opponent_seats, hands):
            scores[seat] = EVALUATOR.evaluate(full_treys, [TREYS[i] for i in hand])
        for index, (_, cost, pots) in enumerate(scenarios):
            returned = 0.
            for amount, eligible in pots:
                best = min(scores[i] for i in eligible)
                winners = [i for i in eligible if scores[i] == best]
                if hero in winners:
                    returned += amount/len(winners)
            profit = returned-cost
            sums[index] += profit
            squares[index] += profit*profit
        count += 1
    if not count:
        return [], 0
    estimates = []
    for (size, cost, pots), total, square in zip(scenarios, sums, squares):
        ev = total/count
        error = math.sqrt(max(0., square/count-ev*ev)/count)
        eligible_pot = sum(amount for amount, _ in pots)
        estimates.append(dict(raise_by=size, cost=cost, ev=ev, stderr=error,
                              equity=(ev+cost)/eligible_pot if eligible_pot else 1.,
                              pot_odds=cost/eligible_pot if eligible_pot else 0.))
    return estimates, count


def defaultAI(state: GameState) -> Action:
    to_call = max(p.chips_bet for p in state.players)-state.my_player.chips_bet
    return Action.check() if to_call <= 0 else Action.fold()


def myAI(state: GameState) -> Action:
    start = time.perf_counter()
    hero_id = state.my_player.id
    memory = _MEMORIES.setdefault(hero_id, Memory())
    _MEMORIES.move_to_end(hero_id)
    if len(_MEMORIES) > 32:
        _MEMORIES.popitem(last=False)
    _learn(state, memory, start+DECISION_SECONDS)
    if state.previous_hands:
        memory.latest_hand = max(record.number for record in state.previous_hands)
    # A new hand has a different deal or a history that no longer extends the
    # preceding call. Do not carry ranges into another hand or another hero.
    key = (memory.latest_hand, tuple(sorted(p.id for p in state.players if p.id is not None)),
           tuple(sorted(card_text(c) for c in state.my_player.hole_cards)))
    old_key = memory.hand_key
    history = tuple(state.history)
    if old_key is None or old_key[0] != key or history[:len(old_key[1])] != old_key[1]:
        memory.ranges.clear()
    memory.hand_key = (key, history)
    if not 2 <= len(state.players) <= 8 or len(state.community_cards) not in (0, 3, 4, 5):
        return defaultAI(state)
    estimates, count = estimate_actions(state, memory, start+DECISION_SECONDS)
    memory.last_decision = dict(simulations=count, actions=estimates, model=MODEL_STATUS)
    if not estimates:
        return defaultAI(state)
    calling = estimates[0]
    to_call = max(p.chips_bet for p in state.players)-state.my_player.chips_bet
    best = max(estimates, key=lambda item: item['ev'])
    # Require a clear value advantage to raise; uncertainty discourages marginal
    # paid calls. Checking is always preferable to folding when it is free.
    raise_margin = max(state.big_blind, .03*state.chips_in_pot, best['stderr'])
    if best['raise_by'] and best['ev'] > max(0., calling['ev'])+raise_margin:
        return Action.raise_by(int(best['raise_by']))
    if to_call <= 0:
        return Action.check()
    return Action.call() if calling['ev'] > .5*calling['stderr'] else Action.fold()
