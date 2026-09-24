"""The wind_down experiment's declared constants and pure parts (#343)."""

from __future__ import annotations

from harness import rival_bench as rb
from harness import winddown_bench as wb
from strategies import field_pace as fp
from strategies import field_rival as fr


def test_the_declared_constants():
    assert wb.CONTENDER == "wind_down" and wb.CHAMPION == "town_melon"
    assert wb.SEEDS == tuple(range(2586, 2602)) and wb.CONTROL_SEED == 2586
    assert wb.CHAMPION_BAR == 0.60 and wb.ANCHOR_BAR == 0.90
    assert wb.WIND_DAY == 28 and wb.WIND_STEP == 28 * fr.TURNS_PER_DAY + 1
    assert wb.LONESPEAR.startswith("lonespear")
    assert wb.criterion is rb.criterion and wb.decided_row is rb.decided_row and rb.PAIRED_MAX_SHORTFALL == 1


def test_the_seeds_are_fresh_against_every_range_already_spent():
    spent = set(range(100, 116)) | set(range(200, 216)) | set(range(300, 332)) \
        | set(range(400, 416)) | set(range(500, 516)) | set(range(600, 616)) \
        | set(range(700, 704)) | set(range(800, 960)) | set(range(960, 1687)) | set(range(1687, 2586))
    assert not spent & set(wb.SEEDS)


def _steps(turns):
    """Fake steps in the real shape: the action at index t answers the
    observation at index t-1. `turns` is a list of (day, shed, seat0_orders,
    seat1_orders); the observation carrying `day` and `shed` sits one index
    before the action that answers it."""
    out = [[{"observation": {"day": 0, "private": {"shed": {}}, "farms": [{"money": 0}, {"money": 0}], "player": 0}, "action": {}},
            {"observation": {"day": 0, "private": {"shed": {}}, "farms": [{"money": 0}, {"money": 0}], "player": 1}, "action": {}}]]
    for day, shed, o0, o1 in turns:
        prev = out[-1]
        for seat, orders in ((0, o0), (1, o1)):
            prev[seat]["observation"] = {"day": day, "private": {"shed": dict(shed)},
                                         "farms": [{"money": 0}, {"money": 0}], "player": seat}
        out.append([{"observation": {"day": day, "private": {"shed": {}}, "farms": [{"money": 0}, {"money": 0}], "player": 0},
                     "action": {"market": list(o0)}},
                    {"observation": {"day": day, "private": {"shed": {}}, "farms": [{"money": 0}, {"money": 0}], "player": 1},
                     "action": {"market": list(o1)}}])
    return out


def test_buys_from_counts_one_seats_buy_orders_from_a_day_on():
    steps = _steps([
        (27, {"WHEAT": 24}, [["BUY_SEED", "WHEAT", 2], ["SELL", "MILK", 3]], [["BUY_PRODUCT", "WHEAT", 4]]),
        (28, {"WHEAT": 24}, [["SELL", "WHEAT", 24]], [["BUY_PRODUCT", "WHEAT", 2], ["HIRE"]]),
        (29, {"WHEAT": 0}, [["HIRE"], ["SELL", "MILK", 1]], [["BUY_ANIMAL", "COW", 1], ["BUY_LAND"]]),
    ])
    assert wb.buys_from(steps, 0, 28) == 0
    assert wb.buys_from(steps, 0, 27) == 1
    assert wb.buys_from(steps, 1, 28) == 3
    assert wb.buys_from(steps, 1, 29) == 2
    assert wb.buys_from([], 0, 28) == 0


def test_shed_on_day_reads_the_last_turn_of_that_day():
    steps = _steps([
        (28, {"WHEAT": 24, "FERTILIZER": 3}, [], []),
        (28, {"WHEAT": 6}, [], []),
        (29, {"WHEAT": 0}, [], []),
    ])
    assert wb.shed_on_day(steps, 0, 28, "WHEAT") == 6
    assert wb.shed_on_day(steps, 0, 28, "FERTILIZER") == 0
    assert wb.shed_on_day(steps, 1, 29, "WHEAT") == 0
    assert wb.shed_on_day(steps, 0, 30, "WHEAT") is None
    assert wb.shed_on_day([], 0, 28, "WHEAT") is None


def test_reading_and_its_failure(monkeypatch):
    monkeypatch.setattr(wb, "buys_from", lambda steps, seat, day: 0)
    monkeypatch.setattr(wb, "shed_on_day", lambda steps, seat, day, item: {"WHEAT": 0, "FERTILIZER": 2}[item])
    assert wb.reading("s", 0) == {"buys_28": 0, "wheat_28": 0, "fertilizer_28": 2}
    monkeypatch.setattr(wb, "shed_on_day", lambda steps, seat, day, item: None)
    import pytest
    with pytest.raises(ValueError):
        wb.reading("s", 0)


def test_mechanism_failures_name_the_bars():
    champ = {"buys_28": 4, "wheat_28": 24, "fertilizer_28": 3}
    good = {"buys_28": 0, "wheat_28": 0, "fertilizer_28": 0}
    ok = wb.WIND_STEP
    assert wb.mechanism_failures(good, champ, first_diff=ok) == []
    assert wb.mechanism_failures(good, champ, first_diff=ok + 30) == []
    assert wb.mechanism_failures({**good, "buys_28": 1}, champ, first_diff=ok) == ["buys_28"]
    assert wb.mechanism_failures(good, {**champ, "buys_28": 0}, first_diff=ok) == ["buys_28"]        # champion must buy
    assert wb.mechanism_failures({**good, "wheat_28": 2}, champ, first_diff=ok) == ["wheat_28"]
    assert wb.mechanism_failures(good, {**champ, "wheat_28": 0}, first_diff=ok) == ["wheat_28"]      # champion must hold some
    assert wb.mechanism_failures({**good, "fertilizer_28": 9}, champ, first_diff=ok) == []           # recorded, not gated
    assert wb.mechanism_failures(good, champ, first_diff=ok - 1) == ["first_divergence"]
    assert wb.mechanism_failures(good, champ, first_diff=None) == ["first_divergence"]
    assert wb.mechanism_failures({"buys_28": 2, "wheat_28": 5, "fertilizer_28": 0}, champ, first_diff=None) == ["buys_28", "wheat_28", "first_divergence"]


def test_the_identity_stub_switches_all_twenty_one_seams_off_and_survives_a_turn():
    from harness.sheep_bench import _seam_names
    names = _seam_names()
    assert len(names) == 21 and "wind_down" in names
    cls = wb.off_class()
    for n in names:
        assert n in cls.__dict__, f"seam {n} not switched off"
    off = cls()
    assert off.wind_down(28) is None and off.crop_plan({"day": 9}) is None and off.water_first() is None
    assert off.HERD_RAMP_F == fp.HERD_RAMP_F and off.CAPS == wb.load_reference().CAPS
    from kaggisim.state import parse
    from kaggle_environments import make
    env = make("kaggriculture", configuration={"seed": 2586, "episodeSteps": 3})
    out = off.act(parse(env.reset()[0].observation))
    assert set(out) >= {"farmer", "hands", "market"}


def test_play_and_the_reference_are_pinned():
    from harness.cashflow import play
    from harness.reserve_bench import MADHUR, REFERENCE
    assert wb.play is play and wb.REFERENCE == REFERENCE == "dense_farm" and wb.MADHUR == MADHUR
