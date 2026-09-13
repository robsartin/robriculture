"""ten_melon (#279): one cap, nothing else."""

from __future__ import annotations

from strategies import field_pace as fp
from strategies import ten_melon as tm
from strategies.payday_herd import PaydayHerdStrategy


def test_the_caps_are_field_paces_with_melon_10():
    assert tm.CAPS_T == {"MELON": 10, "STRAWBERRY": 38, "WHEAT": 24}
    assert fp.CAPS_F == {"MELON": 12, "STRAWBERRY": 38, "WHEAT": 24}
    assert tm.TenMelonStrategy.CAPS == tm.CAPS_T and tm.TenMelonStrategy.CAPS is not fp.CAPS_F


def test_no_seam_is_overridden_and_the_rest_is_payday_herds():
    from harness.sheep_bench import _seam_names
    assert set(tm.TenMelonStrategy.__dict__) & set(_seam_names()) == set()
    p, q = tm.TenMelonStrategy(), PaydayHerdStrategy()
    assert p.name == "ten_melon" and isinstance(p, PaydayHerdStrategy)
    assert p.CAPS["MELON"] == 10 and q.CAPS["MELON"] == 12
    assert p.herd_target(8) == q.herd_target(8) == 8 and p.HERD_RAMP_F == q.HERD_RAMP_F
    assert p.pivot_day() == q.pivot_day() and p.cluster_size() == q.cluster_size()


def test_registered():
    from strategies import load
    assert load("ten_melon") is tm.TenMelonStrategy
