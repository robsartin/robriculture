"""Pasture-first: the herd fronted, with the pasture standing before the head.

#239 removed the labour cap (a third herder) on top of #237's pasture lead,
and its own arm B showed a raised ramp losing 6/16 with two herders. The
ceiling (#234) runs 14 head by day 9; our champion asks `ANIMAL_RAMP` for 4
by day 8. This arm names a front-loaded ramp through the `herd_target` seam
and reads its own ramp for the pasture floor, so pasture stands for the
target before the head arrives. Everything else is `third_herder`'s.
"""

from __future__ import annotations

from strategies import field_rival as fr
from strategies import pasture_first as pf


def test_the_declared_constants():
    assert pf.FRONT_RAMP == ((0, 4), (2, 8), (6, 12))
    assert pf.PastureFirstStrategy.FRONT_RAMP == pf.FRONT_RAMP
    assert pf.PastureFirstStrategy.name == "pasture_first"
    assert pf.PastureFirstStrategy.benchmark is False


def test_the_front_ramp_never_asks_for_fewer_head_than_the_frozen_ramp():
    s = pf.PastureFirstStrategy()
    for day in range(fr.SEASON_DAYS):
        assert s.herd_target(day) >= fr.animal_target(day), day
    assert s.herd_target(0) == 4 and s.herd_target(2) == 8 and s.herd_target(6) == 12
    assert s.herd_target(29) == 12


def test_the_ramp_tops_out_at_the_pasture_block():
    # 12 is `len(PASTURE_TILES)`: a bigger herd would need a layout change,
    # which is a different decision.
    s = pf.PastureFirstStrategy()
    assert max(s.herd_target(d) for d in range(fr.SEASON_DAYS)) == len(fr.PASTURE_TILES)


def test_pasture_stands_for_the_target_before_the_head_arrives():
    # Day 0, nothing placed: the frozen floor would give 1 tile (the ramp asks
    # 1 head); the lead alone 3; this arm wants the 4 the front ramp asks for.
    s = pf.PastureFirstStrategy()
    assert s.pasture_count(0, 0) == 4
    assert s.pasture_count(2, 0) == 8
    assert s.pasture_count(6, 0) == 12
    # Once head is placed the lead still applies, capped at the block.
    assert s.pasture_count(6, 10) == 12
    assert s.pasture_count(0, 3) == 6          # placed + LEAD dominates the ramp


def test_it_is_a_registered_contender_built_on_third_herder():
    from strategies import REGISTRY, load
    from strategies.third_herder import ThirdHerderStrategy
    assert "pasture_first" in REGISTRY
    assert load("pasture_first") is pf.PastureFirstStrategy
    assert issubclass(pf.PastureFirstStrategy, ThirdHerderStrategy)
    # Inherited, not restated: the third herder, the pasture lead, #219's cow
    # rule and the crop caps all come from the bases unchanged.
    s = pf.PastureFirstStrategy()
    assert s.livestock_workers(8) == ThirdHerderStrategy().livestock_workers(8)
    assert pf.PastureFirstStrategy.LEAD_TILES == ThirdHerderStrategy.LEAD_TILES
    assert pf.PastureFirstStrategy.THRESHOLD == ThirdHerderStrategy.THRESHOLD
    assert pf.PastureFirstStrategy.CAPS == ThirdHerderStrategy.CAPS
