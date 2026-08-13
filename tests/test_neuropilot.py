"""neuropilot — NN-guided agent (neuroevolution Phase 1, #64)."""
from __future__ import annotations
import math
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


def test_hire_target_scales_the_hire_count():
    low = np.controller(np.decode_knobs([0.5, 0.0] + [0.5]*6), _obs(hour=0))
    high = np.controller(np.decode_knobs([0.5, 1.0] + [0.5]*6), _obs(hour=0))
    assert sum(o[0] == "HIRE" for o in high["market"]) >= sum(o[0] == "HIRE" for o in low["market"])


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
