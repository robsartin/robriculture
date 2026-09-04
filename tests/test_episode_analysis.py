"""Unit tests for ladder-replay decomposition (issue #157).

We have played 76 rated matches and the replays carry BOTH players' actions and
observations. This module decomposes one side of one episode into where its
money came from and where it went.

The sim has exactly one money inflow -- `farm["money"] += price` on a SELL
commit -- so revenue is market sell revenue and nothing else. Town shops drain
market *inventory*, lifting prices; they never pay a farm.

Sell revenue can only be estimated (the price moves within an order, and both
players commit in lockstep), so every decomposition carries a `residual`: the
gap between the reconstruction and the money the farm actually ended with. A
decomposition whose residual is large is reporting that it is wrong, rather than
looking plausible -- which is the failure mode this project keeps hitting.
"""

from __future__ import annotations

from harness import episode_analysis as ea


def _step(money, action, prices=None, shed=None, day=0, hour=0):
    """One player's slot in a replay step."""
    return {
        "action": action,
        "observation": {
            "day": day, "hour": hour, "player": 0,
            "farms": [{"money": money, "tiles": [], "hands": []}],
            "market": {"prices": prices or {}, "inventory": {}},
            "private": {"shed": shed or {}, "seeds": {}, "inventories": []},
        },
    }


# --- spend: every outflow is exactly computable from the orders themselves ---

def test_seed_spend_is_the_listed_seed_cost_times_quantity():
    orders = [["BUY_SEED", "MELON", 3]]
    assert ea.order_spend(orders, hires_before=0, quadrants=1) == 3 * 80


def test_land_spend_follows_the_quadrant_price_ladder():
    assert ea.order_spend([["BUY_LAND"]], hires_before=0, quadrants=1) == 1000
    assert ea.order_spend([["BUY_LAND"]], hires_before=0, quadrants=2) == 2000
    assert ea.order_spend([["BUY_LAND"]], hires_before=0, quadrants=3) == 4000


def test_hire_spend_escalates_as_the_fibonacci_wage():
    # The n-th hire of a day costs fib(n): 1, 1, 2, 3, 5, ...
    orders = [["HIRE"]] * 5
    assert ea.order_spend(orders, hires_before=0, quadrants=1) == 1 + 1 + 2 + 3 + 5


def test_hire_spend_continues_the_ladder_from_hires_already_made_today():
    assert ea.order_spend([["HIRE"]], hires_before=4, quadrants=1) == 5


def test_animal_spend_is_the_listed_cost():
    assert ea.order_spend([["BUY_ANIMAL", "COW", 1]], hires_before=0, quadrants=1) == 400


def test_a_sell_order_costs_nothing():
    assert ea.order_spend([["SELL", "MELON", 9]], hires_before=0, quadrants=1) == 0


# --- revenue: estimated at the turn's quoted price, capped by what is in the shed ---

def test_sell_revenue_is_units_times_the_quoted_price():
    rev = ea.sell_revenue([["SELL", "MELON", 4]], prices={"MELON": 250},
                          shed={"MELON": 10})
    assert rev == {"MELON": 1000}


def test_sell_revenue_never_counts_stock_the_farm_does_not_hold():
    # An order for more than the shed holds partially fills; counting the whole
    # order would invent revenue.
    rev = ea.sell_revenue([["SELL", "MELON", 40]], prices={"MELON": 250},
                          shed={"MELON": 3})
    assert rev == {"MELON": 750}


def test_sell_revenue_ignores_an_item_with_no_quoted_price():
    assert ea.sell_revenue([["SELL", "SHEEP", 2]], prices={}, shed={"SHEEP": 2}) == {}


# --- the whole episode, with its own validity check attached ---

def test_decomposition_reports_a_residual_against_the_real_final_money():
    # Start 3000, sell 4 melon at 250 (+1000), buy 3 melon seed (-240).
    # A faithful reconstruction lands on the money the replay actually records.
    steps = [
        [_step(3000, {"farmer": ["PASS"], "hands": [], "market": [
            ["SELL", "MELON", 4], ["BUY_SEED", "MELON", 3]]},
            prices={"MELON": 250}, shed={"MELON": 4})],
        [_step(3760, {"farmer": ["PASS"], "hands": [], "market": []})],
    ]
    out = ea.decompose(steps, player=0)
    assert out["revenue"] == {"MELON": 1000}
    assert out["spend"]["seed"] == 240
    assert out["residual"] == 0


def test_a_reconstruction_that_misses_income_reports_a_nonzero_residual():
    # Same trade, but the replay's money went up by 500 more than the orders
    # explain. The residual must surface that rather than quietly balancing.
    steps = [
        [_step(3000, {"farmer": ["PASS"], "hands": [], "market": [
            ["SELL", "MELON", 4]]}, prices={"MELON": 250}, shed={"MELON": 4})],
        [_step(4500, {"farmer": ["PASS"], "hands": [], "market": []})],
    ]
    out = ea.decompose(steps, player=0)
    assert out["residual"] == 500


def test_actions_are_tallied_by_category_across_the_whole_crew():
    steps = [
        [_step(3000, {"farmer": ["WATER"],
                      "hands": [["HARVEST"], ["NORTH"], ["PASS"]],
                      "market": []})],
        [_step(3000, {"farmer": ["PASS"], "hands": [], "market": []})],
    ]
    out = ea.decompose(steps, player=0)
    assert out["actions"]["WATER"] == 1
    assert out["actions"]["HARVEST"] == 1
    assert out["actions"]["NORTH"] == 1
    assert out["actions"]["PASS"] == 2      # one hand, plus the farmer's own
