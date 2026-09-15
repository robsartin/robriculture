"""four_at_eight's bench (#291): fourth_bench's readings on the new contender, fresh seeds."""

from __future__ import annotations

from harness import four8_bench as fb
from harness import fourth_bench as parent
from strategies import field_pace as fp


def test_the_declared_constants():
    assert fb.CONTENDER == "four_at_eight" and fb.CHAMPION == "ten_melon" and fb.ARM_B == "from_ten"
    assert fb.SEEDS == tuple(range(1138, 1154)) and fb.CONTROL_SEED == 1138
    assert fb.CHAMPION_BAR == 0.60 and fb.ANCHOR_BAR == 0.90 and fb.ARM_B_FROM == 10
    assert fb.reading is parent.reading and fb.mechanism_failures is parent.mechanism_failures


def test_the_seeds_are_fresh_against_every_range_already_spent():
    spent = set(range(100, 116)) | set(range(200, 216)) | set(range(300, 332)) \
        | set(range(400, 416)) | set(range(500, 516)) | set(range(600, 616)) \
        | set(range(700, 704)) | set(range(800, 960)) | set(range(960, 1138))
    assert not spent & set(fb.SEEDS)


def test_head_lost_reading_is_printed_only(monkeypatch):
    monkeypatch.setattr(fb, "head_by_day", lambda steps, seat, days: [4, 4, 6, 8, 6, 9, 11])
    assert fb.escapes("s", 0) == 2


def test_the_identity_stub_switches_all_sixteen_seams_off_on_this_contender():
    from harness.sheep_bench import _seam_names
    cls = fb.off_class()
    from strategies.four_at_eight import FourAtEightStrategy
    assert issubclass(cls, FourAtEightStrategy)
    for n in _seam_names():
        assert n in cls.__dict__, f"seam {n} not switched off"
    off = cls()
    assert off.livestock_workers(8) is None and off.HERD_RAMP_F == fp.HERD_RAMP_F and off.CAPS == fb.load_reference().CAPS


def test_arm_b_starts_on_day_ten():
    from strategies.four_at_eight import FourAtEightStrategy
    b = fb.arm_b_class()()
    assert isinstance(b, FourAtEightStrategy) and b.FOURTH_DAY == 10
    assert b.livestock_workers(9) == (1, 2, 6) and b.livestock_workers(10) == (1, 2, 6, 7)
