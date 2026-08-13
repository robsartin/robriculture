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
