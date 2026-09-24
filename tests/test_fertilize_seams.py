# tests/test_fertilize_seams.py
"""The two fertilizer seams on the frozen benchmark (#277): off by default and
byte-identical when off; pickup, the WATER->FERTILIZE intercept and the sweep's
hold-back when on."""

from __future__ import annotations

from strategies import field_rival as fr


def _blank():
    return [[None for _ in range(10)] for _ in range(10)]


def _plant(crop="STRAWBERRY", day=0, watered=False, fert_until=-1, ready=False):
    t = {"kind": "PLANT", "crop": crop, "planted_day": day, "watered_today": watered,
         "fertilized_until_day": fert_until, "yield_units": 0, "consecutive_unwatered": 0,
         "cared_today": False, "harvest_ready": ready, "max_lifespan_step": -1}
    return t


def test_the_constant():
    assert fr.FERT_CARRY == 3


def test_frozen_path_never_picks_up_or_fertilizes_even_with_fertilizer_everywhere():
    tiles = _blank()
    tiles[4][4] = _plant()
    # at the shed, empty-handed, shed stocked: the frozen call has no `shed` and no `fertilize`
    assert fr.crop_worker_action(((4, 4),), tiles, (4, 4), {}, "STRAWBERRY", 12, 3) == ["WATER"]
    # fertilizer in hand, standing on an unfertilized tile: still WATER when the seam is off
    assert fr.crop_worker_action(((4, 4),), tiles, (4, 4), {"FERTILIZER": 3}, "STRAWBERRY", 12, 3,
                                 shed={"FERTILIZER": 10}) == ["WATER"]


def test_pickup_at_the_shed_only_when_active_empty_handed_and_stocked():
    tiles = _blank()
    for x in range(3):
        tiles[0][x] = _plant()          # three lapsed, unwatered strawberry tiles (board is [y][x])
    cluster = ((0, 0), (1, 0), (2, 0))
    on = ("STRAWBERRY", "MELON")
    assert fr.crop_worker_action(cluster, tiles, (4, 4), {}, "STRAWBERRY", 12, 3,
                                 shed={"FERTILIZER": 10}, fertilize=on) == ["PICKUP", "FERTILIZER", 3]
    assert fr.crop_worker_action(cluster, tiles, (4, 4), {}, "STRAWBERRY", 12, 3,
                                 shed={"FERTILIZER": 2}, fertilize=on) == ["PICKUP", "FERTILIZER", 2]
    assert fr.crop_worker_action(cluster, tiles, (4, 4), {}, "STRAWBERRY", 12, 3,
                                 shed={"FERTILIZER": 10}, fertilize=on, fert_carry=1) == ["PICKUP", "FERTILIZER", 1]
    # already holding some: no pickup, go tend
    assert fr.crop_worker_action(cluster, tiles, (4, 4), {"FERTILIZER": 1}, "STRAWBERRY", 12, 3,
                                 shed={"FERTILIZER": 10}, fertilize=on) in (["WEST"], ["NORTH"])
    # shed empty: go tend
    assert fr.crop_worker_action(cluster, tiles, (4, 4), {}, "STRAWBERRY", 12, 3,
                                 shed={}, fertilize=on) in (["WEST"], ["NORTH"])
    # away from the shed: never a trip for fertilizer
    assert fr.crop_worker_action(cluster, tiles, (3, 0), {}, "STRAWBERRY", 12, 3,
                                 shed={"FERTILIZER": 10}, fertilize=on) == ["WEST"]


def test_water_becomes_fertilize_when_the_tile_has_lapsed_and_the_worker_has_some():
    on = ("STRAWBERRY", "MELON")
    tiles = _blank()
    tiles[4][4] = _plant(fert_until=-1)
    inv = {"FERTILIZER": 1}
    assert fr.crop_worker_action(((4, 4),), tiles, (4, 4), inv, "STRAWBERRY", 12, 3,
                                 shed={}, fertilize=on) == ["FERTILIZE"]
    # still fertilized through today: water
    tiles[4][4] = _plant(fert_until=12)
    assert fr.crop_worker_action(((4, 4),), tiles, (4, 4), inv, "STRAWBERRY", 12, 3,
                                 shed={}, fertilize=on) == ["WATER"]
    # lapsed yesterday: fertilize
    tiles[4][4] = _plant(fert_until=11)
    assert fr.crop_worker_action(((4, 4),), tiles, (4, 4), inv, "STRAWBERRY", 12, 3,
                                 shed={}, fertilize=on) == ["FERTILIZE"]
    # crop not in the set: water
    tiles[4][4] = _plant(crop="WHEAT")
    assert fr.crop_worker_action(((4, 4),), tiles, (4, 4), inv, "STRAWBERRY", 12, 3,
                                 shed={}, fertilize=on) == ["WATER"]
    # nothing in hand: water
    tiles[4][4] = _plant()
    assert fr.crop_worker_action(((4, 4),), tiles, (4, 4), {}, "STRAWBERRY", 12, 3,
                                 shed={}, fertilize=on) == ["WATER"]
    # walks toward a lapsed tile it is not standing on
    assert fr.crop_worker_action(((4, 4),), tiles, (4, 6), inv, "STRAWBERRY", 12, 3,
                                 shed={}, fertilize=on) == ["NORTH"]


def test_harvest_is_never_displaced_by_fertilizing(monkeypatch):
    on = ("STRAWBERRY",)
    tiles = _blank()
    tiles[4][4] = _plant()
    monkeypatch.setattr(fr.hh, "harvest_ready", lambda tile, day: True)
    assert fr.crop_worker_action(((4, 4),), tiles, (4, 4), {"FERTILIZER": 2}, "STRAWBERRY", 12, 3,
                                 shed={}, fertilize=on) == ["HARVEST"]


def test_fertilizer_in_hand_is_not_a_load_only_when_the_seam_is_on():
    tiles = _blank()
    tiles[0][0] = _plant(crop="MELON")
    inv = {"MELON": fr.CARRY_LIMIT - 1, "FERTILIZER": 3}
    # seam off: 8 items >= the limit -> head for the shed
    assert fr.crop_worker_action(((0, 0),), tiles, (0, 0), inv, "MELON", 12, 3) in (["EAST"], ["SOUTH"])
    # seam on: 5 produce < the limit -> tend the tile it stands on
    assert fr.crop_worker_action(((0, 0),), tiles, (0, 0), inv, "MELON", 12, 3,
                                 shed={}, fertilize=("MELON",)) == ["FERTILIZE"]


def test_the_sweep_keeps_fert_units_of_fertilizer_and_sells_all_by_default():
    common = dict(day=20, hour=6, money=5_000, hands=10, quadrants=3, animals=0,
                  shed={"FERTILIZER": 30}, seeds={}, empty_plots=0)
    assert ["SELL", "FERTILIZER", 30] in fr.market_orders(**common)
    assert ["SELL", "FERTILIZER", 6] in fr.market_orders(**common, fert=24)
    assert not [o for o in fr.market_orders(**common, fert=40) if o[:2] == ["SELL", "FERTILIZER"]]


def test_the_two_hooks_return_none_on_the_benchmark_and_are_seams():
    s = fr.FieldRivalStrategy()
    assert s.fertilizer_stock() is None and s.fertilize_crops() is None
    from harness.sheep_bench import _seam_names
    names = _seam_names()
    assert {"fertilizer_stock", "fertilize_crops"} <= set(names) and len(names) == 21


def test_a_contender_with_the_seams_on_survives_a_turn():
    cls = type("Fert", (fr.FieldRivalStrategy,), {
        "fertilizer_stock": lambda self, day=None: 5, "fertilize_crops": lambda self, day=None: ("MELON",)})
    from kaggisim.state import parse
    from kaggle_environments import make
    env = make("kaggriculture", configuration={"seed": 1056, "episodeSteps": 3})
    out = cls().act(parse(env.reset()[0].observation))
    assert set(out) >= {"farmer", "hands", "market"}


# --- the hoarding fix (#277 VOID): pickup needs a target, never displaces a chore, and
# --- fertilizer with nowhere to go is returned to the shed

def test_pickup_never_displaces_the_chore_on_the_tile_the_worker_stands_on(monkeypatch):
    tiles = _blank()
    tiles[4][4] = _plant(crop="MELON")
    tiles[0][0] = _plant(crop="MELON")
    monkeypatch.setattr(fr.hh, "harvest_ready", lambda tile, day: True)
    assert fr.crop_worker_action(((4, 4), (0, 0)), tiles, (4, 4), {}, "MELON", 12, 3,
                                 shed={"FERTILIZER": 10}, fertilize=("MELON",)) == ["HARVEST"]


def test_pickup_only_when_a_cluster_tile_can_take_fertilizer_and_only_that_many():
    on = ("STRAWBERRY", "MELON")
    tiles = _blank()
    # an idle worker at the shed with an empty cluster: no pickup, PASS
    assert fr.crop_worker_action((), tiles, (4, 4), {}, "MELON", 12, 3,
                                 shed={"FERTILIZER": 10}, fertilize=on) == ["PASS"]
    # cluster of unplanted tiles and a wheat tile: nothing wants fertilizer -> no pickup
    tiles[0][0] = _plant(crop="WHEAT")
    assert fr.crop_worker_action(((0, 0), (1, 0)), tiles, (4, 4), {}, "MELON", 12, 23,
                                 shed={"FERTILIZER": 10}, fertilize=on)[0] != "PICKUP"
    # two lapsed strawberry tiles, everything else fertilized: pick up exactly two
    tiles[0][0] = _plant(watered=True)
    tiles[0][1] = _plant(watered=True)
    tiles[0][2] = _plant(watered=True, fert_until=14)
    assert fr.crop_worker_action(((0, 0), (1, 0), (2, 0)), tiles, (4, 4), {}, "STRAWBERRY", 12, 3,
                                 shed={"FERTILIZER": 10}, fertilize=on) == ["PICKUP", "FERTILIZER", 2]
    # five lapsed tiles: capped at fert_carry
    for x in range(5):
        tiles[0][x] = _plant(watered=True)
    assert fr.crop_worker_action(tuple((x, 0) for x in range(5)), tiles, (4, 4), {}, "STRAWBERRY", 12, 3,
                                 shed={"FERTILIZER": 10}, fertilize=on) == ["PICKUP", "FERTILIZER", 3]


def test_fertilizer_with_nowhere_to_go_is_returned_to_the_shed():
    on = ("STRAWBERRY",)
    tiles = _blank()
    tiles[0][0] = _plant(watered=True, fert_until=14)   # fertilized and watered: wants nothing
    inv = {"FERTILIZER": 2}
    assert fr.crop_worker_action(((0, 0),), tiles, (4, 4), inv, "STRAWBERRY", 12, 3,
                                 shed={}, fertilize=on) == ["DROP"]
    assert fr.crop_worker_action(((0, 0),), tiles, (2, 4), inv, "STRAWBERRY", 12, 3,
                                 shed={}, fertilize=on) == ["EAST"]
    # but while a tile still wants it, the worker keeps it and goes there
    tiles[0][0] = _plant(watered=True)
    assert fr.crop_worker_action(((0, 0),), tiles, (4, 4), inv, "STRAWBERRY", 12, 3,
                                 shed={}, fertilize=on) in (["WEST"], ["NORTH"])


def test_a_bare_crop_string_is_one_crop_not_its_letters():
    tiles = _blank()
    tiles[4][4] = _plant(crop="MELON")
    assert fr.crop_worker_action(((4, 4),), tiles, (4, 4), {"FERTILIZER": 1}, "MELON", 12, 3,
                                 shed={}, fertilize="MELON") == ["FERTILIZE"]
    tiles[4][4] = _plant(crop="M")
    assert fr.crop_worker_action(((4, 4),), tiles, (4, 4), {"FERTILIZER": 1}, "MELON", 12, 3,
                                 shed={}, fertilize="MELON") == ["WATER"]
