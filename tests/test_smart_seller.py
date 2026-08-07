"""Unit tests for the smart_seller experiment (issue #5, ADR-0007).

The single technique under test is *demand-aware, throttled selling* layered on
`greedy_horizon`'s melon foundation. These exercise the pure selling helpers
directly against fixed price/inventory/demand inputs, so the technique is
validated without a full 720-turn game. The full-game no-crash guard lives in
test_no_crash.py (auto-included via the REGISTRY).
"""

from __future__ import annotations

from strategies import smart_seller as ss


# --- Demand priority: prefer products the town shops currently demand ---

def test_demand_priority_counts_unlocked_shops_demanding_an_item():
    # WHEAT is demanded by BAKERY and PIZZA_SHOP; only BAKERY is unlocked.
    assert ss.demand_priority("WHEAT", ["BAKERY"]) == 1
    assert ss.demand_priority("WHEAT", ["BAKERY", "PIZZA_SHOP"]) == 2


def test_demand_priority_zero_for_undemanded_or_no_shops():
    # No shop demands MELON, so it is never demand-preferred.
    assert ss.demand_priority("MELON", ["BAKERY", "PIZZA_SHOP"]) == 0
    assert ss.demand_priority("WHEAT", []) == 0


def test_single_product_shops_count_double():
    # PET_CAFE demands only CARROT and consumes it at 2x (single-product shop).
    assert ss.demand_priority("CARROT", ["PET_CAFE"]) == 2


# --- Rolling price floor: hold when price is below the floor ---

def test_price_ok_true_at_or_above_floor():
    assert ss.price_ok(250, 250) is True
    assert ss.price_ok(300, 250) is True


def test_price_ok_false_below_floor():
    assert ss.price_ok(249, 250) is False


def test_update_floor_ratchets_up_and_holds_on_a_dip():
    # The floor tracks the running peak so a self-inflicted price dip does not
    # trick us into dumping below what the market has already offered.
    floor = ss.update_floor(0.0, 250)
    assert floor == 250
    floor = ss.update_floor(floor, 280)
    assert floor == 280
    # A dip below the peak does not lower the floor.
    assert ss.update_floor(floor, 260) == 280


# --- Release timing: hold premium goods until the peak-demand window ---

def test_hold_before_the_top_demand_window():
    assert ss.should_release(day=12, season_days=30) is False


def test_release_once_top_demand_tier_opens():
    # Town-center demand hits its top multiplier on day 20 (schedule provenance
    # in the module); we start releasing held inventory then.
    assert ss.should_release(day=20, season_days=30) is True


def test_release_forced_in_the_endgame():
    assert ss.should_release(day=29, season_days=30) is True


# --- Per-turn sell cap: throttle to limit our own price impact ---

def test_sell_quantity_capped_before_endgame():
    assert ss.sell_quantity(held=10, day=22, season_days=30, cap=3) == 3


def test_sell_quantity_liquidates_fully_in_endgame():
    # In the liquidation window the cap is lifted so nothing strands at the buzzer.
    assert ss.sell_quantity(held=10, day=29, season_days=30, cap=3) == 10


def test_sell_quantity_never_exceeds_held():
    assert ss.sell_quantity(held=2, day=22, season_days=30, cap=5) == 2


# --- Sell plan: combine hold + cap + demand ordering ---

def test_sell_plan_holds_melon_before_the_window():
    shed = {"MELON": 6}
    assert ss.sell_plan(shed, unlocked_shops=[], day=12, season_days=30, cap=3) == []


def test_sell_plan_throttles_melon_in_the_window():
    shed = {"MELON": 6}
    plan = ss.sell_plan(shed, unlocked_shops=[], day=22, season_days=30, cap=3)
    assert plan == [["SELL", "MELON", 3]]


def test_sell_plan_liquidates_everything_in_endgame():
    shed = {"MELON": 6}
    plan = ss.sell_plan(shed, unlocked_shops=[], day=29, season_days=30, cap=3)
    assert plan == [["SELL", "MELON", 6]]


def test_sell_plan_orders_demanded_goods_first_and_skips_junk():
    # In the endgame we liquidate every sellable item; a demanded good (WHEAT,
    # via BAKERY) is ordered ahead of the undemanded MELON, and non-market
    # junk / empty slots are excluded.
    shed = {"MELON": 4, "WHEAT": 2, "WEEDS": 9, "CARROT": 0}
    plan = ss.sell_plan(shed, unlocked_shops=["BAKERY"], day=29, season_days=30, cap=3)
    assert plan == [["SELL", "WHEAT", 2], ["SELL", "MELON", 4]]
