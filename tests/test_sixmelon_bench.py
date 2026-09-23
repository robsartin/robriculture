"""The six_melon experiment's declared constants and pure parts (#341)."""

from __future__ import annotations

from harness import rival_bench as rb
from harness import sixmelon_bench as sb
from strategies import field_pace as fp


def test_the_declared_constants():
    assert sb.CONTENDER == "six_melon" and sb.CHAMPION == "town_melon"
    assert sb.SEEDS == tuple(range(2522, 2538)) and sb.CONTROL_SEED == 2522
    assert sb.CHAMPION_BAR == 0.60 and sb.ANCHOR_BAR == 0.90
    assert (sb.EARLY_DAY, sb.EARLY_BAR) == (13, 60)
    assert sb.LONESPEAR.startswith("lonespear")
    assert sb.criterion is rb.criterion and sb.decided_row is rb.decided_row and rb.PAIRED_MAX_SHORTFALL == 1


def test_the_seeds_are_fresh_against_every_range_already_spent():
    spent = set(range(100, 116)) | set(range(200, 216)) | set(range(300, 332)) \
        | set(range(400, 416)) | set(range(500, 516)) | set(range(600, 616)) \
        | set(range(700, 704)) | set(range(800, 960)) | set(range(960, 1687)) | set(range(1687, 2522))
    assert not spent & set(sb.SEEDS)


def _steps(sells):
    """Fake steps: `sells` is a list of (day, seat, item, units) SELL orders, each
    chosen from an observation at `day` -- the way `_turns` dates an action: by
    the PRECEDING step's own observation, never the step that carries the
    action, which is the state the sim already produced by applying it. Each
    entry becomes two consecutive steps: one whose own observation reports
    `day` (what the action was chosen from), followed by the one carrying the
    SELL, whose own observation has already advanced to `day + 1` -- exactly
    what the sim does once the last turn of a day resolves."""
    out = []
    for day, seat, item, units in sells:
        prior = [{"observation": {"day": day}, "action": {}}, {"observation": {"day": day}, "action": {}}]
        acted = [{"observation": {"day": day + 1}, "action": {}}, {"observation": {"day": day + 1}, "action": {}}]
        acted[seat]["action"] = {"market": [["SELL", item, units]]}
        out.append(prior)
        out.append(acted)
    return out


def test_units_by_day_counts_one_seats_sells_through_a_day():
    steps = _steps([(10, 0, "MELON", 18), (11, 0, "MELON", 48), (11, 1, "MELON", 10), (13, 0, "MELON", 6),
                    (14, 0, "MELON", 12), (12, 0, "STRAWBERRY", 4)])
    assert sb.units_by_day(steps, 0, "MELON", 13) == 72
    assert sb.units_by_day(steps, 0, "MELON", 14) == 84
    assert sb.units_by_day(steps, 1, "MELON", 13) == 10
    assert sb.units_by_day(steps, 0, "STRAWBERRY", 13) == 4
    assert sb.units_by_day([], 0, "MELON", 13) == 0


def test_units_by_day_dates_a_sale_by_the_observation_it_answered_not_the_one_it_produced():
    """A SELL on the last turn of day 13 -- whose own step's observation
    already reports day 14, the state the sim produces AFTER the action --
    must still count for day=13; a SELL on the first turn of day 14, chosen
    from a day-14 observation, must not."""
    last_turn_of_13 = _steps([(13, 0, "MELON", 6)])
    first_turn_of_14 = _steps([(14, 0, "MELON", 6)])
    assert sb.units_by_day(last_turn_of_13, 0, "MELON", 13) == 6
    assert sb.units_by_day(first_turn_of_14, 0, "MELON", 13) == 0


def test_reading(monkeypatch):
    monkeypatch.setattr(sb, "units_by_day", lambda steps, seat, item, day: 66)
    monkeypatch.setattr(sb, "units_sold", lambda steps, seat: {"MELON": 78, "STRAWBERRY": 240})
    assert sb.reading("s", 0) == {"melon_early": 66, "melon_units": 78, "strawberry_units": 240}
    monkeypatch.setattr(sb, "units_sold", lambda steps, seat: {})
    assert sb.reading("s", 0)["melon_units"] == 0 and sb.reading("s", 0)["strawberry_units"] == 0


def test_mechanism_failures_name_the_bars():
    champ = {"melon_early": 55, "melon_units": 58, "strawberry_units": 250}
    good = {"melon_early": 66, "melon_units": 78, "strawberry_units": 240}
    assert sb.mechanism_failures(good, champ) == []
    assert sb.mechanism_failures({**good, "melon_early": 59}, {**champ, "melon_early": 10}) == ["melon_early"]     # < EARLY_BAR
    assert sb.mechanism_failures({**good, "melon_early": 66}, {**champ, "melon_early": 66}) == ["melon_early"]     # not > champion's
    assert sb.mechanism_failures({**good, "melon_units": 58}, champ) == ["melon_units"]
    assert sb.mechanism_failures({**good, "strawberry_units": 100}, champ) == []                                   # recorded, not gated
    assert sb.mechanism_failures({"melon_early": 0, "melon_units": 0, "strawberry_units": 0}, champ) == ["melon_early", "melon_units"]


def test_the_identity_stub_switches_all_twenty_seams_off_and_survives_a_turn():
    from harness.sheep_bench import _seam_names
    names = _seam_names()
    assert len(names) == 20 and {"carry_limit", "water_first"} <= set(names)
    cls = sb.off_class()
    for n in names:
        assert n in cls.__dict__, f"seam {n} not switched off"
    off = cls()
    assert off.carry_limit() is None and off.water_first() is None and off.crop_plan({"day": 9}) is None
    assert off.HERD_RAMP_F == fp.HERD_RAMP_F and off.CAPS == sb.load_reference().CAPS
    from kaggisim.state import parse
    from kaggle_environments import make
    env = make("kaggriculture", configuration={"seed": 2522, "episodeSteps": 3})
    out = off.act(parse(env.reset()[0].observation))
    assert set(out) >= {"farmer", "hands", "market"}


def test_play_and_the_reference_are_pinned():
    from harness.cashflow import play
    from harness.reserve_bench import MADHUR, REFERENCE
    assert sb.play is play and sb.REFERENCE == REFERENCE == "dense_farm" and sb.MADHUR == MADHUR
