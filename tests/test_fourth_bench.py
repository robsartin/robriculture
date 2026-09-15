"""The four_herders experiment's declared constants and pure parts (#289)."""

from __future__ import annotations

import pytest

from harness import fourth_bench as fb
from strategies import field_pace as fp


def test_the_declared_constants():
    assert fb.CONTENDER == "four_herders" and fb.CHAMPION == "ten_melon" and fb.ARM_B == "from_eight"
    assert fb.SEEDS == tuple(range(1122, 1138)) and fb.CONTROL_SEED == 1122
    assert fb.CHAMPION_BAR == 0.60 and fb.ANCHOR_BAR == 0.90
    assert (fb.PLACED_DAY, fb.PLACED_BAR, fb.PENDING_DAYS, fb.PLANTED_DAY, fb.ARM_B_FROM) == (14, 12, (14, 20), 16, 8)
    assert fb.LONESPEAR.startswith("lonespear")


def test_the_seeds_are_fresh_against_every_range_already_spent():
    spent = set(range(100, 116)) | set(range(200, 216)) | set(range(300, 332)) \
        | set(range(400, 416)) | set(range(500, 516)) | set(range(600, 616)) \
        | set(range(700, 704)) | set(range(800, 960)) | set(range(960, 1122))
    assert not spent & set(fb.SEEDS)


def _slot(day, hour, shed, seat_player=0):
    return {"action": {"farmer": ["PASS"], "hands": [], "market": []},
            "observation": {"day": day, "hour": hour, "player": seat_player,
                            "farms": [{"money": 0, "tiles": []}, {"money": 0, "tiles": []}],
                            "private": {"shed": shed}},
            "reward": 0, "status": "ACTIVE"}


def test_pending_at_reads_the_last_observation_of_the_day():
    steps = [[_slot(14, 0, {"COW": 1}), _slot(14, 0, {"SHEEP": 9}, 1)],
             [_slot(14, 23, {"COW": 3, "SHEEP": 1, "WHEAT": 5}), _slot(14, 23, {}, 1)],
             [_slot(15, 0, {"COW": 0}), _slot(15, 0, {}, 1)]]
    assert fb.pending_at(steps, 0, 14) == 4 and fb.pending_at(steps, 1, 14) == 0
    assert fb.pending_at(steps, 0, 15) == 0 and fb.pending_at(steps, 0, 20) is None


def _board(n_animals, n_plants=0):
    return {"tiles": [[{"animal": "COW"}] * n_animals + [{"kind": "PLANT", "crop": "MELON"}] * n_plants]}


def test_reading_and_its_failure(monkeypatch):
    monkeypatch.setattr(fb, "board_on_day", lambda steps, seat, day: {14: _board(12), 16: _board(12, 44)}.get(day))
    monkeypatch.setattr(fb, "units_sold", lambda steps, seat: {"MILK": 207, "WOOL": 96})
    monkeypatch.setattr(fb, "pending_at", lambda steps, seat, day: {14: 4, 20: 4}[day])
    assert fb.reading("s", 0) == {"placed_14": 12, "milk": 207, "pending": {14: 4, 20: 4}, "planted_16": 44}
    monkeypatch.setattr(fb, "board_on_day", lambda steps, seat, day: None)
    with pytest.raises(ValueError):
        fb.reading("s", 0)


def test_mechanism_failures_name_the_bars():
    champ = {"placed_14": 11, "milk": 177, "pending": {14: 5, 20: 5}, "planted_16": 47}
    good = {"placed_14": 12, "milk": 207, "pending": {14: 4, 20: 4}, "planted_16": 44}
    assert fb.mechanism_failures(good, champ) == []
    assert fb.mechanism_failures({**good, "placed_14": 11}, champ) == ["placed_14"]
    assert fb.mechanism_failures({**good, "milk": 177}, champ) == ["milk"]
    assert fb.mechanism_failures({**good, "placed_14": 12}, {**champ, "placed_14": 13}) == ["placed_14"]


def test_the_identity_stub_switches_all_sixteen_seams_off_and_survives_a_turn():
    from harness.sheep_bench import _seam_names
    names = _seam_names()
    assert len(names) == 16
    cls = fb.off_class()
    for n in names:
        assert n in cls.__dict__, f"seam {n} not switched off"
    off = cls()
    assert off.livestock_workers(12) is None and off.herd_target(8) is None
    assert off.HERD_RAMP_F == fp.HERD_RAMP_F and off.CAPS == fb.load_reference().CAPS
    from kaggisim.state import parse
    from kaggle_environments import make
    env = make("kaggriculture", configuration={"seed": 1122, "episodeSteps": 3})
    out = off.act(parse(env.reset()[0].observation))
    assert set(out) >= {"farmer", "hands", "market"}


def test_arm_b_starts_on_day_eight_and_changes_nothing_else():
    from strategies.four_herders import FourHerdersStrategy
    b = fb.arm_b_class()()
    assert isinstance(b, FourHerdersStrategy) and b.FOURTH_DAY == 8
    assert b.livestock_workers(7) is None and b.livestock_workers(8) == (1, 2, 6, 7)
