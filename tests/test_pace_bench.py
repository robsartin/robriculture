"""The field_pace experiment's declared constants and the pure parts it adds.

The verdict, formatting and paired external rows are `harness.rival_bench`'s and
the census `harness.farm_census`'s -- imported, not copied. New here: an
ABSOLUTE shape control read off the contender's own census (the field's
medians less a margin), because a package that does not reproduce the shape it
was copied from has not tested the hypothesis, and a payday reading.
"""

from __future__ import annotations

import pytest

from harness import pace_bench as pb
from harness import rival_bench as rb


def test_the_declared_constants():
    """Every value posted to #252 before any code, read straight off the module."""
    assert pb.CONTENDER == "field_pace" and pb.CHAMPION == "third_herder"
    assert pb.SEEDS == tuple(range(896, 912)) and pb.CONTROL_SEED == 896
    assert pb.CHAMPION_BAR == 0.60 and pb.ANCHOR_BAR == 0.90
    assert pb.ARM_B == "crop_pace"
    assert pb.SHAPE_DAY == 8 and pb.CROP_DAY == 12
    assert pb.SHAPE_BARS == {"planted": 30, "quadrants": 2, "hands": 8, "head_placed": 8}
    assert pb.PLANTED_AT_CROP_DAY_BAR == 45 and pb.PAYDAY_MONEY == 5000
    assert pb.PILKWANG == "pilkwang_structured_economic_policy"


def test_the_seeds_are_fresh_against_every_range_already_spent():
    """A #252 result must not reuse a seed already burned by an earlier experiment."""
    spent = set(range(100, 116)) | set(range(200, 216)) | set(range(300, 332)) \
        | set(range(400, 416)) | set(range(500, 516)) | set(range(600, 616)) \
        | set(range(700, 704)) | set(range(800, 896))
    assert not spent & set(pb.SEEDS)


def test_the_verdict_logic_is_rival_benchs_not_a_copy():
    """The re-exported names are the same objects as rival_bench's, not a fork of them."""
    assert pb.criterion is rb.criterion and pb.format_rows is rb.format_rows
    assert pb.format_external is rb.format_external
    assert pb.paired_external_rows is rb.paired_external_rows


def _census(planted, quadrants, hands, head, money, strawberry=0):
    planted_by = {"STRAWBERRY": strawberry, "MELON": planted - strawberry} if planted else {}
    return {"planted_tiles": planted, "planted": planted_by, "quadrants": ["NW", "NE", "SW"][:quadrants],
            "hands": hands, "head_placed": head, "money": float(money)}


def _turns():
    # Two turns a day, days 0..12: the shape lands on day 8, money crosses 5,000 on day 10.
    turns = []
    for day in range(13):
        planted = 20 if day < 6 else (37 if day < 11 else 62)
        quads = 1 if day < 6 else (2 if day < 11 else 3)
        hands = 5 if day < 6 else (8 if day < 8 else 10)
        head = 4 if day < 6 else (8 if day < 8 else 13)
        money = 600 if day < 10 else 18_000
        straw = 0 if day < 5 else 20
        turns.append((day, _census(planted - 1, quads, hands, head, money - 1, straw)))
        turns.append((day, _census(planted, quads, hands, head, money, straw)))
    return turns


def test_shape_reading_takes_the_closing_board_of_each_declared_day_and_the_payday():
    r = pb.shape_reading(_turns())
    assert r["planted"] == 37 and r["quadrants"] == 2 and r["hands"] == 10 and r["head_placed"] == 13
    assert r["strawberry"] == 20 and r["money_at_shape_day"] == 600
    assert r["planted_at_crop_day"] == 62 and r["money_at_crop_day"] == 18_000
    assert r["payday"] == 10


def test_shape_reading_reports_no_payday_when_money_never_crossed():
    turns = [(d, _census(20, 1, 6, 1, 900)) for d in range(13)]
    assert pb.shape_reading(turns)["payday"] is None


def test_shape_reading_raises_when_the_game_never_reached_a_declared_day():
    with pytest.raises(ValueError, match="day 12"):
        pb.shape_reading(_turns()[:20])


def test_closing_says_when_there_were_no_turns_at_all():
    """The empty-turns arm of `_closing`'s message (#252 review M6) -- untested until now."""
    with pytest.raises(ValueError, match="day 8: no turns at all"):
        pb.shape_reading([])


def test_each_shape_bar_can_fail_alone():
    good = pb.shape_reading(_turns())
    assert pb.shape_failures(good) == []
    assert pb.shape_failures(dict(good, planted=29)) == ["planted"]
    assert pb.shape_failures(dict(good, quadrants=1)) == ["quadrants"]
    assert pb.shape_failures(dict(good, hands=7)) == ["hands"]
    assert pb.shape_failures(dict(good, head_placed=7)) == ["head_placed"]
    assert pb.shape_failures(dict(good, planted_at_crop_day=44)) == ["planted_at_crop_day"]
    assert pb.shape_failures(dict(good, planted=0, hands=0)) == ["planted", "hands"]


def test_arm_b_is_the_crop_schedule_on_third_herders_herd_and_is_not_registered():
    from strategies import REGISTRY, field_rival as fr
    from strategies.field_pace import FieldPaceStrategy
    from strategies.third_herder import ThirdHerderStrategy
    cls = pb.arm_b_class()
    assert issubclass(cls, FieldPaceStrategy)
    arm, base = cls(), ThirdHerderStrategy()
    assert arm.hire_target(8) == 10 and arm.land_target(6) == 2 and arm.pivot_day() == 5
    assert arm.cluster_size() == 6 and arm.capital_reserve() == 0 and arm.CAPS == FieldPaceStrategy.CAPS
    for day in (0, 6, 8, 29):
        assert arm.herd_target(day) == base.herd_target(day), day
        assert arm.pasture_count(day, 0) == base.pasture_count(day, 0), day
    assert arm.layout() == base.layout() and fr.FieldRivalStrategy().layout() is None
    assert pb.ARM_B not in REGISTRY and pb.CONTENDER in REGISTRY


def test_format_shape_prints_both_sides_and_the_payday():
    r = pb.shape_reading(_turns())
    text = pb.format_shape([("field_pace", r), ("third_herder", dict(r, payday=None))])
    lines = text.splitlines()
    assert len(lines) == 3 and lines[1].startswith("field_pace") and "day 10" in lines[1]
    assert lines[2].rstrip().endswith("never")
