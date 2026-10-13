from poker.action import Action
from poker.game_state import GameState
from poker.card import Rank
from poker.hand import evaluate
from poker.card import Card
from poker.card import Suit
import random

#used Monte Carlo simulation to estimate equity against active opponents, then compared to pot odds to determine whether to call, raise, or fold.

def myAI(state: GameState) -> Action:

    highest_bet = 0
    equitySum = 0
    raiseThreshold = 0.75
    for player in state.players:
        highest_bet = max(highest_bet, player.chips_bet)
    call_cost = highest_bet - state.my_player.chips_bet
    cards = list(state.my_player.hole_cards)
    all_cards = list(state.my_player.hole_cards | state.community_cards)
    deck = generate_deck(all_cards)
    missingCards = 5 - len(state.community_cards)
    activeOpponents = [player for player in state.players if player.has_folded == False and player is not state.my_player]
    if len(activeOpponents) == 0:
      if call_cost == 0:
        return Action.check()
      return Action.call()
    
    for x in range(8000):
        opponentCards = random.sample(deck, (len(activeOpponents)*2))
        opponentHands = []
        opponentScores = []
        tiedOpponents = 0

        for i in range(len(activeOpponents)):
            cards = opponentCards[2*i:2*i+2]
            opponentHands.append(cards)
        avaliableCommunityCards = [card for card in deck if card not in opponentCards]
        randomCommunityCards = random.sample(avaliableCommunityCards, missingCards)
        finalBoard = list(state.community_cards) + randomCommunityCards

        for x in range(len(opponentHands)):
            opponentFinalHand = opponentHands[x] + finalBoard
            opponentScore = evaluate(opponentFinalHand)
            opponentScores.append(opponentScore)
        highestOpponentScore = max(opponentScores)
        myFinalHand = list(state.my_player.hole_cards) + finalBoard
        myScore = evaluate(myFinalHand)

        for y in range(len(opponentScores)):
            if myScore == opponentScores[y]:
                tiedOpponents += 1
        if myScore > highestOpponentScore:
            equitySum += 1
        elif myScore == highestOpponentScore:
            equitySum += 1/(tiedOpponents + 1)
        else:
            equitySum += 0
    equity = equitySum / 8000
    required_equity = pot_odds_probability(state.chips_in_pot, call_cost)
    availableRaise = state.my_player.chips_in_stack - call_cost

    if equity > required_equity:
        if equity > raiseThreshold and availableRaise > 0:
            raiseAmount = max(1,int(state.chips_in_pot * 0.4))
            raiseAmount = min(raiseAmount, availableRaise)
            return Action.raise_by(raiseAmount)
        return Action.call()
    if call_cost == 0:
        return Action.check()
    return Action.fold()

def pot_odds_probability(currentPot, callCost):
    if callCost == 0:
        return 0.0
    return callCost / (currentPot + callCost)

def generate_deck(cards):
    deck = []
    for rank in Rank:
        for suit in Suit:
            if Card(rank, suit) not in cards:
                deck.append(Card(rank, suit))
    return deck


def defaultAI(state: GameState) -> Action: # This ai runs if myAI raises an exception, returns an invalid action or takes too long
    return Action.check() if state.my_player.chips_bet == max(player.chips_bet for player in state.players) else Action.fold()
