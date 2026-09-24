"""The town_herd experiment's declared constants and pure parts (#302)."""

from __future__ import annotations

import pytest

from harness import rival_bench as rb
from harness import town_bench as tb
from strategies import field_pace as fp


def test_the_declared_constants():
    assert tb.CONTENDER == "town_herd" and tb.CHAMPION == "four_at_eight" and tb.ARM_B == "shop_count"
    assert tb.SEEDS == tuple(range(1171, 1187)) and tb.CONTROL_SEED == 1174
    assert tb.CHAMPION_BAR == 0.60 and tb.ANCHOR_BAR == 0.90
    assert (tb.KIND_DAY, tb.HEAD_DAY) == (12, 14)
    assert tb.LONESPEAR.startswith("lonespear")
    assert tb.criterion is rb.criterion and rb.PAIRED_FLOOR_WINS == 1


def test_the_seeds_are_fresh_against_every_range_already_spent():
    spent = set(range(100, 116)) | set(range(200, 216)) | set(range(300, 332)) \
        | set(range(400, 416)) | set(range(500, 516)) | set(range(600, 616)) \
        | set(range(700, 704)) | set(range(800, 960)) | set(range(960, 1171))
    assert not spent & set(tb.SEEDS)


def _slot(day, hour, shops, seat_player=0):
    return {"action": {"farmer": ["PASS"], "hands": [], "market": []},
            "observation": {"day": day, "hour": hour, "player": seat_player,
                            "farms": [{"money": 0, "tiles": []}, {"money": 0, "tiles": []}],
                            "town": {"unlocked_shops": shops}, "private": {"shed": {}}},
            "reward": 0, "status": "ACTIVE"}


def test_town_on_day_reads_the_last_observation_of_the_day():
    steps = [[_slot(12, 0, ["YARN_STORE"]), _slot(12, 0, ["YARN_STORE"], 1)],
             [_slot(12, 23, ["YARN_STORE", "PIZZA_SHOP"]), _slot(12, 23, ["YARN_STORE", "PIZZA_SHOP"], 1)],
             [_slot(13, 0, ["YARN_STORE", "PIZZA_SHOP"]), _slot(13, 0, ["YARN_STORE", "PIZZA_SHOP"], 1)]]
    assert tb.town_on_day(steps, 0, 12) == ["YARN_STORE", "PIZZA_SHOP"]
    assert tb.town_on_day(steps, 1, 13) == ["YARN_STORE", "PIZZA_SHOP"]
    assert tb.town_on_day(steps, 0, 20) is None


def _board(cows, sheep):
    return {"tiles": [[{"animal": "COW"}] * cows + [{"animal": "SHEEP"}] * sheep + [None, "LOCKED"]]}


def test_reading_and_its_failure(monkeypatch):
    monkeypatch.setattr(tb, "town_on_day", lambda steps, seat, day: ["PET_CAFE", "YARN_STORE", "YARN_STORE", "PIZZA_SHOP"])
    monkeypatch.setattr(tb, "board_on_day", lambda steps, seat, day: _board(4, 8) if day == 14 else None)
    monkeypatch.setattr(tb, "decompose", lambda steps, seat: {"revenue": {"MILK": 9000, "WOOL": 30000}})
    assert tb.reading("s", 0) == {"favoured": "SHEEP", "shops_12": ("PET_CAFE", "YARN_STORE", "YARN_STORE", "PIZZA_SHOP"),
                                  "cows_14": 4, "sheep_14": 8, "milk": 9000, "wool": 30000}
    monkeypatch.setattr(tb, "board_on_day", lambda steps, seat, day: None)
    with pytest.raises(ValueError):
        tb.reading("s", 0)
    monkeypatch.setattr(tb, "board_on_day", lambda steps, seat, day: _board(4, 8))
    monkeypatch.setattr(tb, "town_on_day", lambda steps, seat, day: None)
    with pytest.raises(ValueError):
        tb.reading("s", 0)


def test_mechanism_failures_name_the_bars_of_the_favoured_kind():
    champ = {"favoured": "SHEEP", "shops_12": (), "cows_14": 9, "sheep_14": 3, "milk": 30000, "wool": 12000}
    good = {"favoured": "SHEEP", "shops_12": (), "cows_14": 4, "sheep_14": 8, "milk": 9000, "wool": 30000}
    assert tb.mechanism_failures(good, champ) == []
    assert tb.mechanism_failures({**good, "sheep_14": 3}, champ) == ["sheep_14"]
    assert tb.mechanism_failures({**good, "wool": 12000}, champ) == ["wool"]
    assert tb.mechanism_failures({**good, "sheep_14": 2, "wool": 1}, champ) == ["sheep_14", "wool"]
    cow_champ = {**champ, "favoured": "COW"}
    assert tb.mechanism_failures({**good, "favoured": "COW", "cows_14": 10, "milk": 31000}, cow_champ) == []
    assert tb.mechanism_failures({**good, "favoured": "COW"}, cow_champ) == ["cows_14", "milk"]
    assert tb.mechanism_failures({**good, "favoured": None}, champ) == ["favoured"]


def test_the_identity_stub_switches_all_sixteen_seams_off_and_survives_a_turn():
    from harness.sheep_bench import _seam_names
    names = _seam_names()
    assert len(names) == 21
    cls = tb.off_class()
    for n in names:
        assert n in cls.__dict__, f"seam {n} not switched off"
    off = cls()
    assert off.herd_preference({"town": {"unlocked_shops": ["YARN_STORE"]}}) is None and off.herd_target(8) is None
    assert off.HERD_RAMP_F == fp.HERD_RAMP_F and off.CAPS == tb.load_reference().CAPS
    from kaggisim.state import parse
    from kaggle_environments import make
    env = make("kaggriculture", configuration={"seed": 1174, "episodeSteps": 3})
    out = off.act(parse(env.reset()[0].observation))
    assert set(out) >= {"farmer", "hands", "market"}


def test_arm_b_ignores_owned_head():
    from strategies import town_herd as th
    cls = tb.arm_b_class()
    assert issubclass(cls, th.TownHerdStrategy) and cls.__name__ == "ShopCount"
    b = cls()
    obs = {"player": 0, "farms": [{"tiles": [[{"animal": "SHEEP"}] * 40]}, {"tiles": []}],
           "private": {"shed": {"SHEEP": 5}}, "town": {"unlocked_shops": ["YARN_STORE", "PIZZA_SHOP"]}}
    assert b.owned(obs) == (0, 0)
    assert b.herd_preference(obs) == "SHEEP" and th.TownHerdStrategy().herd_preference(obs) == "COW"
    from strategies import REGISTRY
    assert "shop_count" not in REGISTRY


def test_play_and_the_reference_are_pinned():
    from harness.cashflow import play
    from harness.reserve_bench import MADHUR, PILKWANG, REFERENCE
    assert tb.play is play and tb.REFERENCE == REFERENCE == "dense_farm"
    assert tb.MADHUR == MADHUR and tb.PILKWANG == PILKWANG
