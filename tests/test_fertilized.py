"""fertilized (#277): the two seams on, nothing else."""

from __future__ import annotations

from strategies import fertilized as fz
from strategies.payday_herd import PaydayHerdStrategy


def test_the_declared_knobs():
    assert fz.FERT_CROPS == ("STRAWBERRY", "MELON") and fz.FERT_STOCK == 24


def test_only_the_two_fertilizer_seams_are_overridden():
    from harness.sheep_bench import _seam_names
    assert set(fz.FertilizedStrategy.__dict__) & set(_seam_names()) == {"fertilizer_stock", "fertilize_crops"}
    p, q = fz.FertilizedStrategy(), PaydayHerdStrategy()
    assert p.name == "fertilized" and isinstance(p, PaydayHerdStrategy)
    assert p.fertilizer_stock() == 24 and p.fertilize_crops() == ("STRAWBERRY", "MELON")
    assert q.fertilizer_stock() is None and q.fertilize_crops() is None
    assert p.herd_target(8) == q.herd_target(8) == 8 and p.feed_stock(animals=9) == q.feed_stock(animals=9)


def test_not_registered_because_it_cannot_beat_random():
    """The #277 contender starves its own farm (reward 0 by design of the
    day-0 hold-back) and cannot clear ADR-0006's sanity floor against
    `random`, so it is not a submittable strategy: no module-level STRATEGY,
    no registry entry (#293). The class stays for the record and the bench."""
    from strategies import REGISTRY
    assert "fertilized" not in REGISTRY
    assert not hasattr(fz, "STRATEGY")
