"""The payday_herd experiment's declared constants and pure parts (#274)."""

from __future__ import annotations

import pytest

from harness import fed_bench as fb
from harness import payday_bench as pb
from strategies import field_pace as fp


def test_the_declared_constants():
    assert pb.CONTENDER == "payday_herd" and pb.CHAMPION == "lean_feed" and pb.ARM_B == "hold6"
    assert pb.SEEDS == tuple(range(1040, 1056)) and pb.CONTROL_SEED == 1040
    assert pb.CHAMPION_BAR == 0.60 and pb.ANCHOR_BAR == 0.90
    assert list(pb.CENSUS_DAYS) == list(range(0, 17)) and pb.HEAD_LOST_BAR == 0
    assert (pb.CREW_DAY, pb.CREW_BAR, pb.HEAD_DAY) == (10, 10, 16)
    assert pb.HOLD6_RAMP == ((0, 4), (6, 6), (12, 13))


def test_the_seeds_are_fresh_against_every_range_already_spent():
    spent = set(range(100, 116)) | set(range(200, 216)) | set(range(300, 332)) \
        | set(range(400, 416)) | set(range(500, 516)) | set(range(600, 616)) \
        | set(range(700, 704)) | set(range(800, 960)) | set(range(960, 1040))
    assert not spent & set(pb.SEEDS)


def _board(n):
    return {"tiles": [[{"animal": "COW"}] * n]}


def test_reading_and_its_failure(monkeypatch):
    heads = {d: (4 if d < 6 else 8 if d < 12 else 13) for d in range(0, 17)}
    monkeypatch.setattr(fb, "board_on_day", lambda steps, seat, day: _board(heads[day]))
    monkeypatch.setattr(pb, "hands_on_day", lambda steps, seat, day: {10: 10}.get(day, 6))
    r = pb.reading("s", 0)
    assert r["lost"] == 0 and r["hands_10"] == 10 and r["head_16"] == 13 and len(r["heads"]) == 17
    monkeypatch.setattr(fb, "board_on_day", lambda steps, seat, day: None if day >= 16 else _board(4))
    with pytest.raises(ValueError):
        pb.reading("s", 0)


def test_mechanism_failures_name_the_bars():
    champ = {"lost": 3, "hands_10": 6, "head_16": 11}
    assert pb.mechanism_failures({"lost": 0, "hands_10": 10, "head_16": 11}, champ) == []
    assert pb.mechanism_failures({"lost": 1, "hands_10": 10, "head_16": 11}, champ) == ["lost"]
    assert pb.mechanism_failures({"lost": 0, "hands_10": 9, "head_16": 10}, champ) == ["hands_10", "head_16"]


def test_the_identity_stub_switches_every_seam_off_resets_the_ramp_and_survives_a_turn():
    from harness.sheep_bench import _seam_names
    cls = pb.off_class()
    for n in _seam_names():
        assert n in cls.__dict__, f"seam {n} not switched off"
    off = cls()
    assert off.herd_target(8) is None and off.pasture_count(8, 8) is None and off.layout() is None
    assert off.HERD_RAMP_F == fp.HERD_RAMP_F and off.CAPS == pb.load_reference().CAPS
    from kaggisim.state import parse
    from kaggle_environments import make
    env = make("kaggriculture", configuration={"seed": 1040, "episodeSteps": 3})
    out = off.act(parse(env.reset()[0].observation))
    assert set(out) >= {"farmer", "hands", "market"}


def test_arm_b_holds_at_six_and_changes_nothing_else():
    from harness.sheep_bench import _seam_names
    from strategies.lean_feed import LeanFeedStrategy
    cls = pb.arm_b_class()
    b = cls()
    assert isinstance(b, LeanFeedStrategy) and b.HERD_RAMP_F == pb.HOLD6_RAMP
    assert set(cls.__dict__) & set(_seam_names()) == set()
    assert [b.herd_target(d) for d in (6, 11, 12)] == [6, 6, 13]
