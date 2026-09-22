"""The fert_six experiment's declared constants and pure parts (#282)."""

from __future__ import annotations

import pytest

from harness import six_bench as sb
from strategies import field_pace as fp


def test_the_declared_constants():
    assert sb.CONTENDER == "fert_six" and sb.CHAMPION == "ten_melon" and sb.ARM_B == "from_eight"
    assert sb.SEEDS == tuple(range(1088, 1104)) and sb.CONTROL_SEED == 1088
    assert sb.CHAMPION_BAR == 0.60 and sb.ANCHOR_BAR == 0.90
    assert sb.FERTILIZE_BAR == 100 and sb.STRAWBERRY_FACTOR == 1.5 and list(sb.EARLY_DAYS) == [1, 2, 3, 4, 5]
    assert sb.ARM_B_FROM == 8 and sb.LONESPEAR.startswith("lonespear")


def test_the_seeds_are_fresh_against_every_range_already_spent():
    spent = set(range(100, 116)) | set(range(200, 216)) | set(range(300, 332)) \
        | set(range(400, 416)) | set(range(500, 516)) | set(range(600, 616)) \
        | set(range(700, 704)) | set(range(800, 960)) | set(range(960, 1088))
    assert not spent & set(sb.SEEDS)


def _slot(day, hour, money, action=None, seat_player=0):
    return {"action": action or {"farmer": ["PASS"], "hands": [], "market": []},
            "observation": {"day": day, "hour": hour, "player": seat_player,
                            "farms": [{"money": money, "tiles": []}, {"money": money + 1, "tiles": []}]},
            "reward": 0, "status": "ACTIVE"}


def test_dawn_cash_reads_hour_zero_of_each_day_per_seat():
    steps = [[_slot(0, 0, 3000), _slot(0, 0, 3000, seat_player=1)],
             [_slot(0, 5, 2000), _slot(0, 5, 2000, seat_player=1)],
             [_slot(1, 0, 104), _slot(1, 0, 104, seat_player=1)],
             [_slot(1, 1, 90), _slot(1, 1, 90, seat_player=1)],
             [_slot(2, 0, 175), _slot(2, 0, 175, seat_player=1)]]
    assert sb.dawn_cash(steps, 0, range(0, 4)) == [3000, 104, 175, None]
    assert sb.dawn_cash(steps, 1, range(1, 3)) == [105, 176]


def test_reading_has_the_declared_fields(monkeypatch):
    monkeypatch.setattr(sb, "action_counts", lambda steps, seat: {"FERTILIZE": 170, "WATER": 800})
    monkeypatch.setattr(sb, "units_sold", lambda steps, seat: {"STRAWBERRY": 260, "MELON": 30})
    monkeypatch.setattr(sb, "board_on_day", lambda steps, seat, day: {"tiles": [[{"kind": "PLANT", "crop": "MELON"}] * 20]})
    monkeypatch.setattr(sb, "dawn_cash", lambda steps, seat, days: [104, 175, 632, 912, 1140])
    assert sb.reading("s", 0) == {"fertilize": 170, "strawberry": 260, "melon": 30, "planted_8": 20,
                                  "dawn_1_5": [104, 175, 632, 912, 1140]}
    monkeypatch.setattr(sb, "board_on_day", lambda steps, seat, day: None)
    with pytest.raises(ValueError):
        sb.reading("s", 0)


def test_mechanism_failures_name_the_bars():
    champ = {"fertilize": 0, "strawberry": 149, "melon": 40, "planted_8": 28, "dawn_1_5": [104, 175, 632, 912, 1140]}
    good = {"fertilize": 175, "strawberry": 260, "melon": 30, "planted_8": 20, "dawn_1_5": [104, 175, 632, 912, 1140]}
    assert sb.mechanism_failures(good, champ) == []
    assert sb.mechanism_failures({**good, "fertilize": 99}, champ) == ["fertilize"]
    assert sb.mechanism_failures({**good, "strawberry": 223}, champ) == ["strawberry"]
    assert sb.mechanism_failures({**good, "dawn_1_5": [104, 175, 632, 912, 1100]}, champ) == ["dawn_1_5"]


def test_the_identity_stub_switches_all_sixteen_seams_off_and_survives_a_turn():
    from harness.sheep_bench import _seam_names
    names = _seam_names()
    assert len(names) == 18
    cls = sb.off_class()
    for n in names:
        assert n in cls.__dict__, f"seam {n} not switched off"
    off = cls()
    assert off.fertilize_crops(6) is None and off.fertilizer_stock(6) is None and off.herd_target(8) is None
    assert off.HERD_RAMP_F == fp.HERD_RAMP_F and off.CAPS == sb.load_reference().CAPS
    from kaggisim.state import parse
    from kaggle_environments import make
    env = make("kaggriculture", configuration={"seed": 1088, "episodeSteps": 3})
    out = off.act(parse(env.reset()[0].observation))
    assert set(out) >= {"farmer", "hands", "market"}


def test_arm_b_starts_on_day_eight_and_changes_nothing_else():
    from strategies.fert_six import FertSixStrategy
    b = sb.arm_b_class()()
    assert isinstance(b, FertSixStrategy) and b.FERT_FROM == 8
    assert b.fertilizer_stock(7) is None and b.fertilizer_stock(8) == 8 and b.fertilize_crops(8) == ("MELON", "STRAWBERRY")
