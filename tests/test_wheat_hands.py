"""Unit tests for the wheat_hands experiment (issue #46, ADR-0007).

The single variable is the tail catch crop: WHEAT instead of the champion's
CARROT, reconciled with wheat's second job as cow feed. These tests pin the two
pure helpers that carry the change — `choose_catch_crop` (forces wheat) and
`_sell_orders_keep_feed` (sells wheat surplus but never the feed buffer) — plus
the end-to-end act() shape. The melon/cow/hiring machinery is the champion's and
is covered by its own suites; the full-game no-crash guard lives in test_no_crash.
"""

from __future__ import annotations

from strategies import catch_hands as ch
from strategies import dairy_hands as dh
from strategies import wheat_hands as wht


# --- choose_catch_crop: the one variable — wheat whenever it can fully mature ---

def test_catch_crop_is_wheat_not_carrot_in_the_tail():
    # Deep in the post-melon tail wheat still fits to full maturity -> WHEAT,
    # whereas the champion's ranker would pick CARROT here.
    assert wht.choose_catch_crop(20) == "WHEAT"
    assert ch.choose_catch_crop(20) == "CARROT"


def test_catch_crop_is_wheat_whenever_plantable():
    # For every day wheat can still fully mature, the choice is wheat.
    for day in range(0, wht.SEASON_DAYS):
        expected = "WHEAT" if ch.cc_plantable("WHEAT", day) else None
        assert wht.choose_catch_crop(day) == expected


def test_catch_crop_none_once_wheat_cannot_mature():
    # Wheat needs max_day (4) days to fill out; too close to the buzzer -> None.
    assert wht.choose_catch_crop(wht.SEASON_DAYS - 1) is None


# --- _sell_orders_keep_feed: sell wheat surplus, retain the cow feed buffer ---

def test_sells_wheat_surplus_above_the_feed_buffer():
    orders = wht._sell_orders_keep_feed({"WHEAT": 10})
    assert ["SELL", "WHEAT", 10 - dh.WHEAT_BUFFER] in orders


def test_never_sells_wheat_at_or_below_the_feed_buffer():
    # Exactly the buffer, or less: keep it all for feeding, sell nothing.
    assert wht._sell_orders_keep_feed({"WHEAT": dh.WHEAT_BUFFER}) == []
    assert wht._sell_orders_keep_feed({"WHEAT": 1}) == []


def test_other_products_sell_in_full():
    # Melon and milk are liquidated completely, unaffected by the wheat rule.
    orders = wht._sell_orders_keep_feed({"MELON": 12, "MILK": 3, "WHEAT": 5})
    assert ["SELL", "MELON", 12] in orders
    assert ["SELL", "MILK", 3] in orders
    assert ["SELL", "WHEAT", 5 - dh.WHEAT_BUFFER] in orders


# --- act(): end-to-end shape ---

def _empty_board():
    return [[None for _ in range(10)] for _ in range(10)]


def _obs(hour=0, day=0, money=3000, hands=None, shed=None, seeds=None):
    board = _empty_board()
    return {
        "player": 0,
        "day": day,
        "hour": hour,
        "farms": [
            {"money": money, "tiles": board, "farmer": [4, 4], "hands": hands or []},
            {"money": money, "tiles": _empty_board(), "farmer": [4, 4], "hands": []},
        ],
        "market": {"inventory": {}, "prices": {}},
        "town": {"unlocked_shops": []},
        "private": {"shed": shed or {}, "seeds": seeds or {}, "inventories": [{}]},
    }


def test_act_returns_valid_shape_and_hires_at_dawn():
    action = wht.WheatHandsStrategy().act(_obs(hour=0))
    assert set(action) == {"farmer", "hands", "market"}
    assert len(action["market"]) <= 10
    assert len([o for o in action["market"] if o[0] == "HIRE"]) == wht.MAX_HANDS


def test_act_sells_wheat_surplus_but_keeps_feed_buffer():
    obs = _obs(hour=5, shed={"WHEAT": 8, "MELON": 4})
    action = wht.WheatHandsStrategy().act(obs)
    assert ["SELL", "WHEAT", 8 - dh.WHEAT_BUFFER] in action["market"]
    assert ["SELL", "MELON", 4] in action["market"]


def test_act_emits_one_action_per_existing_hand():
    hands = [[5, 4], [4, 5], [5, 5]]
    action = wht.WheatHandsStrategy().act(_obs(hour=3, hands=hands))
    assert len(action["hands"]) == len(hands)
    assert isinstance(action["farmer"], list) and action["farmer"]
