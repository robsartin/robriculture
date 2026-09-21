"""The fert_eight experiment's declared constants and pure parts (#284)."""

from __future__ import annotations

import pytest

from harness import eight_bench as eb
from strategies import field_pace as fp


def test_the_declared_constants():
    assert eb.CONTENDER == "fert_eight" and eb.CHAMPION == "ten_melon" and eb.ARM_B == "from_ten"
    assert eb.SEEDS == tuple(range(1104, 1120)) and eb.CONTROL_SEED == 1104
    assert eb.CHAMPION_BAR == 0.60 and eb.ANCHOR_BAR == 0.90
    assert eb.FERTILIZE_BAR == 100 and eb.STRAWBERRY_FACTOR == 1.5
    assert list(eb.EARLY_DAYS) == list(range(1, 8)) and eb.PLANTED_DAY == 8 and eb.ARM_B_FROM == 10
    assert eb.LONESPEAR.startswith("lonespear")


def test_the_seeds_are_fresh_against_every_range_already_spent():
    spent = set(range(100, 116)) | set(range(200, 216)) | set(range(300, 332)) \
        | set(range(400, 416)) | set(range(500, 516)) | set(range(600, 616)) \
        | set(range(700, 704)) | set(range(800, 960)) | set(range(960, 1104))
    assert not spent & set(eb.SEEDS)


def test_reading_has_the_declared_fields(monkeypatch):
    monkeypatch.setattr(eb, "action_counts", lambda steps, seat: {"FERTILIZE": 160, "WATER": 800})
    monkeypatch.setattr(eb, "units_sold", lambda steps, seat: {"STRAWBERRY": 262, "MELON": 38})
    monkeypatch.setattr(eb, "board_on_day", lambda steps, seat, day: {"tiles": [[{"kind": "PLANT", "crop": "MELON"}] * 26]})
    monkeypatch.setattr(eb, "dawn_cash", lambda steps, seat, days: [104, 175, 632, 912, 1140, 1401, 11])
    assert eb.reading("s", 0) == {"fertilize": 160, "strawberry": 262, "melon": 38, "planted_8": 26,
                                  "dawn_1_7": [104, 175, 632, 912, 1140, 1401, 11]}
    monkeypatch.setattr(eb, "board_on_day", lambda steps, seat, day: None)
    with pytest.raises(ValueError):
        eb.reading("s", 0)


def test_mechanism_failures_name_the_four_bars():
    champ = {"fertilize": 0, "strawberry": 149, "melon": 40, "planted_8": 26, "dawn_1_7": [1, 2, 3, 4, 5, 6, 7]}
    good = {"fertilize": 160, "strawberry": 262, "melon": 38, "planted_8": 26, "dawn_1_7": [1, 2, 3, 4, 5, 6, 7]}
    assert eb.mechanism_failures(good, champ) == []
    assert eb.mechanism_failures({**good, "fertilize": 99}, champ) == ["fertilize"]
    assert eb.mechanism_failures({**good, "strawberry": 223}, champ) == ["strawberry"]
    assert eb.mechanism_failures({**good, "dawn_1_7": [1, 2, 3, 4, 5, 6, 8]}, champ) == ["dawn_1_7"]
    assert eb.mechanism_failures({**good, "planted_8": 25}, champ) == ["planted_8"]
    assert eb.mechanism_failures({**good, "fertilize": 0, "planted_8": 20}, champ) == ["fertilize", "planted_8"]


def test_the_identity_stub_switches_all_sixteen_seams_off_and_survives_a_turn():
    from harness.sheep_bench import _seam_names
    names = _seam_names()
    assert len(names) == 18
    cls = eb.off_class()
    for n in names:
        assert n in cls.__dict__, f"seam {n} not switched off"
    off = cls()
    assert off.fertilize_crops(8) is None and off.fertilizer_stock(8) is None and off.herd_target(8) is None
    assert off.HERD_RAMP_F == fp.HERD_RAMP_F and off.CAPS == eb.load_reference().CAPS
    from kaggisim.state import parse
    from kaggle_environments import make
    env = make("kaggriculture", configuration={"seed": 1104, "episodeSteps": 3})
    out = off.act(parse(env.reset()[0].observation))
    assert set(out) >= {"farmer", "hands", "market"}


def test_arm_b_starts_on_day_ten_and_changes_nothing_else():
    from strategies.fert_eight import FertEightStrategy
    b = eb.arm_b_class()()
    assert isinstance(b, FertEightStrategy) and b.FERT_FROM == 10
    assert b.fertilizer_stock(9) is None and b.fertilizer_stock(10) == 8 and b.fertilize_crops(10) == ("MELON", "STRAWBERRY")
