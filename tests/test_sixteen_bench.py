"""The fert_sixteen experiment's declared constants and pure parts (#324)."""

from __future__ import annotations

import pytest

from harness import rival_bench as rb
from harness import sixteen_bench as sb
from strategies import field_pace as fp


def test_the_declared_constants():
    assert sb.CONTENDER == "fert_sixteen" and sb.CHAMPION == "twelve_head" and sb.ARM_B == "from_twelve"
    assert sb.SEEDS == tuple(range(1511, 1527)) and sb.CONTROL_SEED == 1511
    assert sb.CHAMPION_BAR == 0.60 and sb.ANCHOR_BAR == 0.90
    assert (sb.FERTILIZE_BAR, sb.STRAWBERRY_FACTOR, sb.ARM_B_FROM) == (100, 1.5, 12)
    assert list(sb.EARLY_DAYS) == list(range(1, 17))
    assert sb.LONESPEAR.startswith("lonespear")
    from harness.reserve_bench import MADHUR
    assert sb.MADHUR == MADHUR
    assert sb.criterion is rb.criterion and sb.decided_row is rb.decided_row and rb.MIN_DECIDED == 8


def test_the_seeds_are_fresh_against_every_range_already_spent():
    spent = set(range(100, 116)) | set(range(200, 216)) | set(range(300, 332)) \
        | set(range(400, 416)) | set(range(500, 516)) | set(range(600, 616)) \
        | set(range(700, 704)) | set(range(800, 960)) | set(range(960, 1511))
    assert not spent & set(sb.SEEDS)


def test_reading_reads_counts_units_and_dawn_cash(monkeypatch):
    monkeypatch.setattr(sb, "action_counts", lambda steps, seat: {"FERTILIZE": 121, "WATER": 900})
    monkeypatch.setattr(sb, "units_sold", lambda steps, seat: {"STRAWBERRY": 278, "FERTILIZER": 110, "MILK": 1})
    monkeypatch.setattr(sb, "dawn_cash", lambda steps, seat, days: [d * 100 for d in days])
    got = sb.reading("s", 0)
    assert got == {"fertilize": 121, "strawberry": 278, "fertilizer_sold": 110, "dawn_1_16": [d * 100 for d in range(1, 17)]}


def test_mechanism_failures_name_the_bars():
    dawn = [d * 100 for d in range(1, 17)]
    champ = {"fertilize": 0, "strawberry": 167, "fertilizer_sold": 150, "dawn_1_16": dawn}
    good = {"fertilize": 121, "strawberry": 278, "fertilizer_sold": 110, "dawn_1_16": list(dawn)}
    assert sb.mechanism_failures(good, champ) == []
    assert sb.mechanism_failures({**good, "fertilize": 99}, champ) == ["fertilize"]
    assert sb.mechanism_failures({**good, "strawberry": 250}, champ) == ["strawberry"]      # 250 < 1.5 * 167
    assert sb.mechanism_failures({**good, "strawberry": 251}, champ) == []                  # 251 >= 250.5
    assert sb.mechanism_failures({**good, "dawn_1_16": dawn[:-1] + [1]}, champ) == ["dawn_1_16"]
    assert sb.mechanism_failures({**good, "fertilize": 0, "strawberry": 1, "dawn_1_16": []}, champ) == ["fertilize", "strawberry", "dawn_1_16"]


def test_the_identity_stub_switches_all_sixteen_seams_off_and_survives_a_turn():
    from harness.sheep_bench import _seam_names
    names = _seam_names()
    assert len(names) == 21
    cls = sb.off_class()
    for n in names:
        assert n in cls.__dict__, f"seam {n} not switched off"
    off = cls()
    assert off.fertilizer_stock(20) is None and off.fertilize_crops(20) is None and off.herd_target(12) is None
    assert off.HERD_RAMP_F == fp.HERD_RAMP_F and off.CAPS == sb.load_reference().CAPS
    from kaggisim.state import parse
    from kaggle_environments import make
    env = make("kaggriculture", configuration={"seed": 1511, "episodeSteps": 3})
    out = off.act(parse(env.reset()[0].observation))
    assert set(out) >= {"farmer", "hands", "market"}


def test_arm_b_is_the_same_line_from_day_twelve():
    from strategies import fert_six as f6
    from strategies import fert_sixteen as fs
    cls = sb.arm_b_class()
    assert issubclass(cls, fs.FertSixteenStrategy) and cls.__name__ == "FromTwelve" and cls.FERT_FROM == 12
    b = cls()
    assert b.fertilizer_stock(11) is None and b.fertilizer_stock(12) == f6.FERT_STOCK
    assert b.fertilize_crops(11) is None and b.fertilize_crops(12) == f6.FERT_CROPS
    assert fs.FertSixteenStrategy().fertilizer_stock(12) is None
    from strategies import REGISTRY
    assert "from_twelve" not in REGISTRY


def test_play_and_the_reference_are_pinned():
    from harness.cashflow import play
    from harness.reserve_bench import REFERENCE
    assert sb.play is play and sb.REFERENCE == REFERENCE == "dense_farm"
