"""Observation helpers, the Strategy base, the defensive wrapper, the registry."""

from __future__ import annotations

import pytest

from kaggisim.state import my_farm, opponent_farm, parse, prices, tile_at
from kaggisim.strategy import Strategy, make_agent
from strategies import load


# --- state helpers ---

def _obs():
    return {
        "player": 0,
        "farms": [
            {"tiles": [[None, {"kind": "PLANT"}]]},
            {"tiles": [[None, None]]},
        ],
        "market": {"prices": {"WHEAT": 25}},
    }


def test_parse_is_identity():
    o = {"a": 1}
    assert parse(o) is o


def test_my_and_opponent_farm():
    obs = _obs()
    assert my_farm(obs) is obs["farms"][0]
    assert opponent_farm(obs) is obs["farms"][1]


def test_prices_reads_market_and_defaults_empty():
    assert prices(_obs()) == {"WHEAT": 25}
    assert prices({}) == {}


def test_tile_at_indexes_row_major():
    farm = _obs()["farms"][0]
    assert tile_at(farm, 1, 0) == {"kind": "PLANT"}
    assert tile_at(farm, 0, 0) is None


# --- Strategy base + defensive wrapper ---

def test_base_strategy_act_is_abstract():
    with pytest.raises(NotImplementedError):
        Strategy().act({})


def test_base_strategy_reset_is_a_noop():
    assert Strategy().reset() is None


class _Boom(Strategy):
    def act(self, state):
        raise ValueError("boom")


def test_make_agent_degrades_to_pass_on_error(monkeypatch):
    monkeypatch.delenv("ROBRICULTURE_STRICT", raising=False)
    agent = make_agent(_Boom())
    assert agent({}) == {"farmer": ["PASS"], "hands": [], "market": []}


def test_make_agent_strict_mode_reraises(monkeypatch):
    monkeypatch.setenv("ROBRICULTURE_STRICT", "1")
    agent = make_agent(_Boom())
    with pytest.raises(ValueError):
        agent({})


# --- registry ---

def test_load_known_strategy():
    assert load("lean").__name__ == "LeanStrategy"


def test_load_unknown_strategy_raises():
    with pytest.raises(KeyError):
        load("not_a_strategy")
