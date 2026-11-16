"""Exact Hold'em best-hand categories for compact PHH card strings."""
from functools import lru_cache
from itertools import combinations

RANKS = '23456789TJQKA'
SUITS = 'shdc'
CATEGORIES = ('high_card', 'pair', 'two_pair', 'three_of_a_kind', 'straight',
              'flush', 'full_house', 'four_of_a_kind', 'straight_flush')
DECK = tuple((rank, suit) for rank in range(13) for suit in range(4))


def _parse(cards):
    if len(cards) % 2:
        raise ValueError('Incomplete PHH card')
    return [(RANKS.index(cards[i]), SUITS.index(cards[i+1]))
            for i in range(0, len(cards), 2)]


def _straight(mask):
    # Five adjacent rank bits, or the ace-low wheel (A2345).
    return bool(mask & (mask >> 1) & (mask >> 2) & (mask >> 3) & (mask >> 4)
                or mask & 0x100F == 0x100F)


def _category(counts, suit_masks, mask):
    for suited in suit_masks:
        if suited.bit_count() >= 5:
            # A straight and a flush only form a straight flush when the
            # straight's five ranks are all in that SAME suit.
            return 8 if _straight(suited) else 5
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


def hand_category(hole_cards, community_cards):
    """Return best-hand category index (0..8), including board-only hands."""
    if len(hole_cards) != 4 or len(community_cards) not in (6, 8, 10):
        raise ValueError('Expected two hole cards and three to five board cards')
    cards = _parse(hole_cards + community_cards)
    if len(set(cards)) != len(cards):
        raise ValueError('Duplicate cards')
    counts, suits, mask = [0]*13, [0]*4, 0
    for rank, suit in cards:
        counts[rank] += 1
        suits[suit] |= 1 << rank
        mask |= 1 << rank
    return _category(counts, suits, mask)


@lru_cache(maxsize=None)
def possible_hands(board):
    """Nine binary flags for achievable best categories on the CURRENT board.

    No future board cards or actual players' hole cards are used. Enumerate
    legal holdings but classify rank/suit patterns directly, without Treys'
    enumeration of five-card subsets or its full numerical hand ranking.
    """
    if len(board) not in (6, 8, 10):
        raise ValueError('Expected three, four, or five visible board cards')
    cards = _parse(board)
    occupied = set(cards)
    if len(occupied) != len(cards):
        raise ValueError('Duplicate community cards')
    counts, suits, mask = [0]*13, [0]*4, 0
    for rank, suit in cards:
        counts[rank] += 1
        suits[suit] |= 1 << rank
        mask |= 1 << rank
    remaining = [card for card in DECK if card not in occupied]
    flags = [0]*9
    for (r1, s1), (r2, s2) in combinations(remaining, 2):
        counts[r1] += 1
        counts[r2] += 1
        current_suits = suits.copy()
        current_suits[s1] |= 1 << r1
        current_suits[s2] |= 1 << r2
        category = _category(counts, current_suits, mask | (1 << r1) | (1 << r2))
        flags[category] = 1
        counts[r1] -= 1
        counts[r2] -= 1
    return tuple(flags)


@lru_cache(maxsize=None)
def hand_category_probabilities(board):
    """Frequencies of current best categories over uniform two-card holdings.

    Only board cards are excluded, matching possible_hands. No future board
    cards are considered. Results follow CATEGORIES and sum to one.
    """
    if len(board) not in (6, 8, 10):
        raise ValueError('Expected three, four, or five visible board cards')
    cards = _parse(board)
    occupied = set(cards)
    if len(occupied) != len(cards):
        raise ValueError('Duplicate community cards')
    remaining = [RANKS[rank] + SUITS[suit]
                 for rank, suit in DECK if (rank, suit) not in occupied]
    counts = [0]*9
    for first, second in combinations(remaining, 2):
        counts[hand_category(first + second, board)] += 1
    total = sum(counts)
    return tuple(count / total for count in counts)
