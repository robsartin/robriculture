"""The twelve_head experiment's declared constants and pure parts (#320)."""

from __future__ import annotations

import pytest

from harness import rival_bench as rb
from harness import twelve_bench as tb
from strategies import field_pace as fp
from strategies import twelve_head as th


def test_the_declared_constants():
    assert tb.CONTENDER == "twelve_head" and tb.CHAMPION == "free_straw"
    assert tb.SEEDS == tuple(range(1463, 1479)) and tb.CONTROL_SEED == 1463
    assert tb.CHAMPION_BAR == 0.60 and tb.ANCHOR_BAR == 0.90 and tb.HEAD_DAY == 20
    assert tb.LONESPEAR.startswith("lonespear")
    assert tb.criterion is rb.criterion and tb.decided_row is rb.decided_row and rb.MIN_DECIDED == 8


def test_the_seeds_are_fresh_against_every_range_already_spent():
    spent = set(range(100, 116)) | set(range(200, 216)) | set(range(300, 332)) \
        | set(range(400, 416)) | set(range(500, 516)) | set(range(600, 616)) \
        | set(range(700, 704)) | set(range(800, 960)) | set(range(960, 1463))
    assert not spent & set(tb.SEEDS)


def _board(cows, sheep):
    return {"tiles": [[{"animal": "COW"}] * cows + [{"animal": "SHEEP"}] * sheep + [None, "LOCKED", {"kind": "PLANT", "crop": "STRAWBERRY"}]]}


def test_reading_and_its_failure(monkeypatch):
    monkeypatch.setattr(tb, "board_on_day", lambda steps, seat, day: _board(9, 3) if day == 20 else None)
    monkeypatch.setattr(tb, "pending_at", lambda steps, seat, day: {20: 0}[day])
    monkeypatch.setattr(tb, "decompose", lambda steps, seat: {"revenue": {"MILK": 30000, "WOOL": 12000, "STRAWBERRY": 1},
                                                              "spend": {"animal": 6300, "seed": 1}})
    assert tb.reading("s", 0) == {"head_20": 12, "pending_20": 0, "animal_spend": 6300, "milk_wool": 42000}
    monkeypatch.setattr(tb, "board_on_day", lambda steps, seat, day: None)
    with pytest.raises(ValueError):
        tb.reading("s", 0)


def test_mechanism_failures_name_the_bars():
    champ = {"head_20": 12, "pending_20": 1, "animal_spend": 6700, "milk_wool": 42000}
    good = {"head_20": 12, "pending_20": 0, "animal_spend": 6300, "milk_wool": 42500}
    assert tb.mechanism_failures(good, champ) == []
    assert tb.mechanism_failures({**good, "pending_20": 1}, champ) == ["pending_20"]
    assert tb.mechanism_failures({**good, "animal_spend": 6700}, champ) == ["animal_spend"]
    assert tb.mechanism_failures({**good, "pending_20": 2, "animal_spend": 7000}, champ) == ["pending_20", "animal_spend"]


def test_the_identity_stub_switches_all_sixteen_seams_off_and_survives_a_turn():
    from harness.sheep_bench import _seam_names
    names = _seam_names()
    assert len(names) == 21
    cls = tb.off_class()
    for n in names:
        assert n in cls.__dict__, f"seam {n} not switched off"
    off = cls()
    assert off.herd_target(12) is None and off.herd_preference({"town": {"unlocked_shops": ["YARN_STORE"]}}) is None
    assert off.HERD_RAMP_F == fp.HERD_RAMP_F and off.HERD_RAMP_F is not th.HERD_RAMP_T
    assert off.CAPS == tb.load_reference().CAPS and "STRAWBERRY" in off.CAPS
    from kaggisim.state import parse
    from kaggle_environments import make
    env = make("kaggriculture", configuration={"seed": 1463, "episodeSteps": 3})
    out = off.act(parse(env.reset()[0].observation))
    assert set(out) >= {"farmer", "hands", "market"}


def test_play_and_the_reference_are_pinned():
    from harness.cashflow import play
    from harness.reserve_bench import MADHUR, PILKWANG, REFERENCE
    assert tb.play is play and tb.REFERENCE == REFERENCE == "dense_farm"
    assert tb.MADHUR == MADHUR and tb.PILKWANG == PILKWANG
