"""Unit tests for the crop/herd frontier sweep (issue #202, ADR-0007).

#196 found the binding constraint on running crops and livestock together, and
it is **worker slack**, not job priority. Every placement and every feeding is a
round trip to the shed, and a large crop line consumes the turns those trips
need. FEED count tracks tiles-per-worker almost exactly:

    neuropilot      62 planted   0 animals   6.9 tiles/worker     0 FEED
    splitbrain      56 planted   4 animals   5.6 tiles/worker    17 FEED
    balanced_farm   20 planted   8 animals   1.8 tiles/worker   153 FEED

So the field's 20-tile crop line is not a sacrifice made to fit animals in — it
is the room the animals need. That makes this a one-parameter question: how far
can the crop line grow before the herd stops standing up?

`dense_farm` is `balanced_farm` with its own crop caps, scaled by a single
factor. **`field_rival` must stay behaviourally frozen** — it is the only anchor
calibrated to the field that beats us, and moving it moves the measuring stick
under the thing being measured. So the caps become a defaulted parameter, and
the first test below is the one that matters: the benchmark's decisions must not
move at all.
"""

from __future__ import annotations

from strategies import dense_farm as df
from strategies import balanced_farm as bf
from strategies import field_rival as fr


def _standing(**kw):
    return dict(kw)


# --- the benchmark must not move ---

def test_the_frozen_benchmark_decides_exactly_as_before():
    # Threading a `caps` parameter through must be behaviour-preserving at its
    # default. If this ever fails, every number measured against `field_rival`
    # in #181, #184 and #193 is retroactively suspect.
    for day in range(0, fr.SEASON_DAYS):
        for standing in ({}, _standing(MELON=12), _standing(STRAWBERRY=15),
                         _standing(MELON=12, STRAWBERRY=15, WHEAT=5)):
            assert (fr.crop_for_plot(day, dict(standing))
                    == fr.crop_for_plot(day, dict(standing), caps=fr.CROP_CAP))


def test_the_benchmark_keeps_its_own_caps():
    assert fr.CROP_CAP == {"MELON": 12, "STRAWBERRY": 15, "WHEAT": 5}
    assert fr.STRATEGY.CAPS == fr.CROP_CAP
    assert fr.STRATEGY.benchmark is True


# --- the one parameter ---

def test_scaling_multiplies_every_cap():
    assert df.scaled_caps(1.0) == fr.CROP_CAP
    doubled = df.scaled_caps(2.0)
    assert doubled == {k: v * 2 for k, v in fr.CROP_CAP.items()}


def test_scaling_rounds_to_whole_tiles():
    caps = df.scaled_caps(1.25)
    assert all(isinstance(v, int) for v in caps.values())
    assert caps["STRAWBERRY"] == 19          # 15 * 1.25 = 18.75


def test_a_scale_below_one_is_refused():
    # The sweep only grows the crop line; shrinking it is #193's setting, which
    # is already measured and live.
    import pytest
    with pytest.raises(ValueError):
        df.scaled_caps(0.5)


def test_the_declared_grid_is_fixed_in_code():
    # Declared in #202 before any measurement, so it cannot grow to fit a result.
    assert df.GRID == (1.0, 1.25, 1.5, 2.0, 2.5)


def test_the_grid_saturates_and_we_know_where():
    # The real ceiling is not the 63 crop tiles owned but the 36 actually
    # assigned to workers by `crop_cluster`. Melon and strawberry never stand
    # together (melon early, strawberry after the pivot), so the simultaneous
    # demand is STRAWBERRY + WHEAT.
    assigned = sum(len(fr.crop_cluster(i)) for i in range(11))
    assert assigned == 36
    reachable = [s for s in df.GRID
                 if df.scaled_caps(s)["STRAWBERRY"] + df.scaled_caps(s)["WHEAT"] <= assigned]
    # Declared in #202 before measuring, so the grid is not trimmed to fit --
    # but the top of it is recorded as saturating rather than silently reported
    # as a distinct setting.
    assert reachable == [1.0, 1.25, 1.5], reachable
    assert df.SATURATES_ABOVE == 1.5


def test_the_control_is_where_the_caps_actually_bind():
    # Measured: balanced_farm plants exactly its caps -- 12 melon at day 8, 15
    # strawberry + 5 wheat after -- while 16 assigned tiles stand idle. So the
    # caps are the binding parameter and this sweep is asking a real question.
    caps = df.scaled_caps(1.0)
    assert caps["STRAWBERRY"] + caps["WHEAT"] == 20


# --- the contender ---

def test_it_is_a_contender_and_leaves_the_benchmark_alone():
    assert df.STRATEGY.benchmark is False
    assert df.STRATEGY.name == "dense_farm"
    assert fr.STRATEGY.benchmark is True


def test_the_control_arm_is_exactly_the_live_agent():
    # The grid's 1.0 point must BE balanced_farm, or there is no baseline to
    # move away from. Asserted without mutating the class -- an earlier version
    # of this test assigned to df.STRATEGY.CAPS, which leaks into every test
    # that runs after it.
    assert df.scaled_caps(1.0) == bf.STRATEGY.CAPS


def test_the_shipped_setting_is_the_one_the_holdout_confirmed():
    assert df.CHOSEN_SCALE == 1.5
    assert df.STRATEGY.CAPS == df.scaled_caps(1.5)
    assert df.STRATEGY.CAPS == {"MELON": 18, "STRAWBERRY": 22, "WHEAT": 8}


def test_the_shipped_setting_still_leaves_the_herd_room():
    # The necessary condition measured 7 animals and 49% livestock revenue at
    # this density -- the frontier has not been crossed.
    caps = df.scaled_caps(df.CHOSEN_SCALE)
    assigned = sum(len(fr.crop_cluster(i)) for i in range(11))
    assert caps["STRAWBERRY"] + caps["WHEAT"] <= assigned


def test_a_bigger_scale_actually_changes_a_planting_decision():
    # Positive control on the parameter itself: at 12 standing melon the frozen
    # caps refuse more, and a scaled-up farm does not.
    standing = _standing(MELON=12)
    assert fr.crop_for_plot(4, dict(standing), caps=fr.CROP_CAP) != "MELON"
    assert fr.crop_for_plot(4, dict(standing), caps=df.scaled_caps(2.0)) == "MELON"
