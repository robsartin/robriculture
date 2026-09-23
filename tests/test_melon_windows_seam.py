"""The melon_windows seam on the frozen benchmark (#334): off by default, a
second melon wave inside a window when it is on."""

from __future__ import annotations

from strategies import field_rival as fr
from strategies import hired_hands as hh

WINDOW = ((12, 13),)


def test_crop_for_day_plants_melon_inside_a_window_and_is_frozen_outside_it():
    assert fr.crop_for_day(12, windows=WINDOW) == "MELON"
    assert fr.crop_for_day(13, windows=WINDOW) == "MELON"
    assert fr.crop_for_day(12, windows=WINDOW, pivot=5) == "MELON"
    for day in (0, 4, 11, 14, 20):
        assert fr.crop_for_day(day, windows=WINDOW) == fr.crop_for_day(day)
    assert fr.crop_for_day(12) == fr.crop_for_day(12, windows=None) == "STRAWBERRY"
    assert fr.crop_for_day(3, windows=WINDOW) == "MELON"           # before the pivot: the frozen answer
    late = ((26, 27),)
    assert not hh.plantable("MELON", 26, fr.SEASON_DAYS)
    assert fr.crop_for_day(26, windows=late) == fr.crop_for_day(26)  # past melon's horizon: frozen


def test_crop_for_plot_still_caps_melon_inside_the_window():
    """Inside the window, melon to its cap, then the day's frozen crop (strawberry),
    then wheat -- never wheat in strawberry's place."""
    caps = {"MELON": 10, "STRAWBERRY": 38, "WHEAT": 24}
    assert fr.crop_for_plot(12, {"MELON": 3}, caps=caps, pivot=5, windows=WINDOW) == "MELON"
    assert fr.crop_for_plot(12, {"MELON": 10}, caps=caps, pivot=5, windows=WINDOW) == "STRAWBERRY"   # capped: the day's frozen crop, not wheat
    assert fr.crop_for_plot(12, {"MELON": 3}, caps=caps, pivot=5) == "STRAWBERRY"


def _orders(windows):
    return fr.market_orders(12, 1, 5000, 10, 2, 8, {}, {}, 5, standing={}, caps={"MELON": 10, "STRAWBERRY": 38, "WHEAT": 24},
                            pivot=5, windows=windows)


def test_market_orders_buys_seed_for_the_windows_crop():
    with_window = [o for o in _orders(WINDOW) if o[0] == "BUY_SEED"]
    without = [o for o in _orders(None) if o[0] == "BUY_SEED"]
    assert with_window and with_window[0][1] == "MELON"
    assert without and without[0][1] == "STRAWBERRY"


def test_the_hook_returns_none_on_the_benchmark_and_is_a_seam():
    from harness.sheep_bench import _seam_names
    assert fr.FieldRivalStrategy().melon_windows() is None
    names = _seam_names()
    assert "melon_windows" in names and len(names) == 20


def test_a_contender_with_the_seam_on_survives_a_turn_and_the_stub_switches_it_off():
    from harness import feed_bench
    from kaggisim.state import parse
    from kaggle_environments import make
    on = type("On", (fr.FieldRivalStrategy,), {"melon_windows": lambda self: WINDOW})()
    env = make("kaggriculture", configuration={"seed": 1671, "episodeSteps": 3})
    out = on.act(parse(env.reset()[0].observation))
    assert set(out) >= {"farmer", "hands", "market"}
    off = feed_bench.off_class()()
    assert off.melon_windows() is None
