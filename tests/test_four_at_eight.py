"""four_at_eight (#291): four_herders from day 8, nothing else."""

from __future__ import annotations

from strategies import four_at_eight as fa
from strategies.four_herders import FourHerdersStrategy


def test_only_the_start_day_changes():
    p = fa.FourAtEightStrategy()
    assert p.name == "four_at_eight" and isinstance(p, FourHerdersStrategy) and p.FOURTH_DAY == 8
    assert set(fa.FourAtEightStrategy.__dict__) & {"livestock_workers", "herd_target", "feed_stock", "CAPS"} == set()
    assert p.livestock_workers(7) is None and p.livestock_workers(8) == (1, 2, 6, 7) and p.livestock_workers(12) == (1, 2, 6, 7)
    assert FourHerdersStrategy().livestock_workers(8) == (1, 2, 6)


def test_registered():
    from strategies import load
    assert load("four_at_eight") is fa.FourAtEightStrategy
