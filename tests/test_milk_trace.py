"""#228: the per-turn MILK trace and the pure readings taken off it.

Only the pure parts are unit-tested here; the live game drivers are
`# pragma: no cover` integration entrypoints like every other harness bench.
The claim checks at the bottom pin the two sim-sourced constants this module
computes the town's draw from -- the whole "ratio to the town's draw" reading
is wrong if either drifts.
"""

from __future__ import annotations

from harness import milk_trace as mt


# --- the town's draw ---------------------------------------------------------

def test_town_draw_should_count_every_milk_shop_when_the_step_is_a_shop_tick():
    # PIZZA_SHOP and SMOOTHIE_SHOP both carry MILK; PET_CAFE does not.
    assert mt.town_draw(["PIZZA_SHOP", "SMOOTHIE_SHOP", "PET_CAFE"], 4, "MILK") == 2


def test_town_draw_should_be_zero_on_a_step_that_is_no_tick_at_all():
    assert mt.town_draw(["PIZZA_SHOP", "SMOOTHIE_SHOP"], 5, "MILK") == 0


def test_town_draw_should_add_the_town_centres_single_unit_on_its_own_tick():
    # Step 24 is both a shop tick and a town-centre tick: 1 shop + 1 centre.
    assert mt.town_draw(["PIZZA_SHOP"], 24, "MILK") == 2


def test_town_draw_should_count_a_shop_drawn_twice_once_per_copy():
    # Shops are drawn with replacement and each instance consumes independently.
    assert mt.town_draw(["PIZZA_SHOP", "PIZZA_SHOP"], 4, "MILK") == 2


def test_town_draw_should_double_a_single_product_shop():
    # The sim's multiplier: a shop with one product pulls two of it per tick.
    assert mt.town_draw(["YARN_STORE"], 4, "WOOL") == 2


# --- reading the trace -------------------------------------------------------

def _row(step, day, price, ours=0, theirs=0):
    return {"step": step, "day": day, "hour": step % 24, "milk_price": price,
            "milk_inventory": 10000, "our_cows": 0, "their_cows": 0,
            "our_milk_sold": ours, "their_milk_sold": theirs}


def test_cumulative_by_day_should_carry_earlier_days_into_every_later_one():
    trace = [_row(0, 0, 160, ours=2), _row(1, 0, 160, ours=3), _row(24, 1, 160, ours=5)]
    assert mt.cumulative_by_day(trace, "our_milk_sold") == {0: 5, 1: 10}


def test_cumulative_by_day_should_hold_a_day_that_sold_nothing_at_the_running_total():
    # A flat day is not a missing day: the cumulative curve must not dip or gap.
    trace = [_row(0, 0, 160, ours=4), _row(24, 1, 160), _row(48, 2, 160, ours=1)]
    assert mt.cumulative_by_day(trace, "our_milk_sold") == {0: 4, 1: 4, 2: 5}


def test_first_day_below_should_report_the_day_the_price_first_broke_the_fraction():
    trace = [_row(0, 0, 240), _row(24, 1, 170), _row(48, 2, 150), _row(72, 3, 40)]
    assert mt.first_day_below(trace, 1.0) == 2      # base 160: 150 is the first below
    assert mt.first_day_below(trace, 0.5) == 3      # 80: only day 3's 40 is below


def test_first_day_below_should_be_none_when_the_price_never_broke_it():
    trace = [_row(0, 0, 240), _row(24, 1, 200)]
    assert mt.first_day_below(trace, 1.0) is None


def test_first_day_below_should_take_the_first_break_even_if_the_price_recovers():
    # "When did it first go" -- not "is it still there now".
    trace = [_row(0, 0, 240), _row(24, 1, 12), _row(48, 2, 300)]
    assert mt.first_day_below(trace, 0.5) == 1


# --- what the units fetched, and what they would have ------------------------

def test_revenue_at_should_price_each_turns_units_at_that_turns_quote():
    assert mt.revenue_at({10: 3, 20: 2}, {10: 100, 20: 50}) == 400.0


def test_revenue_at_should_ignore_a_turn_that_sold_nothing_even_with_no_quote():
    assert mt.revenue_at({10: 3, 20: 0}, {10: 100}) == 300.0


def test_revenue_at_should_raise_when_a_turn_that_sold_units_has_no_quote():
    # A missing quote priced as zero would silently understate the season and
    # read as a collapse; the whole counterfactual turns on this alignment.
    try:
        mt.revenue_at({10: 3, 20: 2}, {10: 100})
    except ValueError as exc:
        assert "20" in str(exc)
    else:
        raise AssertionError("a units-without-a-quote step must be refused")


def test_revenue_if_should_price_our_units_at_the_other_games_path():
    units = {10: 3, 20: 2}
    assert mt.revenue_if(units, {10: 240, 20: 240}) == 1200.0


def test_revenue_if_should_be_the_same_walk_as_revenue_at_on_its_own_path():
    units, prices = {10: 3, 20: 2}, {10: 100, 20: 50}
    assert mt.revenue_if(units, prices) == mt.revenue_at(units, prices)


def test_draw_ratio_should_report_the_farms_volume_against_the_towns():
    assert mt.draw_ratio(150, 300) == 0.5


def test_draw_ratio_should_refuse_a_town_that_draws_nothing():
    # 0 units against a 0 draw is not "no pressure", it is no measurement.
    try:
        mt.draw_ratio(150, 0)
    except ValueError:
        pass
    else:
        raise AssertionError("a non-positive season demand must be refused")


# --- the positive control ----------------------------------------------------

def test_count_cows_should_count_only_cows_and_survive_locked_tiles_and_weeds():
    tiles = [["LOCKED", {"animal": "COW"}, None],
             [{"animal": "SHEEP"}, {"kind": "WEED"}, {"animal": "COW"}]]
    assert mt.count_cows(tiles) == 2


def _traced(units, revenue):
    return [{"day": 8, "our_milk_sold": units, "our_milk_revenue": revenue}]


def _realised(units, revenue):
    return {"items": {"MILK": {"units": units, "revenue": revenue}}}


def test_reconciliation_should_pass_when_the_trace_and_the_season_summary_agree():
    got = mt.reconciliation(_traced(53, 13208), _realised(53, 13208))
    assert got["ok"] and got["units_gap"] == 0 and got["revenue_gap"] == 0


def test_reconciliation_should_fail_when_the_two_walks_disagree_by_one_turn():
    # An off-by-one in the observation an order is priced against shows up here
    # and nowhere else -- that is the whole reason the control exists.
    got = mt.reconciliation(_traced(53, 13208), _realised(51, 12900))
    assert not got["ok"] and got["units_gap"] == 2 and got["revenue_gap"] == 308


def test_reconciliation_should_refuse_a_season_that_sold_no_milk_as_vacuous():
    # 0 == 0 is not a reconciliation: with no units the control proves nothing,
    # so its own precondition has to be reported as unmet.
    got = mt.reconciliation(_traced(0, 0), _realised(0, 0))
    assert not got["ok"] and got["precondition_ok"] is False


# --- claim checks: the two sim constants the town's draw is computed from -----

def test_the_shop_table_matches_the_installed_sim():
    from kaggle_environments.envs.kaggriculture import kaggriculture as sim
    from kaggisim.economy import SHOP_DEMAND
    assert {k: list(v) for k, v in SHOP_DEMAND.items()} == \
        {k: list(v) for k, v in sim.SHOPS.items()}


def test_the_consumption_intervals_match_the_installed_sims_own_defaults():
    # `economy.CONFIG_DEFAULTS["townCenterSellInterval"]` says 12 where the sim
    # says 24; this module takes the sim's, and #228 reports the gap rather
    # than patching a table every other bench reads.
    import json
    import os
    from kaggle_environments.envs.kaggriculture import kaggriculture as sim
    schema = json.load(open(os.path.join(os.path.dirname(sim.__file__),
                                         "kaggriculture.json")))["configuration"]
    assert mt.SHOP_SELL_INTERVAL == schema["townShopSellInterval"]["default"] == 4
    assert mt.TOWN_CENTER_INTERVAL == schema["townCenterSellInterval"]["default"] == 24
