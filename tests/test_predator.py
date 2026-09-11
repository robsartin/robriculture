"""The predator's schedule genome (#199): decode/encode, the frozen identity,
and the seams a genome drives. No full games here -- the bench plays those."""

from __future__ import annotations

import pytest

from strategies import field_rival as fr
from strategies import predator as pr


def test_the_genome_layout_is_the_declared_26_floats():
    assert pr.GENOME_LEN == 26
    assert pr.HAND_DAYS == (0, 8, 12, 16) and pr.HEAD_DAYS == (0, 4, 8, 12, 16, 24)
    assert pr.NEVER == 30 and pr.PREFER == (None, "SHEEP", "COW")
    assert len(pr.PERMS) == 24 and fr.BUY_ORDER in pr.PERMS


def test_the_frozen_schedule_is_the_benchmarks_constants():
    s = pr.Schedule.frozen()
    assert s.hands == (6, 7, 9, 10) and (s.ne_day, s.sw_day) == (12, 16)
    assert s.head == (1, 3, 4, 8, 10, 11) and (s.nw_pasture, s.ne_pasture) == (5, 7)
    assert s.herders == 2 and (s.cap_melon, s.cap_straw, s.cap_wheat) == (12, 15, 5)
    assert (s.pivot, s.cluster) == (10, 4) and pr.PERMS[s.order] == fr.BUY_ORDER
    assert (s.reserve, s.floor, s.carry, s.stock, s.prefer) == (1200, 0, 8, 0, 0)


def test_frozen_round_trips_and_is_26_floats_in_unit_range():
    assert len(pr.FROZEN) == 26 and all(0.0 <= u <= 1.0 for u in pr.FROZEN)
    assert pr.decode(pr.FROZEN) == pr.Schedule.frozen()
    assert pr.decode(pr.encode(pr.Schedule.frozen())) == pr.Schedule.frozen()


def test_decode_enforces_running_max_and_land_order_and_clamps():
    g = list(pr.FROZEN)
    # hands: a later breakpoint below an earlier one is lifted to it
    g[0], g[1], g[2], g[3] = 1.0, 0.0, 0.0, 0.0
    assert pr.decode(g).hands == (10, 10, 10, 10)
    # land: sw before ne is lifted to ne
    g = list(pr.FROZEN); g[4], g[5] = 20 / 31, 3 / 31
    s = pr.decode(g); assert s.ne_day == 20 and s.sw_day == 20
    # out-of-range floats clamp rather than raise
    g = list(pr.FROZEN); g[0] = 7.0; g[1] = -3.0
    assert pr.decode(g).hands[:2] == (10, 10)
    with pytest.raises(ValueError):
        pr.decode(pr.FROZEN[:-1])


def test_order_covers_all_24_permutations_and_stock_zero_means_frozen():
    import dataclasses
    frozen = pr.Schedule.frozen()
    orders = {pr.decode(pr.encode(dataclasses.replace(frozen, order=i))).order for i in range(24)}
    assert orders == set(range(24))
    s = dataclasses.replace(frozen, stock=5)
    assert pr.decode(pr.encode(s)).stock == 5
    assert pr.PredatorStrategy(pr.encode(s)).feed_stock(animals=4) == 5
    assert pr.PredatorStrategy().feed_stock(animals=4) is None


def test_the_default_predator_seams_return_the_frozen_values():
    p = pr.PredatorStrategy()
    assert p.name == "predator" and p.benchmark is True
    for day in range(30):
        assert p.hire_target(day) == fr.hire_target(day)
        assert p.land_target(day) == fr.land_target(day)
        assert p.herd_target(day) == fr.animal_target(day)
        assert p.pasture_count(day, 0) == min(len(fr.PASTURE_TILES), fr.animal_target(day))
        assert p.pasture_count(day, 11) == 11
    assert p.livestock_workers(0) == fr.LIVESTOCK_WORKERS
    assert p.layout() == (fr.PASTURE_TILES, fr.CROP_TILES)
    assert p.CAPS == fr.CROP_CAP and p.pivot_day() == fr.PIVOT_DAY and p.cluster_size() == fr.CLUSTER
    assert p.buy_order() == fr.BUY_ORDER and p.capital_reserve() == fr.CAPITAL_RESERVE
    assert p.spend_floor() is None and p.feed_carry() == fr.FEED_CARRY
    assert p.feed_stock() is None and p.herd_preference({}) is None


def test_a_mutant_genome_drives_every_seam():
    import dataclasses
    s = dataclasses.replace(
        pr.Schedule.frozen(), hands=(3, 3, 5, 5), ne_day=6, sw_day=pr.NEVER + 1,
        head=(0, 2, 2, 6, 6, 6), nw_pasture=2, ne_pasture=0, herders=3,
        cap_melon=20, cap_straw=30, cap_wheat=0, pivot=7, cluster=6,
        order=pr.PERMS.index(("hires", "herd", "land", "seed")), reserve=0, floor=500,
        carry=2, stock=3, prefer=1)
    p = pr.PredatorStrategy(pr.encode(s))
    assert p.schedule == s
    assert [p.hire_target(d) for d in (0, 8, 12, 16)] == [3, 3, 5, 5]
    assert [p.land_target(d) for d in (0, 6, 29)] == [1, 2, 2]
    assert p.herd_target(4) == 2 and p.herd_target(29) == 6
    assert p.pasture_count(29, 0) == 2  # capped at the block's two tiles
    assert p.livestock_workers(0) == (1, 2, 3)
    pasture, crops = p.layout()
    assert pasture == tuple(fr._quadrant_tiles("NW")[1:3]) and not set(pasture) & set(crops)
    assert len(crops) == 75 - 2
    assert p.CAPS == {"MELON": 20, "STRAWBERRY": 30, "WHEAT": 0}
    assert (p.pivot_day(), p.cluster_size()) == (7, 6)
    assert p.buy_order() == ("hires", "herd", "land", "seed")
    assert p.capital_reserve() == 0 and p.spend_floor() == 500
    assert (p.feed_carry(), p.feed_stock()) == (2, 3) and p.herd_preference({}) == "SHEEP"


def test_the_predator_is_registered_as_a_benchmark():
    from strategies import load
    assert load("predator") is pr.PredatorStrategy


def test_zero_herders_is_inexpressible_on_the_benchmark():
    """The seam returns `()` for herders=0, and `field_rival.act` reads an empty
    tuple as "no override" (`self.livestock_workers(day) or LIVESTOCK_WORKERS`),
    so a genome with herders=0 actually runs the frozen pair. Recorded, not fixed:
    changing the genome layout mid-search would re-decode the checkpoint."""
    import dataclasses
    p = pr.PredatorStrategy(pr.encode(dataclasses.replace(pr.Schedule.frozen(), herders=0)))
    assert p.livestock_workers(0) == ()
    assert (p.livestock_workers(0) or fr.LIVESTOCK_WORKERS) == fr.LIVESTOCK_WORKERS
