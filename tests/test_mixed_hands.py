"""Unit tests for mixed_hands — the integration of the melon crew (#33), the
carrot catch-crop + sell-before-hire fix (#27), and the dairy cow (#32).

This is an integration, not a single-variable experiment, so these tests focus on
the *composition* seams the combine introduces: that all product SELLs precede the
HIRE orders (and WHEAT is never sold), that the farmer honors the melon > carrot >
cow priority on its own plot, and that the three overlays coexist in one act()
without crashing or blowing the 10-order market cap. The underlying pure helpers
(`_decide`, `plan_hands_multicrop`, `cow_farmer_action`) are covered by the
catch_hands / dairy_hands suites; here we test them only as wired together.
"""

from __future__ import annotations

from strategies import mixed_hands as mx


def _empty_board():
    return [[None for _ in range(10)] for _ in range(10)]


def _obs(hour=0, day=0, money=3000, hands=None, shed=None, seeds=None,
         board=None, farmer=(4, 4), inv=None):
    return {
        "player": 0,
        "day": day,
        "hour": hour,
        "farms": [
            {"money": money, "tiles": board or _empty_board(),
             "farmer": list(farmer), "hands": hands or []},
            {"money": money, "tiles": _empty_board(), "farmer": [4, 4], "hands": []},
        ],
        "market": {"inventory": {}, "prices": {}},
        "town": {"unlocked_shops": []},
        "private": {"shed": shed or {}, "seeds": seeds or {},
                    "inventories": [inv or {}]},
    }


# --- _sell_orders_no_wheat: sells carrot/melon/milk, never wheat ---

def test_sell_orders_liquidates_products_but_keeps_wheat():
    orders = mx._sell_orders_no_wheat({"MELON": 4, "CARROT": 6, "MILK": 3, "WHEAT": 2})
    assert ["SELL", "CARROT", 6] in orders
    assert ["SELL", "MELON", 4] in orders
    assert ["SELL", "MILK", 3] in orders
    assert all(o[1] != "WHEAT" for o in orders)


def test_sell_orders_empty_shed_is_empty():
    assert mx._sell_orders_no_wheat({}) == []


# --- act(): dawn hires the full crew, shape is valid ---

def test_act_hires_full_crew_at_dawn():
    action = mx.MixedHandsStrategy().act(_obs(hour=0, money=5000))
    hires = [o for o in action["market"] if o[0] == "HIRE"]
    assert len(hires) == mx.MAX_HANDS
    assert len(action["market"]) <= 10
    assert isinstance(action["farmer"], list) and action["farmer"]
    assert action["hands"] == []  # no hands exist yet at hour 0


def test_act_emits_one_action_per_existing_hand():
    hands = [[5, 4], [4, 5], [5, 5]]
    action = mx.MixedHandsStrategy().act(_obs(hour=3, hands=hands))
    assert len(action["hands"]) == len(hands)


# --- Market ordering: every product SELL precedes every HIRE ---

def test_all_sells_precede_hires():
    obs = _obs(hour=0, money=5000, shed={"MELON": 5, "CARROT": 4, "MILK": 2})
    market = mx.MixedHandsStrategy().act(obs)["market"]
    sell_idx = [i for i, o in enumerate(market) if o[0] == "SELL"]
    hire_idx = [i for i, o in enumerate(market) if o[0] == "HIRE"]
    assert sell_idx and hire_idx
    assert max(sell_idx) < min(hire_idx)


def test_melon_sell_survives_the_order_cap_with_a_full_crew():
    # A full dawn crew (9 HIRE) plus milk+melon must not push the melon SELL past
    # the 10-order cap — the whole point of selling before hiring.
    obs = _obs(hour=0, money=5000, shed={"MELON": 7, "MILK": 3})
    market = mx.MixedHandsStrategy().act(obs)["market"]
    assert ["SELL", "MELON", 7] in market
    assert ["SELL", "MILK", 3] in market
    assert len(market) <= 10


def test_wheat_is_never_sold_even_when_held():
    obs = _obs(hour=5, shed={"WHEAT": 2, "MELON": 3})
    market = mx.MixedHandsStrategy().act(obs)["market"]
    assert ["SELL", "MELON", 3] in market
    assert all(not (o[0] == "SELL" and o[1] == "WHEAT") for o in market)


# --- Farmer priority: real melon work beats the cow chore ---

def test_farmer_waters_its_melon_before_tending_the_cow():
    # Unwatered live melon at (4,4): the farmer must WATER, not wander to the cow,
    # even with a placed, hungry cow standing at (2,2).
    board = _empty_board()
    board[4][4] = {"kind": "PLANT", "crop": "MELON", "planted_day": 3,
                   "yield_units": 1, "watered_today": False}
    board[2][2] = {"kind": "PASTURE", "animal": "COW", "yield_units": 0,
                   "fed_today": False, "cared_today": False}
    action = mx.MixedHandsStrategy().act(
        _obs(hour=2, day=4, board=board, inv={"WHEAT": 2})
    )
    assert action["farmer"] == ["WATER"]


def test_farmer_tends_cow_when_its_plot_is_already_watered():
    # Melon already watered (plot wants nothing): the idle farmer turns to the
    # cow — here an unfed cow it is standing on gets FED.
    board = _empty_board()
    board[4][4] = {"kind": "PLANT", "crop": "MELON", "planted_day": 3,
                   "yield_units": 1, "watered_today": True}
    board[2][2] = {"kind": "PASTURE", "animal": "COW", "yield_units": 0,
                   "fed_today": False, "cared_today": False}
    action = mx.MixedHandsStrategy().act(
        _obs(hour=2, day=4, board=board, farmer=(2, 2), inv={"WHEAT": 2})
    )
    assert action["farmer"] == ["FEED"]


def test_farmer_harvests_ready_milk_on_a_spare_turn():
    board = _empty_board()
    # Immature, already-watered melon: the plot wants nothing this turn.
    board[4][4] = {"kind": "PLANT", "crop": "MELON", "planted_day": 16,
                   "yield_units": 0, "watered_today": True}
    board[2][2] = {"kind": "PASTURE", "animal": "COW", "yield_units": 2,
                   "fed_today": True, "cared_today": True}
    action = mx.MixedHandsStrategy().act(
        _obs(hour=2, day=18, board=board, farmer=(2, 2))
    )
    assert action["farmer"] == ["HARVEST"]


# --- Catch-crop: the farmer's own plot grows carrot in the post-melon tail ---

def test_farmer_plants_carrot_in_the_tail_when_melon_has_closed():
    # Day 24: melon horizon closed, carrot still fits; empty (4,4) with carrot
    # seed on hand should be planted with the catch crop, not left fallow.
    obs = _obs(hour=0, day=24, seeds={"CARROT": 2})
    action = mx.MixedHandsStrategy().act(obs)
    assert action["farmer"] == ["PLANT", "CARROT"]


def test_tail_restock_buys_carrot_seed_not_melon():
    obs = _obs(hour=5, day=24, hands=[[4, 4]] * 3)
    market = mx.MixedHandsStrategy().act(obs)["market"]
    seed_buys = [o for o in market if o[0] == "BUY_SEED"]
    assert seed_buys and all(o[1] == "CARROT" for o in seed_buys)


# --- Cow purchase: lowest priority, gated on a comfortable cash buffer ---

def test_buys_cow_when_flush_and_none_exists():
    obs = _obs(hour=5, money=mx.dh.COW_COST + mx.dh.COW_MONEY_BUFFER + 100)
    market = mx.MixedHandsStrategy().act(obs)["market"]
    assert ["BUY_ANIMAL", "COW", 1] in market


def test_no_cow_purchase_when_capital_is_tight():
    obs = _obs(hour=5, money=300)
    market = mx.MixedHandsStrategy().act(obs)["market"]
    assert ["BUY_ANIMAL", "COW", 1] not in market


def test_no_second_cow_when_one_is_placed():
    board = _empty_board()
    board[2][2] = {"kind": "PASTURE", "animal": "COW", "yield_units": 0}
    obs = _obs(hour=5, money=5000, board=board)
    market = mx.MixedHandsStrategy().act(obs)["market"]
    assert ["BUY_ANIMAL", "COW", 1] not in market


def test_market_never_exceeds_ten_orders():
    # Worst case: dawn full crew + three product sells + seed + cow + wheat.
    obs = _obs(hour=0, money=5000, shed={"MELON": 9, "CARROT": 5, "MILK": 3})
    assert len(mx.MixedHandsStrategy().act(obs)["market"]) <= 10
