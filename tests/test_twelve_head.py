"""twelve_head (#320): the herd ramp's last step is twelve, nothing else."""

from __future__ import annotations

from strategies import free_straw as fs
from strategies import twelve_head as th
from strategies.free_straw import FreeStrawStrategy
from strategies.payday_herd import HERD_RAMP_P


def test_the_ramp_is_payday_herds_with_its_last_step_at_twelve():
    assert th.HERD_RAMP_T == ((0, 4), (6, 8), (12, 12))
    assert th.HERD_RAMP_T[:2] == HERD_RAMP_P[:2] and HERD_RAMP_P[2] == (12, 13)
    assert th.TwelveHeadStrategy.HERD_RAMP_F is th.HERD_RAMP_T


def test_herd_target_reads_the_ramp_and_never_thirteen():
    p, q = th.TwelveHeadStrategy(), FreeStrawStrategy()
    assert [p.herd_target(d) for d in (0, 6, 12, 20, 29)] == [4, 8, 12, 12, 12]
    assert [q.herd_target(d) for d in (0, 6, 12, 20)] == [4, 8, 13, 13]
    assert all(p.herd_target(d) == q.herd_target(d) for d in range(0, 12))


def test_the_class_overrides_nothing_but_the_ramp():
    from harness import sheep_bench as sb
    p = th.TwelveHeadStrategy()
    assert p.name == "twelve_head" and isinstance(p, FreeStrawStrategy) and p.FOURTH_DAY == 8 and p.benchmark is False
    assert p.CAPS is fs.CAPS_S
    assert set(th.TwelveHeadStrategy.__dict__) & set(sb._seam_names()) == set()
    assert not [k for k, v in th.TwelveHeadStrategy.__dict__.items() if callable(v)]
    q = FreeStrawStrategy()
    assert p.livestock_workers(8) == q.livestock_workers(8) and p.buy_order() == q.buy_order() and p.pivot_day() == q.pivot_day()


def test_registered():
    from strategies import load
    assert load("twelve_head") is th.TwelveHeadStrategy
