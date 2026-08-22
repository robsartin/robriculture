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


def test_controller_fertilizes_farmer_plot_on_a_low_pref_duty_day():
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
