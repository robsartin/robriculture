"""neuropilot — NN-guided agent (neuroevolution Phase 1, #64)."""
from __future__ import annotations
import math
from kaggisim import economy
from strategies import neuropilot as np


def _obs(day=0, hour=0, money=3000, hands=None, tiles=None, shed=None,
         unlocked=("NW",), prices=None, opp_money=3000):
    board = tiles or [[None]*10 for _ in range(10)]
    hands = hands or []
    return {
        "player": 0, "day": day, "hour": hour,
        "farms": [
            {"money": money, "tiles": board, "farmer": [4, 4], "hands": hands,
             "unlocked_quadrants": list(unlocked)},
            {"money": opp_money, "tiles": [[None]*10 for _ in range(10)], "farmer": [4, 4], "hands": []},
        ],
        "market": {"inventory": {}, "prices": prices or {}},
        "town": {"unlocked_shops": []},
        "private": {"shed": shed or {}, "seeds": {}, "inventories": [{} for _ in range(1 + len(hands))]},
    }


def test_features_has_fixed_length_all_in_unit_range():
    f = np.features(_obs())
    assert len(f) == np.N_FEATURES
    assert all(0.0 <= v <= 1.0 for v in f)


def test_features_is_deterministic():
    o = _obs(day=5, money=12000)
    assert np.features(o) == np.features(o)


def test_features_reflects_day_progress():
    # A later day pushes the day-fraction feature higher (feature index 0).
    assert np.features(_obs(day=20))[0] > np.features(_obs(day=1))[0]


def test_features_never_raises_returns_neutral_on_malformed():
    assert np.features({"garbage": True}) == np.NEUTRAL_FEATURES
    assert len(np.NEUTRAL_FEATURES) == np.N_FEATURES


def test_genome_size_matches_layer_shapes():
    # W1 (h1*n_in) + b1 (h1) + W2 (n_out*h1) + b2 (n_out)
    assert np.genome_size(4, 3, 2) == (3*4 + 3) + (2*3 + 2)


def test_forward_outputs_are_in_unit_range_and_right_length():
    g = np.random_genome(np.N_FEATURES, np.H1, np.N_KNOBS, seed=1)
    mlp = np.MLP.from_genome(g, np.N_FEATURES, np.H1, np.N_KNOBS)
    out = mlp.forward([0.5] * np.N_FEATURES)
    assert len(out) == np.N_KNOBS
    assert all(0.0 <= v <= 1.0 for v in out)


def test_forward_is_deterministic():
    g = np.random_genome(np.N_FEATURES, np.H1, np.N_KNOBS, seed=2)
    mlp = np.MLP.from_genome(g, np.N_FEATURES, np.H1, np.N_KNOBS)
    x = [0.3] * np.N_FEATURES
    assert mlp.forward(x) == mlp.forward(x)


def test_tiny_genome_forward_matches_hand_computation():
    # n_in=1, h1=1, n_out=1. genome = [W1, b1, W2, b2] = [1.0, 0.0, 1.0, 0.0].
    mlp = np.MLP.from_genome([1.0, 0.0, 1.0, 0.0], 1, 1, 1)
    h = math.tanh(1.0*0.5 + 0.0)
    expected = 1.0/(1.0+math.exp(-(1.0*h + 0.0)))
    assert abs(mlp.forward([0.5])[0] - expected) < 1e-9


def test_default_genome_has_the_right_length():
    assert len(np.DEFAULT_GENOME) == np.genome_size(np.N_FEATURES, np.H1, np.N_KNOBS)


def test_mlp_forward_matches_hand_computation_with_distinct_dims():
    # n_in=2, h1=3, n_out=1 — distinct dims so a W1/W2 row/column transpose
    # would change the result (the all-dims-1 tiny test above can't catch
    # that: every dim is 1 there, so transposing changes nothing).
    genome = [
        1.0, 0.0,       # W1 row 0 (hidden unit 0's weights on [x0, x1])
        0.0, 1.0,       # W1 row 1
        1.0, 1.0,       # W1 row 2
        0.0, 0.0, 0.0,  # b1
        2.0, 3.0, 4.0,  # W2 row 0 (n_out=1, over the 3 hidden units)
        0.5,            # b2
    ]
    assert len(genome) == np.genome_size(2, 3, 1)
    mlp = np.MLP.from_genome(genome, 2, 3, 1)
    x = [1.0, 2.0]
    h = [
        math.tanh(1.0 * x[0] + 0.0 * x[1] + 0.0),
        math.tanh(0.0 * x[0] + 1.0 * x[1] + 0.0),
        math.tanh(1.0 * x[0] + 1.0 * x[1] + 0.0),
    ]
    expected = 1.0 / (1.0 + math.exp(-(2.0 * h[0] + 3.0 * h[1] + 4.0 * h[2] + 0.5)))
    out = mlp.forward(x)
    assert len(out) == 1
    assert abs(out[0] - expected) < 1e-9


# --- Task 3: knob decode + minimal controller -------------------------------

def test_decode_knobs_maps_all_eight_fields_into_unit_range():
    k = np.decode_knobs([0.0, 0.25, 0.5, 0.75, 1.0, 0.1, 0.9, 0.4])
    assert 0.0 <= k.sell_throttle <= 1.0 and 0.0 <= k.crop_mix <= 1.0
    assert k.hire_target == 0.25


def test_step_toward_moves_and_passes():
    from kaggisim.actions import MOVES
    assert np._step_toward([4, 4], [4, 4]) == ["PASS"]
    assert np._step_toward([0, 4], [4, 4])[0] in MOVES


def test_controller_returns_a_legal_shape():
    k = np.decode_knobs([0.5]*np.N_KNOBS)
    a = np.controller(k, _obs(hour=0))
    assert isinstance(a["farmer"], list) and a["farmer"]
    assert isinstance(a["hands"], list)
    assert len(a["market"]) <= 10


def test_controller_sells_lead_the_market_list():
    k = np.decode_knobs([0.0] + [0.5]*(np.N_KNOBS-1))  # sell_throttle low => sell freely
    a = np.controller(k, _obs(hour=0, shed={"MELON": 10}))
    sells = [i for i, o in enumerate(a["market"]) if o[0] == "SELL"]
    non_sells = [i for i, o in enumerate(a["market"]) if o[0] != "SELL"]
    assert not non_sells or (not sells) or max(sells) < min(non_sells)


# --- #89: marginal-price-aware selling (replaces the all-or-nothing dump) ---

def test_sells_entire_shed_when_threshold_is_zero():
    """A zero sell_throttle floors the stopping price at 0 — every held unit
    clears the market's own price floor, so the whole shed still sells."""
    orders = np._sell_orders({"MELON": 60}, {}, sell_throttle=0.0)
    assert orders == [["SELL", "MELON", 60]]


def test_caps_quantity_when_marginal_price_falls_below_threshold():
    """Melon's quadratic over-supply penalty (economy.MARKET_PARAMS['MELON'],
    above_func='sq') means a high sell_throttle stops the walk part-way
    through a flooded shed instead of dumping it all in one order."""
    I0 = economy.MARKET_PARAMS["MELON"]["I0"]
    orders = np._sell_orders(
        {"MELON": 60}, {"MELON": I0 + 50}, sell_throttle=0.7
    )
    assert orders == [["SELL", "MELON", 37]]


def test_sells_in_full_for_a_deep_market_even_at_a_high_threshold():
    """WHEAT's near-bottomless log curve clears the whole shed at the same
    threshold that caps melon — only the steep curves get held back."""
    I0 = economy.MARKET_PARAMS["WHEAT"]["I0"]
    orders = np._sell_orders(
        {"WHEAT": 60}, {"WHEAT": I0 + 50}, sell_throttle=0.7
    )
    assert orders == [["SELL", "WHEAT", 60]]


def test_omits_an_item_the_walk_caps_to_zero():
    """When even the first unit clears below threshold, no order is emitted
    at all (never a ['SELL', item, 0])."""
    I0 = economy.MARKET_PARAMS["MELON"]["I0"]
    orders = np._sell_orders(
        {"MELON": 10}, {"MELON": I0 + 500}, sell_throttle=0.99
    )
    assert orders == []


def test_reads_current_market_inventory_not_a_stale_snapshot():
    """The cap is driven by the live market_inventory argument, not a cached
    price ratio — an unlisted item defaults to the curve's own I0 anchor."""
    orders_at_anchor = np._sell_orders({"MELON": 60}, {}, sell_throttle=0.7)
    I0 = economy.MARKET_PARAMS["MELON"]["I0"]
    orders_flooded = np._sell_orders(
        {"MELON": 60}, {"MELON": I0 + 40}, sell_throttle=0.7
    )
    assert orders_flooded[0][2] < orders_at_anchor[0][2]


def test_hire_target_scales_the_hire_count():
    low = np.controller(np.decode_knobs([0.5, 0.0] + [0.5]*6), _obs(hour=0))
    high = np.controller(np.decode_knobs([0.5, 1.0] + [0.5]*6), _obs(hour=0))
    assert sum(o[0] == "HIRE" for o in high["market"]) >= sum(o[0] == "HIRE" for o in low["market"])


def test_sell_and_seed_survive_when_a_full_hire_target_would_overflow_the_cap():
    """#117's adversarial case: a full hire target (9, at MAX_HANDS) plus a
    pending sell plus a needed seed buy is 11 candidate orders against a cap
    of 10 (`economy.CONFIG_DEFAULTS["maxMarketOrdersPerTurn"]`). CLAUDE.md
    requires sells never be the ones truncated; seed buys must also survive
    or planting stalls. Hires are the low-priority one that must absorb the
    overflow instead.
    """
    cap = economy.CONFIG_DEFAULTS["maxMarketOrdersPerTurn"]
    k = np.decode_knobs([0.0, 1.0] + [0.5]*6)  # sell freely; max hire_target
    a = np.controller(k, _obs(hour=0, money=3000, shed={"MELON": 10}))
    market = a["market"]
    kinds = [o[0] for o in market]
    assert len(market) <= cap
    assert kinds.count("SELL") == 1
    assert kinds.count("BUY_SEED") == 1
    n_hire = kinds.count("HIRE")
    assert n_hire == cap - kinds.count("SELL") - kinds.count("BUY_SEED")
    assert n_hire < np.MAX_HANDS


def test_act_runs_and_returns_legal_shape():
    a = np.NeuroPilotStrategy().act(_obs(hour=0))
    assert set(a) == {"farmer", "hands", "market"} and len(a["market"]) <= 10


def test_strategy_registered_as_contender():
    assert np.STRATEGY.benchmark is False and np.STRATEGY.name == "neuropilot"


# --- Task 4: livestock + fertilizer vocabulary --------------------------------

def test_animal_chore_builds_pasture_on_empty_unlocked_tile():
    tiles = [[None]*10 for _ in range(10)]
    a = np._animal_chore((5, 0), "COW", [5, 0], tiles, {}, {}, ["NW", "NE"])
    assert a == ["BUILD_PASTURE"]


def test_animal_chore_none_when_land_locked():
    tiles = [[None]*10 for _ in range(10)]
    assert np._animal_chore((5, 0), "COW", [5, 0], tiles, {}, {}, ["NW"]) is None


def test_livestock_orders_buy_land_before_animals_when_pace_high():
    k = np.decode_knobs([0.5, 0.5, 1.0, 0.5, 1.0, 0.5, 0.0, 0.5])  # pace high, reserve low
    orders = np._livestock_market_orders(k, _obs(money=100000, unlocked=("NW",)), 0)
    assert ["BUY_LAND"] in orders


def test_controller_still_sells_first_with_livestock_active():
    k = np.decode_knobs([0.0, 0.5, 1.0, 1.0, 1.0, 0.5, 0.0, 0.5])
    a = np.controller(k, _obs(hour=0, money=100000, shed={"MELON": 8}, unlocked=("NW", "NE", "SW")))
    sells = [i for i, o in enumerate(a["market"]) if o[0] == "SELL"]
    non = [i for i, o in enumerate(a["market"]) if o[0] != "SELL"]
    assert not non or not sells or max(sells) < min(non)


def test_land_order_stops_once_ne_and_sw_are_unlocked():
    # No ANIMAL_TILES quadrant lives in SE — cap land at NE+SW (2 extra
    # quadrants), mirroring meta_bot.land_orders' n_extra >= 2 guard, instead
    # of also reaching for the $4000 SE quadrant once affordable.
    assert np._land_order(["NW", "NE", "SW"], money=1_000_000, pace=1.0) == []


def test_land_order_no_longer_hard_gates_below_pace_half():
    """#97: the old `pace < 0.5: return []` cliff is gone. A pace of 0.05
    still doesn't buy at a modest, realistic money level, while a higher
    pace does at that same level -- the gate is a continuous requirement,
    not a discontinuity at 0.5. (#100 recalibrated the buffer's *size* --
    see test_land_order_buys_late_when_low_but_nonzero_pace_given_realistic_money
    for why $50k, the old test's money level, no longer makes the point: it
    cleared even the old 0.05 requirement's neighborhood under the new,
    flat-dollar buffer.)"""
    assert np._land_order(["NW"], money=5_000, pace=0.05) == []
    assert np._land_order(["NW"], money=5_000, pace=0.5) == [["BUY_LAND"]]


def test_land_order_buys_eventually_at_low_but_nonzero_pace_given_enough_money():
    """The property the old hard cutoff made impossible: a genome stuck
    below the old 0.5 gate is not stuck forever -- given a big enough money
    buffer, even a small pace like 0.05 still produces BUY_LAND."""
    assert np._land_order(["NW"], money=10_000_000, pace=0.05) == [["BUY_LAND"]]


def test_land_order_buys_when_high_pace_near_broke_like_observed_competitor():
    """#100: `pilkwang` (harness/production_report.py measurement, #95/#101),
    the external agent that outscores us ~9:1, buys land near-broke as soon
    as it can afford it -- day 7 at ~$1.3k-2.4k for the $1,000 NE quadrant.
    A high pace (0.9) should demand a comparably small, single-digit-
    thousands buffer, not the tens of thousands the pre-#100 curve required
    even near pace=1."""
    assert np._land_order(["NW"], money=2_500, pace=0.9) == [["BUY_LAND"]]


def test_land_order_buys_late_when_low_but_nonzero_pace_given_realistic_money():
    """#100: the pre-recalibration curve demanded ~$37k at the evolved
    genome's observed pace (~0.097) -- far beyond the ~$17.9k-$39k the
    champion ever accumulates in a 720-turn game (#95/#96 measurement), so
    the region evolution actually explored was flat and unbuyable. The
    recalibrated flat-dollar buffer (independent of price, matching how
    little `meta_rancher`'s real NE/SW buys differ in required cash --
    #101) puts a low-but-nonzero pace like 0.05 inside that envelope: it
    buys late, once money nears the accumulated peak, rather than never."""
    assert np._land_order(["NW"], money=16_500, pace=0.05) == [["BUY_LAND"]]
    assert np._land_order(["NW"], money=10_000, pace=0.05) == []


def test_land_order_required_money_is_monotonic_in_pace():
    """No cliff anywhere in [0, 1]: once a fixed money level buys land at
    some pace, every higher pace also buys at that same money level (the
    required buffer only shrinks as pace rises)."""
    paces = [0.01, 0.05, 0.1, 0.2, 0.3, 0.5, 0.7, 0.9, 1.0]
    money = 2_000_000
    results = [np._land_order(["NW"], money=money, pace=p) == [["BUY_LAND"]] for p in paces]
    # Once True, must stay True for every higher pace (no flat-then-cliff region).
    seen_true = False
    for buys in results:
        if buys:
            seen_true = True
        assert buys or not seen_true


def test_land_order_pace_near_zero_is_effectively_never_within_a_season_budget():
    """Pace near zero isn't a hard cutoff, but it must still be effectively
    unreachable within a realistic 720-turn game's money -- $19,594 was the
    diagnosed champion's entire unspent end-of-game cash pile (#96)."""
    assert np._land_order(["NW"], money=19_594, pace=0.01) == []


def test_fertilize_duty_period_shrinks_as_pref_rises():
    """No hard 0.5 gate: the duty-cycle period is a continuous, monotonic
    function of fertilize_pref -- higher pref means an equal-or-shorter
    period (fertilizing at least as often), never a flat off/on switch."""
    assert np._fertilize_duty_period(0.9) <= np._fertilize_duty_period(0.5)
    assert np._fertilize_duty_period(0.5) <= np._fertilize_duty_period(0.1)
    assert np._fertilize_duty_period(0.1) <= np._fertilize_duty_period(0.01)


def test_is_fertilize_day_true_for_a_low_but_nonzero_pref_on_its_period_day():
    """A pref stuck below the old 0.5 gate still gets fertilize days -- just
    less often than a high pref, never zero of them."""
    pref = 0.1
    period = np._fertilize_duty_period(pref)
    assert period == 10
    assert np._is_fertilize_day(pref, day=period) is True
    assert np._is_fertilize_day(pref, day=period - 1) is False


def test_fertilizer_buy_order_fires_on_a_low_pref_duty_day():
    """The buy-fallback gate no longer requires pref >= 0.5 -- a low-but-
    nonzero pref still issues the order on its duty-cycle day."""
    tiles = [[None] * 10 for _ in range(10)]
    x, y = np.CROP_PLOTS[0]
    tiles[y][x] = {"kind": "PLANT", "fertilized_until_day": -1}
    k = np.decode_knobs([0.5, 0.5, 0.5, 0.5, 0.5, 0.1, 0.5, 0.5])  # fertilize_pref = 0.1
    period = np._fertilize_duty_period(k.fertilize_pref)
    state = _obs(day=period, money=3000, tiles=tiles)
    assert np._fertilizer_buy_order(k, state, cap=1) == [["BUY_PRODUCT", "FERTILIZER", 1]]


def test_fertilizer_buy_order_skips_an_off_duty_day_for_a_low_pref():
    """Same low pref, a day that isn't a multiple of its duty-cycle period:
    no buy order this turn -- frequency, not an unconditional switch."""
    tiles = [[None] * 10 for _ in range(10)]
    x, y = np.CROP_PLOTS[0]
    tiles[y][x] = {"kind": "PLANT", "fertilized_until_day": -1}
    k = np.decode_knobs([0.5, 0.5, 0.5, 0.5, 0.5, 0.1, 0.5, 0.5])  # fertilize_pref = 0.1, period 10
    state = _obs(day=1, money=3000, tiles=tiles)
    assert np._fertilizer_buy_order(k, state, cap=1) == []


def test_controller_picks_up_fertilizer_for_farmer_plot_on_a_low_pref_duty_day():
    """The worker-action gate (previously `fertilize_pref >= 0.5`) now fires
    on the pref's duty-cycle day even for a pref below the old threshold."""
    tiles = [[None] * 10 for _ in range(10)]
    x, y = np.CROP_PLOTS[0]
    tiles[y][x] = {"kind": "PLANT", "fertilized_until_day": -1}
    k = np.decode_knobs([0.5, 0.5, 0.0, 0.0, 0.0, 0.1, 0.5, 0.5])  # fertilize_pref = 0.1
    period = np._fertilize_duty_period(k.fertilize_pref)
    a = np.controller(k, _obs(day=period, hour=0, money=3000, tiles=tiles, shed={"FERTILIZER": 5}))
    assert a["farmer"] == ["PICKUP", "FERTILIZER", 1]


def test_load_champion_genome_valid_and_invalid(tmp_path):
    """load_champion_genome returns the genome if file exists & length is correct; None otherwise."""
    import json
    good = tmp_path / "good.json"
    good.write_text(json.dumps({"genome": [0.0]*np.genome_size(np.N_FEATURES, np.H1, np.N_KNOBS), "meta": {}}))
    assert np.load_champion_genome(str(good)) is not None
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"genome": [0.0, 0.0], "meta": {}}))   # wrong length
    assert np.load_champion_genome(str(bad)) is None
    assert np.load_champion_genome(str(tmp_path / "missing.json")) is None


def test_load_champion_genome_malformed_json_returns_none(tmp_path):
    """A file that isn't valid JSON at all never raises; returns None."""
    malformed = tmp_path / "malformed.json"
    malformed.write_text("{not valid json")
    assert np.load_champion_genome(str(malformed)) is None


def test_load_champion_genome_missing_genome_key_returns_none(tmp_path):
    """Valid JSON but missing the "genome" key never raises; returns None."""
    import json
    no_genome_key = tmp_path / "no_genome_key.json"
    no_genome_key.write_text(json.dumps({"meta": {}}))
    assert np.load_champion_genome(str(no_genome_key)) is None


def test_default_genome_is_the_packaged_local_champion():
    """The evolved champion ships inside strategies/ so it travels in the submission
    tarball (build/package.py copies strategies/, not harness/). DEFAULT_GENOME must
    load that package-local file — otherwise a submitted neuropilot silently reverts
    to random weights."""
    local = np.load_champion_genome(np._LOCAL_GENOME)
    assert local is not None
    assert len(local) == np.genome_size(np.N_FEATURES, np.H1, np.N_KNOBS)
    assert np.DEFAULT_GENOME == local


# --- #71: quadrant-derived crop plots (restored from #113) ---

def test_crop_plots_prefix_matches_the_old_hardcoded_nw_crew():
    # The generator must reproduce the shipped NW ordering exactly for the
    # first 10 plots: with MAX_HANDS = 9 that is every plot the controller
    # could previously reach, so this task changes no behaviour.
    assert np.crop_plots(("NW",))[:10] == [
        (4, 4), (3, 4), (4, 3), (2, 4), (3, 3), (4, 2), (1, 4), (2, 3), (3, 2), (4, 1),
    ]


def test_crop_plots_grows_when_a_quadrant_unlocks():
    # Buying land must add workable tiles -- the whole point of #71.
    assert len(np.crop_plots(("NW", "NE"))) > len(np.crop_plots(("NW",)))


def test_crop_plots_never_yields_a_tile_on_unowned_land():
    # Every NW plot has x <= 4 and y <= 4; nothing from another quadrant leaks in.
    assert all(x <= 4 and y <= 4 for x, y in np.crop_plots(("NW",)))


def test_crop_plots_never_collides_with_an_animal_tile():
    # Structural, not checked at use-time: the herd's tiles are filtered out
    # at construction, so a crop job can never be sent onto a pasture.
    animal_positions = {pos for pos, _ in np.ANIMAL_TILES}
    everywhere = np.crop_plots(("NW", "NE", "SW", "SE"))
    assert animal_positions.isdisjoint(everywhere)


def test_crop_plots_is_deterministic_and_nearest_shed_first():
    # ADR-0005: same input, same list, every time; ordered by walk distance.
    plots = np.crop_plots(("NW", "NE"))
    assert plots == np.crop_plots(("NW", "NE"))
    dists = [np._manhattan(np.SHED_TILE, p) for p in plots]
    assert dists == sorted(dists)
    assert plots[0] == np.SHED_TILE


def test_crop_plots_returns_empty_for_no_quadrants():
    # Must degrade, not raise -- the controller turns this into all-PASS.
    assert np.crop_plots(()) == []


def test_manhattan_is_l1_distance():
    # Validates that Manhattan distance is the sum of absolute coordinate differences.
    assert np._manhattan((0, 0), (3, 4)) == 7
    assert np._manhattan((4, 4), (4, 4)) == 0


# --- #71: job enumeration ---

def _knobs(**over):
    """A Knobs with every field at a mid value, overridable per test."""
    base = dict(sell_throttle=0.5, hire_target=0.5, livestock_pace=0.5,
                livestock_labor_share=0.5, herd_target_scale=0.5,
                fertilize_pref=0.0, capital_reserve=0.5, crop_mix=0.5)
    base.update(over)
    return np.Knobs(**base)


def test_candidate_jobs_has_one_crop_job_per_owned_plot():
    # Every owned tile gets a work order; use day=1 so pref=0.0 is genuinely a non-duty day (1 % huge_period != 0).
    jobs = np.candidate_jobs(_obs(day=1), _knobs())
    crop = [j for j in jobs if j.kind == "CROP"]
    assert len(crop) == len(np.crop_plots(("NW",)))


def test_candidate_jobs_grows_when_a_quadrant_unlocks():
    # More land must mean more work available -- the hypothesis under test.
    few = np.candidate_jobs(_obs(unlocked=("NW",)), _knobs())
    many = np.candidate_jobs(_obs(unlocked=("NW", "NE")), _knobs())
    assert len(many) > len(few)


def test_candidate_jobs_omits_animal_jobs_on_unowned_land():
    # Cows live in NE, sheep in SW; owning only NW means no animal work exists.
    jobs = np.candidate_jobs(_obs(unlocked=("NW",)), _knobs())
    assert not [j for j in jobs if j.kind in np._ANIMAL_KINDS]


def test_candidate_jobs_includes_animal_jobs_once_their_quadrant_is_owned():
    # Unlocking a quadrant unlocks animal work on that quadrant's pastures.
    jobs = np.candidate_jobs(_obs(unlocked=("NW", "NE")), _knobs())
    cows = [j for j in jobs if j.kind == "COW"]
    assert len(cows) == sum(1 for _, k in np.ANIMAL_TILES if k == "COW")


def test_candidate_jobs_positions_are_unique():
    # No two workers can ever be routed to the same tile: the fertilize job
    # REPLACES the shed tile's crop job rather than sitting beside it.
    jobs = np.candidate_jobs(_obs(unlocked=("NW", "NE", "SW")), _knobs(fertilize_pref=1.0))
    positions = [j.pos for j in jobs]
    assert len(positions) == len(set(positions))


def _shed_tile_wanting_fertilizer():
    # A live, unfertilized plant at SHED_TILE: the only tile the FERTILIZE
    # job can ever land on, and #71's filter (finding 1) now requires it to
    # actually want fertilizer before the job is enumerated at all.
    tiles = [[None] * 10 for _ in range(10)]
    x, y = np.SHED_TILE
    tiles[y][x] = {"kind": "PLANT", "fertilized_until_day": -1}
    return tiles


def test_candidate_jobs_replaces_the_shed_crop_job_with_fertilize_on_a_duty_day():
    # On a fertilize duty day, the shed tile gets a FERTILIZE job, not a CROP job; no position is duplicated.
    # Shed stock is required: `_fertilize_or_fetch` is asked with an empty
    # inventory (finding 1), so an empty shed would have nothing to fetch.
    jobs = np.candidate_jobs(_obs(day=0, tiles=_shed_tile_wanting_fertilizer(), shed={"FERTILIZER": 5}),
                              _knobs(fertilize_pref=1.0))
    at_shed = [j for j in jobs if j.pos == np.SHED_TILE]
    assert len(at_shed) == 1 and at_shed[0].kind == "FERTILIZE"


def test_candidate_jobs_has_no_fertilize_job_when_the_knob_is_off():
    # knob=0.0 produces a huge period; day=1 ensures 1 % period != 0, so it is not a fertilize duty day.
    jobs = np.candidate_jobs(_obs(day=1, tiles=_shed_tile_wanting_fertilizer(), shed={"FERTILIZER": 5}),
                              _knobs(fertilize_pref=0.0))
    assert not [j for j in jobs if j.kind == "FERTILIZE"]


def test_candidate_jobs_fertilize_value_rises_with_fertilize_pref():
    # The other reinterpreted knob: it now weights the fertilize job instead
    # of gating a duty cycle, so a keener setting must outbid more jobs.
    o = _obs(day=0, tiles=_shed_tile_wanting_fertilizer(), shed={"FERTILIZER": 5})
    low = [j for j in np.candidate_jobs(o, _knobs(fertilize_pref=0.3))
           if j.kind == "FERTILIZE"]
    high = [j for j in np.candidate_jobs(o, _knobs(fertilize_pref=1.0))
            if j.kind == "FERTILIZE"]
    assert low and high and high[0].value > low[0].value


def test_candidate_jobs_animal_value_rises_with_livestock_labor_share():
    # The reinterpreted knob: it now weights animal work instead of peeling
    # a fixed fraction of workers off the crop crew.
    o = _obs(unlocked=("NW", "NE"))
    low = [j for j in np.candidate_jobs(o, _knobs(livestock_labor_share=0.1)) if j.kind == "COW"]
    high = [j for j in np.candidate_jobs(o, _knobs(livestock_labor_share=0.9)) if j.kind == "COW"]
    assert high[0].value > low[0].value


def test_candidate_jobs_is_sorted_best_first_and_deterministic():
    # Jobs are value-ordered descending and tie-break by position; two calls on identical input reproduce exactly.
    o = _obs(unlocked=("NW", "NE"))
    jobs = np.candidate_jobs(o, _knobs())
    assert jobs == np.candidate_jobs(o, _knobs())
    assert [j.value for j in jobs] == sorted((j.value for j in jobs), reverse=True)


def test_candidate_jobs_returns_empty_when_nothing_is_owned():
    # Degrades rather than raising; the controller turns this into all-PASS.
    assert np.candidate_jobs(_obs(unlocked=()), _knobs()) == []


# --- #71 review finding 1: only tiles with actual work are enumerated,
# so a worker whose tile has gone idle is freed for real work elsewhere ---

def test_candidate_jobs_omits_a_crop_tile_with_nothing_to_do():
    # A fully-watered, not-yet-mature plant wants nothing this turn: no CROP
    # job at all, not a job a worker would just camp on.
    tiles = [[None] * 10 for _ in range(10)]
    x, y = np.SHED_TILE
    tiles[y][x] = {"kind": "PLANT", "watered_today": True, "planted_day": 0}
    jobs = np.candidate_jobs(_obs(day=0, tiles=tiles, unlocked=("NW",)), _knobs())
    assert not [j for j in jobs if j.pos == np.SHED_TILE]


def test_candidate_jobs_enumerates_a_hungry_animal_even_with_no_wheat_carrier():
    # `_animal_tile_has_work` asks with an empty inventory on purpose: whether
    # the tile wants work, not whether the asking worker personally can do it
    # right now. A hungry animal must still show up as work when the shed
    # (not any one worker) holds the WHEAT to feed it.
    #
    # `cared_today: True` (and no yield_units/fertilizer_available) is
    # required so the hunger clause is the ONLY thing that can make this
    # tile enumerate as work -- `_animal_chore`'s unconditional `care()`
    # fallback fires whenever `cared_today` is unset, since
    # `_animal_tile_has_work` always calls it with the worker "on" the tile
    # (pos == tile_pos). Leaving `cared_today` unset made an earlier version
    # of this test pass for the wrong reason (vacuous against a deleted
    # hunger clause) -- see task-5-report.md's vacuity-check section.
    tiles = [[None] * 10 for _ in range(10)]
    tiles[0][5] = {"kind": "PASTURE", "animal": "COW", "fed_today": False, "cared_today": True}
    jobs = np.candidate_jobs(_obs(tiles=tiles, unlocked=("NW", "NE"), shed={"WHEAT": 5}), _knobs())
    assert any(j.pos == (5, 0) and j.kind == "COW" for j in jobs)


def test_candidate_jobs_enumerates_a_bought_but_unplaced_animal():
    # A built pasture holding an unplaced animal (bought, sitting in the
    # shed) must be work: it's the only route left to stand the herd up now
    # that no worker-peel routes anyone there unconditionally.
    tiles = [[None] * 10 for _ in range(10)]
    tiles[0][5] = {"kind": "PASTURE"}
    jobs = np.candidate_jobs(_obs(tiles=tiles, unlocked=("NW", "NE"), shed={"COW": 1}), _knobs())
    assert any(j.pos == (5, 0) and j.kind == "COW" for j in jobs)


def test_controller_moves_a_worker_off_an_idle_tile_to_a_plantable_one():
    # The whole point of finding 1: a worker standing on a tile with nothing
    # left to do this turn (fully watered, not mature) must not just PASS
    # forever -- it gets reassigned to a nearby empty, plantable tile and
    # walks there instead.
    tiles = [[None] * 10 for _ in range(10)]
    x, y = np.SHED_TILE
    tiles[y][x] = {"kind": "PLANT", "watered_today": True, "planted_day": 0}
    out = np.controller(_knobs(crop_mix=1.0), _obs(day=0, tiles=tiles))
    assert out["farmer"] != ["PASS"]


# --- #71: greedy worker assignment ---

def test_assign_workers_gives_each_worker_a_distinct_job():
    # No double-booking: each worker claims exactly one unclaimed job.
    jobs = [np.Job((0, 0), "CROP", 1.0), np.Job((1, 1), "CROP", 1.0),
            np.Job((2, 2), "CROP", 1.0)]
    got = np.assign_workers([(0, 0), (1, 1), (2, 2)], jobs)
    assert len({j.pos for j in got}) == 3


def test_assign_workers_returns_none_when_jobs_run_out():
    # A worker with nothing to do passes; it must not crash or double-book.
    got = np.assign_workers([(0, 0), (5, 5)], [np.Job((0, 0), "CROP", 1.0)])
    assert got[0].pos == (0, 0) and got[1] is None


def test_assign_workers_returns_all_none_for_an_empty_job_list():
    # Empty job list degrades gracefully: all workers get None.
    assert np.assign_workers([(0, 0), (1, 1)], []) == [None, None]


def test_assign_workers_prefers_the_nearer_of_two_equal_jobs():
    # Distance is the tiebreaker when job values are equal.
    near, far = np.Job((0, 1), "CROP", 1.0), np.Job((9, 9), "CROP", 1.0)
    assert np.assign_workers([(0, 0)], [far, near])[0] == near


def test_assign_workers_walks_to_a_job_worth_the_trip():
    # Travel cost is 0.05/tile: 11 tiles away costs 0.55, so far (2.0 - 0.55 = 1.45)
    # still beats near (1.0 - 0.05 = 0.95). Proves the travel penalty does not swamp
    # a genuinely more valuable job. Its sibling test_assign_workers_declines_a_job_not_worth_the_trip
    # discriminates the subtraction itself (near 1.0 beats far 1.2 when cost flips the outcome).
    near = np.Job((0, 1), "CROP", 1.0)
    far = np.Job((0, 10 + 1), "COW", 2.0)
    assert np.assign_workers([(0, 0)], [far, near])[0] == far


def test_assign_workers_declines_a_job_not_worth_the_trip():
    # Same 11-tile penalty (0.55): far (1.2 - 0.55 = 0.65) loses to near (1.0 - 0.05 = 0.95).
    # This is the half that actually discriminates the travel-cost subtraction.
    near = np.Job((0, 1), "CROP", 1.0)
    far = np.Job((0, 10 + 1), "COW", 1.2)
    assert np.assign_workers([(0, 0)], [far, near])[0] == near


def test_assign_workers_is_deterministic():
    # Same input produces the same assignment every time (ADR-0005).
    jobs = [np.Job((0, 0), "CROP", 1.0), np.Job((0, 1), "CROP", 1.0)]
    positions = [(0, 0), (0, 1)]
    assert np.assign_workers(positions, jobs) == np.assign_workers(positions, jobs)


def test_job_score_discounts_distance():
    # A job's worth falls as distance rises — distance is charged against value at
    # a fixed rate. Standing on a job (distance 0) costs nothing, so the job is worth
    # its full value; further away, the value diminishes linearly.
    job = np.Job((0, 5), "CROP", 1.0)
    assert np._job_score((0, 0), job) == 1.0 - np.TRAVEL_COST * 5
    assert np._job_score((0, 5), job) == 1.0


# --- #71: per-tile animal job action (replaces beat-walking) ---

def _cow_tiles(**tile):
    """A board with a cow structure at (5, 0), the first COW animal tile."""
    board = [[None] * 10 for _ in range(10)]
    board[0][5] = {"kind": "PASTURE", "animal": "COW", **tile}
    return board


def test_animal_job_action_feeds_a_hungry_animal_it_is_standing_on():
    # Feed leads maintenance: an animal escapes after two unfed days.
    tiles = _cow_tiles(fed_today=False)
    got = np._animal_job_action((5, 0), "COW", (5, 0), tiles,
                                {"WHEAT": 1}, {}, ("NW", "NE"))
    assert got[0] == "FEED"


def test_animal_job_action_fetches_wheat_from_the_shed_when_it_holds_none():
    # Feed leads maintenance: an animal escapes after two unfed days.
    tiles = _cow_tiles(fed_today=False)
    got = np._animal_job_action((5, 0), "COW", np.SHED_TILE, tiles,
                                {}, {"WHEAT": 5}, ("NW", "NE"))
    assert got[0] == "PICKUP"


def test_animal_job_action_builds_a_pasture_on_a_bare_owned_tile():
    # Setup, not just tending -- without this the herd can never stand up.
    tiles = [[None] * 10 for _ in range(10)]
    got = np._animal_job_action((5, 0), "COW", (5, 0), tiles, {}, {}, ("NW", "NE"))
    assert got[0] == "BUILD_PASTURE"


def test_animal_job_action_places_an_animal_it_is_carrying():
    # Setup, not just tending -- placing the bought animal is required to stand up the herd.
    tiles = [[None] * 10 for _ in range(10)]
    tiles[0][5] = {"kind": "PASTURE"}
    got = np._animal_job_action((5, 0), "COW", (5, 0), tiles,
                                {"COW": 1}, {}, ("NW", "NE"))
    assert got[0] == "PLACE"


def test_animal_job_action_walks_toward_its_tile_when_nothing_else_applies():
    # Falls through to walk when idle -- the worker must reach its tile to wait for work.
    tiles = _cow_tiles(fed_today=True, cared_today=True)
    got = np._animal_job_action((5, 0), "COW", (0, 0), tiles, {}, {}, ("NW", "NE"))
    assert got[0] in ("EAST", "WEST", "NORTH", "SOUTH")


def test_animal_job_action_never_returns_none():
    # The controller appends this straight into the action list (ADR-0006).
    tiles = _cow_tiles(fed_today=True, cared_today=True)
    got = np._animal_job_action((5, 0), "COW", (5, 0), tiles, {}, {}, ("NW", "NE"))
    assert isinstance(got, list) and got


# --- #71: the controller dispatches assigned jobs ---

def test_assign_workers_sends_a_worker_to_a_tile_outside_nw_once_it_is_owned():
    # This exercises candidate_jobs + assign_workers directly, not
    # controller() -- see test_controller_routes_a_worker_onto_newly_owned_land
    # below for the end-to-end version. With 10 workers and only NW owned
    # every worker stays in NW; owning NE must put at least one on an NE tile.
    # livestock_labor_share=0.0 pins out animal jobs so an x>=5 assignment
    # can only come from crop work on the newly-owned NE land, not a cow tile.
    hands = [[4, 4]] * 9
    o = _obs(hands=hands, unlocked=("NW", "NE"))
    jobs = np.candidate_jobs(o, _knobs(livestock_labor_share=0.0))
    got = np.assign_workers([[4, 4]] + hands, jobs)
    assert any(j is not None and j.pos[0] >= 5 for j in got)


def test_assign_workers_never_sends_two_workers_to_the_same_tile():
    # Also exercises candidate_jobs + assign_workers directly, not
    # controller(). No two workers may claim the same job -- this is what
    # keeps controller() from ever emitting two actions for one tile.
    hands = [[4, 4]] * 9
    o = _obs(hands=hands, unlocked=("NW", "NE", "SW"))
    got = [j for j in np.assign_workers([[4, 4]] + hands, np.candidate_jobs(o, _knobs()))
           if j is not None]
    assert len({j.pos for j in got}) == len(got)


def test_controller_routes_a_worker_onto_newly_owned_land():
    # The end-to-end claim #71 exists to prove: controller() itself (not
    # just the enumeration/assignment helpers above) routes work onto
    # newly-bought land. All 10 workers start exactly on SHED_TILE
    # (x=4, NW's east edge), so no NW tile ever requires an eastward step;
    # an "EAST" action can only come from a worker assigned an NE tile
    # (x>=5) in the quadrant that just got unlocked.
    # livestock_labor_share=0.0 pins out animal jobs (which the old
    # worker-peel could also walk east to reach, e.g. a cow tile in NE) so
    # an EAST here can only be crop work on the newly-owned land.
    hands = [[4, 4]] * 9
    out = np.controller(_knobs(livestock_labor_share=0.0), _obs(hands=hands, unlocked=("NW", "NE")))
    assert "EAST" in [a[0] for a in [out["farmer"], *out["hands"]]]


def test_controller_returns_a_legal_shape_with_no_land_and_no_jobs():
    # Degenerate case: nothing owned -> every worker passes, no crash.
    o = _obs(hands=[[0, 0]], unlocked=())
    out = np.controller(_knobs(), o)
    assert out["farmer"] == ["PASS"]
    assert out["hands"] == [["PASS"]]


def test_controller_emits_one_action_per_worker():
    hands = [[4, 4]] * 5
    out = np.controller(_knobs(), _obs(hands=hands))
    assert len(out["hands"]) == len(hands)
    assert isinstance(out["farmer"], list) and out["farmer"]


def test_controller_respects_the_market_order_cap():
    # #117's budgeting must survive: a job-driven controller emits more
    # orders and presses the cap harder.
    cap = economy.CONFIG_DEFAULTS["maxMarketOrdersPerTurn"]
    out = np.controller(_knobs(hire_target=1.0), _obs(hands=[[4, 4]] * 9, money=99999))
    assert len(out["market"]) <= cap


def test_controller_buys_seed_for_assigned_tiles_not_every_owned_plot():
    # Seed accounting follows the assignment, not a prefix of CROP_PLOTS.
    # Farmer + 3 hands on an empty NW board: 4 workers take 4 empty crop
    # tiles, so exactly 4 seeds are wanted -- not the 25 tiles NW contains,
    # and not the 2 the old livestock_labor_share peel would have left.
    out = np.controller(_knobs(crop_mix=1.0), _obs(hands=[[4, 4]] * 3, money=99999))
    buys = [o for o in out["market"] if o[0] == "BUY_SEED"]
    assert buys == [["BUY_SEED", "MELON", 4]]
