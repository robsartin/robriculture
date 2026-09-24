"""The even_split experiment's declared constants and pure parts (#310)."""

from __future__ import annotations

import pytest

from harness import even_bench as eb
from harness import rival_bench as rb
from strategies import field_pace as fp


def test_the_declared_constants():
    assert eb.CONTENDER == "even_split" and eb.CHAMPION == "town_split" and eb.ARM_B == "half_always"
    assert eb.SEEDS == tuple(range(1223, 1271)) and eb.IDENTITY_SEED == 1223
    assert eb.CHAMPION_BAR == 0.60 and eb.ANCHOR_BAR == 0.90
    assert (eb.KIND_DAY, eb.HEAD_DAY, eb.BALANCE_BAR) == (12, 14, 2)
    assert eb.LONESPEAR.startswith("lonespear")
    assert eb.criterion is rb.criterion and eb.decided_row is rb.decided_row and rb.MIN_DECIDED == 8


def test_the_seeds_are_fresh_against_every_range_already_spent():
    spent = set(range(100, 116)) | set(range(200, 216)) | set(range(300, 332)) \
        | set(range(400, 416)) | set(range(500, 516)) | set(range(600, 616)) \
        | set(range(700, 704)) | set(range(800, 960)) | set(range(960, 1223))
    assert not spent & set(eb.SEEDS)


def test_half_share_is_a_half_whenever_there_is_a_yarn_store():
    assert eb.half_share(["YARN_STORE"]) == 0.5 and eb.half_share(["YARN_STORE", "PIZZA_SHOP"]) == 0.5
    assert eb.half_share(["PIZZA_SHOP"]) == 0.0
    assert eb.half_share(["BAKERY"]) is None and eb.half_share([]) is None


def test_is_uneven_town_needs_both_drains_and_an_unequal_share():
    assert eb.is_uneven_town(2 / 3) and eb.is_uneven_town(0.4) and eb.is_uneven_town(0.8)
    assert not eb.is_uneven_town(0.5) and not eb.is_uneven_town(1.0) and not eb.is_uneven_town(0.0)
    assert not eb.is_uneven_town(None)


def _board(cows, sheep):
    return {"tiles": [[{"animal": "COW"}] * cows + [{"animal": "SHEEP"}] * sheep + [None, "LOCKED"]]}


def test_reading_and_its_failure(monkeypatch):
    monkeypatch.setattr(eb, "town_on_day", lambda steps, seat, day: ["YARN_STORE", "SMOOTHIE_SHOP", "SMOOTHIE_SHOP", "ICE_CREAM_SHOP"])
    monkeypatch.setattr(eb, "board_on_day", lambda steps, seat, day: _board(6, 6) if day == 14 else None)
    monkeypatch.setattr(eb, "decompose", lambda steps, seat: {"revenue": {"MILK": 30000, "WOOL": 35000}})
    got = eb.reading("s", 0)
    assert got["share_12"] == pytest.approx(0.4) and got["even_12"] == 0.5
    assert got["shops_12"] == ("YARN_STORE", "SMOOTHIE_SHOP", "SMOOTHIE_SHOP", "ICE_CREAM_SHOP")
    assert (got["cows_14"], got["sheep_14"], got["balance_14"], got["milk"], got["wool"]) == (6, 6, 0, 30000, 35000)
    monkeypatch.setattr(eb, "board_on_day", lambda steps, seat, day: _board(9, 3))
    assert eb.reading("s", 0)["balance_14"] == 6
    monkeypatch.setattr(eb, "board_on_day", lambda steps, seat, day: None)
    with pytest.raises(ValueError):
        eb.reading("s", 0)
    monkeypatch.setattr(eb, "board_on_day", lambda steps, seat, day: _board(6, 6))
    monkeypatch.setattr(eb, "town_on_day", lambda steps, seat, day: None)
    with pytest.raises(ValueError):
        eb.reading("s", 0)


def test_control_game_is_the_first_seed_with_an_uneven_town(monkeypatch):
    shares = {1223: 1.0, 1224: 0.5, 1225: None, 1226: 0.4, 1227: 2 / 3}
    monkeypatch.setattr(eb, "reading", lambda steps, seat: {"share_12": shares[steps]})
    played = []

    def play(contender, champion, seed):
        played.append((contender, champion, seed))
        return seed
    assert eb.control_game((1223, 1224, 1225, 1226, 1227), play=play) == (1226, 1226)
    assert played == [("even_split", "town_split", s) for s in (1223, 1224, 1225, 1226)]
    assert eb.control_game((1223, 1224, 1225), play=play) is None


def test_mechanism_failures_name_the_bars():
    champ = {"share_12": 0.4, "even_12": 0.5, "shops_12": (), "cows_14": 7, "sheep_14": 5, "balance_14": 2, "milk": 1, "wool": 1}
    good = {**champ, "cows_14": 6, "sheep_14": 6, "balance_14": 0}
    assert eb.mechanism_failures(good, champ) == []
    assert eb.mechanism_failures({**good, "balance_14": 1}, champ) == []
    assert eb.mechanism_failures({**good, "balance_14": 2}, champ) == ["balance_vs_champion"]
    assert eb.mechanism_failures({**good, "balance_14": 3}, {**champ, "balance_14": 6}) == ["balance"]
    assert eb.mechanism_failures({**good, "balance_14": 4}, {**champ, "balance_14": 2}) == ["balance", "balance_vs_champion"]


def test_the_identity_stub_switches_all_sixteen_seams_off_and_survives_a_turn():
    from harness.sheep_bench import _seam_names
    names = _seam_names()
    assert len(names) == 21
    cls = eb.off_class()
    for n in names:
        assert n in cls.__dict__, f"seam {n} not switched off"
    off = cls()
    assert off.herd_preference({"town": {"unlocked_shops": ["YARN_STORE", "PIZZA_SHOP"]}}) is None and off.herd_target(8) is None
    assert off.HERD_RAMP_F == fp.HERD_RAMP_F and off.CAPS == eb.load_reference().CAPS
    from kaggisim.state import parse
    from kaggle_environments import make
    env = make("kaggriculture", configuration={"seed": 1223, "episodeSteps": 3})
    out = off.act(parse(env.reset()[0].observation))
    assert set(out) >= {"farmer", "hands", "market"}


def test_arm_b_uses_half_share():
    from strategies import even_split as es
    cls = eb.arm_b_class()
    assert issubclass(cls, es.EvenSplitStrategy) and cls.__name__ == "HalfAlways"
    b = cls()
    assert b.sheep_share(["YARN_STORE"]) == 0.5 and es.EvenSplitStrategy().sheep_share(["YARN_STORE"]) == 1.0
    assert b.sheep_share(["PIZZA_SHOP"]) == 0.0 and b.sheep_share(["BAKERY"]) is None
    from strategies import REGISTRY
    assert "half_always" not in REGISTRY


def test_play_and_the_reference_are_pinned():
    from harness.cashflow import play
    from harness.reserve_bench import MADHUR, PILKWANG, REFERENCE
    assert eb.play is play and eb.REFERENCE == REFERENCE == "dense_farm"
    assert eb.MADHUR == MADHUR and eb.PILKWANG == PILKWANG
