"""The fed_herd experiment's declared constants and pure parts (#270)."""

from __future__ import annotations

import pytest

from harness import fed_bench as fb


def test_the_declared_constants():
    assert fb.CONTENDER == "fed_herd" and fb.CHAMPION == "lean_feed" and fb.ARM_B == "feed_floor"
    assert fb.SEEDS == tuple(range(1008, 1024)) and fb.CONTROL_SEED == 1008
    assert fb.CHAMPION_BAR == 0.60 and fb.ANCHOR_BAR == 0.90
    assert list(fb.CENSUS_DAYS) == list(range(0, 17)) and fb.HEAD_LOST_BAR == 0 and fb.HEAD_DAY == 12


def test_the_seeds_are_fresh_against_every_range_already_spent():
    spent = set(range(100, 116)) | set(range(200, 216)) | set(range(300, 332)) \
        | set(range(400, 416)) | set(range(500, 516)) | set(range(600, 616)) \
        | set(range(700, 704)) | set(range(800, 960)) | set(range(960, 1008))
    assert not spent & set(fb.SEEDS)


def _board(n):
    return {"tiles": [[{"animal": "COW"}] * n]}


def test_head_by_day_and_head_lost(monkeypatch):
    heads = {0: 4, 1: 4, 2: 6, 3: 3, 4: 5, 5: None}
    monkeypatch.setattr(fb, "board_on_day", lambda steps, seat, day: _board(heads[day]) if heads.get(day) is not None else None)
    assert fb.head_by_day("s", 0, range(0, 6)) == [4, 4, 6, 3, 5, None]
    assert fb.head_lost([4, 4, 6, 3, 5, None]) == 3
    assert fb.head_lost([9, 6, 9, 9, 6]) == 6
    assert fb.head_lost([]) == 0 and fb.head_lost([None, 3, None, 1]) == 2


def test_head_reading_and_its_failure(monkeypatch):
    heads = {d: (4 if d < 6 else 9 if d < 9 else 6) for d in range(0, 17)}
    monkeypatch.setattr(fb, "board_on_day", lambda steps, seat, day: _board(heads[day]))
    r = fb.head_reading("s", 0)
    assert r["lost"] == 3 and r["head_12"] == 6 and len(r["heads"]) == 17
    monkeypatch.setattr(fb, "board_on_day", lambda steps, seat, day: None if day >= 12 else _board(4))
    with pytest.raises(ValueError):
        fb.head_reading("s", 0)


def test_mechanism_failures_name_the_bars():
    champ = {"lost": 3, "head_12": 9}
    assert fb.mechanism_failures({"lost": 0, "head_12": 11}, champ) == []
    assert fb.mechanism_failures({"lost": 0, "head_12": 9}, champ) == []
    assert fb.mechanism_failures({"lost": 1, "head_12": 11}, champ) == ["lost"]
    assert fb.mechanism_failures({"lost": 2, "head_12": 8}, champ) == ["lost", "head_12"]


def test_the_identity_stub_switches_every_seam_off_and_survives_a_turn():
    from harness.sheep_bench import _seam_names
    cls = fb.off_class()
    for n in _seam_names():
        assert n in cls.__dict__, f"seam {n} not switched off"
    off = cls()
    assert off.feed_stock(4) is None and off.layout() is None and off.CAPS == fb.load_reference().CAPS
    from kaggisim.state import parse
    from kaggle_environments import make
    env = make("kaggriculture", configuration={"seed": 1008, "episodeSteps": 3})
    out = off.act(parse(env.reset()[0].observation))
    assert set(out) >= {"farmer", "hands", "market"}


def test_arm_b_is_lean_feed_with_a_feed_only_floor():
    from strategies.lean_feed import LeanFeedStrategy
    b = fb.arm_b_class()()
    assert isinstance(b, LeanFeedStrategy)
    assert b.spend_floor(day=7, animals=9, shed={"WHEAT": 4}, prices={"WHEAT": 30}) == (18 - 4) * 30
    assert b.spend_floor(day=7, animals=9, shed={"WHEAT": 40}, prices={"WHEAT": 30}) == 0
    assert b.spend_floor(day=7, animals=9, shed={}, prices={}) == 18 * 25
    assert b.spend_floor() == 0
    assert b.feed_stock(animals=9) == 9   # the floor arm keeps lean_feed's one feeding


def test_census_summary_takes_medians_per_side():
    games = [{"seed": 1008, "seat": 0, "contender_lost": 0, "champion_lost": 3},
             {"seed": 1009, "seat": 1, "contender_lost": 1, "champion_lost": 0},
             {"seed": 1010, "seat": 0, "contender_lost": 0, "champion_lost": 7}]
    s = fb.census_summary(games)
    assert s == {"games": 3, "contender_lost_median": 0, "champion_lost_median": 3,
                 "contender_games_with_escapes": 1, "champion_games_with_escapes": 2}
