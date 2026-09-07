"""The #237 experiment's declared constants and the pure parts it adds.

The counting and verdict logic is `harness.rival_bench`'s, imported rather
than copied. What is new here: the placebo ramp, the mechanism-fired reading
built on `harness.farm_census.aggregate`, and the split-row merge that lets
the contender's first four seeds be read out of the criterion run instead of
being played a second time.
"""

from __future__ import annotations

from harness import pasture_bench as pb
from harness import rival_bench as rb


def test_the_declared_constants():
    assert pb.CONTENDER == "pasture_ahead" and pb.CHAMPION == "rival_aware"
    assert pb.REFERENCE == "dense_farm"
    assert pb.EXTERNAL == "lonespear_kaggriculture_v21"
    assert pb.SEEDS == tuple(range(800, 816))
    assert pb.CHAMPION_BAR == 0.60 and pb.ANCHOR_BAR == 0.90
    assert pb.CONTROL_SEED == 800
    assert pb.PLACEBO_SEEDS == (800, 801, 802, 803)
    assert pb.PASTURE_TILES_FIRED == 5 and pb.PASTURE_DAY_BAR == 2
    assert pb.SHED_TURNS_BAR == 120


def test_the_seeds_are_fresh_against_every_range_already_spent():
    # 100-115, 200-215, 300-331, 400-415, 500-515 (#202/#211/#219/#222), 600-615
    # (#225) and 700-703 (#229/#234) are spent; re-using a range re-uses a
    # measurement.
    spent = set(range(100, 116)) | set(range(200, 216)) | set(range(300, 332)) \
        | set(range(400, 416)) | set(range(500, 516)) | set(range(600, 616)) \
        | set(range(700, 704))
    assert not spent & set(pb.SEEDS)


def test_the_verdict_logic_is_rival_benchs_not_a_copy():
    assert pb.criterion is rb.criterion
    assert pb.format_rows is rb.format_rows
    assert pb.first_day_at_or_above is rb.first_day_at_or_above


def test_the_placebo_ramp_is_the_declared_one_three_head_earlier_at_each_step():
    from strategies import field_rival as fr
    assert pb.PLACEBO_RAMP == ((0, 3), (4, 5), (8, 8), (12, 10), (16, 11), (24, 11))
    # It only ever raises the frozen ramp -- a placebo that bought FEWER head
    # would be a different change, not "the same farm with a bigger herd".
    for day in range(fr.SEASON_DAYS):
        assert pb.placebo_target(day) >= fr.animal_target(day), day
    assert pb.placebo_target(0) == 3 and pb.placebo_target(12) == 10


# --- the mechanism-fired reading ---------------------------------------------

def _turns(pasture_by_turn, held_by_turn):
    """`[(day, census)]` with one turn per entry, a day every 24 turns."""
    return [(i // 24, {"head_held": h, "head_placed": 0,
                       "structures": {"PASTURE": {"total": p, "free": 0},
                                      "COOP": {"total": 0, "free": 0}}})
            for i, (p, h) in enumerate(zip(pasture_by_turn, held_by_turn))]


def test_mechanism_reading_should_report_the_first_day_pasture_reached_the_bar():
    turns = _turns([1] * 24 + [5] * 24, [0] * 48)
    assert pb.mechanism_reading(turns)["first_day_pasture"] == 1


def test_mechanism_reading_should_report_no_day_when_the_bar_is_never_reached():
    # `None` is the honest reading for "never built five tiles" -- it must not
    # collapse to a day number that would read as firing.
    turns = _turns([4] * 48, [0] * 48)
    assert pb.mechanism_reading(turns)["first_day_pasture"] is None


def test_mechanism_reading_should_count_the_turns_head_waited_in_the_shed():
    turns = _turns([5] * 10, [0, 1, 2, 0, 3, 1, 0, 0, 0, 0])
    r = pb.mechanism_reading(turns)
    assert r["turns_with_head_in_shed"] == 4 and r["turns"] == 10


def test_mechanism_ok_should_pass_when_both_declared_limbs_are_met():
    assert pb.mechanism_ok({"first_day_pasture": 2, "turns_with_head_in_shed": 119})
    assert pb.mechanism_ok({"first_day_pasture": 0, "turns_with_head_in_shed": 0})


def test_mechanism_ok_should_fail_when_the_fifth_pasture_arrives_too_late():
    assert not pb.mechanism_ok({"first_day_pasture": 3, "turns_with_head_in_shed": 0})
    assert not pb.mechanism_ok({"first_day_pasture": None, "turns_with_head_in_shed": 0})


def test_mechanism_ok_should_fail_when_head_still_waits_in_the_shed():
    assert not pb.mechanism_ok({"first_day_pasture": 0, "turns_with_head_in_shed": 120})


# --- the split-row merge ------------------------------------------------------

def _row(wins, ties, games, seeds="800-803"):
    return {"name": "pasture_ahead", "opponent": "rival_aware", "wins": wins,
            "ties": ties, "games": games, "seeds": seeds}


def test_merge_rows_should_add_the_two_halves_into_one_sixteen_seed_row():
    # The criterion row is played in two halves so the first four seeds can be
    # read beside the placebo without playing those four games twice. The split
    # is at an EVEN index, so `head_to_head_rate`'s alternate-by-list-position
    # gives each seed the same seat it would have had in the whole list.
    merged = pb.merge_rows(_row(3, 0, 4, "800-803"), _row(9, 1, 12, "804-815"))
    assert merged["wins"] == 12 and merged["ties"] == 1 and merged["games"] == 16
    assert merged["seeds"] == "800-815"
    assert merged["opponent"] == "rival_aware"


def test_merge_rows_should_refuse_halves_that_are_not_the_same_pairing():
    # Two different opponents summed into one row would be a silently wrong
    # win-rate, so it is an error rather than an addition.
    try:
        pb.merge_rows(_row(1, 0, 4), dict(_row(1, 0, 4), opponent="dense_farm"))
    except ValueError:
        return
    raise AssertionError("merging rows from different pairings should raise")


def test_the_split_halves_cover_the_declared_seeds_exactly_once():
    assert pb.SEEDS[:4] + pb.SEEDS[4:] == pb.SEEDS
    assert len(pb.SEEDS[:4]) % 2 == 0, "an odd split would swap every later seat"


def test_format_mechanism_should_print_both_sides_and_read_never_as_never():
    # A side that never built five tiles must not print a day number, and both
    # sides appear so the champion's own numbers are read beside the contender's.
    text = pb.format_mechanism([
        ("pasture_ahead", {"first_day_pasture": 1, "turns_with_head_in_shed": 40,
                           "turns": 719, "max_pasture": 12, "max_head_placed": 11}),
        ("rival_aware", {"first_day_pasture": None, "turns_with_head_in_shed": 482,
                         "turns": 719, "max_pasture": 8, "max_head_placed": 8}),
    ])
    lines = text.splitlines()
    assert len(lines) == 3
    assert "pasture_ahead" in lines[1] and "40/719" in lines[1]
    assert "never" in lines[2] and "482/719" in lines[2]
