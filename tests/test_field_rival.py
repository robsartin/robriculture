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


# --- crop_worker_action: tend the cluster, then bank the harvest ---

def _blank_board():
    return [[None for _ in range(10)] for _ in range(10)]


def test_crop_worker_steps_toward_a_tile_that_needs_work():
    tiles = _blank_board()
    action = fr.crop_worker_action(((0, 0),), tiles, (4, 4), {}, "MELON", 0, 0)
    assert action in (["WEST"], ["NORTH"])


def test_crop_worker_acts_on_the_tile_it_is_standing_on():
    tiles = _blank_board()
    assert fr.crop_worker_action(((4, 4),), tiles, (4, 4), {}, "MELON", 0, 0) == [
        "PLANT", "MELON"]


def test_crop_worker_carrying_a_full_load_heads_for_the_shed():
    # The shed caps at 100 items total and yield only counts once it is banked,
    # so a loaded worker banks before tending anything else.
    tiles = _blank_board()
    inv = {"MELON": fr.CARRY_LIMIT}
    action = fr.crop_worker_action(((0, 0),), tiles, (0, 0), inv, "MELON", 5, 5)
    assert action == ["EAST"], action


def test_crop_worker_drops_when_it_is_loaded_and_standing_at_the_shed():
    tiles = _blank_board()
    inv = {"MELON": fr.CARRY_LIMIT}
    assert fr.crop_worker_action((), tiles, (4, 4), inv, "MELON", 5, 5) == ["DROP"]


def test_crop_worker_banks_leftovers_when_the_cluster_needs_nothing():
    # Every tile watered and immature: nothing to do in the field, so an idle
    # worker with anything in hand walks it back rather than holding it.
    tiles = _blank_board()
    tiles[4][4] = _plant(watered_today=True)
    action = fr.crop_worker_action(((4, 4),), tiles, (4, 4), {"MELON": 1}, "MELON", 3, 5)
    assert action == ["DROP"]


# --- market_orders: the ramps, under the sim's 10-order-per-turn cap ---

def test_market_never_exceeds_the_per_turn_order_cap():
    # Dawn on the day both the land buy and the herd jump land, with money for
    # everything -- the turn where hires, land, animals, seed and sells collide.
    orders = fr.market_orders(day=12, hour=0, money=500_000, hands=0,
                              quadrants=1, animals=0, shed={"MELON": 60},
                              seeds={}, empty_plots=27)
    assert len(orders) <= fr.MAX_ORDERS, orders


def test_market_hires_toward_the_measured_ramp_at_dawn_only():
    dawn = fr.market_orders(day=16, hour=0, money=500_000, hands=0, quadrants=3,
                            animals=11, shed={}, seeds={}, empty_plots=0)
    assert sum(1 for o in dawn if o[0] == "HIRE") == fr.hire_target(16)
    midday = fr.market_orders(day=16, hour=7, money=500_000, hands=0, quadrants=3,
                              animals=11, shed={}, seeds={}, empty_plots=0)
    assert not [o for o in midday if o[0] == "HIRE"]


def test_market_buys_land_when_the_ramp_calls_for_it_and_never_beyond_three():
    at12 = fr.market_orders(day=12, hour=0, money=500_000, hands=10, quadrants=1,
                            animals=11, shed={}, seeds={}, empty_plots=0)
    assert ["BUY_LAND"] in at12
    done = fr.market_orders(day=24, hour=0, money=500_000, hands=10, quadrants=3,
                            animals=11, shed={}, seeds={}, empty_plots=0)
    assert ["BUY_LAND"] not in done


def test_market_sells_the_shed_down():
    orders = fr.market_orders(day=20, hour=3, money=0, hands=10, quadrants=3,
                              animals=11, shed={"MELON": 12}, seeds={},
                              empty_plots=0)
    assert ["SELL", "MELON", 12] in orders


def test_market_buys_no_seed_it_cannot_pay_for():
    orders = fr.market_orders(day=2, hour=3, money=0, hands=6, quadrants=1,
                              animals=1, shed={}, seeds={}, empty_plots=20)
    assert not [o for o in orders if o[0] == "BUY_SEED"]


def test_market_never_sells_the_feed_wheat_it_just_bought():
    # The herd eats bought wheat. Selling the shed indiscriminately would buy it
    # back and sell it again every turn, churning money into the spread.
    orders = fr.market_orders(day=20, hour=3, money=5_000, hands=10, quadrants=3,
                              animals=8, shed={"WHEAT": fr.feed_buffer(8), "MILK": 3},
                              seeds={}, empty_plots=0)
    assert not [o for o in orders if o[:2] == ["SELL", "WHEAT"]], orders
    assert ["SELL", "MILK", 3] in orders


def test_market_sells_only_the_wheat_above_the_feed_buffer():
    orders = fr.market_orders(day=20, hour=3, money=5_000, hands=10, quadrants=3,
                              animals=8, shed={"WHEAT": fr.feed_buffer(8) + 5},
                              seeds={}, empty_plots=0)
    assert ["SELL", "WHEAT", 5] in orders


# --- herd_worker_action: the livestock state machine ---

def test_herder_builds_the_pasture_it_is_standing_on():
    tiles = _blank_board()
    assert fr.herd_worker_action(((3, 4),), tiles, (3, 4), {}, {}, 0) == ["BUILD_PASTURE"]


def test_herder_places_an_animal_it_is_carrying_on_an_empty_pasture():
    tiles = _blank_board()
    tiles[4][3] = {"kind": "PASTURE"}
    assert fr.herd_worker_action(((3, 4),), tiles, (3, 4), {"COW": 1}, {}, 0) == [
        "PLACE", "COW"]


def test_herder_fetches_a_bought_animal_from_the_shed():
    tiles = _blank_board()
    tiles[4][3] = {"kind": "PASTURE"}
    action = fr.herd_worker_action(((3, 4),), tiles, (4, 4), {}, {"COW": 1}, 0)
    assert action == ["PICKUP", "COW", 1]


def test_herder_harvests_a_producing_animal():
    tiles = _blank_board()
    tiles[4][3] = {"kind": "PASTURE", "animal": "COW", "yield_units": 2,
                   "fed_today": False, "cared_today": False}
    assert fr.herd_worker_action(((3, 4),), tiles, (3, 4), {"WHEAT": 2}, {}, 9) == [
        "HARVEST"]


def test_herder_feeds_a_hungry_animal_from_its_own_wheat():
    # An animal dies at consecutive_unfed >= 2, and FEED consumes wheat from the
    # worker's own inventory, not the shed.
    tiles = _blank_board()
    tiles[4][3] = {"kind": "PASTURE", "animal": "COW", "yield_units": 0,
                   "fed_today": False, "cared_today": False}
    assert fr.herd_worker_action(((3, 4),), tiles, (3, 4), {"WHEAT": 1}, {}, 9) == [
        "FEED"]


def test_herder_with_no_wheat_in_hand_goes_to_the_shed_for_feed():
    tiles = _blank_board()
    tiles[4][3] = {"kind": "PASTURE", "animal": "COW", "yield_units": 0,
                   "fed_today": False, "cared_today": False}
    action = fr.herd_worker_action(((3, 4),), tiles, (4, 4), {}, {"WHEAT": 9}, 9)
    assert action == ["PICKUP", "WHEAT", fr.FEED_CARRY]


def test_herder_cares_only_when_already_standing_on_a_fed_animal():
    tiles = _blank_board()
    tiles[4][3] = {"kind": "PASTURE", "animal": "COW", "yield_units": 0,
                   "fed_today": True, "cared_today": False}
    assert fr.herd_worker_action(((3, 4),), tiles, (3, 4), {}, {}, 9) == ["CARE"]


def test_herder_ignores_pasture_tiles_on_land_it_does_not_own_yet():
    # PASTURE_TILES runs into NE, which is locked until day 12; a herder that
    # walked out to build there would burn its day on a tile the sim no-ops.
    tiles = _blank_board()
    tiles[4][3] = "LOCKED"          # the herd's only assigned tile, (3, 4)
    action = fr.herd_worker_action(((3, 4),), tiles, (4, 4), {}, {}, 0)
    assert action == ["PASS"], action


# --- every order must survive the sim's own parser ---

def test_every_emitted_order_parses_in_the_simulator():
    # The sim silently discards an order its `_parse_order` rejects -- a
    # BUY_ANIMAL without an explicit count parses to None and vanishes, which
    # reads exactly like "we could not afford it". Use the sim as the oracle.
    from kaggle_environments.envs.kaggriculture import kaggriculture as sim

    cases = [
        dict(day=0, hour=0, money=3_000, hands=0, quadrants=1, animals=0,
             shed={}, seeds={}, empty_plots=15),
        dict(day=12, hour=0, money=500_000, hands=0, quadrants=1, animals=0,
             shed={"MELON": 40, "MILK": 5, "WHEAT": 9}, seeds={}, empty_plots=27),
        dict(day=20, hour=6, money=8_000, hands=10, quadrants=3, animals=8,
             shed={"STRAWBERRY": 12}, seeds={"STRAWBERRY": 2}, empty_plots=4),
    ]
    for case in cases:
        for order in fr.market_orders(**case):
            assert sim._parse_order(order) is not None, (order, case)


def test_seed_for_empty_plots_outranks_the_herd():
    # Melon does not pay out until day 10. An animal ramp that spends the
    # opening bankroll leaves no seed money and the farm never starts: measured
    # at 30 reward against 55,638 before this rule existed.
    orders = fr.market_orders(day=4, hour=3, money=1_500, hands=6, quadrants=1,
                              animals=0, shed={}, seeds={}, empty_plots=15)
    kinds = [o[0] for o in orders]
    assert "BUY_SEED" in kinds
    assert "BUY_ANIMAL" not in kinds, orders


def test_herd_is_bought_only_out_of_surplus():
    # With deep reserves the ramp proceeds as measured.
    rich = fr.market_orders(day=12, hour=3, money=50_000, hands=9, quadrants=2,
                            animals=0, shed={}, seeds={}, empty_plots=0)
    assert sum(1 for o in rich if o[0] == "BUY_ANIMAL") == fr.animal_target(12)
    # Just above the seed line but below the reserve: no animal.
    thin = fr.market_orders(day=12, hour=3, money=fr.CAPITAL_RESERVE, hands=9,
                            quadrants=2, animals=0, shed={}, seeds={},
                            empty_plots=0)
    assert not [o for o in thin if o[0] == "BUY_ANIMAL"], thin


def test_animals_waiting_in_the_shed_count_against_the_ramp():
    # An animal is bought into the shed and only becomes a placed animal when a
    # herder walks it out. Counting placed head alone re-buys the whole ramp on
    # every one of the day's 24 turns: measured at 79 sheep in a 100-item shed,
    # which then silently discards every harvest.
    orders = fr.market_orders(day=12, hour=3, money=50_000, hands=9, quadrants=2,
                              animals=2, shed={"SHEEP": 5}, seeds={},
                              empty_plots=0)
    bought = sum(1 for o in orders if o[0] == "BUY_ANIMAL")
    assert bought == fr.animal_target(12) - 2 - 5, orders


def test_livestock_in_the_shed_is_never_offered_to_the_market():
    # SHEEP/COW are not tradable PRODUCTS; a SELL for one is a dead order that
    # burns a slot under the 10-order cap.
    orders = fr.market_orders(day=12, hour=3, money=1_000, hands=9, quadrants=2,
                              animals=2, shed={"SHEEP": 3, "MILK": 2}, seeds={},
                              empty_plots=0)
    assert not [o for o in orders if o[:2] == ["SELL", "SHEEP"]], orders
    assert ["SELL", "MILK", 2] in orders


def test_dawn_hires_are_not_crowded_out_by_the_sell_sweep():
    # The whole crew is hired in the hour-0 turn and the day's wages total under
    # 150, so hires must claim their slots before sells under the 10-order cap.
    # Money carries overnight, so the sweep loses nothing by waiting a turn.
    shed = {"MELON": 5, "STRAWBERRY": 5, "MILK": 5, "WOOL": 5, "EGG": 5}
    orders = fr.market_orders(day=16, hour=0, money=50_000, hands=0, quadrants=3,
                              animals=11, shed=shed, seeds={}, empty_plots=0)
    assert sum(1 for o in orders if o[0] == "HIRE") == fr.hire_target(16), orders


def test_feed_buffer_scales_with_the_herd():
    # Each animal eats one wheat per feeding and escapes at consecutive_unfed
    # >= 2. A fixed four-wheat buffer starves a herd of eleven, which then
    # escapes as fast as it is bought -- measured stuck at 8 of 11 head.
    assert fr.feed_buffer(11) > fr.feed_buffer(3)
    assert fr.feed_buffer(11) >= 11


def test_market_stocks_feed_for_the_whole_herd():
    orders = fr.market_orders(day=20, hour=6, money=50_000, hands=10, quadrants=3,
                              animals=11, shed={}, seeds={}, empty_plots=0)
    buys = [o for o in orders if o[:2] == ["BUY_PRODUCT", "WHEAT"]]
    assert buys and buys[0][2] >= 11, orders


def test_the_whole_feed_buffer_is_held_back_from_the_sell_sweep():
    orders = fr.market_orders(day=20, hour=6, money=5_000, hands=10, quadrants=3,
                              animals=11, shed={"WHEAT": fr.feed_buffer(11)},
                              seeds={}, empty_plots=0)
    assert not [o for o in orders if o[:2] == ["SELL", "WHEAT"]], orders
