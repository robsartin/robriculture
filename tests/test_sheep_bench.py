"""The sheep_first experiment's declared constants and pure parts (#268)."""

from __future__ import annotations

from harness import sheep_bench as sb
from strategies import field_rival as fr


def test_the_declared_constants():
    assert sb.CONTENDER == "sheep_first" and sb.CHAMPION == "lean_feed"
    assert sb.SEEDS == tuple(range(992, 1008)) and sb.CONTROL_SEED == 992
    assert sb.CHAMPION_BAR == 0.60 and sb.ANCHOR_BAR == 0.90 and sb.ARM_B == "drop_rule"
    assert (sb.SHEEP_DAY, sb.SHEEP_BAR, sb.SHEEP_DAY_16, sb.SHEEP_BAR_16) == (8, 4, 16, 6)
    assert sb.LONESPEAR == "lonespear_kaggriculture_v21" and sb.PILKWANG.startswith("pilkwang")


def test_the_seeds_are_fresh_against_every_range_already_spent():
    spent = set(range(100, 116)) | set(range(200, 216)) | set(range(300, 332)) \
        | set(range(400, 416)) | set(range(500, 516)) | set(range(600, 616)) \
        | set(range(700, 704)) | set(range(800, 960)) | set(range(960, 992))
    assert not spent & set(sb.SEEDS)


def _tile(animal=None):
    return {"animal": animal} if animal else {"kind": "WEED"}


def test_sheep_reading_reads_the_boards_and_the_revenue(monkeypatch):
    boards = {8: {"tiles": [[_tile("SHEEP"), _tile("SHEEP"), _tile("COW"), _tile()]]},
              16: {"tiles": [[_tile("SHEEP")] * 6 + [_tile("COW")] * 5]}}
    monkeypatch.setattr(sb, "board_on_day", lambda steps, seat, day: boards[day])
    monkeypatch.setattr(sb, "decompose", lambda steps, seat: {"revenue": {"WOOL": 21000, "MILK": 30000}, "spend": {}, "actions": {}, "final_money": 0, "residual": 0})
    assert sb.sheep_reading("steps", 0) == {"sheep_8": 2, "sheep_16": 6, "cows_16": 5, "wool": 21000, "milk": 30000}


def test_sheep_reading_raises_when_a_declared_day_was_never_reached(monkeypatch):
    monkeypatch.setattr(sb, "board_on_day", lambda steps, seat, day: None)
    import pytest
    with pytest.raises(ValueError):
        sb.sheep_reading("steps", 0)


def test_mechanism_failures_name_the_bars():
    good = {"sheep_8": 4, "sheep_16": 6, "cows_16": 5, "wool": 25000, "milk": 1}
    champ = {"sheep_8": 3, "sheep_16": 3, "cows_16": 8, "wool": 12000, "milk": 1}
    assert sb.mechanism_failures(good, champ) == []
    assert sb.mechanism_failures({**good, "sheep_8": 3}, champ) == ["sheep_8"]
    assert sb.mechanism_failures({**good, "sheep_16": 5, "wool": 12000}, champ) == ["sheep_16", "wool"]


def test_the_identity_stub_switches_every_seam_off_and_survives_a_turn():
    seams = [n for n in dir(fr.FieldRivalStrategy)
             if callable(getattr(fr.FieldRivalStrategy, n)) and not n.startswith("_") and n != "act"
             and getattr(fr.FieldRivalStrategy, n).__doc__ and "seam" in getattr(fr.FieldRivalStrategy, n).__doc__.lower()]
    cls = sb.off_class()
    off = cls()
    for n in seams:
        assert n in cls.__dict__, f"seam {n} not switched off"
    assert off.herd_preference({}) is None and off.feed_stock(4) is None and off.layout() is None
    assert off.CAPS == sb.load_reference().CAPS
    from kaggisim.state import parse
    from kaggle_environments import make
    env = make("kaggriculture", configuration={"seed": 992, "episodeSteps": 3})
    obs = env.reset()[0].observation
    out = off.act(parse(obs))
    assert set(out) >= {"farmer", "hands", "market"}


def test_arm_b_drops_the_rule_and_nothing_else():
    cls = sb.arm_b_class()
    b = cls()
    from strategies.lean_feed import LeanFeedStrategy
    assert isinstance(b, LeanFeedStrategy) and b.herd_preference({"player": 0, "farms": [{"tiles": [[{"animal": "SHEEP"}] * 5]}]}) is None
