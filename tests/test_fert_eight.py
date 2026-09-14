"""fert_eight (#284): fert_six from day 8, nothing else."""

from __future__ import annotations

from strategies import fert_eight as fe
from strategies.fert_six import FERT_CROPS, FERT_STOCK, FertSixStrategy


def test_only_the_start_day_changes():
    assert fe.FERT_FROM_EIGHT == 8
    assert set(fe.FertEightStrategy.__dict__) - {"__module__", "__doc__", "__qualname__", "__firstlineno__", "__static_attributes__"} \
        <= {"name", "benchmark", "FERT_FROM"}
    p = fe.FertEightStrategy()
    assert p.name == "fert_eight" and isinstance(p, FertSixStrategy) and p.FERT_FROM == 8
    for day in (0, 6, 7):
        assert p.fertilizer_stock(day) is None and p.fertilize_crops(day) is None
    for day in (8, 12, 29):
        assert p.fertilizer_stock(day) == FERT_STOCK == 8 and p.fertilize_crops(day) == FERT_CROPS == ("MELON", "STRAWBERRY")
    assert FertSixStrategy().fertilizer_stock(7) == 8      # the parent still starts on day 6


def test_registered():
    from strategies import load
    assert load("fert_eight") is fe.FertEightStrategy
