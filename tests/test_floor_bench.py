"""The dusk_floor experiment's declared constants and the pure parts it adds.

Bars, readers and the verdict are `harness.reserve_bench`'s / `order_bench`'s /
`rival_bench`'s -- imported, not copied. New here: the twelve-hook identity stub
(the floor seam switched off) and a wages-only arm B.
"""

from __future__ import annotations

from harness import floor_bench as fb
from harness import reserve_bench as rsb
from harness import rival_bench as rb


def test_the_declared_constants():
    # Declared on #258 before any code; not to be tuned.
    assert fb.CONTENDER == "dusk_floor" and fb.CHAMPION == "third_herder" and fb.BASELINE == "herd_first"
    assert fb.SEEDS == tuple(range(944, 960)) and fb.CONTROL_SEED == 944
    assert fb.CHAMPION_BAR == 0.60 and fb.ANCHOR_BAR == 0.90
    assert fb.ARM_B == "wage_floor"
    assert (fb.HEAD_DAY, fb.HEAD_BAR, fb.HANDS_BAR, fb.CROP_DAY, fb.PLANTED_GAP_BAR) == (8, 8, 8, 12, 12)


def test_the_seeds_are_fresh_against_every_range_already_spent():
    # 928 was #256's control seed; 929-943 were declared there and never played, not reused.
    spent = set(range(100, 116)) | set(range(200, 216)) | set(range(300, 332)) \
        | set(range(400, 416)) | set(range(500, 516)) | set(range(600, 616)) \
        | set(range(700, 704)) | set(range(800, 944))
    assert not spent & set(fb.SEEDS)


def test_the_bars_readers_and_verdict_are_imported_not_copied():
    assert fb.crew_ok is rsb.crew_ok and fb.mechanism_failures is rsb.mechanism_failures
    assert fb.order_reading is rsb.order_reading and fb.crop_line_ok is rsb.crop_line_ok
    assert fb.format_order_shape is rsb.format_order_shape
    assert fb.criterion is rb.criterion and fb.paired_external_rows is rb.paired_external_rows
    assert fb.MADHUR == rsb.MADHUR and fb.PILKWANG == rsb.PILKWANG and fb.REFERENCE == rsb.REFERENCE


def test_the_identity_stub_switches_every_seam_off_and_survives_a_turn():
    """Twelve hooks off, the floor among them, at their current arity; a real
    reset observation catches the next arity drift."""
    from kaggle_environments import make
    off = fb.off_class()()
    assert off.spend_floor(8, 4, {}, {}) is None and off.spend_floor() is None
    assert off.capital_reserve(8, 4) is None and off.buy_order() is None and off.layout() is None
    obs = make("kaggriculture", configuration={"seed": 1}).state[0].observation
    assert set(off.act(obs)) == {"farmer", "hands", "market"}


def test_arm_b_keeps_the_wages_only_and_is_not_registered():
    from strategies import REGISTRY
    from strategies.dawn_reserve import wage_bill
    from strategies.herd_first import HerdFirstStrategy
    cls = fb.arm_b_class()
    assert issubclass(cls, HerdFirstStrategy)
    arm = cls()
    assert arm.spend_floor(5, 4, {}, {"WHEAT": 25}) == wage_bill(arm.hire_target(6)) == 54
    assert arm.spend_floor(7, 8, {}, {}) == 143 and arm.spend_floor() == 12
    assert arm.buy_order() == ("hires", "herd", "land", "seed")
    assert fb.ARM_B not in REGISTRY and fb.CONTENDER in REGISTRY
