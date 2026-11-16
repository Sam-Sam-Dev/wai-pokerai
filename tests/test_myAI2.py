import importlib.util
import os
from pathlib import Path
import random
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import myAI2 as bot
from poker.action import Action
from poker.card import Card, Rank, Suit
from poker.game_state import GameState, HandAction
from poker.player import Blind, MyPlayer, Player
from poker.internals.engine import Match
from poker.internals.rules import Rules


def card(text):
    return Card(list(Rank)['23456789TJQKA'.index(text[0])], list(Suit)['shdc'.index(text[1])])


def state(hole=('As', 'Ks'), board=('Qs', 'Js', 'Ts', '2h', '3d'), bet=0, stack=100, others=1):
    me = MyPlayer(id=1, blind=Blind.SMALL, chips_in_stack=stack, chips_bet=0,
                  hole_cards=set(map(card, hole)))
    players = [me] + [Player(id=i+2, blind=Blind.BIG if i == 0 else None,
                            chips_in_stack=100, chips_bet=bet) for i in range(others)]
    return GameState(my_player=me, players=players, chips_in_pot=30+bet*others,
                     community_cards=set(map(card, board)), small_blind=1, big_blind=2)


class EquityBotTests(unittest.TestCase):
    def setUp(self):
        bot._MEMORIES.clear()
        self.model = patch.object(bot, '_MODEL', None)
        self.model.start()
        self.addCleanup(self.model.stop)

    def test_royal_board_multiway_ties(self):
        s = state(hole=('2h', '3d'), board=('As', 'Ks', 'Qs', 'Js', 'Ts'), others=2)
        estimates, count = bot.estimate_actions(s, bot.Memory(), time.perf_counter()+1)
        self.assertEqual(count, bot.SIMULATIONS)
        self.assertAlmostEqual(estimates[0]['equity'], 1/3)
        self.assertEqual(bot.myAI(s), Action.check())

    def test_nuts_raise_is_additional_integer_and_within_stack(self):
        s = state(bet=10, stack=60)
        action = bot.myAI(s)
        self.assertIs(action.kind, Action.Kind.RAISE)
        self.assertIs(type(action.amount), int)
        self.assertGreaterEqual(action.amount, s.min_raise)
        self.assertLessEqual(action.amount, 50)

    def test_beaten_hand_folds_even_with_same_category(self):
        s = state(hole=('Kh', 'Kd'), board=('2c', '3d', '5h', '7s', '9c'), bet=100)
        pair = (bot.CARD_INDEX['Ah'], bot.CARD_INDEX['Ad'])
        with patch.object(bot, 'opponent_ranges', return_value=[([pair], [1.])]):
            self.assertEqual(bot.myAI(s), Action.fold())

    def test_short_all_in_call_and_side_pot(self):
        s = state(bet=100, stack=5, others=2)
        action = bot.myAI(s)
        self.assertEqual(action, Action.call())
        players = bot._ordered(s.players)
        hero = next(i for i, p in enumerate(players) if p.id == 1)
        _, paid = bot._starting_stacks(s, players)
        scenarios = bot._scenarios(s, players, hero, paid)
        self.assertEqual(len(scenarios), 1)
        self.assertEqual(scenarios[0][1], 5)
        self.assertEqual(sum(p for p, _ in scenarios[0][2]), 15)

    def test_dead_money_and_refund_pots(self):
        pots = bot._pots([10, 30, 30], [False, False, False], 0)
        self.assertEqual(pots, [(30, (0, 1, 2))])
        self.assertEqual(bot._pots([40, 10], [False, False], 0), [(20, (0, 1)), (30, (0,))])
        self.assertEqual(bot._pots([10, 20], [False, True], 0), [(30, (0,))])

    def test_no_raise_when_every_opponent_is_all_in(self):
        s = state()
        s.players[1].chips_in_stack = 0
        self.assertIsNot(bot.myAI(s).kind, Action.Kind.RAISE)

    def test_legal_ranges_exclude_hero_and_board(self):
        s = state()
        board = tuple(sorted(bot.CARD_INDEX[bot.card_text(c)] for c in s.community_cards))
        hole = tuple(bot.CARD_INDEX[bot.card_text(c)] for c in s.my_player.hole_cards)
        ranges = bot.opponent_ranges(s, s.players[1:], bot.Memory(), board, hole)
        for pair in ranges[0][0]:
            self.assertFalse(set(pair).intersection((*board, *hole)))
        self.assertTrue(all(a < b for a, b in zip(ranges[0][1], ranges[0][1][1:])))

    def test_deadline_exhaustion_returns_legal_fallback(self):
        s = state(bet=10)
        with patch.object(bot, 'DECISION_SECONDS', 0):
            self.assertEqual(bot.myAI(s), Action.fold())
        s.players[1].chips_bet = 0
        with patch.object(bot, 'DECISION_SECONDS', 0):
            self.assertEqual(bot.myAI(s), Action.check())

    def test_real_engine_actions_and_starting_stacks(self):
        rules = Rules()
        rules.hands = 12
        checked = []
        match = None

        def observed(s):
            players = bot._ordered(s.players)
            recovered, _ = bot._starting_stacks(s, players)
            for p, total in zip(players, recovered):
                seat = next(seat for seat in match.seats if seat.id == p.id)
                self.assertEqual(total, seat.stack+seat.total_bet)
            action = bot.myAI(s)
            if action.kind is Action.Kind.CHECK:
                self.assertEqual(max(p.chips_bet for p in s.players), s.my_player.chips_bet)
            checked.append(action)
            return action

        match = Match(ais=[('equity', observed), ('caller', lambda s: Action.call()),
                           ('caller2', lambda s: Action.call())], rules=rules, seed=7)
        for i, seat in enumerate(match.seats):
            seat.id = i+1
        match.play()
        self.assertTrue(checked)
        self.assertEqual([seat.errors for seat in match.seats], [0, 0, 0])

    def test_checkpoint_loading_and_context_feature_input(self):
        import torch
        from torch import nn
        model = nn.Sequential(nn.Linear(1369, 256), nn.ReLU(), nn.Dropout(.15),
                              nn.Linear(256, 128), nn.ReLU(), nn.Dropout(.15), nn.Linear(128, 10))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'opponent.pth'
            torch.save(dict(schema='opponent-v1', classes=list(bot.CLASSES), input_features=1369,
                            model_state_dict=model.state_dict(), mean=torch.zeros(1369),
                            std=torch.ones(1369)), path)
            with patch.dict(os.environ, POKER_OPPONENT_MODEL=str(path)):
                spec = importlib.util.spec_from_file_location('equity_with_model', ROOT/'myAI2.py')
                loaded = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(loaded)
            self.assertIsNotNone(loaded._MODEL)
            s = state(bet=10)
            s.history = [HandAction(id=2, street=3, kind=Action.Kind.RAISE, chips_bet=10)]
            action = loaded.myAI(s)
            self.assertIsInstance(action, Action)
            self.assertIn(2, loaded._MEMORIES[1].ranges)
            self.assertEqual(len(loaded._MEAN), 1369)


if __name__ == '__main__':
    unittest.main()
