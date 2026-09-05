"""Unit tests for the split-brain experiment (issue #196, ADR-0007).

#187 tried to bolt a herd onto the champion and the farm collapsed at every
setting. Its root cause was structural: one crew, one job queue, ties broken by
tile coordinate, so the herd got **13 FEED actions a season** against the field's
153, and above labour parity the crop line collapsed outright.

#193 then got the herd by *shrinking the crop line to a third* — 20 planted
tiles against the champion's 62 — and beat the champion 69%. But our crop line is
the strongest thing in the replay data (55,958 median revenue against the winning
field's 28,361, #157), and that version throws it away.

Nothing has yet run **both at full size**. This does it by giving the ranch its
own workers, so the crop brain can never starve it by wanting to water tile
(0,0) instead.

The two tile sets do not overlap: `crop_plots` returns 62 tiles and
`ANIMAL_TILES` 13, with an empty intersection, so a dedicated ranch crew cannot
collide with the crop brain's assignments.
"""

from __future__ import annotations

from strategies import neuropilot as npx
from strategies import splitbrain as sb


def _knobs(**over):
    base = dict(sell_throttle=0.5, hire_target=0.3, livestock_pace=0.5,
                livestock_labor_share=0.1063, herd_target_scale=0.0098,
                fertilize_pref=0.5, capital_reserve=0.5, crop_mix=0.5)
    base.update(over)
    return npx.Knobs(**base)


# --- the premise this experiment rests on ---

def test_crop_land_and_animal_land_do_not_overlap():
    # If they did, a dedicated ranch crew would fight the crop brain for tiles
    # and the split would solve nothing.
    crop = set(npx.crop_plots(["NW", "NE", "SW"]))
    animal = {pos for pos, _ in npx.ANIMAL_TILES}
    assert crop and animal
    assert not (crop & animal)


# --- the crew split ---

def test_the_ranch_takes_the_tail_of_the_crew():
    # Tail, not head: worker 0 is the farmer, who starts shed-adjacent and is
    # the crop brain's most valuable unit.
    idx = sb.ranch_indices(10)
    assert idx == (7, 8, 9)
    assert len(idx) == sb.RANCH_WORKERS


def test_no_worker_is_diverted_before_the_crew_can_spare_one():
    # Early game the farm is 1-2 workers; peeling one for a herd we cannot yet
    # afford would cost crop tiles for nothing.
    assert sb.ranch_indices(1) == ()
    assert sb.ranch_indices(sb.MIN_CREW_BEFORE_SPLIT - 1) == ()
    assert sb.ranch_indices(sb.MIN_CREW_BEFORE_SPLIT) != ()


def test_the_crop_brain_keeps_the_majority_of_a_full_crew():
    # The hypothesis is "both businesses at full size", so the crop line must
    # keep enough hands to hold >= 45 planted tiles.
    crop = 10 - len(sb.ranch_indices(10))
    assert crop >= 7


# --- the knobs the champion left switched off ---

def test_the_crew_is_hired_to_full_strength():
    # The field runs a bigger crew than we do (11 workers against our 8). The
    # champion's evolved hire_target does not reach MAX_HANDS.
    assert sb.floor_knobs(_knobs(hire_target=0.3)).hire_target == 1.0


def test_the_herd_target_is_raised_off_zero():
    # The champion's genome sets herd_target_scale to a median 0.0098, which
    # _herd_targets rounds to zero animals for the whole game (#187).
    assert npx._herd_targets(_knobs()) == (0, 0)
    floored = sb.floor_knobs(_knobs())
    assert sum(npx._herd_targets(floored)) >= 8


def test_floors_never_lower_a_knob_the_network_pushed_higher():
    high = _knobs(hire_target=1.0, herd_target_scale=1.0)
    assert sb.floor_knobs(high) is high


def test_only_crew_and_herd_knobs_are_touched():
    # Crucially livestock_labor_share is NOT floored: #187 showed raising it
    # makes the shared job queue hand crop tiles to the herd and collapses the
    # crop line. The split removes the need to touch it at all.
    before, after = _knobs(), sb.floor_knobs(_knobs())
    for field in npx.Knobs._fields:
        if field in ("hire_target", "herd_target_scale"):
            continue
        assert getattr(after, field) == getattr(before, field), field


def test_the_labour_knob_is_deliberately_left_alone():
    assert sb.floor_knobs(_knobs()).livestock_labor_share == 0.1063


# --- feed, the supply the champion never buys ---

def test_feed_is_bought_for_a_placed_herd():
    # neuropilot's only BUY_PRODUCT is FERTILIZER; it never buys wheat, so the
    # herd starves at consecutive_unfed >= 2 unless crop_mix happens to pick
    # wheat (#187).
    orders = sb.feed_orders(animals=9, shed={}, money=9_000, price=25, room=4)
    assert orders and orders[0][:2] == ["BUY_PRODUCT", "WHEAT"]
    assert orders[0][2] >= 9


def test_no_feed_without_a_herd():
    assert sb.feed_orders(animals=0, shed={}, money=9_000, price=25, room=4) == []


def test_no_feed_when_the_shed_is_stocked():
    assert sb.feed_orders(animals=4, shed={"WHEAT": 99}, money=9_000,
                          price=25, room=4) == []


def test_feed_never_claims_a_slot_the_controller_needed():
    assert sb.feed_orders(animals=9, shed={}, money=9_000, price=25, room=0) == []


def test_feed_order_survives_the_simulators_parser():
    from kaggle_environments.envs.kaggriculture import kaggriculture as sim
    for order in sb.feed_orders(animals=9, shed={}, money=9_000, price=25, room=4):
        assert sim._parse_order(order) is not None, order


def test_it_is_a_contender():
    assert sb.STRATEGY.benchmark is False
    assert sb.STRATEGY.name == "splitbrain"


# --- a ranch worker must move on once its tile is tended ---

def test_a_tended_tile_releases_the_worker_to_its_next_one():
    # `_animal_job_action` never returns None -- it always produces some action,
    # including a walk -- so testing it for "does this tile want work" pins the
    # worker to its first tile forever. Measured: exactly 3 BUILD_PASTURE and 3
    # animals all season, one per ranch worker, while 6 cows and 2 sheep sat in
    # the shed. `_animal_chore` is the one that returns None when a tile is
    # fully tended, so that is the right question to ask.
    tiles = [[None] * 10 for _ in range(10)]
    first, second = npx.ANIMAL_TILES[0][0], npx.ANIMAL_TILES[1][0]
    # First tile: a placed animal, fed, cared, nothing left to collect.
    tiles[first[1]][first[0]] = {"kind": "PASTURE", "animal": "COW",
                                 "yield_units": 0, "fed_today": True,
                                 "cared_today": True, "fertilizer_available": False}
    # Second tile: bare ground that still wants a pasture built.
    assert sb.wants_work(first, "COW", tiles, {}, {}, ["NW", "NE", "SW"]) is False
    assert sb.wants_work(second, "COW", tiles, {}, {}, ["NW", "NE", "SW"]) is True


def test_a_tile_on_unbought_land_wants_nothing():
    tiles = [[None] * 10 for _ in range(10)]
    pos = npx.ANIMAL_TILES[0][0]
    assert sb.wants_work(pos, "COW", tiles, {}, {}, ["NW"]) is False


# --- feed logistics: one wheat per round trip is the binding constraint ---

def test_a_ranch_worker_at_the_shed_loads_wheat_in_bulk():
    # `_animal_job_action` fetches ONE wheat per trip, and the animal tiles are
    # 4-5 tiles from the shed, so each feeding costs a ~10-turn round trip.
    # Measured: 1,127 walking actions against 14 FEED across a season, for a
    # herd needing roughly 5.5 feeds a day.
    load = sb.shed_pickup(pos=npx.SHED_TILE, inv={}, shed={"WHEAT": 50}, animals=11)
    assert load is not None
    assert load[:2] == ["PICKUP", "WHEAT"]
    assert load[2] >= 4


def test_no_bulk_load_away_from_the_shed():
    assert sb.shed_pickup(pos=(0, 0), inv={}, shed={"WHEAT": 50}, animals=11) is None


def test_no_bulk_load_when_already_carrying_enough():
    assert sb.shed_pickup(pos=npx.SHED_TILE, inv={"WHEAT": 99},
                          shed={"WHEAT": 50}, animals=11) is None


def test_no_bulk_load_when_the_shed_is_empty():
    assert sb.shed_pickup(pos=npx.SHED_TILE, inv={}, shed={}, animals=11) is None


def test_no_bulk_load_without_a_herd_to_feed():
    assert sb.shed_pickup(pos=npx.SHED_TILE, inv={}, shed={"WHEAT": 50}, animals=0) is None


# --- establish the herd before farming it ---

def _tile(**kw):
    t = {"kind": "PASTURE", "yield_units": 0, "fed_today": True,
         "cared_today": True, "fertilizer_available": False}
    t.update(kw)
    return t


def test_setting_up_a_pasture_outranks_collecting_a_byproduct():
    # COLLECT_FERTILIZER regenerates daily, so a tile holding a placed animal is
    # never "done" and a first-match scan pins the worker there forever. Measured:
    # 3 animals placed all season while 6 cows and 2 sheep sat in the shed, the
    # crew harvesting fertilizer off the three it had.
    tiles = [[None] * 10 for _ in range(10)]
    established, empty = npx.ANIMAL_TILES[0][0], npx.ANIMAL_TILES[1][0]
    tiles[established[1]][established[0]] = _tile(animal="COW", fertilizer_available=True)
    order = sb.tile_priority(
        [npx.ANIMAL_TILES[0], npx.ANIMAL_TILES[1]], tiles, {}, {"COW": 5},
        ["NW", "NE", "SW"])
    assert order and order[0][0] == empty, order


def test_a_hungry_animal_still_comes_first():
    # An animal escapes at consecutive_unfed >= 2 -- losing its whole 400-500
    # purchase -- so feeding outranks even standing up a new pasture.
    tiles = [[None] * 10 for _ in range(10)]
    hungry, empty = npx.ANIMAL_TILES[0][0], npx.ANIMAL_TILES[1][0]
    tiles[hungry[1]][hungry[0]] = _tile(animal="COW", fed_today=False)
    order = sb.tile_priority(
        [npx.ANIMAL_TILES[0], npx.ANIMAL_TILES[1]], tiles, {"WHEAT": 3},
        {"COW": 5}, ["NW", "NE", "SW"])
    assert order[0][0] == hungry, order


def test_tiles_wanting_nothing_are_dropped_entirely():
    tiles = [[None] * 10 for _ in range(10)]
    done = npx.ANIMAL_TILES[0][0]
    tiles[done[1]][done[0]] = _tile(animal="COW")
    order = sb.tile_priority([npx.ANIMAL_TILES[0]], tiles, {}, {}, ["NW", "NE", "SW"])
    assert order == []


def test_loading_feed_never_preempts_carrying_an_animal_out():
    # Both happen at the shed tile. Grabbing wheat first means the worker walks
    # away without the cow, every single visit -- the herd can never grow past
    # what was placed before the first feed run. Self-inflicted while fixing the
    # feed round trip; caught by re-measuring rather than by the earlier tests,
    # which only ever asked about wheat.
    assert sb.shed_pickup(npx.SHED_TILE, {}, {"WHEAT": 6, "COW": 6}, animals=3) is None
    # With no livestock waiting, loading feed is exactly right.
    assert sb.shed_pickup(npx.SHED_TILE, {}, {"WHEAT": 6}, animals=3) is not None
