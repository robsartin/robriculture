"""NW pasture block: the pasture opened before the head (#246).

#244 fronted the herd ramp and owned 10 head by day 9 -- the cash was there
-- but placed 5 and spent 561 turns with head in the shed: `PASTURE_TILES`
runs into NE, which is bought on day 12, so pasture is land-capped at five
until then. `BUILD_PASTURE` is free and instant, and the ceiling (#234)
builds fourteen pasture tiles inside NW alone by day 7. This arm is
`pasture_first` with the twelve-tile block moved into NW through the layout
seam; the crop tiles follow the frozen rule with the block removed.
"""

from __future__ import annotations

from strategies import field_rival as fr
from strategies import nw_pasture as nw


def test_the_declared_constants():
    assert nw.PASTURE_BLOCK == tuple(fr._quadrant_tiles("NW")[1:13])
    assert nw.NwPastureStrategy.PASTURE_BLOCK == nw.PASTURE_BLOCK
    assert nw.NwPastureStrategy.CROP_TILES == nw.CROP_TILES
    assert nw.NwPastureStrategy.name == "nw_pasture"
    assert nw.NwPastureStrategy.benchmark is False


def test_the_block_is_twelve_nw_tiles_that_keep_the_frozen_shed_prefix():
    # Twelve is len(PASTURE_TILES): the ramp's ceiling and every inherited rule
    # reading the block length are unchanged; only WHERE the tiles are moves.
    assert len(nw.PASTURE_BLOCK) == len(fr.PASTURE_TILES) == 12
    assert all(fr.quadrant_of(x, y) == "NW" for x, y in nw.PASTURE_BLOCK)
    assert (4, 4) not in nw.PASTURE_BLOCK                       # the shed-access tile stays crop
    assert nw.PASTURE_BLOCK[:5] == fr.PASTURE_TILES[:5]        # the herders' walk is unchanged
    assert len(set(nw.PASTURE_BLOCK)) == 12


def test_crop_tiles_are_the_frozen_rule_with_the_block_removed():
    owned = [t for q in fr.OWNED_QUADRANTS for t in fr._quadrant_tiles(q)]
    assert not (set(nw.CROP_TILES) & set(nw.PASTURE_BLOCK))
    assert set(nw.CROP_TILES) | set(nw.PASTURE_BLOCK) == set(owned)
    assert nw.CROP_TILES[0] == (4, 4)
    assert sum(1 for x, y in nw.CROP_TILES if fr.quadrant_of(x, y) == "NW") == 13


def test_slot_three_straddles_nw_and_ne_and_the_first_three_slots_are_all_nw():
    # Slots are sliced from CROP_TILES by the frozen `_crop_slot`; worker 5 is
    # slot 3 under the herder pair (1, 2). Its hand works one NW tile until NE
    # opens on day 12 -- the declared, visible cost of the block.
    s = nw.NwPastureStrategy()
    block, crops = s.layout()
    assert block is nw.PASTURE_BLOCK and crops is nw.CROP_TILES
    for worker in (0, 3, 4):
        assert all(fr.quadrant_of(x, y) == "NW" for x, y in fr.crop_cluster(worker, crops=crops))
    assert fr.crop_cluster(5, crops=crops) == ((0, 0), (5, 4), (5, 3), (6, 4))


def test_it_is_a_registered_contender_built_on_pasture_first():
    from strategies import REGISTRY, load
    from strategies.pasture_first import PastureFirstStrategy
    assert "nw_pasture" in REGISTRY
    assert load("nw_pasture") is nw.NwPastureStrategy
    assert issubclass(nw.NwPastureStrategy, PastureFirstStrategy)
    # Inherited, not restated: the front ramp, the third herder, the lead,
    # #219's cow rule and the crop caps all come from the bases unchanged.
    s = nw.NwPastureStrategy()
    assert nw.NwPastureStrategy.FRONT_RAMP == PastureFirstStrategy.FRONT_RAMP
    assert s.herd_target(6) == 12 and s.pasture_count(6, 0) == 12
    assert s.livestock_workers(8) == PastureFirstStrategy().livestock_workers(8)
    assert s.land_target(12) is None                           # the frozen land ramp
