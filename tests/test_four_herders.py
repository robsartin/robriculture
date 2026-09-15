"""four_herders (#289): the livestock seam gains a fourth worker from day 12, nothing else."""

from __future__ import annotations

from strategies import field_rival as fr
from strategies import four_herders as fh
from strategies.third_herder import HERDER_DAY, THIRD_HERDER
from strategies.ten_melon import TenMelonStrategy


def test_the_declared_knobs():
    assert (fh.FOURTH_HERDER, fh.FOURTH_DAY) == (7, 12)
    assert (HERDER_DAY, THIRD_HERDER) == (8, 6) and fr.LIVESTOCK_WORKERS == (1, 2)


def test_the_seam_by_day_and_nothing_else_overridden():
    from harness.sheep_bench import _seam_names
    assert set(fh.FourHerdersStrategy.__dict__) & set(_seam_names()) == {"livestock_workers"}
    p, q = fh.FourHerdersStrategy(), TenMelonStrategy()
    assert p.name == "four_herders" and isinstance(p, TenMelonStrategy)
    for day in (0, 5, 7):
        assert p.livestock_workers(day) is None and q.livestock_workers(day) is None
    for day in (8, 11):
        assert p.livestock_workers(day) == (1, 2, 6) == q.livestock_workers(day)
    for day in (12, 16, 29):
        assert p.livestock_workers(day) == (1, 2, 6, 7) and q.livestock_workers(day) == (1, 2, 6)
    assert p.CAPS == q.CAPS and p.herd_target(12) == q.herd_target(12) == 13


def test_registered():
    from strategies import load
    assert load("four_herders") is fh.FourHerdersStrategy
