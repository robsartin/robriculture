# tests/test_pasture_ahead.py
"""#237: pasture built to placed head + 3, from day 0.

`lonespear_v21` stands its 5th pasture on day 0 against our day 12 and holds
head in the shed on 4% of turns against our 67% (#234). This contender keeps
`LEAD` tiles standing ahead of the head already placed, through the
`pasture_count` seam on the frozen benchmark. Everything else -- crop caps,
ramps, sells, land, feed, the hire schedule and #219's cow rule -- is
`rival_aware`'s.
"""

from __future__ import annotations

from strategies import field_rival as fr
from strategies import pasture_ahead as pa


def _grid():
    """Every (day, placed head) the rule can ever be asked about."""
    for day in range(fr.SEASON_DAYS):
        for placed in range(len(fr.PASTURE_TILES) + 1):
            yield day, placed


def test_the_lead_is_declared():
    assert pa.LEAD == 3 and pa.PastureAheadStrategy.LEAD_TILES == 3


def test_it_builds_three_tiles_on_day_zero_where_the_benchmark_builds_one():
    # The whole mechanism in one number: the benchmark's ramp says 1 tile on
    # day 0, and pasture beyond 5 cannot exist before the NE land buy anyway.
    assert pa.PastureAheadStrategy().pasture_count(0, 0) == 3
    assert len(fr.active_pastures(0, 0)) == 1


def test_it_keeps_the_lead_ahead_of_the_head_already_placed():
    s = pa.PastureAheadStrategy()
    assert s.pasture_count(0, 2) == 5
    assert s.pasture_count(8, 4) == 7


def test_it_never_asks_for_more_tiles_than_the_pasture_block_has():
    s = pa.PastureAheadStrategy()
    assert all(s.pasture_count(day, placed) <= len(fr.PASTURE_TILES)
               for day, placed in _grid())
    assert s.pasture_count(24, len(fr.PASTURE_TILES)) == len(fr.PASTURE_TILES)


def test_it_never_asks_for_fewer_tiles_than_the_benchmark_would_build():
    # The rule only ever ADDS pasture: a contender that could build LESS than
    # the frozen ramp would be a second, unmeasured change.
    s = pa.PastureAheadStrategy()
    for day, placed in _grid():
        assert s.pasture_count(day, placed) >= len(fr.active_pastures(day, placed)), \
            (day, placed)


def test_it_is_a_registered_contender_built_on_the_champion():
    from strategies import REGISTRY, load
    from strategies.rival_aware import RivalAwareStrategy
    assert "pasture_ahead" in REGISTRY and load("pasture_ahead") is pa.PastureAheadStrategy
    assert issubclass(pa.PastureAheadStrategy, RivalAwareStrategy)
    assert pa.PastureAheadStrategy.benchmark is False
    assert pa.PastureAheadStrategy.CAPS == RivalAwareStrategy.CAPS
    assert pa.PastureAheadStrategy.THRESHOLD == RivalAwareStrategy.THRESHOLD


def test_identity_control_the_rule_off_is_rival_aware_to_the_value():
    # Control (i): with `pasture_count` back to None -- the benchmark's own
    # rule -- the contender IS `rival_aware` on a full seeded game, both
    # seats' rewards equal to the value.
    from kaggle_environments import make
    from kaggisim.strategy import make_agent
    from strategies import load

    class Off(pa.PastureAheadStrategy):
        def pasture_count(self, day, animals):
            return None

    def rewards(ours):
        env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": 800})
        env.run([make_agent(ours), make_agent(load("rival_aware")())])
        return [s.reward or 0 for s in env.steps[-1]]

    base = rewards(load("rival_aware")())
    assert base[0] > 0, "POSITIVE CONTROL: no money moved"
    assert rewards(Off()) == base
