# tests/test_wind_down_seam.py
"""The wind_down seam on the frozen benchmark (#343): off by default; on, the
farm buys nothing, keeps no feed and holds no fertilizer back."""

from __future__ import annotations

from strategies import field_rival as fr


def _obs(seed=2586, steps=3):
    from kaggisim.state import parse
    from kaggle_environments import make
    env = make("kaggriculture", configuration={"seed": seed, "episodeSteps": steps})
    return parse(env.reset()[0].observation)


def test_the_hook_returns_none_on_the_benchmark_and_is_a_seam():
    from harness.sheep_bench import _seam_names
    assert fr.FieldRivalStrategy().wind_down(28) is None
    names = _seam_names()
    assert "wind_down" in names and len(names) == 21


def test_no_spend_is_a_floor_no_farm_reaches():
    assert isinstance(fr.NO_SPEND, int) and fr.NO_SPEND >= 10 ** 9


def test_market_orders_with_the_wind_down_values_sells_feed_and_buys_nothing():
    shed = {"WHEAT": 24, "FERTILIZER": 5, "MILK": 3}
    on = fr.market_orders(20, 5, 20000, 10, 3, 12, shed, {}, 6, standing={}, caps={"MELON": 10, "WHEAT": 24},
                          pivot=5, floor=fr.NO_SPEND, feed=0, fert=0)
    assert ["SELL", "WHEAT", 24] in on and ["SELL", "FERTILIZER", 5] in on and ["SELL", "MILK", 3] in on
    assert not [o for o in on if o[0].startswith("BUY")]
    off = fr.market_orders(20, 5, 20000, 10, 3, 12, shed, {}, 6, standing={}, caps={"MELON": 10, "WHEAT": 24}, pivot=5)
    assert [o for o in off if o[0] == "SELL" and o[1] == "WHEAT"] == [["SELL", "WHEAT", 24 - fr.feed_buffer(12)]] or \
        not [o for o in off if o[0] == "SELL" and o[1] == "WHEAT"]
    assert [o for o in off if o[0] == "BUY_SEED"]                   # the frozen farm still buys seed for its 6 empty plots


def test_act_passes_the_wind_down_values_only_when_the_hook_fires(monkeypatch):
    seen = {}
    real = fr.market_orders
    def spy(*a, **k):
        seen.update({"floor": k.get("floor"), "feed": k.get("feed"), "fert": k.get("fert")})
        return real(*a, **k)
    monkeypatch.setattr(fr, "market_orders", spy)
    obs = _obs()
    fr.FieldRivalStrategy().act(obs)
    assert seen == {"floor": None, "feed": None, "fert": None}
    seen.clear()
    got = []
    on = type("On", (fr.FieldRivalStrategy,), {"wind_down": lambda self, day: (got.append(day), True)[1]})()
    out = on.act(obs)
    assert set(out) >= {"farmer", "hands", "market"}
    assert seen == {"floor": fr.NO_SPEND, "feed": 0, "fert": 0}
    assert got == [obs.get("day", 0)]


def test_the_stub_switches_it_off():
    from harness import feed_bench
    off = feed_bench.off_class()()
    assert off.wind_down(28) is None
