"""Unit tests for the calibrated sparring opponent (issue #181, ADR-0007).

`field_rival` is not a candidate agent — it is a *measuring instrument*. The five
current anchors are swept 20/20 by the submitted champion and none of them plants
a single strawberry, so no paired experiment run against them can distinguish a
better agent from a worse one (#181). This strategy reproduces the archetype
measured from 63 real ladder replays: melon-heavy through day ~8, pivoting to
strawberry from day ~10, with a livestock line running underneath.

These tests pin the pure schedule helpers that carry the calibration. The
end-to-end profile (does it actually hit 12 melon at day 8?) is a full-game
measurement, not a unit test, and lives in the issue's pass criterion.
"""

from __future__ import annotations

from strategies import field_rival as fr


# --- crop_for_day: the measured melon -> strawberry pivot ---

def test_plants_melon_before_the_pivot():
    # The field that beats us holds 11-12 melon tiles through day 8.
    for day in range(0, fr.PIVOT_DAY):
        assert fr.crop_for_day(day) == "MELON", day


def test_plants_strawberry_after_the_pivot():
    # From day ~10 the field swings to strawberry (13 tiles by day 12).
    assert fr.crop_for_day(fr.PIVOT_DAY) == "STRAWBERRY"
    assert fr.crop_for_day(16) == "STRAWBERRY"


def test_plants_nothing_once_the_horizon_closes():
    # A strawberry planted this late cannot reach first yield before the buzzer;
    # the measured field is down to 1 strawberry tile by day 28.
    assert fr.crop_for_day(fr.SEASON_DAYS - 1) is None


# --- the measured ramps: hands, land, livestock ---

def test_hire_target_follows_the_measured_hand_ramp():
    # Field medians: 6 hands at day 4, 7 at day 8, 9 at day 12, 10 from day 16.
    assert fr.hire_target(4) == 6
    assert fr.hire_target(8) == 7
    assert fr.hire_target(12) == 9
    assert fr.hire_target(16) == 10
    assert fr.hire_target(24) == 10


def test_hire_target_never_exceeds_the_board_crew():
    for day in range(0, fr.SEASON_DAYS):
        assert 0 <= fr.hire_target(day) <= fr.MAX_HANDS, day


def test_land_target_follows_the_measured_quadrant_ramp():
    # Field medians: 1 quadrant through day 8, 2 by day 12, 3 from day 16.
    assert fr.land_target(4) == 1
    assert fr.land_target(8) == 1
    assert fr.land_target(12) == 2
    assert fr.land_target(16) == 3
    assert fr.land_target(24) == 3


def test_animal_target_follows_the_measured_livestock_ramp():
    # Field medians: 3 animals at day 4, 4 at day 8, 8 at day 12, 10 at 16, 11 at 24.
    assert fr.animal_target(4) == 3
    assert fr.animal_target(8) == 4
    assert fr.animal_target(12) == 8
    assert fr.animal_target(16) == 10
    assert fr.animal_target(24) == 11


def test_ramps_are_monotone_nondecreasing():
    # Every measured ramp only ever grows; the field never sells land or a herd.
    for fn in (fr.hire_target, fr.land_target, fr.animal_target):
        vals = [fn(d) for d in range(0, fr.SEASON_DAYS)]
        assert vals == sorted(vals), (fn.__name__, vals)


# --- the tile layout: NW must carry the whole early game ---

def test_crop_and_pasture_tiles_never_overlap():
    assert not (set(fr.CROP_TILES) & set(fr.PASTURE_TILES))


def test_every_tile_is_on_the_board_and_never_in_the_quadrant_we_never_buy():
    # land_target caps at 3 quadrants: NW, then NE, then SW. SE is never owned,
    # so a tile there would be permanently unreachable.
    for tile in list(fr.CROP_TILES) + list(fr.PASTURE_TILES):
        x, y = tile
        assert 0 <= x < 10 and 0 <= y < 10, tile
        assert fr.quadrant_of(x, y) in ("NW", "NE", "SW"), tile


def test_pastures_needed_before_the_land_buy_are_in_the_starting_quadrant():
    # The herd cannot all live in NW -- the field fills nearly all 25 NW tiles
    # with crops by day 8. What must be in NW is every head the ramp calls for
    # BEFORE the second quadrant is bought; the rest follow the land.
    buy_day = next(d for d in range(fr.SEASON_DAYS) if fr.land_target(d) >= 2)
    needed = fr.animal_target(buy_day - 1)
    for x, y in fr.PASTURE_TILES[:needed]:
        assert fr.quadrant_of(x, y) == "NW", (x, y)


def test_pasture_block_covers_the_peak_herd():
    assert len(fr.PASTURE_TILES) >= fr.animal_target(fr.SEASON_DAYS - 1)


def test_early_crop_clusters_fall_inside_the_starting_quadrant():
    # With the day-0 crew (hire_target(0) hands + the farmer) every assigned crop
    # tile must be in NW, or the farm cannot reach the measured 12 melon by day 8.
    workers = 1 + fr.hire_target(0)
    for i in range(workers):
        for x, y in fr.crop_cluster(i):
            assert fr.quadrant_of(x, y) == "NW", (i, x, y)


def test_livestock_workers_have_no_crop_cluster():
    assert fr.crop_cluster(fr.LIVESTOCK_WORKERS[0]) == ()
    assert fr.crop_cluster(fr.LIVESTOCK_WORKERS[1]) == ()


def test_crop_clusters_partition_the_crop_tiles_without_repeats():
    seen = []
    for i in range(1 + fr.MAX_HANDS):
        seen.extend(fr.crop_cluster(i))
    assert len(seen) == len(set(seen)), "a tile is tended by two workers"
    assert set(seen) <= set(fr.CROP_TILES)


def test_full_crew_tends_enough_tiles_for_the_measured_peak():
    # The field peaks at 27 planted tiles on day 16.
    total = sum(len(fr.crop_cluster(i)) for i in range(1 + fr.MAX_HANDS))
    assert total >= 27, total


# --- plot_action: the per-tile decision ---

def _plant(crop="MELON", day=0, **kw):
    tile = {"kind": "PLANT", "crop": crop, "planted_day": day,
            "watered_today": False, "yield_units": 0}
    tile.update(kw)
    return tile


def test_plants_an_empty_tile_with_todays_crop():
    assert fr.plot_action(None, "MELON", day=0, hour=0) == ["PLANT", "MELON"]
    assert fr.plot_action(None, "STRAWBERRY", day=12, hour=0) == ["PLANT", "STRAWBERRY"]


def test_never_plants_on_the_last_turn_of_the_day():
    # A plant is created with consecutive_unwatered=1 and dies at 2, so one
    # planted on the final turn cannot be watered and is dead by morning.
    last = fr.TURNS_PER_DAY - 1
    assert fr.plot_action(None, "MELON", day=0, hour=last) == ["PASS"]


def test_never_plants_when_there_is_no_crop_for_today():
    assert fr.plot_action(None, None, day=29, hour=0) == ["PASS"]


def test_waters_a_dry_standing_plant():
    assert fr.plot_action(_plant(), "MELON", day=3, hour=5) == ["WATER"]


def test_leaves_an_already_watered_plant_alone():
    assert fr.plot_action(_plant(watered_today=True), "MELON", day=3, hour=5) == ["PASS"]


def test_harvest_beats_watering_when_the_crop_is_ready():
    tile = _plant(day=0, yield_units=4)
    assert fr.plot_action(tile, "MELON", day=12, hour=5) == ["HARVEST"]


def test_harvests_an_ongoing_crop_again_after_it_regrows():
    # Strawberry is ongoing: the tile survives harvest and accrues more units,
    # so a second HARVEST must still be offered later in the season.
    tile = _plant("STRAWBERRY", day=10, yield_units=2, watered_today=True)
    assert fr.plot_action(tile, "STRAWBERRY", day=25, hour=5) == ["HARVEST"]


def test_digs_a_weed():
    assert fr.plot_action({"kind": "WEED"}, "MELON", day=3, hour=5) == ["DIG"]


def test_never_acts_on_locked_land():
    # Tiles in an unbought quadrant read as the string "LOCKED".
    assert fr.plot_action("LOCKED", "MELON", day=3, hour=5) == ["PASS"]


# --- nearest_shed: every worker's drop point ---

def test_nearest_shed_picks_the_closest_access_tile():
    assert fr.nearest_shed((0, 0)) == (4, 4)
    assert fr.nearest_shed((9, 0)) == (5, 4)
    assert fr.nearest_shed((0, 9)) == (4, 5)


def test_nearest_shed_is_reachable_from_anywhere_on_the_board():
    for y in range(10):
        for x in range(10):
            assert fr.nearest_shed((x, y)) in set(fr.SHED_ACCESS.values())
