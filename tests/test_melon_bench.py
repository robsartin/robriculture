"""The ten_melon experiment's declared constants and pure parts (#279)."""

from __future__ import annotations

import pytest

from harness import melon_bench as mb
from strategies import field_pace as fp


def test_the_declared_constants():
    assert mb.CONTENDER == "ten_melon" and mb.CHAMPION == "payday_herd" and mb.ARM_B == "cap11"
    assert mb.SEEDS == tuple(range(1072, 1088)) and mb.CONTROL_SEED == 1072
    assert mb.CHAMPION_BAR == 0.60 and mb.ANCHOR_BAR == 0.90
    assert (mb.MELON_BAR, mb.PLANTED_DAY, mb.PLANTED_BAR) == (44, 8, 28)
    assert mb.CAPS_B == {"MELON": 11, "STRAWBERRY": 38, "WHEAT": 24}
    assert mb.LONESPEAR.startswith("lonespear") and mb.PILKWANG.startswith("pilkwang")


def test_the_seeds_are_fresh_against_every_range_already_spent():
    spent = set(range(100, 116)) | set(range(200, 216)) | set(range(300, 332)) \
        | set(range(400, 416)) | set(range(500, 516)) | set(range(600, 616)) \
        | set(range(700, 704)) | set(range(800, 960)) | set(range(960, 1072))
    assert not spent & set(mb.SEEDS)


def _step(seat_actions):
    return [{"action": a, "observation": {}, "reward": 0, "status": "ACTIVE"} for a in seat_actions]


STEPS = [
    _step([{"farmer": ["PASS"], "hands": [], "market": [["SELL", "MELON", 20], ["SELL", "WHEAT", 3]]},
           {"farmer": ["PASS"], "hands": [], "market": [["SELL", "MELON", 12]]}]),
    _step([{"farmer": ["PASS"], "hands": [], "market": [["SELL", "MELON", 25]]},
           {"farmer": ["PASS"], "hands": [], "market": [["SELL", "MELON", 24], ["BUY_SEED", "MELON", 1]]}]),
]


def _board(n):
    return {"tiles": [[{"kind": "PLANT", "crop": "MELON"}] * n]}


def test_reading_and_its_failure(monkeypatch):
    monkeypatch.setattr(mb, "board_on_day", lambda steps, seat, day: _board({0: 29, 1: 25}[seat]) if day == 8 else None)
    assert mb.reading(STEPS, 0) == {"melon": 45, "planted_8": 29}
    assert mb.reading(STEPS, 1) == {"melon": 36, "planted_8": 25}
    monkeypatch.setattr(mb, "board_on_day", lambda steps, seat, day: None)
    with pytest.raises(ValueError):
        mb.reading(STEPS, 0)


def test_mechanism_failures_name_the_bars():
    champ = {"melon": 40, "planted_8": 25}
    assert mb.mechanism_failures({"melon": 45, "planted_8": 29}, champ) == []
    assert mb.mechanism_failures({"melon": 44, "planted_8": 28}, champ) == []
    assert mb.mechanism_failures({"melon": 43, "planted_8": 29}, champ) == ["melon"]
    assert mb.mechanism_failures({"melon": 45, "planted_8": 27}, champ) == ["planted_8"]
    # above the bar but below the champion in the same game still fails
    assert mb.mechanism_failures({"melon": 45, "planted_8": 29}, {"melon": 46, "planted_8": 30}) == ["melon", "planted_8"]


def test_the_identity_stub_switches_all_sixteen_seams_off_and_survives_a_turn():
    from harness.sheep_bench import _seam_names
    names = _seam_names()
    assert len(names) == 18
    cls = mb.off_class()
    for n in names:
        assert n in cls.__dict__, f"seam {n} not switched off"
    off = cls()
    assert off.herd_target(8) is None and off.fertilize_crops() is None
    assert off.HERD_RAMP_F == fp.HERD_RAMP_F and off.CAPS == mb.load_reference().CAPS
    from kaggisim.state import parse
    from kaggle_environments import make
    env = make("kaggriculture", configuration={"seed": 1072, "episodeSteps": 3})
    out = off.act(parse(env.reset()[0].observation))
    assert set(out) >= {"farmer", "hands", "market"}


def test_arm_b_is_cap_11_and_nothing_else():
    from harness.sheep_bench import _seam_names
    from strategies.ten_melon import TenMelonStrategy
    cls = mb.arm_b_class()
    b = cls()
    assert isinstance(b, TenMelonStrategy) and b.CAPS == mb.CAPS_B
    assert set(cls.__dict__) & set(_seam_names()) == set()
