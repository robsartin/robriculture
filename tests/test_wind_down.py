"""wind_down (#343): from day 28 buy nothing, keep no feed, hold no fertilizer,
and nothing else."""

from __future__ import annotations

from strategies import wind_down as wd
from strategies.town_melon import TownMelonStrategy


def test_the_declared_day_and_hook():
    p = wd.WindDownStrategy()
    assert wd.WIND_DOWN_DAY == 28
    assert p.wind_down(28) is True and p.wind_down(29) is True
    assert p.wind_down(27) is None and p.wind_down(0) is None and p.wind_down(None) is None
    assert TownMelonStrategy().wind_down(28) is None


def test_the_class_defines_only_the_hook():
    from harness import sheep_bench as sb
    p = wd.WindDownStrategy()
    assert p.name == "wind_down" and isinstance(p, TownMelonStrategy) and p.benchmark is False
    assert set(wd.WindDownStrategy.__dict__) & set(sb._seam_names()) == {"wind_down"}
    assert {k for k, v in wd.WindDownStrategy.__dict__.items() if callable(v)} == {"wind_down"}
    assert p.crop_plan({"day": 9}) == TownMelonStrategy().crop_plan({"day": 9})
    assert p.carry_limit() is None and p.water_first() is None


def test_registered():
    from strategies import load
    assert load("wind_down") is wd.WindDownStrategy
