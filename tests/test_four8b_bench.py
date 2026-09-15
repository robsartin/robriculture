"""four_at_eight's second run (#299): four8_bench on fresh seeds under the amended limb."""

from __future__ import annotations

from harness import four8_bench as parent
from harness import four8b_bench as b
from harness import rival_bench as rb


def test_the_declared_constants():
    assert b.CONTENDER == "four_at_eight" and b.CHAMPION == "ten_melon" and b.ARM_B == "from_ten"
    assert b.SEEDS == tuple(range(1154, 1170)) and b.CONTROL_SEED == 1154
    assert b.CHAMPION_BAR == 0.60 and b.ANCHOR_BAR == 0.90 and b.ARM_B_FROM == 10
    assert b.reading is parent.reading and b.mechanism_failures is parent.mechanism_failures
    assert b.off_class is parent.off_class and b.arm_b_class is parent.arm_b_class and b.escapes is parent.escapes


def test_the_seeds_are_fresh_against_every_range_already_spent():
    spent = set(range(100, 116)) | set(range(200, 216)) | set(range(300, 332)) \
        | set(range(400, 416)) | set(range(500, 516)) | set(range(600, 616)) \
        | set(range(700, 704)) | set(range(800, 960)) | set(range(960, 1154))
    assert not spent & set(b.SEEDS)


def test_the_verdict_is_the_amended_criterion():
    assert b.criterion is rb.criterion and rb.PAIRED_FLOOR_WINS == 1 and rb.regressed(0, 1) is False
