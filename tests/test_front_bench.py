"""The pasture-first experiment's declared constants and the pure parts it adds.

The verdict and formatting are `harness.rival_bench`'s (now with #152's paired
external limb), the census readings `harness.farm_census`'s and the bench's
shape `harness.herder_bench`'s -- imported, not copied. New here: the
mechanism is read on head OWNED (placed + held) at day 9, because under the
frozen layout pasture is land-capped at five tiles until the NE quadrant on
day 12, so the arm's fired-or-not signal is the herd bought, not the herd
standing (measured on spent seed 816 before this was declared).
"""

from __future__ import annotations

import pytest

from harness import front_bench as fb
from harness import rival_bench as rb


def test_the_declared_constants():
    assert fb.CONTENDER == "pasture_first" and fb.CHAMPION == "third_herder"
    assert fb.SEEDS == tuple(range(864, 880))
    assert fb.CONTROL_SEED == 864
    assert fb.CHAMPION_BAR == 0.60 and fb.ANCHOR_BAR == 0.90
    assert fb.OWNED_DAY == 9 and fb.CROP_DAY == 16
    assert fb.OWNED_DELTA_BAR == 4
    assert fb.PLANTED_GAP_BAR == 5
    assert fb.ARM_B == "front_ramp"


def test_the_seeds_are_fresh_against_every_range_already_spent():
    spent = set(range(100, 116)) | set(range(200, 216)) | set(range(300, 332)) \
        | set(range(400, 416)) | set(range(500, 516)) | set(range(600, 616)) \
        | set(range(700, 704)) | set(range(800, 864))
    assert not spent & set(fb.SEEDS)


def test_the_verdict_logic_is_rival_benchs_not_a_copy():
    assert fb.criterion is rb.criterion
    assert fb.format_rows is rb.format_rows
    assert fb.format_external is rb.format_external
    assert fb.paired_external_rows is rb.paired_external_rows


def _census(head_placed, head_held, planted, pasture):
    return {"head_placed": head_placed, "head_held": head_held, "planted_tiles": planted,
            "structures": {"PASTURE": {"total": pasture, "occupied": 0, "empty": pasture}}}


def _turns():
    # Two turns a day for days 0..16: head arrives on day 9, is placed by day 12.
    turns = []
    for day in range(17):
        placed = 0 if day < 9 else (5 if day < 12 else 8)
        held = 0 if day < 9 else (7 if day < 12 else 0)
        turns.append((day, _census(placed, held, 20, 5)))
        turns.append((day, _census(placed, held, 20 if day < 16 else 30, 5)))
    return turns


def test_reading_takes_the_closing_board_of_each_declared_day():
    r = fb.mechanism_reading(_turns())
    assert r["head_owned_at_day"] == 12          # 5 placed + 7 held on day 9
    assert r["head_placed_at_day"] == 5 and r["head_held_at_day"] == 7
    assert r["planted_tiles_at_crop_day"] == 30  # the day's closing board
    assert r["turns_with_head_in_shed"] == 6     # days 9, 10, 11 x 2 turns
    assert r["max_head_placed"] == 8


def test_reading_raises_when_the_game_never_reached_a_declared_day():
    with pytest.raises(ValueError, match="day 16"):
        fb.mechanism_reading(_turns()[:20])


def test_deltas_are_signed_so_bigger_is_better_except_the_crop_gap():
    c = {"head_owned_at_day": 12, "head_placed_at_day": 5, "planted_tiles_at_crop_day": 30,
         "turns_with_head_in_shed": 561}
    k = {"head_owned_at_day": 4, "head_placed_at_day": 4, "planted_tiles_at_crop_day": 28,
         "turns_with_head_in_shed": 218}
    d = fb.mechanism_deltas(c, k)
    assert d == {"owned_delta": 8, "placed_delta": 1, "shed_delta": -343, "planted_gap": 2}
    assert fb.mechanism_ok(d) is True and fb.crop_line_ok(d) is True
    assert fb.mechanism_ok(dict(d, owned_delta=3)) is False
    assert fb.crop_line_ok(dict(d, planted_gap=6)) is False


def test_arm_b_is_the_front_ramp_on_two_herders_and_is_not_registered():
    from strategies import REGISTRY, field_rival as fr
    from strategies.pasture_ahead import PastureAheadStrategy
    from strategies.pasture_first import FRONT_RAMP
    cls = fb.arm_b_class()
    assert issubclass(cls, PastureAheadStrategy)
    arm = cls()
    assert arm.livestock_workers(8) is None           # the benchmark's pair, no third herder
    for day in range(fr.SEASON_DAYS):
        assert arm.herd_target(day) == max(fr._ramp(FRONT_RAMP, day), fr.animal_target(day)), day
    assert arm.pasture_count(0, 0) == 4 and arm.pasture_count(6, 0) == 12
    assert fb.ARM_B not in REGISTRY and fb.CONTENDER in REGISTRY


def test_format_mechanism_prints_both_sides():
    r = {"head_owned_at_day": 12, "head_placed_at_day": 5, "head_held_at_day": 7,
         "planted_tiles_at_crop_day": 30, "turns_with_head_in_shed": 561, "turns": 719,
         "max_head_placed": 11}
    text = fb.format_mechanism([("pasture_first", r), ("third_herder", r)])
    lines = text.splitlines()
    assert len(lines) == 3 and lines[1].startswith("pasture_first") and "561/719" in lines[1]
