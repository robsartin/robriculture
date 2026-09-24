"""The town_melon experiment's declared constants and pure parts (#337)."""

from __future__ import annotations

from harness import deadtown_bench as db
from harness import rival_bench as rb
from strategies import field_pace as fp
from strategies import field_rival as fr


def test_the_declared_constants():
    assert db.CONTENDER == "town_melon" and db.CHAMPION == "second_melon"
    assert db.CHAMPION_BAR == 0.60 and db.ANCHOR_BAR == 0.90
    assert db.SCAN_FROM == 2359 and db.SEED_COUNT == 16 and db.MELON_UNITS_BAR == 100
    assert db.MAX_SCAN == 400
    assert db.DEAD_STEP == 9 * fr.TURNS_PER_DAY + 1
    assert db.LONESPEAR.startswith("lonespear")
    assert db.criterion is rb.criterion and db.decided_row is rb.decided_row and rb.PAIRED_MAX_SHORTFALL == 1


def test_the_scan_starts_past_every_seed_already_spent():
    spent = set(range(100, 116)) | set(range(200, 216)) | set(range(300, 332)) \
        | set(range(400, 416)) | set(range(500, 516)) | set(range(600, 616)) \
        | set(range(700, 704)) | set(range(800, 960)) | set(range(960, 1687)) | set(range(1687, 2359))
    assert db.SCAN_FROM > max(spent)


def test_screen_keeps_the_first_dead_seeds_in_order_and_names_the_first_live_one():
    dead = {2359: True, 2360: False, 2361: True, 2362: True, 2363: False, 2364: True}
    out = db.screen(range(2359, 2400), dead.__getitem__, 3)
    assert out == {"seeds": (2359, 2361, 2362), "live_seed": 2360, "read": 4}
    out = db.screen(range(2359, 2365), lambda s: True, 2)
    assert out == {"seeds": (2359, 2360), "live_seed": None, "read": 2}


def test_screen_reads_every_seed_when_too_few_are_dead():
    out = db.screen(range(2359, 2363), lambda s: s == 2361, 2)
    assert out == {"seeds": (2361,), "live_seed": 2359, "read": 4}


def test_reading_and_its_failure(monkeypatch):
    monkeypatch.setattr(db, "units_sold", lambda steps, seat: {"MELON": 148, "STRAWBERRY": 40})
    assert db.reading("s", 0) == {"melon_units": 148, "strawberry_units": 40}
    monkeypatch.setattr(db, "units_sold", lambda steps, seat: {})
    assert db.reading("s", 0) == {"melon_units": 0, "strawberry_units": 0}


def test_mechanism_failures_name_the_bars():
    champ = {"melon_units": 68, "strawberry_units": 120}
    good = {"melon_units": 148, "strawberry_units": 40}
    ok = db.DEAD_STEP
    assert db.mechanism_failures(good, champ, first_diff=ok) == []
    assert db.mechanism_failures(good, champ, first_diff=ok + 50) == []
    assert db.mechanism_failures({**good, "melon_units": 99}, {**champ, "melon_units": 10}, first_diff=ok) == ["melon_units"]   # < bar
    assert db.mechanism_failures({**good, "melon_units": 148}, {**champ, "melon_units": 148}, first_diff=ok) == ["melon_units"]  # not > champion's
    assert db.mechanism_failures({**good, "strawberry_units": 120}, champ, first_diff=ok) == ["strawberry_units"]
    assert db.mechanism_failures(good, champ, first_diff=ok - 1) == ["first_divergence"]
    assert db.mechanism_failures(good, champ, first_diff=None) == ["first_divergence"]
    assert db.mechanism_failures({"melon_units": 0, "strawberry_units": 200}, champ, first_diff=None) == ["melon_units", "strawberry_units", "first_divergence"]


def test_live_failures_compare_the_seat_zero_streams(monkeypatch):
    monkeypatch.setattr(db, "seat_actions", lambda steps, seat: steps[seat])
    assert db.live_failures([["a", "b"], ["x"]], [["a", "b"], ["y"]]) == []
    assert db.live_failures([["a", "b"], ["x"]], [["a", "c"], ["x"]]) == ["live_identity"]
    assert db.live_failures([["a"], ["x"]], [["a", "b"], ["x"]]) == ["live_identity"]


def test_the_identity_stub_switches_all_twenty_one_seams_off_and_survives_a_turn():
    from harness.sheep_bench import _seam_names
    names = _seam_names()
    assert len(names) == 21 and "crop_plan" in names
    cls = db.off_class()
    for n in names:
        assert n in cls.__dict__, f"seam {n} not switched off"
    off = cls()
    assert off.crop_plan({"day": 9}) is None and off.melon_windows() is None and off.herd_target(12) is None
    assert off.HERD_RAMP_F == fp.HERD_RAMP_F and off.CAPS == db.load_reference().CAPS
    from kaggisim.state import parse
    from kaggle_environments import make
    env = make("kaggriculture", configuration={"seed": 2359, "episodeSteps": 3})
    out = off.act(parse(env.reset()[0].observation))
    assert set(out) >= {"farmer", "hands", "market"}


def test_play_and_the_reference_are_pinned():
    from harness.cashflow import play
    from harness.reserve_bench import MADHUR, REFERENCE
    assert db.play is play and db.REFERENCE == REFERENCE == "dense_farm" and db.MADHUR == MADHUR
