"""The herd_first experiment's declared constants and the pure parts it adds.

The verdict machinery is `harness.rival_bench`'s and the census readers
`harness.pace_bench`'s -- imported, not copied. New here: an absolute head-placed
control at day 8 (the bar #252 failed) and a crop-line control PAIRED against
field_pace on the same seed, the cost the arm is allowed to pay.
"""

from __future__ import annotations

from harness import order_bench as ob
from harness import pace_bench as pb
from harness import rival_bench as rb


def test_the_declared_constants():
    # Declared on #254 before any code; not to be tuned.
    assert ob.CONTENDER == "herd_first" and ob.CHAMPION == "third_herder" and ob.PACE == "field_pace"
    assert ob.SEEDS == tuple(range(912, 928)) and ob.CONTROL_SEED == 912
    assert ob.CHAMPION_BAR == 0.60 and ob.ANCHOR_BAR == 0.90
    assert ob.ARM_B == "herd_mid" and ob.ORDER_B == ("hires", "land", "herd", "seed")
    assert ob.HEAD_DAY == 8 and ob.HEAD_BAR == 8
    assert ob.CROP_DAY == 12 and ob.PLANTED_GAP_BAR == 12


def test_the_seeds_are_fresh_against_every_range_already_spent():
    # 896 was #252's control seed; 897-911 were never played but are not reused.
    spent = set(range(100, 116)) | set(range(200, 216)) | set(range(300, 332)) \
        | set(range(400, 416)) | set(range(500, 516)) | set(range(600, 616)) \
        | set(range(700, 704)) | set(range(800, 912))
    assert not spent & set(ob.SEEDS)


def test_the_verdict_logic_and_the_readers_are_imported_not_copied():
    assert ob.criterion is rb.criterion and ob.format_rows is rb.format_rows
    assert ob.format_external is rb.format_external
    assert ob.paired_external_rows is rb.paired_external_rows
    assert ob.shape_reading is pb.shape_reading and ob.format_shape is pb.format_shape
    assert ob.REFERENCE == pb.REFERENCE and ob.PILKWANG == pb.PILKWANG


def _reading(head=8, planted_at_12=40):
    return {"planted": 25, "quadrants": 2, "hands": 9, "head_placed": head, "strawberry": 10,
            "money_at_shape_day": 300.0, "planted_at_crop_day": planted_at_12,
            "money_at_crop_day": 4000.0, "payday": 11}


def test_mechanism_gates_on_head_placed_at_the_bar():
    # The bar #252 failed at 6: eight placed passes, seven does not.
    assert ob.mechanism_ok(_reading(head=8)) is True
    assert ob.mechanism_ok(_reading(head=7)) is False


def test_crop_line_is_paired_against_field_pace_within_the_gap():
    # The cost the arm may pay: twelve tiles either side of field_pace's count.
    pace = _reading(planted_at_12=47)
    assert ob.crop_line_ok(_reading(planted_at_12=35), pace) is True
    assert ob.crop_line_ok(_reading(planted_at_12=34), pace) is False
    assert ob.crop_line_ok(_reading(planted_at_12=59), pace) is True
    assert ob.crop_line_ok(_reading(planted_at_12=60), pace) is False


def test_arm_b_is_herd_before_seed_after_land_and_is_not_registered():
    from strategies import REGISTRY
    from strategies.field_pace import FieldPaceStrategy
    cls = ob.arm_b_class()
    assert issubclass(cls, FieldPaceStrategy)
    arm, base = cls(), FieldPaceStrategy()
    assert arm.buy_order() == ob.ORDER_B and base.buy_order() is None
    assert arm.herd_target(8) == base.herd_target(8) and arm.layout() == base.layout()
    assert ob.ARM_B not in REGISTRY and ob.CONTENDER in REGISTRY
