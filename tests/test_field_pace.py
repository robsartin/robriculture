"""field_pace: the field's schedule on third_herder, as one package (#252).

A census of third_herder vs pilkwang on spent seeds 864-867 read the field's
schedule straight off both boards: 5 hands, 4 head and no cash reserve from
day 0, strawberry from day 5, NE on day 6, 10 hands and 13 head by day 8, SW
on day 11, 62 planted by day 12, 14 pasture tiles inside NW. #244 and #246
showed one knob at a time is cash-limited; this arm moves all of them at once,
every value declared on #252, none tuned.
"""

from __future__ import annotations

from strategies import field_rival as fr
from strategies import field_pace as fp
from strategies.third_herder import ThirdHerderStrategy


def test_the_declared_constants():
    """Every knob the module docstring promises, on the module and mirrored onto the class."""
    assert fp.HAND_RAMP_F == ((0, 5), (6, 8), (8, 10), (15, 12))
    assert fp.LAND_RAMP_F == ((0, 1), (6, 2), (11, 3))
    assert fp.PIVOT_F == 5
    assert fp.CAPS_F == {"MELON": 12, "STRAWBERRY": 38, "WHEAT": 24}
    assert fp.CLUSTER_F == 6
    assert fp.HERD_RAMP_F == ((0, 4), (6, 8), (8, 13))
    assert fp.PASTURE_BLOCK_F == tuple(fr._quadrant_tiles("NW")[1:15])
    assert fp.RESERVE_F == 0
    s = fp.FieldPaceStrategy
    assert s.name == "field_pace" and s.benchmark is False and s.CAPS == fp.CAPS_F
    for attr in ("HAND_RAMP_F", "LAND_RAMP_F", "PIVOT_F", "CLUSTER_F", "HERD_RAMP_F",
                 "PASTURE_BLOCK_F", "CROP_TILES_F", "RESERVE_F"):
        assert getattr(s, attr) == getattr(fp, attr), attr


def test_every_hook_answers_with_the_declared_schedule():
    """Each seam returns the field's own ramp/value, not a frozen default."""
    s = fp.FieldPaceStrategy()
    assert [s.hire_target(d) for d in (0, 5, 6, 8, 15, 29)] == [5, 5, 8, 10, 12, 12]
    assert [s.land_target(d) for d in (0, 5, 6, 11, 29)] == [1, 1, 2, 3, 3]
    assert s.pivot_day() == 5 and s.cluster_size() == 6 and s.capital_reserve() == 0
    assert [s.herd_target(d) for d in (0, 6, 8, 29)] == [4, 8, 13, 13]
    assert s.layout() == (fp.PASTURE_BLOCK_F, fp.CROP_TILES_F)


def test_the_herd_ramp_never_asks_for_fewer_head_than_the_frozen_ramp():
    s = fp.FieldPaceStrategy()
    for day in range(fr.SEASON_DAYS):
        assert s.herd_target(day) >= fr.animal_target(day), day


def test_the_block_is_fourteen_nw_tiles_keeping_the_frozen_shed_prefix():
    """The pasture block is 14 distinct NW tiles, excludes the shed-access tile, and
    keeps the frozen benchmark's first five so the herders' shed walk is unchanged."""
    assert len(fp.PASTURE_BLOCK_F) == 14 and len(set(fp.PASTURE_BLOCK_F)) == 14
    assert all(fr.quadrant_of(x, y) == "NW" for x, y in fp.PASTURE_BLOCK_F)
    assert (4, 4) not in fp.PASTURE_BLOCK_F
    assert fp.PASTURE_BLOCK_F[:5] == fr.PASTURE_TILES[:5]


def test_crop_tiles_are_the_frozen_rule_with_the_block_removed():
    """Crop tiles and pasture block are disjoint and partition every owned tile."""
    owned = [t for q in fr.OWNED_QUADRANTS for t in fr._quadrant_tiles(q)]
    assert not (set(fp.CROP_TILES_F) & set(fp.PASTURE_BLOCK_F))
    assert set(fp.CROP_TILES_F) | set(fp.PASTURE_BLOCK_F) == set(owned)
    assert fp.CROP_TILES_F[0] == (4, 4)


def test_pasture_count_caps_at_its_own_block_and_floors_at_its_own_ramp():
    # pasture_first caps at the frozen twelve (#246's deferred minor); this arm
    # runs fourteen tiles and must be allowed to stand them all.
    s = fp.FieldPaceStrategy()
    assert s.pasture_count(0, 0) == 4               # the ramp asks 4 on day 0
    assert s.pasture_count(8, 0) == 13
    assert s.pasture_count(8, 12) == 14             # placed + lead 3, capped at 14
    assert s.pasture_count(29, 14) == 14


def test_it_is_a_registered_contender_built_on_third_herder():
    """Auto-discovered, and its inherited seams still resolve through third_herder."""
    from strategies import REGISTRY, load
    assert "field_pace" in REGISTRY and load("field_pace") is fp.FieldPaceStrategy
    assert issubclass(fp.FieldPaceStrategy, ThirdHerderStrategy)
    s = fp.FieldPaceStrategy()
    assert s.livestock_workers(8) == ThirdHerderStrategy().livestock_workers(8)
    assert fp.FieldPaceStrategy.LEAD_TILES == ThirdHerderStrategy.LEAD_TILES
    assert fp.FieldPaceStrategy.THRESHOLD == ThirdHerderStrategy.THRESHOLD


def _worked(day, hands):
    """Crop tiles the crew can actually plant on `day`: every non-herding worker's
    cluster, counted once, restricted to the quadrants the land ramp owns by then --
    a slot that reaches into a locked quadrant holds tiles nobody can plant yet.
    Workers are the farmer plus `hands`; herders come from the seam."""
    from strategies import field_rival as fr
    s = fp.FieldPaceStrategy()
    workers = s.livestock_workers(day) or fr.LIVESTOCK_WORKERS
    owned = fr.OWNED_QUADRANTS[:s.land_target(day)]
    tiles = set()
    for worker in range(1 + hands):
        tiles.update(t for t in fr.crop_cluster(worker, workers, crops=s.CROP_TILES_F,
                                                cluster=s.CLUSTER_F)
                     if fr.quadrant_of(*t) in owned)
    return len(tiles)


def test_the_crew_works_fewer_tiles_than_the_schedule_names_in_every_window():
    """The positive control the shape bars were missing (#252 review C2): with the
    slot layout frozen to the herder pair and slots sliced by number with no regard
    for which quadrant is owned yet, the crew can plant far fewer tiles than the
    schedule's 37 and 62 name -- and the third herder's slot idles from day 8.
    These are the ceilings the absolute bars sat on: 30 at day 8 against a bar of 30."""
    assert _worked(0, 5) == 11        # NW only: slots 1-3 reach past the 14-tile block into locked NE
    assert _worked(6, 8) == 36        # NE bought: seven crop workers, slot 6 wholly in locked SW
    assert _worked(8, 10) == 30       # third herder takes worker 6 -> slot 4 idles; slots 6-8 in locked SW
    assert _worked(11, 10) == 48      # SW bought: every held tile plantable
    assert _worked(15, 10) == 48      # the twelfth hand is never hired (C1)
