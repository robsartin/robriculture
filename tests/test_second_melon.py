"""second_melon (#334): a second melon wave on days 12-13, nothing else."""

from __future__ import annotations

from strategies import field_rival as fr
from strategies import free_straw
from strategies import second_melon as sm
from strategies import twelve_head as th
from strategies.fert_sixteen import FertSixteenStrategy


def test_the_window_is_days_twelve_and_thirteen():
    p = sm.SecondMelonStrategy()
    assert sm.MELON_WINDOWS == ((12, 13),) and p.melon_windows() is sm.MELON_WINDOWS
    assert FertSixteenStrategy().melon_windows() is None
    assert fr.crop_for_day(12, windows=p.melon_windows()) == "MELON"
    assert fr.crop_for_day(14, windows=p.melon_windows()) == "STRAWBERRY"


def test_the_class_defines_only_the_window():
    from harness import sheep_bench as sb
    p = sm.SecondMelonStrategy()
    assert p.name == "second_melon" and isinstance(p, FertSixteenStrategy) and p.benchmark is False
    assert set(sm.SecondMelonStrategy.__dict__) & set(sb._seam_names()) == {"melon_windows"}
    assert {k for k, v in sm.SecondMelonStrategy.__dict__.items() if callable(v)} == {"melon_windows"}
    assert p.CAPS is free_straw.CAPS_S and p.CAPS["MELON"] == 10 and p.HERD_RAMP_F is th.HERD_RAMP_T
    assert p.FERT_FROM == 16 and p.fertilize_crops(16) == FertSixteenStrategy().fertilize_crops(16)


def test_registered():
    from strategies import load
    assert load("second_melon") is sm.SecondMelonStrategy
