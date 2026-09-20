"""fert_sixteen's third run (#329): sixteen_bench on fresh seeds under the amended external limb."""

from __future__ import annotations

from harness import rival_bench as rb
from harness import sixteen_bench as parent
from harness import sixteenc_bench as b


def test_the_declared_constants():
    assert b.CONTENDER == "fert_sixteen" and b.CHAMPION == "twelve_head" and b.ARM_B == "from_twelve"
    assert b.SEEDS == tuple(range(1543, 1559)) and b.CONTROL_SEED == 1543
    assert b.CHAMPION_BAR == 0.60 and b.ANCHOR_BAR == 0.90 and b.ARM_B_FROM == 12
    assert (b.FERTILIZE_BAR, b.STRAWBERRY_FACTOR) == (100, 1.5) and list(b.EARLY_DAYS) == list(range(1, 17))
    assert b.reading is parent.reading and b.mechanism_failures is parent.mechanism_failures
    assert b.off_class is parent.off_class and b.arm_b_class is parent.arm_b_class and b.escapes is parent.escapes
    assert b.LONESPEAR == parent.LONESPEAR and b.MADHUR == parent.MADHUR


def test_the_seeds_are_fresh_against_every_range_already_spent():
    spent = set(range(100, 116)) | set(range(200, 216)) | set(range(300, 332)) \
        | set(range(400, 416)) | set(range(500, 516)) | set(range(600, 616)) \
        | set(range(700, 704)) | set(range(800, 960)) | set(range(960, 1543))
    assert not spent & set(b.SEEDS)


def test_the_verdict_is_the_amended_limb():
    assert b.criterion is rb.criterion and b.decided_row is rb.decided_row
    assert rb.PAIRED_MAX_SHORTFALL == 1 and rb.PAIRED_FLOOR_WINS == 1
    assert rb.external_failing({"madhur": (15, 16), "lonespear": (8, 1), "shashank": (16, 16)}) == []
    assert rb.external_failing({"madhur": (14, 16)}) == ["external:madhur"]
