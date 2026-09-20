"""fert_sixteen's fourth run (#331): the mechanism control compares the contender's
seat with the champion's own play in that seat, never with the other seat."""

from __future__ import annotations

import pytest

from harness import rival_bench as rb
from harness import sixteen_bench as parent
from harness import sixteend_bench as b


def test_the_declared_constants():
    assert b.CONTENDER == "fert_sixteen" and b.CHAMPION == "twelve_head" and b.ARM_B == "from_twelve"
    assert b.SEEDS == tuple(range(1559, 1575)) and b.CONTROL_SEED == 1559
    assert b.CHAMPION_BAR == 0.60 and b.ANCHOR_BAR == 0.90 and b.ARM_B_FROM == 12
    assert (b.FERTILIZE_BAR, b.STRAWBERRY_FACTOR, b.LEVER_DAY) == (100, 1.5, 16) and list(b.EARLY_DAYS) == list(range(1, 17))
    assert b.off_class is parent.off_class and b.arm_b_class is parent.arm_b_class
    assert b.criterion is rb.criterion and b.decided_row is rb.decided_row and rb.PAIRED_MAX_SHORTFALL == 1


def test_the_seeds_are_fresh_against_every_range_already_spent():
    spent = set(range(100, 116)) | set(range(200, 216)) | set(range(300, 332)) \
        | set(range(400, 416)) | set(range(500, 516)) | set(range(600, 616)) \
        | set(range(700, 704)) | set(range(800, 960)) | set(range(960, 1559))
    assert not spent & set(b.SEEDS)


def _steps(*actions_by_seat):
    return [[{"action": a} for a in step] for step in zip(*actions_by_seat)]


def test_first_divergence_is_the_first_step_the_contenders_seat_differs_from_the_champions_own():
    ours = _steps(["a", "a", "b", "c"], ["x", "x", "x", "x"])
    own = _steps(["a", "a", "a", "a"], ["y", "y", "y", "y"])
    assert b.first_divergence(ours, own, 0) == 2
    assert b.first_divergence(own, own, 0) is None
    assert b.first_divergence(ours, own, 1) == 0


def test_reading_reads_counts_units_and_dawn_cash(monkeypatch):
    monkeypatch.setattr(b, "action_counts", lambda steps, seat: {"FERTILIZE": 121})
    monkeypatch.setattr(b, "units_sold", lambda steps, seat: {"STRAWBERRY": 278})
    monkeypatch.setattr(b, "dawn_cash", lambda steps, seat, days: [d for d in days])
    assert b.reading("s", 0) == {"fertilize": 121, "strawberry": 278, "dawn_1_16": list(range(1, 17))}


def test_mechanism_failures_compare_with_the_champions_own_seat():
    dawn = list(range(1, 17))
    contender = {"fertilize": 121, "strawberry": 278, "dawn_1_16": list(dawn)}
    champion = {"fertilize": 0, "strawberry": 167, "dawn_1_16": [9] * 16}      # the other seat: never compared
    own = {"fertilize": 0, "strawberry": 170, "dawn_1_16": list(dawn)}          # the champion's own seat-0 play
    assert b.mechanism_failures(contender, champion, own, first_diff=386) == []
    assert b.mechanism_failures(contender, champion, own, first_diff=None) == []
    assert b.mechanism_failures(contender, champion, own, first_diff=384) == []          # 16 * 24: the first turn of day 16
    assert b.mechanism_failures(contender, champion, own, first_diff=383) == ["lever_day"]
    assert b.mechanism_failures({**contender, "dawn_1_16": dawn[:-1] + [0]}, champion, own, first_diff=386) == ["dawn_1_16"]
    assert b.mechanism_failures({**contender, "fertilize": 99}, champion, own, first_diff=386) == ["fertilize"]
    assert b.mechanism_failures({**contender, "strawberry": 250}, champion, own, first_diff=386) == ["strawberry"]   # < 1.5 * 167
    assert b.mechanism_failures({**contender, "fertilize": 0, "strawberry": 1, "dawn_1_16": []}, champion, own, first_diff=0) \
        == ["fertilize", "strawberry", "dawn_1_16", "lever_day"]


def test_play_and_the_reference_are_pinned():
    from harness.cashflow import play
    from harness.reserve_bench import REFERENCE
    assert b.play is play and b.REFERENCE == REFERENCE == "dense_farm"
