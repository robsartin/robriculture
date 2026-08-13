"""neuropilot — NN-guided agent (neuroevolution Phase 1, #64)."""
from __future__ import annotations
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
