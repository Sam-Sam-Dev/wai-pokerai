from poker.action import Action
from poker.game_state import GameState
from poker.card import Rank
from poker.hand import evaluate
from poker.card import Card
from poker.card import Suit
import random

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

def myAI(state: GameState) -> Action:
    #sx = state
    #print(state.chips_in_pot)
    #Call_Odds = MonteCarlo(sx,Action.call(), 0)
    #print(state.chips_in_pot)
    if len(state.community_cards) == 0:
        return Action.call()
    else:
        return Action.raise_by(state.my_player.chips_in_stack-state.my_player.chips_bet)
    return defaultAI(state)


def defaultAI(state: GameState) -> Action: # This ai runs if myAI raises an exception, returns an invalid action or takes too long
    return Action.check() if state.my_player.chips_bet == max(player.chips_bet for player in state.players) else Action.fold()
