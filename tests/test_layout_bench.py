"""The NW-pasture experiment's declared constants and the pure parts it adds.

The verdict, formatting and paired external rows are `harness.rival_bench`'s,
the census readings `harness.farm_census`'s and the day readings
`harness.front_bench`'s -- imported, not copied. New here: the mechanism is
read on head PLACED at day 9 (the number #244's control should have been on,
now that the block is inside NW and nothing land-caps it), and the first day
with eight pasture tiles standing is recorded beside it.
"""

from __future__ import annotations

import pytest

from harness import front_bench as fb
from harness import layout_bench as lb
from harness import rival_bench as rb


def test_the_declared_constants():
    assert lb.CONTENDER == "nw_pasture" and lb.CHAMPION == "third_herder"
    assert lb.SEEDS == tuple(range(880, 896))
    assert lb.CONTROL_SEED == 880
    assert lb.CHAMPION_BAR == 0.60 and lb.ANCHOR_BAR == 0.90
    assert lb.PLACED_DAY == 9 and lb.CROP_DAY == 16
    assert lb.EARLY_CROP_DAY == 8
    assert lb.PLACED_DELTA_BAR == 4
    assert lb.PLANTED_GAP_BAR == 5
    assert lb.PASTURE_STANDING == 8
    assert lb.ARM_B == "early_land"
    assert lb.LAND_RAMP_B == ((0, 1), (6, 2), (16, 3))


def test_the_seeds_are_fresh_against_every_range_already_spent():
    spent = set(range(100, 116)) | set(range(200, 216)) | set(range(300, 332)) \
        | set(range(400, 416)) | set(range(500, 516)) | set(range(600, 616)) \
        | set(range(700, 704)) | set(range(800, 880))
    assert not spent & set(lb.SEEDS)


def test_the_verdict_logic_is_rival_benchs_and_the_readers_are_front_benchs():
    assert lb.criterion is rb.criterion
    assert lb.format_rows is rb.format_rows
    assert lb.format_external is rb.format_external
    assert lb.paired_external_rows is rb.paired_external_rows
    assert lb.mechanism_deltas is fb.mechanism_deltas


def _census(head_placed, head_held, planted, pasture):
    return {"head_placed": head_placed, "head_held": head_held, "planted_tiles": planted,
            "structures": {"PASTURE": {"total": pasture, "occupied": 0, "empty": pasture}}}


def _turns():
    # Two turns a day for days 0..16: eight pasture stand from day 3, head is
    # placed on it from day 5, nothing waits in the shed after day 6. Day 8
    # plants 11 then 13 (closing board 13); every other day before 16 plants
    # 20 -- so the day-8 reading can only be right if it takes day 8's
    # closing board, not any other day's.
    turns = []
    for day in range(17):
        pasture = 5 if day < 3 else 8
        placed = 0 if day < 5 else 8
        held = 2 if day in (5, 6) else 0
        if day == 8:
            first, second = 11, 13
        elif day < 16:
            first, second = 20, 20
        else:
            first, second = 30, 30
        turns.append((day, _census(placed, held, first, pasture)))
        turns.append((day, _census(placed, held, second, pasture)))
    return turns


def test_reading_takes_the_closing_board_and_the_first_day_the_block_stood():
    r = lb.mechanism_reading(_turns())
    assert r["head_placed_at_day"] == 8 and r["head_held_at_day"] == 0
    assert r["head_owned_at_day"] == 8
    assert r["planted_tiles_at_crop_day"] == 30
    assert r["planted_tiles_at_early_day"] == 13
    assert r["turns_with_head_in_shed"] == 4     # days 5, 6 x 2 turns
    assert r["first_day_pasture_standing"] == 3


def test_reading_reports_none_when_the_block_never_stood():
    turns = [(d, _census(0, 0, 13, 5)) for d in range(17)]
    assert lb.mechanism_reading(turns)["first_day_pasture_standing"] is None


def test_reading_raises_when_the_game_never_reached_a_declared_day():
    with pytest.raises(ValueError, match="day 16"):
        lb.mechanism_reading(_turns()[:20])


def test_mechanism_gates_on_placed_head_and_the_crop_line_on_the_gap():
    c = {"head_owned_at_day": 10, "head_placed_at_day": 8, "planted_tiles_at_crop_day": 30,
         "turns_with_head_in_shed": 90}
    k = {"head_owned_at_day": 4, "head_placed_at_day": 4, "planted_tiles_at_crop_day": 30,
         "turns_with_head_in_shed": 212}
    d = lb.mechanism_deltas(c, k)
    assert d == {"owned_delta": 6, "placed_delta": 4, "shed_delta": 122, "planted_gap": 0}
    assert lb.mechanism_ok(d) is True and lb.crop_line_ok(d) is True
    assert lb.mechanism_ok(dict(d, placed_delta=3)) is False
    # Owned head no longer gates: #244's control passed on it and the arm lost.
    assert lb.mechanism_ok(dict(d, placed_delta=4, owned_delta=0)) is True
    assert lb.crop_line_ok(dict(d, planted_gap=6)) is False


def test_arm_b_buys_ne_on_day_six_and_is_not_registered():
    from strategies import REGISTRY, field_rival as fr
    from strategies.nw_pasture import NwPastureStrategy
    cls = lb.arm_b_class()
    assert issubclass(cls, NwPastureStrategy)
    arm = cls()
    assert arm.land_target(5) == 1 and arm.land_target(6) == 2 and arm.land_target(16) == 3
    assert arm.land_target(11) == 2 and fr.land_target(11) == 1     # the frozen ramp waits for 12
    assert arm.layout() == NwPastureStrategy().layout()              # the block rides along
    assert lb.ARM_B not in REGISTRY and lb.CONTENDER in REGISTRY


def test_format_mechanism_prints_both_sides_with_the_first_day_column():
    r = {"head_owned_at_day": 10, "head_placed_at_day": 8, "head_held_at_day": 2,
         "planted_tiles_at_crop_day": 30, "planted_tiles_at_early_day": 13,
         "turns_with_head_in_shed": 90, "turns": 719,
         "max_head_placed": 12, "first_day_pasture_standing": 3}
    text = lb.format_mechanism([("nw_pasture", r), ("third_herder", dict(r, first_day_pasture_standing=None))])
    lines = text.splitlines()
    assert len(lines) == 3 and lines[1].startswith("nw_pasture") and "90/719" in lines[1]
    assert "planted @8" in lines[0]
    assert lines[2].rstrip().endswith("never")
