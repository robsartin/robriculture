"""The crop_plan seam on the frozen benchmark (#337): off by default; when it
fires, the turn's caps and melon windows are its pair."""

from __future__ import annotations

from strategies import field_rival as fr

DEAD_CAPS = {"MELON": 24, "WHEAT": 24, "STRAWBERRY": 0}
DEAD_WINDOWS = ((9, 18),)


def _obs(seed=1671, steps=3):
    from kaggisim.state import parse
    from kaggle_environments import make
    env = make("kaggriculture", configuration={"seed": seed, "episodeSteps": steps})
    return parse(env.reset()[0].observation)


def test_the_hook_returns_none_on_the_benchmark_and_is_a_seam():
    from harness.sheep_bench import _seam_names
    assert fr.FieldRivalStrategy().crop_plan(_obs()) is None
    names = _seam_names()
    assert "crop_plan" in names and len(names) == 21


def test_act_uses_the_plans_caps_and_windows_for_the_turn(monkeypatch):
    seen = []
    def spy(day, standing, season_days=fr.SEASON_DAYS, caps=None, pivot=None, windows=None):
        seen.append((caps, windows))
        return None
    monkeypatch.setattr(fr, "crop_for_plot", spy)
    got = []
    on = type("On", (fr.FieldRivalStrategy,),
               {"crop_plan": lambda self, obs: (got.append(obs), (DEAD_CAPS, DEAD_WINDOWS))[1]})()
    obs = _obs()
    out = on.act(obs)
    assert set(out) >= {"farmer", "hands", "market"}
    assert seen and all(c is DEAD_CAPS and w is DEAD_WINDOWS for c, w in seen)
    assert got and got[0] is obs
    seen.clear()
    fr.FieldRivalStrategy().act(_obs())
    assert seen and all(c is fr.FieldRivalStrategy.CAPS and w is None for c, w in seen)


def test_market_orders_sees_the_plans_caps_and_windows(monkeypatch):
    seen = {}
    real = fr.market_orders
    def spy(*a, **k):
        seen["caps"], seen["windows"] = k.get("caps"), k.get("windows")
        return real(*a, **k)
    monkeypatch.setattr(fr, "market_orders", spy)
    on = type("On", (fr.FieldRivalStrategy,), {"crop_plan": lambda self, obs: (DEAD_CAPS, DEAD_WINDOWS)})()
    on.act(_obs())
    assert seen["caps"] is DEAD_CAPS and seen["windows"] is DEAD_WINDOWS


def test_the_stub_switches_it_off():
    from harness import feed_bench
    off = feed_bench.off_class()()
    assert off.crop_plan(_obs()) is None
