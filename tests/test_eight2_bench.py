"""fert_eight's second run (#286): the planting bar dropped, the seeds moved."""

from __future__ import annotations

import pytest

from harness import eight2_bench as e2


def test_the_declared_constants():
    assert e2.CONTENDER == "fert_eight" and e2.CHAMPION == "ten_melon" and e2.ARM_B == "from_ten"
    assert e2.SEEDS == tuple(range(1105, 1121)) and e2.CONTROL_SEED == 1120 and 1120 in e2.SEEDS
    assert e2.CHAMPION_BAR == 0.60 and e2.ANCHOR_BAR == 0.90
    assert e2.FERTILIZE_BAR == 100 and e2.STRAWBERRY_FACTOR == 1.5
    assert list(e2.EARLY_DAYS) == list(range(1, 8)) and list(e2.PLANT_DAYS) == list(range(6, 14))
    assert e2.ARM_B_FROM == 10


def test_the_seeds_are_the_declared_unplayed_range_plus_the_control():
    spent = set(range(100, 116)) | set(range(200, 216)) | set(range(300, 332)) \
        | set(range(400, 416)) | set(range(500, 516)) | set(range(600, 616)) \
        | set(range(700, 704)) | set(range(800, 960)) | set(range(960, 1105))
    assert not spent & set(e2.SEEDS)


def test_reading_prints_planting_by_day_and_gates_only_the_three_mechanism_bars(monkeypatch):
    monkeypatch.setattr(e2, "action_counts", lambda steps, seat: {"FERTILIZE": 171})
    monkeypatch.setattr(e2, "units_sold", lambda steps, seat: {"STRAWBERRY": 257, "MELON": 30})
    monkeypatch.setattr(e2, "board_on_day", lambda steps, seat, day: {"tiles": [[{"kind": "PLANT", "crop": "MELON"}] * (day + 10)]})
    monkeypatch.setattr(e2, "dawn_cash", lambda steps, seat, days: [1, 2, 3, 4, 5, 6, 7])
    r = e2.reading("s", 0)
    assert r == {"fertilize": 171, "strawberry": 257, "melon": 30, "dawn_1_7": [1, 2, 3, 4, 5, 6, 7],
                 "planted": [16, 17, 18, 19, 20, 21, 22, 23]}
    champ = {**r, "fertilize": 0, "strawberry": 148, "planted": [18, 28, 28, 26, 42, 48, 47, 47]}
    assert e2.mechanism_failures(r, champ) == []                      # planting is not gated
    assert e2.mechanism_failures({**r, "fertilize": 99}, champ) == ["fertilize"]
    assert e2.mechanism_failures({**r, "strawberry": 221}, champ) == ["strawberry"]
    assert e2.mechanism_failures({**r, "dawn_1_7": [1, 2, 3, 4, 5, 6, 8]}, champ) == ["dawn_1_7"]
    monkeypatch.setattr(e2, "board_on_day", lambda steps, seat, day: None)
    with pytest.raises(ValueError):
        e2.reading("s", 0)


def test_off_class_and_arm_b_are_eight_benchs():
    from harness import eight_bench as eb
    assert e2.off_class is eb.off_class and e2.arm_b_class is eb.arm_b_class
    b = e2.arm_b_class()()
    assert b.FERT_FROM == 10
