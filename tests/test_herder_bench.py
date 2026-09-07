"""The #239 experiment's declared constants and the pure parts it adds.

The verdict and row formatting are `harness.rival_bench`'s, imported rather
than copied, and the bench's shape is `harness.pasture_bench`'s. What is new
here: #237's VOID replaced the absolute mechanism bars with **deltas against
the champion measured on the same seed**, so the readings below are three
paired differences rather than three absolute thresholds, and the day-16
board readings they are built from.
"""

from __future__ import annotations

import pytest

from harness import herder_bench as hb
from harness import rival_bench as rb


def test_the_declared_constants():
    assert hb.CONTENDER == "third_herder" and hb.CHAMPION == "rival_aware"
    assert hb.REFERENCE == "dense_farm"
    assert hb.EXTERNAL == "lonespear_kaggriculture_v21"
    assert hb.SEEDS == tuple(range(816, 832))
    assert hb.EXTERNAL_SEEDS == (816, 817, 818, 819)
    assert hb.CHAMPION_BAR == 0.60 and hb.ANCHOR_BAR == 0.90
    assert hb.CONTROL_SEED == 816
    assert hb.MECHANISM_DAY == 16
    assert hb.HEAD_DELTA_BAR == 3
    assert hb.SHED_DELTA_BAR == 100
    assert hb.PLANTED_GAP_BAR == 5


def test_the_seeds_are_fresh_against_every_range_already_spent():
    # 100-115, 200-215, 300-331, 400-415, 500-515, 600-615, 700-703 and now
    # 800-815 (#237) are spent; re-using a range re-uses a measurement.
    spent = set(range(100, 116)) | set(range(200, 216)) | set(range(300, 332)) \
        | set(range(400, 416)) | set(range(500, 516)) | set(range(600, 616)) \
        | set(range(700, 704)) | set(range(800, 816))
    assert not spent & set(hb.SEEDS)


def test_the_verdict_logic_is_rival_benchs_not_a_copy():
    assert hb.criterion is rb.criterion
    assert hb.format_rows is rb.format_rows


def test_arm_b_carries_the_two_thirty_sevens_raised_ramp_verbatim():
    from strategies import field_rival as fr
    assert hb.RAISED_RAMP == ((0, 3), (4, 5), (8, 8), (12, 10), (16, 11), (24, 11))
    # It only ever raises the frozen ramp -- an arm that bought FEWER head
    # would be a different change, not "the same farm with a bigger herd".
    for day in range(fr.SEASON_DAYS):
        assert hb.raised_target(day) >= fr.animal_target(day), day
    assert hb.raised_target(0) == 3 and hb.raised_target(12) == 10


def test_the_three_arms_are_named_and_only_arm_a_is_registered():
    from strategies import REGISTRY
    assert hb.CONTENDER in REGISTRY
    assert hb.ARM_C == "pasture_ahead" and hb.ARM_C in REGISTRY
    # Arm B is built in-process: an unregistered arm cannot be promoted or
    # packaged by accident.
    assert hb.ARM_B not in REGISTRY


# --- the day-16 board reading -------------------------------------------------

def _turns(pasture, held, placed, planted):
    """`[(day, census)]`, one entry per turn, a day every 24 turns."""
    return [(i // 24, {"head_held": h, "head_placed": pl, "planted_tiles": pt,
                       "structures": {"PASTURE": {"total": p, "free": 0},
                                      "COOP": {"total": 0, "free": 0}}})
            for i, (p, h, pl, pt) in enumerate(zip(pasture, held, placed, planted))]


def _game(days=18, pasture=8, held=0, placed=5, planted=20):
    n = 24 * days
    return _turns([pasture] * n, [held] * n, [placed] * n, [planted] * n)


def test_the_reading_should_take_the_last_census_of_the_declared_day():
    # The day's closing board, not its opening one: a tile built at hour 20
    # counts on the day it was built.
    turns = _game(days=18)
    turns[16 * 24 + 23] = (16, dict(turns[16 * 24 + 23][1], head_placed=9))
    assert hb.mechanism_reading(turns)["head_placed_at_day"] == 9


def test_the_reading_should_carry_both_board_numbers_and_the_shed_wait():
    turns = _game(days=18, held=1, placed=7, planted=22)
    r = hb.mechanism_reading(turns)
    assert r["head_placed_at_day"] == 7
    assert r["planted_tiles_at_day"] == 22
    assert r["turns_with_head_in_shed"] == 18 * 24
    assert r["turns"] == 18 * 24
    assert r["max_pasture"] == 8 and r["max_head_placed"] == 7


def test_the_reading_should_refuse_a_game_that_never_reached_the_day():
    # "The game stopped at day 12" must not be silently read as a day-16
    # board of zeroes -- that would look like a mechanism that did not fire.
    with pytest.raises(ValueError):
        hb.mechanism_reading(_game(days=12))


# --- the declared deltas ------------------------------------------------------

def _reading(head, shed, planted):
    return {"head_placed_at_day": head, "turns_with_head_in_shed": shed,
            "planted_tiles_at_day": planted, "turns": 719,
            "max_pasture": 8, "max_head_placed": head}


def test_the_deltas_are_signed_in_the_declared_direction():
    # More head is positive, FEWER shed turns is positive, and the crop gap is
    # unsigned -- a crop line that ran away from the champion's is as much a
    # confound as one that collapsed.
    d = hb.mechanism_deltas(_reading(11, 300, 24), _reading(8, 449, 30))
    assert d["head_delta"] == 3
    assert d["shed_delta"] == 149
    assert d["planted_gap"] == 6


def test_mechanism_ok_should_pass_exactly_at_the_declared_bars():
    assert hb.mechanism_ok(hb.mechanism_deltas(_reading(11, 349, 30),
                                               _reading(8, 449, 30)))


def test_mechanism_ok_should_fail_when_too_little_head_reached_the_pasture():
    assert not hb.mechanism_ok(hb.mechanism_deltas(_reading(10, 349, 30),
                                                   _reading(8, 449, 30)))


def test_mechanism_ok_should_fail_when_the_shed_wait_barely_moved():
    assert not hb.mechanism_ok(hb.mechanism_deltas(_reading(11, 350, 30),
                                                   _reading(8, 449, 30)))


def test_crop_line_ok_should_fail_when_the_crop_line_moved_too_far():
    # Control (iii): a herder taken off the crops is the cost, and it must
    # stay visible rather than becoming a second change.
    assert hb.crop_line_ok(hb.mechanism_deltas(_reading(11, 349, 25),
                                               _reading(8, 449, 30)))
    assert not hb.crop_line_ok(hb.mechanism_deltas(_reading(11, 349, 24),
                                                   _reading(8, 449, 30)))


def test_format_mechanism_should_print_both_sides_and_all_six_numbers():
    text = hb.format_mechanism([(hb.CONTENDER, _reading(11, 300, 24)),
                                (hb.CHAMPION, _reading(8, 449, 30))])
    lines = text.splitlines()
    assert len(lines) == 3
    assert "11" in lines[1] and "300/719" in lines[1] and "24" in lines[1]
    assert "8" in lines[2] and "449/719" in lines[2] and "30" in lines[2]


def test_format_pairings_should_name_both_sides_of_every_recorded_row():
    # Arms B and C both play `rival_aware`, so a table keyed on the opponent
    # alone would print the same label twice and hide which row is which.
    rows = [{"name": hb.ARM_B, "opponent": hb.CHAMPION, "wins": 2, "ties": 0,
             "games": 16, "seeds": "816-831"},
            {"name": hb.ARM_C, "opponent": hb.CHAMPION, "wins": 9, "ties": 1,
             "games": 16, "seeds": "816-831"}]
    text = hb.format_pairings(rows)
    lines = text.splitlines()
    assert len(lines) == 3
    assert hb.ARM_B in lines[1] and "12.5%" in lines[1]
    assert hb.ARM_C in lines[2] and "56.2%" in lines[2]
