"""Unit tests for the dual-income experiment (issue #187, ADR-0007).

#157 decomposed 63 real ladder matches: livestock and its free fertilizer
byproduct are **62% of the winning field's revenue**, and our champion earns
none of it. Our crop line is actually the strongest in that data (56K against
the field's 28K) — we simply have one business where the field has two.

The champion is not missing the machinery. `neuropilot` already implements the
whole livestock line — cows, sheep, feeding, `COLLECT_FERTILIZER`, the lot —
driven by a `herd_target_scale` knob. Its evolved genome sets that knob to a
median **0.0098**, and `_herd_targets` rounds `0.0098 * 13` to **zero animals**
for the entire game. Evolution switched the second business off.

So the single variable here is that knob, floored. Everything else — every other
knob, the network, the crop line, the controller — is the champion's, untouched.
"""

from __future__ import annotations

from strategies import dual_income as di
from strategies import neuropilot as npx


def _knobs(**over):
    base = dict(sell_throttle=0.5, hire_target=0.5, livestock_pace=0.5,
                livestock_labor_share=0.5, herd_target_scale=0.0098,
                fertilize_pref=0.5, capital_reserve=0.5, crop_mix=0.5)
    base.update(over)
    return npx.Knobs(**base)


# --- the champion's herd is off; this is what that looks like ---

def test_the_champion_genome_asks_for_no_animals():
    # Guards the premise of the whole experiment. If this ever fails, the
    # champion has started keeping livestock and #187 is moot.
    assert npx._herd_targets(_knobs()) == (0, 0)


# --- the one variable ---

def test_herd_floor_raises_a_switched_off_knob_to_the_measured_field_herd():
    floored = di.floor_herd(_knobs(herd_target_scale=0.0098))
    assert npx._herd_targets(floored) == (npx.N_COW, di.TARGET_HERD - npx.N_COW)
    assert sum(npx._herd_targets(floored)) == di.TARGET_HERD


def test_target_herd_matches_the_field_measured_in_the_replays():
    # #157: opponents who beat us hold a median of 11 animals from day 16 on.
    assert di.TARGET_HERD == 11


def test_the_strategy_is_a_contender_not_a_benchmark():
    assert di.STRATEGY.benchmark is False
    assert di.STRATEGY.name == "dual_income"


def test_it_reuses_the_champion_network_unchanged():
    # Same genome, same MLP -- the crop line must be the control.
    mine, champion = di.STRATEGY().mlp, npx.NeuroPilotStrategy().mlp
    assert (mine.w1, mine.b1, mine.w2, mine.b2) == (
        champion.w1, champion.b1, champion.w2, champion.b2)


# --- the two knobs are entangled; flooring one alone cannot fire ---

def test_an_animal_job_loses_to_every_crop_job_at_the_champion_labour_knob():
    # Diagnosis, pinned. Animal job value is ANIMAL_JOB_SCALE * livestock_labor_share
    # = 2.0 * 0.1063 = 0.213, against CROP_JOB_VALUE 1.0. At TRAVEL_COST 0.05 an
    # animal job only wins if the nearest crop job is ~16 tiles further away --
    # impossible on a 10x10 board with crop work anywhere near the worker.
    champion_share = 0.1063
    animal = npx.ANIMAL_JOB_SCALE * champion_share
    crop = npx.CROP_JOB_VALUE
    tiles_of_slack = (crop - animal) / npx.TRAVEL_COST
    assert animal < crop
    assert tiles_of_slack > 15, tiles_of_slack   # board diagonal is 18


def test_labour_floor_makes_an_animal_job_outrank_a_crop_job_not_merely_tie_it():
    # Parity is not enough. `candidate_jobs` sorts ties by position and
    # `assign_workers` keeps the first on a tie, so at exactly equal value the
    # low-coordinate crop tiles win every tie and the herd is never tended:
    # measured, 13 FEED actions in a whole season against field_rival's 153.
    # An unfed animal is a permanent 400-500 loss; an unwatered plant costs ~100
    # and survives a day, so the animal job is genuinely worth more.
    floored = di.floor_herd(_knobs(livestock_labor_share=0.1063))
    assert npx.ANIMAL_JOB_SCALE * floored.livestock_labor_share > npx.CROP_JOB_VALUE


def test_labour_floor_makes_an_animal_job_at_least_match_a_crop_job():
    # Without this the herd is bought and never placed: 9 cows and 2 sheep sat
    # in the shed all game, which with melon hit the 100-item cap exactly and
    # silently discarded every later harvest. Measured: final money 45,945 ->
    # 1,050.
    floored = di.floor_herd(_knobs(livestock_labor_share=0.1063))
    assert npx.ANIMAL_JOB_SCALE * floored.livestock_labor_share >= npx.CROP_JOB_VALUE


def test_the_labour_floor_never_lowers_a_knob_the_network_pushed_higher():
    high = _knobs(herd_target_scale=1.0, livestock_labor_share=0.9)
    assert di.floor_herd(high) is high


def test_only_livestock_knobs_are_touched():
    # The crop line is the control in this experiment.
    before = _knobs()
    after = di.floor_herd(before)
    for field in npx.Knobs._fields:
        if field in ("herd_target_scale", "livestock_labor_share"):
            continue
        assert getattr(after, field) == getattr(before, field), field


# --- the herd needs feed, and the champion never buys any ---

def _state(animals=0, wheat=0, money=10_000, market=None):
    tiles = [[None] * 10 for _ in range(10)]
    for i in range(animals):
        x, y = npx.ANIMAL_TILES[i][0]
        tiles[y][x] = {"kind": "PASTURE", "animal": npx.ANIMAL_TILES[i][1],
                       "fed_today": False, "yield_units": 0}
    return {
        "player": 0, "day": 14, "hour": 5,
        "farms": [{"money": money, "tiles": tiles, "hands": [],
                   "unlocked_quadrants": ["NW", "NE", "SW"], "farmer": [4, 4]}],
        "market": {"prices": {"WHEAT": 25}, "inventory": {}},
        "private": {"shed": {"WHEAT": wheat}, "seeds": {}, "inventories": [{}]},
    }, {"farmer": ["PASS"], "hands": [], "market": list(market or [])}


def test_feed_is_bought_once_the_herd_exists():
    # neuropilot's only BUY_PRODUCT is FERTILIZER; it never buys WHEAT. FEED
    # spends wheat from a worker's inventory, sourced from the shed, so unless
    # crop_mix happens to pick wheat the herd starves and escapes at
    # consecutive_unfed >= 2. Measured: cows cycled buy -> place -> starve ->
    # re-buy at 400 a head, and livestock revenue never left zero.
    state, action = _state(animals=11, wheat=0)
    orders = di.feed_orders(state, action)
    assert orders and orders[0][:2] == ["BUY_PRODUCT", "WHEAT"]
    assert orders[0][2] >= 11


def test_no_feed_is_bought_without_a_herd():
    state, action = _state(animals=0, wheat=0)
    assert di.feed_orders(state, action) == []


def test_no_feed_is_bought_when_the_shed_is_already_stocked():
    state, action = _state(animals=4, wheat=99)
    assert di.feed_orders(state, action) == []


def test_feed_orders_respect_the_per_turn_order_cap():
    full = [["SELL", "MELON", 1]] * di.MAX_ORDERS
    state, action = _state(animals=11, wheat=0, market=full)
    assert di.feed_orders(state, action) == []


def test_feed_order_survives_the_simulators_parser():
    from kaggle_environments.envs.kaggriculture import kaggriculture as sim
    state, action = _state(animals=11, wheat=0)
    for order in di.feed_orders(state, action):
        assert sim._parse_order(order) is not None, order


def test_the_feed_buffer_is_not_sold_back_out_again():
    # neuropilot's _sell_orders liquidates any sellable item in the shed, wheat
    # included -- so buying feed and dumping it the same turn would churn money
    # into the spread every turn. Same defect field_rival had (#181).
    state, _ = _state(animals=11, wheat=30)
    kept = di.keep_feed(state, [["SELL", "WHEAT", 30], ["SELL", "MELON", 5]])
    wheat_sells = [o for o in kept if o[:2] == ["SELL", "WHEAT"]]
    assert wheat_sells == [] or wheat_sells[0][2] <= 30 - di.feed_target(11)
    assert ["SELL", "MELON", 5] in kept
