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
#
# Replay layout, verified against a real episode: the action recorded at index t
# was chosen from -- and applied to -- the observation at index t-1. In episode
# 78443212 the SELL of 96 melon sits at index 289, while the shed holding those
# 96 melon is the observation at index 288; money moves 3,537 -> 21,808 across
# that pair. Pairing action[t] with observation[t] instead reads every order
# against the state it already produced.

def test_orders_are_read_against_the_state_they_were_chosen_from():
    # Index 0 holds the opening state; the order at index 1 acts on it.
    steps = [
        [_step(3000, {"farmer": ["PASS"], "hands": [], "market": []},
               prices={"MELON": 250}, shed={"MELON": 4})],
        [_step(3760, {"farmer": ["PASS"], "hands": [], "market": [
            ["SELL", "MELON", 4], ["BUY_SEED", "MELON", 3]]},
            prices={"MELON": 1}, shed={})],
    ]
    out = ea.decompose(steps, player=0)
    # Priced at 250 (the state the order was chosen from), not at 1.
    assert out["revenue"] == {"MELON": 1000}
    assert out["spend"]["seed"] == 240
    assert out["residual"] == 0


def test_a_reconstruction_that_misses_income_reports_a_nonzero_residual():
    steps = [
        [_step(3000, {"farmer": ["PASS"], "hands": [], "market": []},
               prices={"MELON": 250}, shed={"MELON": 4})],
        [_step(4500, {"farmer": ["PASS"], "hands": [], "market": [
            ["SELL", "MELON", 4]]}, prices={"MELON": 250}, shed={})],
    ]
    out = ea.decompose(steps, player=0)
    assert out["residual"] == 500


def test_actions_are_tallied_by_category_across_the_whole_crew():
    steps = [
        [_step(3000, {"farmer": ["PASS"], "hands": [], "market": []})],
        [_step(3000, {"farmer": ["WATER"],
                      "hands": [["HARVEST"], ["NORTH"], ["PASS"]],
                      "market": []})],
    ]
    out = ea.decompose(steps, player=0)
    assert out["actions"]["WATER"] == 1
    assert out["actions"]["HARVEST"] == 1
    assert out["actions"]["NORTH"] == 1
    assert out["actions"]["PASS"] == 2      # index-0 farmer, plus the idle hand


# --- the shed a SELL draws on is the post-DROP shed, not the observed one ---

def test_sell_counts_stock_a_worker_banks_in_the_same_turn():
    # The interpreter applies every unit action -- DROP included -- BEFORE it
    # processes market orders. A crew that banks its harvest and sells it in one
    # turn is the normal case, so capping at the observed pre-DROP shed erases
    # almost all real revenue (measured: 994 estimated against 48,144 actual).
    rev = ea.sell_revenue(
        [["SELL", "MELON", 6]],
        prices={"MELON": 250},
        shed={"MELON": 1},
        banked={"MELON": 5},           # a hand DROPs 5 melon this same turn
    )
    assert rev == {"MELON": 1500}


def test_banked_stock_is_still_capped_by_what_actually_exists():
    rev = ea.sell_revenue([["SELL", "MELON", 40]], prices={"MELON": 250},
                          shed={"MELON": 1}, banked={"MELON": 2})
    assert rev == {"MELON": 750}


def test_banked_units_are_summed_across_every_worker_that_drops():
    inventories = [{"MELON": 2}, {"MELON": 3, "MILK": 1}, {"MELON": 9}]
    actions = {"farmer": ["DROP"], "hands": [["DROP"], ["WATER"]]}
    # Workers 0 and 1 DROP; worker 2 is watering and banks nothing.
    assert ea.banked_this_turn(actions, inventories) == {"MELON": 5, "MILK": 1}


def test_nothing_is_banked_when_no_worker_drops():
    inventories = [{"MELON": 4}]
    assert ea.banked_this_turn({"farmer": ["WATER"], "hands": []}, inventories) == {}


# --- revenue walks the price curve, because a big sell moves it ---

def test_a_large_sell_walks_the_price_down_the_curve():
    # Measured on a real episode: 96 melon quoted at 244 realised 190/unit.
    # Pricing every unit at the opening quote overstates a big order badly.
    flat = 96 * 244
    walked = ea.sell_revenue([["SELL", "MELON", 96]], prices={"MELON": 244},
                             shed={"MELON": 96}, inventory={"MELON": 10000})["MELON"]
    assert walked < flat
    assert 96 * 150 < walked < 96 * 244


def test_a_single_unit_sells_at_the_quoted_price():
    # One unit cannot move the curve, so the walk must agree with the quote.
    from kaggisim.economy import market_price
    expected = market_price("MELON", 10000)
    got = ea.sell_revenue([["SELL", "MELON", 1]], prices={"MELON": expected},
                          shed={"MELON": 1}, inventory={"MELON": 10000})
    assert got == {"MELON": expected}


def test_revenue_falls_back_to_the_quote_when_inventory_is_unknown():
    # Older captures may lack market inventory; the estimate degrades rather
    # than disappearing.
    got = ea.sell_revenue([["SELL", "MELON", 2]], prices={"MELON": 200},
                          shed={"MELON": 2}, inventory=None)
    assert got == {"MELON": 400}


# --- realised price per unit: the #146 instrument ---
#
# Revenue alone cannot answer "are we crashing our own market?". The question is
# what each *unit* fetched, and how that decayed over the season. `sell_revenue`
# already walks the curve unit by unit; `unit_prices` exposes the walk itself.

def test_unit_prices_reports_each_units_own_realised_price():
    # Strawberry glut is linear/1.60 off T=100, so each unit sold above the
    # anchor costs the next one 1.92: 120 -> 118 -> 116.
    got = ea.unit_prices([["SELL", "STRAWBERRY", 3]], prices={"STRAWBERRY": 120},
                         shed={"STRAWBERRY": 3}, inventory={"STRAWBERRY": 10000})
    assert got == {"STRAWBERRY": [120, 118, 116]}


def test_unit_prices_sum_to_the_reported_sell_revenue():
    # The two must not be able to drift: one is the sum of the other.
    orders = [["SELL", "STRAWBERRY", 40]]
    kwargs = dict(prices={"STRAWBERRY": 120}, shed={"STRAWBERRY": 40},
                  inventory={"STRAWBERRY": 10000})
    prices = ea.unit_prices(orders, **kwargs)
    assert ea.sell_revenue(orders, **kwargs) == {
        "STRAWBERRY": sum(prices["STRAWBERRY"])}


def test_unit_prices_is_capped_by_stock_like_sell_revenue():
    got = ea.unit_prices([["SELL", "MELON", 40]], prices={"MELON": 250},
                         shed={"MELON": 3})
    assert got == {"MELON": [250, 250, 250]}


def test_summarize_prices_reports_the_mean_against_the_items_base():
    # Strawberry's base is 120; a season averaging 90 realised 75% of base.
    got = ea.summarize_prices([120, 60], "STRAWBERRY")
    assert got["units"] == 2
    assert got["revenue"] == 180
    assert got["mean_price"] == 90.0
    assert got["base"] == 120
    assert got["pct_of_base"] == 0.75


def test_summarize_prices_end_of_season_window_is_the_last_quarter_of_units():
    # The question is what a unit fetched *after* the season's selling, not on
    # average across it -- so the reported end-of-season price is the last
    # LATE_WINDOW of units, here the final two of eight.
    seq = [120, 120, 120, 120, 120, 120, 30, 6]
    got = ea.summarize_prices(seq, "STRAWBERRY")
    assert got["late_units"] == 2
    assert got["late_mean_price"] == 18.0
    assert got["late_pct_of_base"] == 0.15
    assert got["last_unit_price"] == 6


def test_summarize_prices_late_window_never_empties_on_a_tiny_season():
    got = ea.summarize_prices([120], "STRAWBERRY")
    assert got["late_units"] == 1
    assert got["late_mean_price"] == 120.0


def test_price_realisation_accumulates_units_sold_across_the_whole_season():
    steps = [
        [_step(3000, {"farmer": ["PASS"], "hands": [], "market": []},
               prices={"STRAWBERRY": 120}, shed={"STRAWBERRY": 2})],
        [_step(3240, {"farmer": ["PASS"], "hands": [], "market": [
            ["SELL", "STRAWBERRY", 2]]}, prices={"STRAWBERRY": 60},
            shed={"STRAWBERRY": 2})],
        [_step(3360, {"farmer": ["PASS"], "hands": [], "market": [
            ["SELL", "STRAWBERRY", 2]]}, prices={"STRAWBERRY": 60}, shed={})],
    ]
    out = ea.price_realisation(steps, player=0)
    berry = out["items"]["STRAWBERRY"]
    assert berry["units"] == 4
    assert berry["revenue"] == 2 * 120 + 2 * 60
    assert berry["mean_price"] == 90.0


def test_price_realisation_reports_the_markets_closing_quote():
    # A positive control on the reconstruction: the market's own end-of-season
    # quote is recorded, not inferred, so a walk that has drifted is visible.
    steps = [
        [_step(3000, {"farmer": ["PASS"], "hands": [], "market": []},
               prices={"STRAWBERRY": 120}, shed={})],
        [_step(3000, {"farmer": ["PASS"], "hands": [], "market": []},
               prices={"STRAWBERRY": 7}, shed={})],
    ]
    out = ea.price_realisation(steps, player=0)
    assert out["final_quotes"]["STRAWBERRY"] == 7


def test_summarize_prices_of_an_item_never_sold_is_all_zero():
    # A product with no sales must read as zero, not as a division by zero.
    got = ea.summarize_prices([], "MELON")
    assert got["units"] == 0
    assert got["mean_price"] == 0.0
    assert got["late_pct_of_base"] == 0.0
    assert got["base"] == 250


def test_price_realisation_keeps_the_raw_per_unit_sequence():
    # The decay *shape* is the finding; a mean alone cannot show it.
    steps = [
        [_step(3000, {"farmer": ["PASS"], "hands": [], "market": []},
               prices={"STRAWBERRY": 120}, shed={"STRAWBERRY": 3})],
        [_step(3354, {"farmer": ["PASS"], "hands": [], "market": [
            ["SELL", "STRAWBERRY", 3]]}, prices={"STRAWBERRY": 120}, shed={})],
    ]
    steps[0][0]["observation"]["market"]["inventory"] = {"STRAWBERRY": 10000}
    out = ea.price_realisation(steps, player=0)
    assert out["unit_prices"]["STRAWBERRY"] == [120, 118, 116]


# --- BUY_PRODUCT: the outflow the decomposition used to drop on the floor ---
#
# `dense_farm` buys 432 wheat a season through BUY_PRODUCT. Counting none of it
# left decompose reporting a -19,000 residual on a 35,000 game -- 55% of final
# money, against the ~7% the module treats as normal. Silently dropping an
# order verb turns "we cannot price this" into "this never happened".

def test_buying_a_product_is_a_real_outflow():
    # The sim quotes a BUY at the post-buy inventory, so the first unit off a
    # 10,000-unit wheat market costs market_price(WHEAT, 9999).
    from kaggisim.economy import market_price
    spend = ea.order_spend([["BUY_PRODUCT", "WHEAT", 1]], hires_before=0,
                           quadrants=1, prices={"WHEAT": 25},
                           inventory={"WHEAT": 10000})
    assert spend == market_price("WHEAT", 9999)


def test_buying_walks_the_price_up_as_it_drains_the_market():
    # Each unit bought lifts the price of the next, the mirror of a big sell.
    from kaggisim.economy import market_price
    flat = 50 * market_price("WHEAT", 9999)
    walked = ea.order_spend([["BUY_PRODUCT", "WHEAT", 50]], hires_before=0,
                            quadrants=1, prices={"WHEAT": 25},
                            inventory={"WHEAT": 10000})
    assert walked > flat


def test_bought_product_lands_in_its_own_spend_bucket():
    from kaggisim.economy import market_price
    out = ea.spend_by_category([["BUY_PRODUCT", "FERTILIZER", 2]], hires_before=0,
                               quadrants=1, prices={"FERTILIZER": 100},
                               inventory={"FERTILIZER": 10000})
    assert out["product"] == market_price("FERTILIZER", 9999) + market_price("FERTILIZER", 9998)
    assert out["seed"] == 0


def test_buying_falls_back_to_the_quote_when_inventory_is_unknown():
    # Degrade rather than disappear -- the failure this whole test block exists
    # to stop is an unpriceable order counting as zero.
    assert ea.order_spend([["BUY_PRODUCT", "WHEAT", 4]], hires_before=0,
                          quadrants=1, prices={"WHEAT": 30}) == 120
# --- the first sale of one item: the melon-sprint necessary condition (#205) ---


def _pair(a_slot, b_slot):
    """One replay step holding both players' slots."""
    return [a_slot, b_slot]


def _idle(day=0, hour=0, shed=None, prices=None, inventory=None):
    """A turn that does nothing. The observation it carries is the one the NEXT
    step's action was chosen from -- the module's own indexing convention."""
    slot = _step(0, {"farmer": ["PASS"], "hands": [], "market": []},
                 prices=prices, shed=shed, day=day, hour=hour)
    if inventory is not None:
        slot["observation"]["market"]["inventory"] = inventory
    return slot


def _sells(item, n, day=0, hour=0):
    """A turn whose only market order is a SELL."""
    return _step(0, {"farmer": ["PASS"], "hands": [],
                     "market": [["SELL", item, n]]}, day=day, hour=hour)


def test_first_sale_reports_the_day_the_item_first_reaches_the_market():
    # The order is read against the observation it was CHOSEN from, one step
    # earlier -- so the reported day/hour are that observation's, not the one
    # the sale produced.
    steps = [
        _pair(_idle(day=9), _idle(day=9)),
        _pair(_idle(day=10, hour=11, shed={"MELON": 4}, prices={"MELON": 250}),
              _idle(day=10, hour=11)),
        _pair(_sells("MELON", 4, day=10, hour=12), _idle(day=10, hour=12)),
    ]
    got = ea.first_sale(steps, 0, "MELON")
    assert got is not None, "the sale was never found"
    assert (got["day"], got["hour"]) == (10, 11)


def test_first_sale_reports_the_realised_price_per_unit():
    # Realised, not quoted: the sim walks the curve per unit, so four melon
    # opening at inventory 10000 do not all fetch the 250 on the ticker.
    steps = [
        _pair(_idle(day=10, hour=11, shed={"MELON": 4}, prices={"MELON": 250},
                    inventory={"MELON": 10000}),
              _idle(day=10, hour=11)),
        _pair(_sells("MELON", 4, day=10, hour=12), _idle(day=10, hour=12)),
    ]
    got = ea.first_sale(steps, 0, "MELON")
    assert got["units"] == 4
    assert got["price"] == got["revenue"] / 4
    # Four units barely move melon's curve (250 - 0.01*n^2), so the realised
    # price here IS the quote; the walk is demonstrated on a real batch below.
    assert got["price"] == 250


def test_first_sale_prices_a_real_batch_below_the_quote():
    # Melon carries the steepest glut in the table (sq/3.60). A hundred units
    # walk it from 250 to 150, so the batch realises well under the ticker --
    # which is the whole reason batch size is the design parameter (#205).
    steps = [
        _pair(_idle(day=10, hour=11, shed={"MELON": 100}, prices={"MELON": 250},
                    inventory={"MELON": 10000}),
              _idle(day=10, hour=11)),
        _pair(_sells("MELON", 100, day=10, hour=12), _idle(day=10, hour=12)),
    ]
    got = ea.first_sale(steps, 0, "MELON")
    assert got["units"] == 100
    assert got["quoted"] == 250
    assert 200 < got["price"] < 220


def test_first_sale_flags_a_turn_the_opponent_also_sold_into():
    # Both sides commit unit-by-unit against the same pre-commit inventory, so a
    # contested turn's per-side walk is an overestimate and must say so.
    before = _idle(day=10, hour=11, shed={"MELON": 4}, prices={"MELON": 250},
                   inventory={"MELON": 10000})
    sale = _sells("MELON", 4, day=10, hour=12)
    contested = [_pair(before, before), _pair(sale, sale)]
    assert ea.first_sale(contested, 0, "MELON")["contested"] is True
    alone = [_pair(before, _idle(day=10, hour=11)),
             _pair(sale, _idle(day=10, hour=12))]
    assert ea.first_sale(alone, 0, "MELON")["contested"] is False


def test_first_sale_skips_an_order_that_cannot_fill():
    # A SELL against an empty shed moves nothing. Dating the first sale to it
    # would claim we were first on a turn no melon changed hands.
    steps = [
        _pair(_idle(day=9, hour=2, prices={"MELON": 250}), _idle(day=9, hour=2)),
        _pair(_sells("MELON", 4, day=9, hour=3), _idle(day=9, hour=3)),
        _pair(_idle(day=10, hour=11, shed={"MELON": 4}, prices={"MELON": 250}),
              _idle(day=10, hour=11)),
        _pair(_sells("MELON", 4, day=10, hour=12), _idle(day=10, hour=12)),
    ]
    assert ea.first_sale(steps, 0, "MELON")["day"] == 10


def test_first_sale_counts_stock_banked_in_the_same_turn():
    # The crew banks its harvest and sells it in the same turn -- capping at the
    # pre-DROP shed would report no sale at all.
    before = _idle(day=10, hour=11, prices={"MELON": 250})
    before["observation"]["private"]["inventories"] = [{"MELON": 5}]
    sale = _step(0, {"farmer": ["DROP"], "hands": [],
                     "market": [["SELL", "MELON", 5]]}, day=10, hour=12)
    steps = [_pair(before, _idle(day=10, hour=11)), _pair(sale, _idle(day=10, hour=12))]
    assert ea.first_sale(steps, 0, "MELON")["units"] == 5


def test_first_sale_is_none_when_the_item_is_never_sold():
    steps = [_pair(_idle(day=0), _idle(day=0)), _pair(_idle(day=1), _idle(day=1))]
    assert ea.first_sale(steps, 0, "MELON") is None


def test_first_sale_ignores_other_items_sold_in_the_same_sweep():
    # The champion sweeps its whole shed every turn, so wheat and fertilizer
    # ride along in the same order list. Counting them would date the melon
    # sale to whichever turn the shed first held anything at all.
    before = _idle(day=8, hour=4, shed={"WHEAT": 6, "MELON": 4},
                   prices={"WHEAT": 25, "MELON": 250}, inventory={"MELON": 10000})
    sweep = _step(0, {"farmer": ["PASS"], "hands": [],
                      "market": [["SELL", "WHEAT", 6], ["SELL", "MELON", 4],
                                 ["BUY_SEED", "STRAWBERRY", 1]]},
                  day=8, hour=5)
    steps = [_pair(before, _idle(day=8, hour=4)), _pair(sweep, _idle(day=8, hour=5))]
    got = ea.first_sale(steps, 0, "MELON")
    assert got["units"] == 4
    assert got["revenue"] == 4 * 250


def test_first_sale_survives_a_step_with_no_action():
    # Real replays carry steps whose action is absent -- an agent that timed out,
    # or the terminal step. A crash there would lose the whole measurement.
    stale = _pair(_idle(day=10, hour=11, shed={"MELON": 4}, prices={"MELON": 250}),
                  {"observation": {}})
    steps = [stale, _pair(_sells("MELON", 4, day=10, hour=12), {"observation": {}})]
    assert ea.first_sale(steps, 0, "MELON")["contested"] is False
