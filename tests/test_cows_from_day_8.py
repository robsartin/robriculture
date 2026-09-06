# tests/test_cows_from_day_8.py
"""#225: the clock the #219 arms point at -- cows from day 8, no rival reading.

The declared switch day, the seam behaviour either side of it, the registration
shape, and the identity control with the switch day put past the season.
"""

from __future__ import annotations

from strategies import cows_from_day_8 as c8


def test_the_switch_day_is_declared():
    assert c8.SWITCH_DAY == 8 and c8.CowsFromDay8Strategy.DAY == 8


def test_prefers_cows_from_day_8_and_not_on_day_7():
    s = c8.CowsFromDay8Strategy()
    assert s.herd_preference({"day": 7}) is None
    assert s.herd_preference({"day": 8}) == "COW"
    assert s.herd_preference({"day": 20}) == "COW"


def test_a_missing_day_prefers_nothing_rather_than_raising():
    # ADR-0006: herd_preference is called on the act() path the no-crash gate
    # covers, so a malformed observation must degrade, not raise.
    assert c8.CowsFromDay8Strategy().herd_preference({}) is None


def test_it_is_a_registered_contender_built_on_dense_farm():
    from strategies import REGISTRY, load
    from strategies.dense_farm import DenseFarmStrategy
    assert "cows_from_day_8" in REGISTRY and load("cows_from_day_8") is c8.CowsFromDay8Strategy
    assert issubclass(c8.CowsFromDay8Strategy, DenseFarmStrategy)
    assert c8.CowsFromDay8Strategy.benchmark is False
    assert c8.CowsFromDay8Strategy.CAPS == DenseFarmStrategy.CAPS


def test_identity_control_switch_day_past_the_season_is_dense_farm_to_the_value():
    # #225 control 1: with the switch day unreachable the contender IS
    # dense_farm on a full seeded game, both seats' rewards equal to the value.
    from kaggle_environments import make
    from kaggisim.strategy import make_agent
    from strategies import load

    class Off(c8.CowsFromDay8Strategy):
        DAY = 10 ** 9

    def rewards(ours):
        env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": 21})
        env.run([make_agent(ours), make_agent(load("dense_farm")())])
        return [s.reward or 0 for s in env.steps[-1]]

    base = rewards(load("dense_farm")())
    assert base[0] > 0, "POSITIVE CONTROL: no money moved"
    assert rewards(Off()) == base
