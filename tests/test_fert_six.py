"""fert_six (#282): the two fertilizer seams on from day 6, nothing else."""

from __future__ import annotations

from strategies import fert_six as fs
from strategies.ten_melon import TenMelonStrategy


def test_the_declared_knobs():
    assert (fs.FERT_FROM, fs.FERT_STOCK, fs.FERT_CROPS) == (6, 8, ("MELON", "STRAWBERRY"))


def test_the_seams_switch_on_at_day_six_and_nothing_else_is_overridden():
    from harness.sheep_bench import _seam_names
    assert set(fs.FertSixStrategy.__dict__) & set(_seam_names()) == {"fertilizer_stock", "fertilize_crops"}
    p, q = fs.FertSixStrategy(), TenMelonStrategy()
    assert p.name == "fert_six" and isinstance(p, TenMelonStrategy)
    for day in (0, 3, 5):
        assert p.fertilizer_stock(day) is None and p.fertilize_crops(day) is None
    for day in (6, 12, 29):
        assert p.fertilizer_stock(day) == 8 and p.fertilize_crops(day) == ("MELON", "STRAWBERRY")
    assert p.fertilizer_stock() is None and p.fertilize_crops() is None      # a bare call is day 0
    assert p.CAPS == q.CAPS and p.herd_target(8) == q.herd_target(8) and p.feed_stock(animals=9) == q.feed_stock(animals=9)


def test_registered():
    from strategies import load
    assert load("fert_six") is fs.FertSixStrategy
