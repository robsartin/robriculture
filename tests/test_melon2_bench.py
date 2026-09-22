"""The second_melon experiment's declared constants and pure parts (#334)."""

from __future__ import annotations

import pytest

from harness import melon2_bench as mb
from harness import rival_bench as rb
from strategies import field_pace as fp


def test_the_declared_constants():
    assert mb.CONTENDER == "second_melon" and mb.CHAMPION == "fert_sixteen"
    assert mb.SEEDS == tuple(range(1671, 1687)) and mb.CONTROL_SEED == 1671
    assert mb.CHAMPION_BAR == 0.60 and mb.ANCHOR_BAR == 0.90
    assert (mb.MELON_DAY, mb.LATE_DAY, mb.MELON_BAR) == (14, 20, 5)
    assert mb.LONESPEAR.startswith("lonespear")
    assert mb.criterion is rb.criterion and mb.decided_row is rb.decided_row and rb.PAIRED_MAX_SHORTFALL == 1


def test_the_seeds_are_fresh_against_every_range_already_spent():
    spent = set(range(100, 116)) | set(range(200, 216)) | set(range(300, 332)) \
        | set(range(400, 416)) | set(range(500, 516)) | set(range(600, 616)) \
        | set(range(700, 704)) | set(range(800, 960)) | set(range(960, 1671))
    assert not spent & set(mb.SEEDS)


def _board(melon, straw=0):
    return {"tiles": [[{"kind": "PLANT", "crop": "MELON"}] * melon + [{"kind": "PLANT", "crop": "STRAWBERRY"}] * straw + [None, "LOCKED", {"animal": "COW"}]]}


def test_reading_and_its_failure(monkeypatch):
    monkeypatch.setattr(mb, "board_on_day", lambda steps, seat, day: {14: _board(7, 30), 20: _board(7, 35)}.get(day))
    monkeypatch.setattr(mb, "units_sold", lambda steps, seat: {"MELON": 62, "STRAWBERRY": 250})
    assert mb.reading("s", 0) == {"melon_14": 7, "melon_20": 7, "melon_units": 62, "strawberry_units": 250}
    monkeypatch.setattr(mb, "board_on_day", lambda steps, seat, day: _board(0, 40) if day == 14 else None)
    assert mb.reading("s", 0)["melon_20"] is None
    monkeypatch.setattr(mb, "board_on_day", lambda steps, seat, day: None)
    with pytest.raises(ValueError):
        mb.reading("s", 0)


def test_mechanism_failures_name_the_bars():
    champ = {"melon_14": 0, "melon_20": 0, "melon_units": 40, "strawberry_units": 271}
    good = {"melon_14": 7, "melon_20": 7, "melon_units": 62, "strawberry_units": 250}
    assert mb.mechanism_failures(good, champ) == []
    assert mb.mechanism_failures({**good, "melon_14": 4}, champ) == ["melon_14"]                 # < MELON_BAR
    assert mb.mechanism_failures({**good, "melon_14": 6}, {**champ, "melon_14": 6}) == ["melon_14"]  # not > champion's
    assert mb.mechanism_failures({**good, "melon_units": 40}, champ) == ["melon_units"]
    assert mb.mechanism_failures({**good, "melon_14": 0, "melon_units": 1}, champ) == ["melon_14", "melon_units"]


def test_the_identity_stub_switches_all_eighteen_seams_off_and_survives_a_turn():
    from harness.sheep_bench import _seam_names
    names = _seam_names()
    assert len(names) == 18 and "melon_windows" in names
    cls = mb.off_class()
    for n in names:
        assert n in cls.__dict__, f"seam {n} not switched off"
    off = cls()
    assert off.melon_windows() is None and off.fertilize_crops(20) is None and off.herd_target(12) is None
    assert off.HERD_RAMP_F == fp.HERD_RAMP_F and off.CAPS == mb.load_reference().CAPS
    from kaggisim.state import parse
    from kaggle_environments import make
    env = make("kaggriculture", configuration={"seed": 1671, "episodeSteps": 3})
    out = off.act(parse(env.reset()[0].observation))
    assert set(out) >= {"farmer", "hands", "market"}


def test_play_and_the_reference_are_pinned():
    from harness.cashflow import play
    from harness.reserve_bench import MADHUR, REFERENCE
    assert mb.play is play and mb.REFERENCE == REFERENCE == "dense_farm" and mb.MADHUR == MADHUR
