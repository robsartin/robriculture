"""The dawn_reserve experiment's declared constants and the pure parts it adds.

Readers are `harness.order_bench`'s and the verdict `harness.rival_bench`'s --
imported, not copied. New here: a crew bar beside the head bar (the crew is
what the reserve exists to keep) and the crop line paired against herd_first.
"""

from __future__ import annotations

from harness import order_bench as ob
from harness import pace_bench as pb
from harness import reserve_bench as rsb
from harness import rival_bench as rb


def test_the_declared_constants():
    # Declared on #256 before any code; not to be tuned.
    assert rsb.CONTENDER == "dawn_reserve" and rsb.CHAMPION == "third_herder"
    assert rsb.BASELINE == "herd_first"
    assert rsb.SEEDS == tuple(range(928, 944)) and rsb.CONTROL_SEED == 928
    assert rsb.CHAMPION_BAR == 0.60 and rsb.ANCHOR_BAR == 0.90
    assert rsb.ARM_B == "wage_reserve"
    assert rsb.HEAD_DAY == 8 and rsb.HEAD_BAR == 8 and rsb.HANDS_BAR == 8
    assert rsb.CROP_DAY == 12 and rsb.PLANTED_GAP_BAR == 12
    assert rsb.MADHUR == "madhur_sabherwal_hub_geometry_agent"


def test_the_seeds_are_fresh_against_every_range_already_spent():
    # 912-927 were #254's; everything through 927 is spent.
    spent = set(range(100, 116)) | set(range(200, 216)) | set(range(300, 332)) \
        | set(range(400, 416)) | set(range(500, 516)) | set(range(600, 616)) \
        | set(range(700, 704)) | set(range(800, 928))
    assert not spent & set(rsb.SEEDS)


def test_the_readers_and_the_verdict_are_imported_not_copied():
    assert rsb.order_reading is ob.order_reading and rsb.format_order_shape is ob.format_order_shape
    assert rsb.crop_line_ok is ob.crop_line_ok
    assert rsb.criterion is rb.criterion and rsb.paired_external_rows is rb.paired_external_rows
    assert rsb.REFERENCE == pb.REFERENCE and rsb.PILKWANG == pb.PILKWANG


def _reading(hands=9, head=8):
    return {"planted": 25, "quadrants": 2, "hands": hands, "head_placed": head, "head_held": 0,
            "pasture_free": 4, "strawberry": 10, "money_at_shape_day": 300.0,
            "planted_at_crop_day": 45, "money_at_crop_day": 4000.0, "payday": 11}


def test_each_mechanism_bar_can_fail_alone_and_names_itself():
    # herd_first had 2 hands and 8 head at day 8: the crew bar is the new one.
    assert rsb.crew_ok(_reading(hands=8)) is True and rsb.crew_ok(_reading(hands=7)) is False
    assert rsb.mechanism_failures(_reading()) == []
    assert rsb.mechanism_failures(_reading(hands=2)) == ["hands"]
    assert rsb.mechanism_failures(_reading(head=6)) == ["head_placed"]
    assert rsb.mechanism_failures(_reading(hands=2, head=6)) == ["hands", "head_placed"]


def test_arm_b_keeps_the_wages_only_and_is_not_registered():
    from strategies import REGISTRY
    from strategies.dawn_reserve import wage_bill
    from strategies.herd_first import HerdFirstStrategy
    cls = rsb.arm_b_class()
    assert issubclass(cls, HerdFirstStrategy)
    arm = cls()
    assert arm.capital_reserve(5, 4) == wage_bill(arm.hire_target(6)) == 54
    assert arm.capital_reserve(7, 8) == 143
    assert arm.buy_order() == ("hires", "herd", "land", "seed")
    assert rsb.ARM_B not in REGISTRY and rsb.CONTENDER in REGISTRY


def test_the_identity_stub_switches_every_seam_off_and_survives_a_turn():
    """The identity control's Off class must answer every hook the contender's
    bases define with the frozen None -- with the hook's CURRENT arity. #256
    gave `capital_reserve` two arguments and the old one-argument lambda raised
    TypeError inside `act`; a real reset observation catches the next such drift."""
    from kaggle_environments import make
    off = rsb.off_class()()
    assert off.capital_reserve(8, 4) is None and off.capital_reserve() is None
    assert off.buy_order() is None and off.layout() is None and off.hire_target(8) is None
    obs = make("kaggriculture", configuration={"seed": 1}).state[0].observation
    assert set(off.act(obs)) == {"farmer", "hands", "market"}
