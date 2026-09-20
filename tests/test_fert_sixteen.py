"""fert_sixteen (#324): the fertilizer line from day 16, nothing else."""

from __future__ import annotations

from strategies import fert_six as f6
from strategies import fert_sixteen as fs
from strategies import free_straw
from strategies import twelve_head as th
from strategies.twelve_head import TwelveHeadStrategy


def test_the_seams_fire_from_day_sixteen_with_fert_sixs_constants():
    p = fs.FertSixteenStrategy()
    assert fs.FERT_FROM == 16 and p.FERT_FROM == 16
    assert p.fertilizer_stock(None) is None and p.fertilize_crops(None) is None
    for d in (0, 8, 12, 15):
        assert p.fertilizer_stock(d) is None and p.fertilize_crops(d) is None
    for d in (16, 20, 29):
        assert p.fertilizer_stock(d) == f6.FERT_STOCK == 8
        assert p.fertilize_crops(d) == f6.FERT_CROPS == ("MELON", "STRAWBERRY")


def test_the_class_defines_exactly_the_two_fertilizer_seams():
    from harness import sheep_bench as sb
    p = fs.FertSixteenStrategy()
    assert p.name == "fert_sixteen" and isinstance(p, TwelveHeadStrategy) and p.benchmark is False
    assert set(fs.FertSixteenStrategy.__dict__) & set(sb._seam_names()) == {"fertilizer_stock", "fertilize_crops"}
    assert {k for k, v in fs.FertSixteenStrategy.__dict__.items() if callable(v)} == {"fertilizer_stock", "fertilize_crops"}
    assert p.HERD_RAMP_F is th.HERD_RAMP_T and p.CAPS is free_straw.CAPS_S and p.FOURTH_DAY == 8
    q = TwelveHeadStrategy()
    assert p.herd_target(20) == q.herd_target(20) == 12 and p.buy_order() == q.buy_order()


def test_registered():
    from strategies import load
    assert load("fert_sixteen") is fs.FertSixteenStrategy
