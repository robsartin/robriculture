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


# --- the counterfactual herd rules (pure seams; the subclasses only call these)

def _obs(day=10, our_cows=0, shed_cows=0, rival_sheep=2):
    tiles = [[{"animal": "COW"}] * our_cows or [None]]
    theirs = [[{"animal": "SHEEP"}] * rival_sheep or [None]]
    return {"player": 0, "day": day,
            "farms": [{"tiles": tiles}, {"tiles": theirs}],
            "private": {"shed": {"COW": shed_cows}}}


def test_our_cows_should_count_the_shed_as_well_as_the_pasture():
    # `field_rival.market_orders` counts a bought-but-unplaced animal as pending
    # against the ramp; a cap that ignored the shed would buy the same cow 24
    # times a day, which is how the ramp was measured buying 79 sheep.
    assert mt.our_cows(_obs(our_cows=4, shed_cows=2)) == 6


def test_capped_cow_preference_should_ask_for_cows_below_the_cap():
    assert mt.capped_cow_preference(_obs(our_cows=5), 6) == "COW"


def test_capped_cow_preference_should_fall_back_to_the_budget_rule_at_the_cap():
    # `None` is not "buy nothing": it hands the decision back to the benchmark's
    # own budget rule, which buys sheep when it can afford them.
    assert mt.capped_cow_preference(_obs(our_cows=4, shed_cows=2), 6) is None


def test_capped_cow_preference_should_stay_quiet_when_the_rival_runs_no_sheep():
    # The cap is a variant of rival_aware, not of unconditional cows: with no
    # rival herd there is nothing to steer away from.
    assert mt.capped_cow_preference(_obs(our_cows=0, rival_sheep=0), 6) is None


def test_dated_cow_preference_should_ask_for_cows_before_the_switch_day():
    assert mt.dated_cow_preference(_obs(day=19), 20) == "COW"


def test_dated_cow_preference_should_fall_back_on_and_after_the_switch_day():
    assert mt.dated_cow_preference(_obs(day=20), 20) is None
    assert mt.dated_cow_preference(_obs(day=25), 20) is None


def test_dated_cow_preference_should_stay_quiet_when_the_rival_runs_no_sheep():
    assert mt.dated_cow_preference(_obs(day=5, rival_sheep=0), 20) is None


# --- the printed reading -----------------------------------------------------

def test_at_days_should_hold_the_last_known_total_across_a_day_with_no_turns():
    # The curve is cumulative: a day the trace has no row for did not sell zero,
    # it sold nothing new, and the total standing at that point is the answer.
    assert mt._at_days({0: 1, 8: 10, 20: 30}, (8, 12, 20)) == [10, 10, 30]


def test_at_days_should_report_a_day_the_season_never_reached_as_missing():
    assert mt._at_days({0: 1, 8: 10}, (8, 28)) == [10, None]


def _record(**over):
    r = {"seed": 601, "seat": 1, "our_name": "rival_aware", "their_name": "meta_bot",
         "control": {"ok": True, "trace_units": 53, "trace_revenue": 2900.0,
                     "season_units": 53, "season_revenue": 2900.0},
         "shop_instances": 8, "milk_shops": 2, "milk_shop_days": [21, 24],
         "season_demand": 246,
         "first_day_band": 11, "first_day_half": 13,
         "our_by_day": {8: 0, 12: 20, 16: 40, 20: 53, 24: 53, 28: 53},
         "their_by_day": {8: 0, 12: 60, 16: 140, 20: 200, 24: 260, 28: 300},
         "our_units": 53, "their_units": 300, "combined_units": 353,
         "draw_ratio": 1.435, "revenue_here": 2900.0, "revenue_reference": 13100.0,
         "reference_seed": 600}
    r.update(over)
    return r


def test_format_seed_report_should_lead_with_the_control_and_name_the_seats():
    out = mt.format_seed_report(_record()).splitlines()
    assert "seat 1" in out[0] and "meta_bot in seat 0" in out[0]
    assert "control" in out[1] and "OK" in out[1]


def test_format_seed_report_should_say_the_trace_is_not_believed_on_a_mismatch():
    bad = _record(control={"ok": False, "trace_units": 53, "trace_revenue": 2900.0,
                           "season_units": 51, "season_revenue": 2800.0})
    assert "not believed" in mt.format_seed_report(bad)


def test_format_seed_report_should_carry_both_collapse_days_and_the_draw_ratio():
    out = mt.format_seed_report(_record())
    assert "base band on day 11" in out and "50% of base on day 13" in out
    assert "1.44x the town" in out and "246-unit draw" in out


def test_format_seed_report_should_say_when_the_towns_milk_shops_arrived():
    # How many milk shops the town ended with says nothing on its own: a shop
    # that unlocks on day 21 drained six days of a thirty-day season.
    assert "arriving on days [21, 24]" in mt.format_seed_report(_record())


def test_format_seed_report_should_say_never_for_a_band_the_price_kept():
    out = mt.format_seed_report(_record(first_day_band=None, first_day_half=None))
    assert "base band on day never" in out and "50% of base on day never" in out


def test_format_seed_report_should_price_our_units_on_the_reference_path_too():
    out = mt.format_seed_report(_record())
    assert "2,900 here" in out and "13,100 on seed 600's price path" in out
    assert "-10,200" in out


def test_format_seed_report_should_omit_the_reference_line_on_the_reference_seed():
    # Seed 600 priced against seed 600 is a tautology, not a counterfactual.
    r = _record(seed=600, seat=0)
    r.pop("reference_seed")
    assert "price path" not in mt.format_seed_report(r)


# --- the counterfactual table ------------------------------------------------

def _cf(variant, seed, money, delta, cows, late):
    return {"variant": variant, "seed": seed, "final_money": money,
            "delta_money": delta, "max_cows": cows, "our_units": 53,
            "realised_pct_of_base": 0.34, "late_pct_of_base": late,
            "held": late >= 0.5}


def test_format_counterfactuals_should_mark_a_late_window_at_or_above_half_as_held():
    rows = [_cf("rival_aware", 601, 30000.0, 0.0, 11, 0.029),
            _cf("cap_6_cows", 601, 31000.0, 1000.0, 6, 0.61)]
    out = mt.format_counterfactuals(rows).splitlines()
    assert "floored" in out[1] and "held" in out[2]


def test_format_counterfactuals_should_carry_the_signed_money_delta_and_the_head():
    rows = [_cf("cap_6_cows", 600, 33000.0, -1100.0, 6, 1.4)]
    out = mt.format_counterfactuals(rows)
    assert "-1,100" in out and "cap_6_cows" in out and " 6 " in out


def test_format_counterfactuals_should_flag_a_variant_whose_head_never_changed():
    # A cap that did not bind bought the same herd as the unmodified agent, so
    # its money and its price are the champion's, not a counterfactual.
    rows = [_cf("rival_aware", 601, 30000.0, 0.0, 11, 0.03),
            _cf("cap_6_cows", 601, 30000.0, 0.0, 11, 0.03)]
    assert "mechanism did not fire" in mt.format_counterfactuals(rows)


def test_format_counterfactuals_should_not_flag_the_baseline_row_of_a_later_seed():
    # Rows arrive variant-major, so the unmodified agent's seed-601 row is the
    # second line of the table. It is a baseline, not a counterfactual that
    # failed to fire, and flagging it would read as a broken variant.
    rows = [_cf("rival_aware", 600, 34000.0, 0.0, 11, 1.5),
            _cf("rival_aware", 601, 30000.0, 0.0, 11, 0.03),
            _cf("cap_6_cows", 600, 33000.0, -1000.0, 6, 1.4),
            _cf("cap_6_cows", 601, 31000.0, 1000.0, 6, 0.61)]
    assert "mechanism did not fire" not in mt.format_counterfactuals(rows)


# --- when the town's milk shops arrived --------------------------------------

def _shop_row(day, milk_shops):
    return {"day": day, "milk_shops": milk_shops}


def test_shop_arrival_days_should_report_the_day_each_milk_shop_appeared():
    trace = [_shop_row(0, 0), _shop_row(6, 1), _shop_row(12, 1), _shop_row(21, 2)]
    assert mt.shop_arrival_days(trace) == [6, 21]


def test_shop_arrival_days_should_report_a_town_that_never_drew_milk_as_empty():
    assert mt.shop_arrival_days([_shop_row(0, 0), _shop_row(20, 0)]) == []


def test_shop_arrival_days_should_count_two_shops_unlocking_on_the_same_day_twice():
    # The count is what drives the draw; a day that added two instances added
    # twice the appetite, and one arrival day would understate it.
    trace = [_shop_row(0, 0), _shop_row(24, 2)]
    assert mt.shop_arrival_days(trace) == [24, 24]
