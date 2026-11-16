from poker.action import Action
from poker.game_state import GameState
from poker.card import Rank
from poker.player import Blind
#from poker.hand import evaluate
from poker.card import Card
from poker.card import Suit
import random
#import torch
#import treys
import csv

def generate_deck(cards):
    deck = set()
    for rank in Rank:
        for suit in Suit:
            if Card(rank, suit) not in cards:
                deck.add(Card(rank, suit))
    return deck

def MonteCarlo(s: GameState, a: Action, depth):
    # check if the game has ended
    #if len(s.community_cards) == 5 and s.players[0].
    #s.my_player.hole_cards
    s.chips_in_pot += 500
    if depth > 15:
        return 0
    return 0

def card_to_string(card: Card) -> str:
    rank_map = {
        Rank.TWO: "2",
        Rank.THREE: "3",
        Rank.FOUR: "4",
        Rank.FIVE: "5",
        Rank.SIX: "6",
        Rank.SEVEN: "7",
        Rank.EIGHT: "8",
        Rank.NINE: "9",
        Rank.TEN: "T",
        Rank.JACK: "J",
        Rank.QUEEN: "Q",
        Rank.KING: "K",
        Rank.ACE: "A",
    }

    suit_map = {
        Suit.SPADE: "s",
        Suit.HEART: "h",
        Suit.DIAMOND: "d",
        Suit.CLUB: "c",
    }

    return rank_map[card.rank] + suit_map[card.suit]

comsize = -1
all_in = 0

# Loaded once when the competition program imports this bot.
from pathlib import Path
import math
import torch
from torch import nn
import treys
from hand_categories import possible_hands
from hand_categories import hand_category_probabilities

# SR4 (active). To use SR5, comment out this checkpoint and architecture,
# then uncomment both SR5 alternatives below and the feature call in myAI.
_checkpoint = torch.load(Path(__file__).with_name('model_best_combined22.pth'),
                         map_location='cpu', weights_only=True)
_model = nn.Sequential(nn.Linear(155, 64), nn.ReLU(), nn.Linear(64, 32),
                       nn.ReLU(), nn.Linear(32, 1))
# SR5: replace this filename with your checkpoint trained on 164 inputs.
# _checkpoint = torch.load(Path(__file__).with_name('model_best_sr5.pth'),
#                          map_location='cpu', weights_only=True)
# _model = nn.Sequential(nn.Linear(164, 64), nn.ReLU(), nn.Linear(64, 32),
#                        nn.ReLU(), nn.Linear(32, 1))
_model.load_state_dict(_checkpoint['model_state_dict'])
_model.eval()
_mean, _std = _checkpoint['mean'], _checkpoint['std']
_evaluator = treys.Evaluator()


def generate_features(state: GameState) -> list[float]:
    """155 SR4 inputs at the latest completed-street/current-board boundary.

    Deliberately reproduces the training serializer's cumulative bets, pot,
    starting-stack minimum and zero call amount. Current-street actions are
    used only to reconstruct starting stacks, not as trained boundary inputs.
    """
    count = len(state.players)
    if not 2 <= count <= 8 or len(state.community_cards) not in (3, 4, 5):
        raise ValueError('Model requires 2..8 players and a flop, turn or river')
    # PHH indices begin at the small blind, or the big blind heads-up.
    first_blind = Blind.BIG if count == 2 else Blind.SMALL
    first = next(i for i, player in enumerate(state.players) if player.blind is first_blind)
    players = state.players[first:] + state.players[:first]
    seats = {player.id: i for i, player in enumerate(players)}
    hero = seats[state.my_player.id]
    current_street = len(state.community_cards)-2
    actual_bets = [0.0]*count
    contributions = [0.0]*count
    for i, player in enumerate(players):
        blind = state.small_blind if player.blind is Blind.SMALL else state.big_blind if player.blind is Blind.BIG else 0
        actual_bets[i] = blind
        contributions[i] = state.ante + blind
    # Replay real contributions to recover stacks at the start of the hand.
    # return_uncalled refunds unmatched contributions at each street end.
    for street in range(current_street+1):
        if street:
            actual_bets = [0.0]*count
        for action in state.history:
            if action.street == street:
                seat = seats[action.id]
                contributions[seat] += action.chips_bet-actual_bets[seat]
                actual_bets[seat] = action.chips_bet
        if street < current_street:
            top = max(range(count), key=contributions.__getitem__)
            second = max(contributions[i] for i in range(count) if i != top)
            contributions[top] -= max(0.0, contributions[top]-second)
    stacks = [player.chips_in_stack+contributions[i] for i, player in enumerate(players)]
    total = sum(stacks)
    if total <= 0:
        raise ValueError('Invalid starting chip total')
    bets, folded = [0.0]*count, [False]*count
    summaries = [0.0]*100
    pot, to_call = 0.0, 0.0
    for street in range(current_street):
        raises = [0]*count
        for action in state.history:
            if action.street != street:
                continue
            seat = seats[action.id]
            if action.kind is Action.Kind.FOLD:
                folded[seat] = True
            elif action.kind in (Action.Kind.CHECK, Action.Kind.CALL):
                bets[seat] += min(to_call, stacks[seat]-bets[seat])
                pot += to_call
            elif action.kind is Action.Kind.RAISE:
                bets[seat] += action.chips_bet
                pot += action.chips_bet
                to_call = action.chips_bet
                raises[seat] += 1
        for seat in range(count):
            offset = 25*street+3*seat
            summaries[offset] = bets[seat]/total if seat != hero else 0.0
            summaries[offset+1] = raises[seat]
            summaries[offset+2] = int(folded[seat]) if seat != hero else 0
    hole = [treys.Card.new(card_to_string(card)) for card in state.my_player.hole_cards]
    board_text = ''.join(sorted(card_to_string(card) for card in state.community_cards))
    board = [treys.Card.new(board_text[i:i+2]) for i in range(0, len(board_text), 2)]
    score = _evaluator.evaluate(board, hole)
    best = [0]*9
    best[min(9-_evaluator.get_rank_class(score), 8)] = 1
    position = [int(i == hero) for i in range(8)]
    general = [bets[hero]/total, 0.0, min(stacks)/total, pot/total,
               _evaluator.get_five_card_rank_percentage(score)] + best
    occupied = [int(i < count) for i in range(8)]
    starting = [stack/total for stack in stacks]+[0.0]*(8-count)
    blinds = ([1.0, state.small_blind/state.big_blind] if count == 2
              else [0.5, 1.0]) + [0.0]*6
    features = position+general+occupied+starting+blinds+summaries+list(possible_hands(board_text))
    if len(features) != 155 or not all(math.isfinite(value) for value in features):
        raise ValueError('Invalid model features')
    return features


def generate_features_sr5(state: GameState) -> list[float]:
    """164 SR5 inputs: SR4 features followed by nine category probabilities.

    Category order is high card through straight flush. Probabilities count
    uniform legal hole-card pairs on the current board, excluding board cards
    only (including holdings overlapping hero's cards, as in training SR5).
    """
    features = generate_features(state)
    board_text = ''.join(sorted(card_to_string(card) for card in state.community_cards))
    features += list(hand_category_probabilities(board_text))
    if len(features) != 164 or not all(math.isfinite(value) for value in features):
        raise ValueError('Invalid SR5 model features')
    return features


# Completed hands are delivered on our next turn through previous_hands.
import fcntl
import hashlib
import json
import os
import uuid

_HAND_LOG = Path(os.environ.get('POKER_HAND_LOG',
                 str(Path(__file__).with_name('hand_logs') / 'myAI.phhs')))
_log_session = uuid.uuid4().hex
_logged_hands = set()
_observed_hands = {}

VALUE = {
    Rank.TWO: 2, Rank.THREE: 3, Rank.FOUR: 4, Rank.FIVE: 5,
    Rank.SIX: 6, Rank.SEVEN: 7, Rank.EIGHT: 8, Rank.NINE: 9,
    Rank.TEN: 10, Rank.JACK: 11, Rank.QUEEN: 12, Rank.KING: 13,
    Rank.ACE: 14,
}


def chen(a: Card, b: Card) -> float:
    # Bill Chen's score for two cards, only used to put the 1326 starting hands in order
    high, low = sorted((VALUE[a.rank], VALUE[b.rank]), reverse=True)
    score, gap = {14: 10, 13: 8, 12: 7, 11: 6}.get(high, high / 2), high - low - 1
    return max(score * 2, 5) + (high == 5) if gap < 0 else score - min(gap, 4) - (gap >= 3) + 2 * (a.suit is b.suit) + (gap <= 1 and high < 12)


def chen_confidence(a: Card, b: Card) -> float:
    """Normalize Chen's [-1.5, 20] range to a [0, 1] preflop confidence.

    This measures starting-hand strength, not win probability or whether a
    call is profitable; it does not account for opponents, position or price.
    Usage: confidence = chen_confidence(*state.my_player.hole_cards)
    """
    return max(0.0, min(1.0, (chen(a, b) + 1.5) / 21.5))


def log_completed_hands(state: GameState) -> None:
    """Append delivered HandRecords as PHH, preserving unknown hole cards."""
    observer = state.my_player.id
    for hand in state.previous_hands:
        # Rotate physical seats to the PHH convention without changing ids.
        first_blind = Blind.BIG if len(hand.players) == 2 else Blind.SMALL
        first = next(i for i, player in enumerate(hand.players) if player.blind is first_blind)
        players = hand.players[first:] + hand.players[:first]
        seats = {player.id: i+1 for i, player in enumerate(players)}
        signature = (_log_session, hand.number, tuple(seats),
                     tuple(hand.actions), tuple(map(card_to_string, hand.board)))
        hand_id = hashlib.sha256(repr(signature).encode()).hexdigest()
        if hand_id in _logged_hands:
            continue
        known = {player_id: ''.join(sorted(map(card_to_string, cards)))
                 for player_id, cards in hand.shown.items()}
        # Save our own privately observed cards even when we folded or mucked.
        observed = _observed_hands.get(observer)
        if observed is not None:
            player_ids, actions, board, cards = observed
            if (player_ids == frozenset(seats)
                    and list(actions) == hand.actions[:len(actions)]
                    and board.issubset(hand.board)):
                known[observer] = cards
                del _observed_hands[observer]
        actions = [f'd dh p{seats[player.id]} {known.get(player.id, "????")}'
                   for player in players]
        board = ''.join(map(card_to_string, hand.board))
        dealt_street = 0
        for action in hand.actions:
            while dealt_street < action.street:
                dealt_street += 1
                cards = board[:6] if dealt_street == 1 else board[2*dealt_street+2:2*dealt_street+4]
                actions.append(f'd db {cards}')
            player = f'p{seats[action.id]}'
            if action.kind is Action.Kind.RAISE:
                actions.append(f'{player} cbr {action.chips_bet}')
            elif action.kind is Action.Kind.FOLD:
                actions.append(f'{player} f')
            else:
                actions.append(f'{player} cc')
        # All-in runouts may deal streets with no subsequent player actions.
        final_street = max(0, len(hand.board)-2)
        while dealt_street < final_street:
            dealt_street += 1
            cards = board[:6] if dealt_street == 1 else board[2*dealt_street+2:2*dealt_street+4]
            actions.append(f'd db {cards}')
        for player_id in hand.shown:
            actions.append(f'p{seats[player_id]} sm {known[player_id]}')
        winnings = [hand.won.get(player.id, 0) for player in players]
        finishing = [player.chips_in_stack for player in players]
        # chips_bet in a HandRecord includes every street and the ante,
        # with uncalled bets already returned by the engine.
        starting = [player.chips_in_stack + player.chips_bet - winnings[i]
                    for i, player in enumerate(players)]
        data = {
            'variant': 'NT',
            'ante_trimming_status': False,
            'antes': [hand.ante]*len(players),
            'blinds_or_straddles': [hand.small_blind, hand.big_blind]+[0]*(len(players)-2),
            'min_bet': hand.big_blind,
            'starting_stacks': starting,
            'actions': actions,
            'players': [str(player.id) for player in players],
            'finishing_stacks': finishing,
            'winnings': winnings,
            'venue': 'WarwickAI poker-comp',
            'hand': hand_id,
            '_log_session': _log_session,
            '_observer_id': str(observer),
        }
        # JSON scalar/list syntax here is also valid TOML. Each unique table
        # is one hand, as expected by HandHistory.load_all in scwipt.py.
        record = '\n[h_'+hand_id+']\n'
        record += '\n'.join(f'{key} = {json.dumps(value)}' for key, value in data.items())+'\n'
        _HAND_LOG.parent.mkdir(parents=True, exist_ok=True)
        with _HAND_LOG.open('a', encoding='utf-8') as output:
            # Multiple poker test processes can safely append to one file.
            fcntl.flock(output.fileno(), fcntl.LOCK_EX)
            output.write(record)
            output.flush()
        _logged_hands.add(hand_id)
    _observed_hands[observer] = (
        frozenset(player.id for player in state.players), tuple(state.history),
        frozenset(state.community_cards),
        ''.join(sorted(map(card_to_string, state.my_player.hole_cards))),
    )


def myAI(state: GameState) -> Action:
    #log_completed_hands(state)
    mycards = list(state.my_player.hole_cards)
    to_call = max(player.chips_bet for player in state.players)-state.my_player.chips_bet
    if len(state.community_cards) == 0:
        #return Action.call()
        # No preflop training rows: check or call at most one big blind.
        #return Action.check() if to_call == 0 else Action.call() if chen(mycards[0],mycards[1]) >= 5 else Action.fold()
        #return Action.check() if to_call == 0 else Action.call() if random.random() < (0.25+(chen_confidence( mycards[0],mycards[1]))) else Action.fold()
        return Action.check() if to_call == 0 else Action.call() if to_call <= state.my_player.chips_in_stack*0.2 else Action.fold()
        return Action.check() if to_call == 0 else Action.call() if to_call <= state.big_blind*10 else Action.fold()
    if len(state.players) > 8:
        return Action.check() if to_call == 0 else Action.fold()
    features = torch.tensor(generate_features(state), dtype=torch.float32)
    # SR5: uncomment this and comment out the SR4 feature call above.
    # features = torch.tensor(generate_features_sr5(state), dtype=torch.float32)
    with torch.inference_mode():
        probability = _model(((features-_mean)/_std).unsqueeze(0)).sigmoid().item()
    can_raise = any(player.id != state.my_player.id and not player.has_folded
                    and player.chips_in_stack > 0 for player in state.players)
    if probability >= 0.7 and can_raise and state.my_player.chips_in_stack >= to_call+state.min_raise:
        return Action.raise_by(state.min_raise)
    if to_call == 0:
        return Action.check()
    return Action.call() if probability >= 0.5 else Action.fold()


def defaultAI(state: GameState) -> Action: # This ai runs if myAI raises an exception, returns an invalid action or takes too long
    return Action.call()
    return Action.check() if state.my_player.chips_bet == max(player.chips_bet for player in state.players) else Action.fold()

"""
if comsize == len(state.community_cards):
        return Action.call()
    comsize = len(state.community_cards)
    mh = list(state.my_player.hole_cards)
    comc = list(state.community_cards)
    hand = [treys.Card.new(card_to_string(mh[0])),treys.Card.new(card_to_string(mh[1]))]
    board = []
    for c in comc:
        board.append(treys.Card.new(card_to_string(c)))
    #print("67")
    heval = treys.Evaluator()
    #print("hehe")
    hscore = heval.evaluate(hand=hand,board=board)
    #print("hehe2")
    p_rank = heval.get_five_card_rank_percentage(hscore)
    #print("hehe3")
    #print(p_rank)
    #print("hehe end")
    #if len(state.community_cards) == 0:
"""


def calculate_hand_strength(hole_cards, community_cards):
    all_cards = list(hole_cards) + list(community_cards)
    
    # flush
    suits = [card.suit for card in all_cards]
    is_flush = any(suits.count(suit) >= 5 for suit in Suit)

    # straight
    present_values = set(rank_values[card.rank] for card in all_cards)
    # low ace
    if 14 in present_values:
        present_values.add(1)

    is_straight = False
    for low_end in range(1, 11):
        if set(range(low_end, low_end + 5)).issubset(present_values):
            is_straight = True
            break

    # pair three, four
    ranks = [card.rank for card in all_cards]
    counts = [ranks.count(rank) for rank in set(ranks)]

    pairs = counts.count(2)
    threes = counts.count(3)
    quads = counts.count(4)

    is_full_house = (threes > 0 and pairs > 0) or threes > 1

    # hole cards used for pair, three, four check
    hole_ranks = [card.rank for card in hole_cards]
    board_ranks = [card.rank for card in community_cards]

    hole_contributed = (hole_ranks[0] == hole_ranks[1]) or (hole_ranks[0] in board_ranks) or (hole_ranks[1] in board_ranks)

    board_suits = [card.suit for card in community_cards]
    flush_possible = any(board_suits.count(suit) >= 3 for suit in Suit)

    if is_flush and is_straight:
        return 0.95 # Straight Flush
    elif quads > 0:
        return 0.95 if hole_contributed else 0.10 # Four of a kind
    elif is_full_house:
        return 0.95 if hole_contributed else 0.10 # Full House
    elif is_flush:
        return 0.90 # Flush
    elif is_straight:
        return 0.90 if not flush_possible else 0.85 # Straight
    elif threes > 0:
        return 0.70 if hole_contributed else 0.10 # Three of a Kind
    elif pairs >= 2:
        return 0.60 if hole_contributed else 0.10 # Two Pair
    elif pairs == 1:
        return 0.40 if hole_contributed else 0.10 # One Pair
    else:
        return 0.10 # High Card

def get_best_hand(com_cards):
    max_strength = -1
    for R in Rank:
        for S in Suit:
            for r in Rank:
                for s in Suit:
                    h = {Card.new(R,S),Card.new(r,s)}
                    max_strength = max(max_strength,calculate_hand_strength(h,com_cards))
    return max_strength
                    
