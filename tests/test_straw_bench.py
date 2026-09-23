"""The free_straw experiment's declared constants and pure parts (#312)."""

from __future__ import annotations

import pytest

from harness import rival_bench as rb
from harness import straw_bench as sb
from strategies import field_pace as fp


def test_the_declared_constants():
    assert sb.CONTENDER == "free_straw" and sb.CHAMPION == "town_split"
    assert sb.SEEDS == tuple(range(1303, 1319)) and sb.CONTROL_SEED == 1303
    assert sb.CHAMPION_BAR == 0.60 and sb.ANCHOR_BAR == 0.90
    assert (sb.TILE_DAY, sb.LATE_DAY) == (16, 20)
    assert sb.LONESPEAR.startswith("lonespear")
    assert sb.criterion is rb.criterion and sb.decided_row is rb.decided_row and rb.MIN_DECIDED == 8


def test_the_seeds_are_fresh_against_every_range_already_spent():
    spent = set(range(100, 116)) | set(range(200, 216)) | set(range(300, 332)) \
        | set(range(400, 416)) | set(range(500, 516)) | set(range(600, 616)) \
        | set(range(700, 704)) | set(range(800, 960)) | set(range(960, 1303))
    assert not spent & set(sb.SEEDS)


def _board(straw, wheat=0, melon=0):
    tiles = [{"kind": "PLANT", "crop": "STRAWBERRY"}] * straw + [{"kind": "PLANT", "crop": "WHEAT"}] * wheat \
        + [{"kind": "PLANT", "crop": "MELON"}] * melon + [None, "LOCKED", {"animal": "COW"}, {"kind": "WEED"}]
    return {"tiles": [tiles]}


def test_reading_and_its_failure(monkeypatch):
    monkeypatch.setattr(sb, "board_on_day", lambda steps, seat, day: {16: _board(42, 0, 3), 20: _board(42, 4)}.get(day))
    monkeypatch.setattr(sb, "decompose", lambda steps, seat: {"revenue": {"STRAWBERRY": 36803, "WHEAT": 892, "MILK": 1}})
    assert sb.reading("s", 0) == {"straw_16": 42, "straw_20": 42, "strawberry": 36803, "wheat": 892}
    monkeypatch.setattr(sb, "board_on_day", lambda steps, seat, day: _board(38) if day == 16 else None)
    assert sb.reading("s", 0)["straw_20"] is None
    monkeypatch.setattr(sb, "board_on_day", lambda steps, seat, day: None)
    with pytest.raises(ValueError):
        sb.reading("s", 0)


def test_mechanism_failures_name_the_bars():
    champ = {"straw_16": 38, "straw_20": 38, "strawberry": 33393, "wheat": 2239}
    good = {"straw_16": 42, "straw_20": 42, "strawberry": 36803, "wheat": 892}
    assert sb.mechanism_failures(good, champ) == []
    assert sb.mechanism_failures({**good, "straw_16": 38}, champ) == ["straw_16"]
    assert sb.mechanism_failures({**good, "strawberry": 33393}, champ) == ["strawberry"]
    assert sb.mechanism_failures({**good, "straw_16": 30, "strawberry": 1}, champ) == ["straw_16", "strawberry"]


def test_the_identity_stub_switches_all_sixteen_seams_off_and_survives_a_turn():
    from harness.sheep_bench import _seam_names
    names = _seam_names()
    assert len(names) == 20
    cls = sb.off_class()
    for n in names:
        assert n in cls.__dict__, f"seam {n} not switched off"
    off = cls()
    assert off.herd_preference({"town": {"unlocked_shops": ["YARN_STORE"]}}) is None and off.herd_target(8) is None
    assert off.HERD_RAMP_F == fp.HERD_RAMP_F and off.CAPS == sb.load_reference().CAPS and "STRAWBERRY" in off.CAPS
    from kaggisim.state import parse
    from kaggle_environments import make
    env = make("kaggriculture", configuration={"seed": 1303, "episodeSteps": 3})
    out = off.act(parse(env.reset()[0].observation))
    assert set(out) >= {"farmer", "hands", "market"}


def test_play_and_the_reference_are_pinned():
    from harness.cashflow import play
    from harness.reserve_bench import MADHUR, PILKWANG, REFERENCE
    assert sb.play is play and sb.REFERENCE == REFERENCE == "dense_farm"
    assert sb.MADHUR == MADHUR and sb.PILKWANG == PILKWANG
