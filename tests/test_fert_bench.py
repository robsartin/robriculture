"""The fertilized experiment's declared constants and pure parts (#277)."""

from __future__ import annotations

from harness import fert_bench as fb
from strategies import field_pace as fp


def test_the_declared_constants():
    assert fb.CONTENDER == "fertilized" and fb.CHAMPION == "payday_herd" and fb.ARM_B == "melon_only"
    assert fb.SEEDS == tuple(range(1056, 1072)) and fb.CONTROL_SEED == 1056
    assert fb.CHAMPION_BAR == 0.60 and fb.ANCHOR_BAR == 0.90
    assert fb.FERTILIZE_BAR == 30 and fb.STRAWBERRY_FACTOR == 1.5
    assert fb.LONESPEAR.startswith("lonespear") and fb.PILKWANG.startswith("pilkwang")


def test_the_seeds_are_fresh_against_every_range_already_spent():
    spent = set(range(100, 116)) | set(range(200, 216)) | set(range(300, 332)) \
        | set(range(400, 416)) | set(range(500, 516)) | set(range(600, 616)) \
        | set(range(700, 704)) | set(range(800, 960)) | set(range(960, 1056))
    assert not spent & set(fb.SEEDS)


def _step(seat_actions):
    """One step: a list of per-seat slots, each with an action dict."""
    return [{"action": a, "observation": {}, "reward": 0, "status": "ACTIVE"} for a in seat_actions]


STEPS = [
    _step([{"farmer": ["WATER"], "hands": [["FERTILIZE"], ["WATER"]], "market": [["SELL", "STRAWBERRY", 4], ["SELL", "FERTILIZER", 2]]},
           {"farmer": ["PASS"], "hands": [["WATER"]], "market": [["SELL", "MELON", 3]]}]),
    _step([{"farmer": ["FERTILIZE"], "hands": [["HARVEST"], ["FERTILIZE"]], "market": [["SELL", "STRAWBERRY", 6], ["BUY_SEED", "WHEAT", 1]]},
           {"farmer": ["WATER"], "hands": [], "market": [["SELL", "MELON", 5], ["SELL", "STRAWBERRY", 1]]}]),
]


def test_action_counts_and_units_sold_read_one_seat():
    assert fb.action_counts(STEPS, 0) == {"WATER": 2, "FERTILIZE": 3, "HARVEST": 1}
    assert fb.action_counts(STEPS, 1) == {"PASS": 1, "WATER": 2}
    assert fb.units_sold(STEPS, 0) == {"STRAWBERRY": 10, "FERTILIZER": 2}
    assert fb.units_sold(STEPS, 1) == {"MELON": 8, "STRAWBERRY": 1}


def test_reading_has_the_declared_fields():
    assert fb.reading(STEPS, 0) == {"fertilize": 3, "water": 2, "strawberry": 10, "melon": 0, "fertilizer_sold": 2}
    assert fb.reading(STEPS, 1) == {"fertilize": 0, "water": 2, "strawberry": 1, "melon": 8, "fertilizer_sold": 0}


def test_mechanism_failures_name_the_bars():
    champ = {"fertilize": 0, "water": 900, "strawberry": 150, "melon": 45, "fertilizer_sold": 230}
    good = {"fertilize": 40, "water": 850, "strawberry": 225, "melon": 45, "fertilizer_sold": 120}
    assert fb.mechanism_failures(good, champ) == []
    assert fb.mechanism_failures({**good, "fertilize": 29}, champ) == ["fertilize"]
    assert fb.mechanism_failures({**good, "strawberry": 224}, champ) == ["strawberry"]
    assert fb.mechanism_failures({**good, "melon": 44, "fertilize": 0}, champ) == ["fertilize", "melon"]


def test_the_identity_stub_switches_all_sixteen_seams_off_and_survives_a_turn():
    from harness.sheep_bench import _seam_names
    names = _seam_names()
    assert len(names) == 17
    cls = fb.off_class()
    for n in names:
        assert n in cls.__dict__, f"seam {n} not switched off"
    off = cls()
    assert off.fertilizer_stock() is None and off.fertilize_crops() is None and off.herd_target(8) is None
    assert off.HERD_RAMP_F == fp.HERD_RAMP_F and off.CAPS == fb.load_reference().CAPS
    from kaggisim.state import parse
    from kaggle_environments import make
    env = make("kaggriculture", configuration={"seed": 1056, "episodeSteps": 3})
    out = off.act(parse(env.reset()[0].observation))
    assert set(out) >= {"farmer", "hands", "market"}


def test_arm_b_fertilizes_melon_only():
    from strategies.fertilized import FertilizedStrategy
    b = fb.arm_b_class()()
    assert isinstance(b, FertilizedStrategy)
    assert b.fertilize_crops() == ("MELON",) and b.fertilizer_stock() == 24


def test_arm_b_survives_a_turn_at_the_seams_new_arity():
    """The seams take the day since #282; a stub with the old arity crashes the
    moment `act` runs (found at review, #282)."""
    from kaggisim.state import parse
    from kaggle_environments import make
    b = fb.arm_b_class()()
    assert b.fertilize_crops(6) == ("MELON",) and b.fertilizer_stock(6) == 24
    env = make("kaggriculture", configuration={"seed": 1088, "episodeSteps": 3})
    out = b.act(parse(env.reset()[0].observation))
    assert set(out) >= {"farmer", "hands", "market"}
