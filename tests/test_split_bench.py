"""The town_split experiment's declared constants and pure parts (#305)."""

from __future__ import annotations

import pytest

from harness import rival_bench as rb
from harness import split_bench as sb
from strategies import field_pace as fp


def test_the_declared_constants():
    assert sb.CONTENDER == "town_split" and sb.CHAMPION == "four_at_eight" and sb.ARM_B == "even_split"
    assert sb.SEEDS == tuple(range(1191, 1223)) and sb.IDENTITY_SEED == 1191
    assert sb.CHAMPION_BAR == 0.60 and sb.ANCHOR_BAR == 0.90
    assert (sb.KIND_DAY, sb.HEAD_DAY, sb.COWS_BAR) == (12, 14, 3)
    assert sb.LONESPEAR.startswith("lonespear")
    assert sb.criterion is rb.criterion and sb.decided_row is rb.decided_row and rb.MIN_DECIDED == 8


def test_the_seeds_are_fresh_against_every_range_already_spent():
    spent = set(range(100, 116)) | set(range(200, 216)) | set(range(300, 332)) \
        | set(range(400, 416)) | set(range(500, 516)) | set(range(600, 616)) \
        | set(range(700, 704)) | set(range(800, 960)) | set(range(960, 1191))
    assert not spent & set(sb.SEEDS)


def test_even_share_is_half_when_both_drains_exist():
    assert sb.even_share(["YARN_STORE", "PIZZA_SHOP"]) == 0.5
    assert sb.even_share(["YARN_STORE", "YARN_STORE", "PIZZA_SHOP", "SMOOTHIE_SHOP", "ICE_CREAM_SHOP"]) == 0.5
    assert sb.even_share(["YARN_STORE"]) == 1.0 and sb.even_share(["PIZZA_SHOP"]) == 0.0
    assert sb.even_share(["BAKERY"]) is None and sb.even_share([]) is None


def test_is_split_town_needs_both_drains():
    assert sb.is_split_town(0.5) and sb.is_split_town(2 / 3) and sb.is_split_town(0.01)
    assert not sb.is_split_town(1.0) and not sb.is_split_town(0.0) and not sb.is_split_town(None)


def _board(cows, sheep):
    return {"tiles": [[{"animal": "COW"}] * cows + [{"animal": "SHEEP"}] * sheep + [None, "LOCKED"]]}


def test_reading_and_its_failure(monkeypatch):
    monkeypatch.setattr(sb, "town_on_day", lambda steps, seat, day: ["BAKERY", "YARN_STORE", "SMOOTHIE_SHOP", "FARMERS_MARKET"])
    monkeypatch.setattr(sb, "board_on_day", lambda steps, seat, day: _board(4, 8) if day == 14 else None)
    monkeypatch.setattr(sb, "decompose", lambda steps, seat: {"revenue": {"MILK": 9000, "WOOL": 30000}})
    got = sb.reading("s", 0)
    assert got["share_12"] == pytest.approx(2 / 3)
    assert got["shops_12"] == ("BAKERY", "YARN_STORE", "SMOOTHIE_SHOP", "FARMERS_MARKET")
    assert (got["cows_14"], got["sheep_14"], got["milk"], got["wool"]) == (4, 8, 9000, 30000)
    monkeypatch.setattr(sb, "board_on_day", lambda steps, seat, day: None)
    with pytest.raises(ValueError):
        sb.reading("s", 0)
    monkeypatch.setattr(sb, "board_on_day", lambda steps, seat, day: _board(4, 8))
    monkeypatch.setattr(sb, "town_on_day", lambda steps, seat, day: None)
    with pytest.raises(ValueError):
        sb.reading("s", 0)


def test_control_game_is_the_first_seed_with_a_split_town(monkeypatch):
    shares = {1191: 1.0, 1192: None, 1193: 0.4, 1194: 0.5}
    monkeypatch.setattr(sb, "reading", lambda steps, seat: {"share_12": shares[steps]})
    played = []

    def play(contender, champion, seed):
        played.append((contender, champion, seed))
        return seed
    assert sb.control_game((1191, 1192, 1193, 1194), play=play) == (1193, 1193)
    assert played == [("town_split", "four_at_eight", 1191), ("town_split", "four_at_eight", 1192),
                      ("town_split", "four_at_eight", 1193)]
    assert sb.control_game((1191, 1192), play=play) is None


def test_mechanism_failures_name_the_bars():
    champ = {"share_12": 2 / 3, "shops_12": (), "cows_14": 9, "sheep_14": 3, "milk": 40000, "wool": 20000}
    good = {"share_12": 2 / 3, "shops_12": (), "cows_14": 4, "sheep_14": 8, "milk": 15000, "wool": 45000}
    assert sb.mechanism_failures(good, champ) == []
    assert sb.mechanism_failures({**good, "sheep_14": 3}, champ) == ["sheep_14"]
    assert sb.mechanism_failures({**good, "cows_14": 2}, champ) == ["cows_14"]
    assert sb.mechanism_failures({**good, "cows_14": 3}, champ) == []
    assert sb.mechanism_failures({**good, "wool": 20000}, champ) == ["wool"]
    assert sb.mechanism_failures({**good, "sheep_14": 1, "cows_14": 1, "wool": 1}, champ) == ["sheep_14", "cows_14", "wool"]


def test_the_identity_stub_switches_all_sixteen_seams_off_and_survives_a_turn():
    from harness.sheep_bench import _seam_names
    names = _seam_names()
    assert len(names) == 16
    cls = sb.off_class()
    for n in names:
        assert n in cls.__dict__, f"seam {n} not switched off"
    off = cls()
    assert off.herd_preference({"town": {"unlocked_shops": ["YARN_STORE"]}}) is None and off.herd_target(8) is None
    assert off.HERD_RAMP_F == fp.HERD_RAMP_F and off.CAPS == sb.load_reference().CAPS
    from kaggisim.state import parse
    from kaggle_environments import make
    env = make("kaggriculture", configuration={"seed": 1191, "episodeSteps": 3})
    out = off.act(parse(env.reset()[0].observation))
    assert set(out) >= {"farmer", "hands", "market"}


def test_arm_b_uses_the_even_share():
    from strategies import town_split as ts
    cls = sb.arm_b_class()
    assert issubclass(cls, ts.TownSplitStrategy) and cls.__name__ == "EvenSplit"
    b = cls()
    assert b.sheep_share(["YARN_STORE", "PIZZA_SHOP", "PIZZA_SHOP", "PIZZA_SHOP"]) == 0.5
    assert ts.TownSplitStrategy().sheep_share(["YARN_STORE", "PIZZA_SHOP", "PIZZA_SHOP", "PIZZA_SHOP"]) == pytest.approx(0.4)
    from strategies import REGISTRY
    assert "even_split" not in REGISTRY


def test_play_and_the_reference_are_pinned():
    from harness.cashflow import play
    from harness.reserve_bench import MADHUR, PILKWANG, REFERENCE
    assert sb.play is play and sb.REFERENCE == REFERENCE == "dense_farm"
    assert sb.MADHUR == MADHUR and sb.PILKWANG == PILKWANG
