from poker.action import Action
from poker.game_state import GameState
from poker.card import Rank
from poker.player import Blind
#from poker.hand import evaluate
from poker.card import Card
from poker.card import Suit
import random
#import torch
import treys
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

def myAI(state: GameState) -> Action:
    global comsize
    global all_in
    if state.my_player.blind is Blind.BIG:
        if len(state.community_cards) == 0:
            return Action.call()
        elif max(state.my_player.chips_in_stack-state.my_player.chips_bet,0) != 0:
            #return Action.raise_by(min(state.my_player.chips_in_stack-state.my_player.chips_bet,state.min_raise))
            return Action.raise_by(max(state.my_player.chips_in_stack-state.my_player.chips_bet,0))
        else:  
            return Action.fold()
    else:
        return Action.fold()
    #sx = state
    #print(state.chips_in_pot)
    #Call_Odds = MonteCarlo(sx,Action.call(), 0)
    #print(state.chips_in_pot)
    #if state.my_player.blind is Blind.BIG:
    to_call = max([p.chips_bet for p in state.players])-state.my_player.chips_bet
    mh = list(state.my_player.hole_cards)
    comc = list(state.community_cards)
    hand = [treys.Card.new(card_to_string(mh[0])),treys.Card.new(card_to_string(mh[1]))]
    board = []
    for c in comc:
        board.append(treys.Card.new(card_to_string(c)))
    #print("67")
    heval = treys.Evaluator()
    
    #print("hehe")
    if len(state.community_cards) != 0:
        hscore = heval.evaluate(hand=hand,board=board)
        #print("hehe2")
        p_rank = heval.get_five_card_rank_percentage(hscore)
        
        #print("hehe3")
        #print(p_rank)
        #print("hehe end")
        passed = True
        for pl in state.players:
            if pl.chips_in_stack != 0:
                if random.random() < p_rank * max(to_call/state.my_player.chips_in_stack,1.0):
                    passed = False
    if len(state.community_cards) == 0:
        if to_call < 10:
            return Action.call()
        else:
            return Action.fold()
    elif max(state.my_player.chips_in_stack-state.my_player.chips_bet,0) != 0:
        if p_rank < 0.1:
            return Action.raise_by(min(state.my_player.chips_in_stack-state.my_player.chips_bet,state.min_raise))
        else:
            return Action.fold()
    else:  
        return Action.fold()
    """
    allin = 0
    stacks = [p.chips_in_stack for p in state.players]
    if state.my_player.chips_in_stack == max(stacks):
        stacks.remove(max(stacks))
        if state.my_player.chips_in_stack/max(stacks) > 3:
            allin = 1
    print(state.my_player.chips_in_stack,max(stacks))
    if len(state.community_cards) == 0:
            return Action.call()
    else:
        if allin == 1:
            if max(state.my_player.chips_in_stack-state.my_player.chips_bet,0) != 0:
                return Action.raise_by(state.my_player.chips_in_stack-state.my_player.chips_bet)
            else:
                return Action.fold()
        else:
            my_hand_strength = calculate_hand_strength(state.my_player.hole_cards,state.community_cards)
            best_strength = get_best_hand(state.community_cards)
            if my_hand_strength == best_strength:
                if max(state.my_player.chips_in_stack-state.my_player.chips_bet,0) != 0:
                    return Action.call()
                    return Action.raise_by(state.my_player.chips_in_stack-state.my_player.chips_bet)
                else:
                    return Action.fold()
            else:
                return Action.fold()
    #else:
        #return Action.fold()
    if comsize == len(state.community_cards):
        return Action.call()
    

    stacks = [p.chips_in_stack for p in state.players]
    
    if len(state.community_cards) == 0:
        if state.my_player.chips_in_stack == max(stacks):
            stacks.remove(max(stacks))
            if state.my_player.chips_in_stack/max(stacks) > 3:
                all_in = 1
                return Action.call()
            else:
                all_in = 0
                to_call = max([p.chips_bet for p in state.players])-state.my_player.chips_bet
                if to_call > int(state.my_player.chips_in_stack*0.05):
                    return Action.fold()
                else:
                    return Action.call() if to_call != 0 else Action.check()
        else:
            all_in = 0
            to_call = max([p.chips_bet for p in state.players])-state.my_player.chips_bet
            if to_call > int(state.my_player.chips_in_stack*0.05):
                return Action.fold()
            else:
                return Action.call() if to_call != 0 else Action.check()
    elif len(state.community_cards) == 3:
        if all_in == 1:
            if max(state.my_player.chips_in_stack-state.my_player.chips_bet,0) != 0:
                return Action.raise_by(state.my_player.chips_in_stack-state.my_player.chips_bet)
            else:
                return Action.fold()
        else:
            my_hand_strength = calculate_hand_strength(state.my_player.hole_cards,state.community_cards)
            best_strength = get_best_hand(state.community_cards)
            #if best_strength-my_hand_strength < 0.20:
            if my_hand_strength > 0.40:
                return Action.call()
            else:
                return Action.fold()
    else:
        to_call = max([p.chips_bet for p in state.players])-state.my_player.chips_bet
        return Action.call() if to_call != 0 else Action.check()
           """ 
    """ # call then all in
    if len(state.community_cards) == 0:
        return Action.call()
    elif max(state.my_player.chips_in_stack-state.my_player.chips_bet,0) != 0:
        return Action.raise_by(state.my_player.chips_in_stack-state.my_player.chips_bet)
    else:
        return Action.fold()"""
    return defaultAI(state)


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
                    