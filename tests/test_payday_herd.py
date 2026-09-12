"""payday_herd (#274): one ramp step moved to payday, nothing else."""

from __future__ import annotations

from strategies import field_pace as fp
from strategies import field_rival as fr
from strategies import payday_herd as ph
from strategies.lean_feed import LeanFeedStrategy


def test_the_ramp_is_lean_feeds_with_the_last_step_on_day_12():
    assert ph.HERD_RAMP_P == ((0, 4), (6, 8), (12, 13))
    assert fp.HERD_RAMP_F == ((0, 4), (6, 8), (8, 13))
    assert ph.PaydayHerdStrategy.HERD_RAMP_F == ph.HERD_RAMP_P


def test_no_seam_is_overridden_and_the_targets_follow_the_ramp():
    from harness.sheep_bench import _seam_names
    assert set(ph.PaydayHerdStrategy.__dict__) & set(_seam_names()) == set()
    p, q = ph.PaydayHerdStrategy(), LeanFeedStrategy()
    assert p.name == "payday_herd" and isinstance(p, LeanFeedStrategy)
    assert [p.herd_target(d) for d in (0, 6, 8, 11, 12, 16)] == [4, 8, 8, 8, 13, 13]
    assert [q.herd_target(d) for d in (0, 6, 8, 11, 12, 16)] == [4, 8, 13, 13, 13, 13]
    assert p.herd_target(24) == max(13, fr.animal_target(24))
    assert p.pasture_count(8, 8) == min(len(fp.PASTURE_BLOCK_F), max(8 + p.LEAD_TILES, 8))
    assert p.pasture_count(12, 8) == min(len(fp.PASTURE_BLOCK_F), 13)
    assert p.feed_stock(animals=9) == q.feed_stock(animals=9) and p.buy_order() == q.buy_order()


def test_registered():
    from strategies import load
    assert load("payday_herd") is ph.PaydayHerdStrategy
