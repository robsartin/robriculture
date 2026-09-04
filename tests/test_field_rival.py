"""Unit tests for the calibrated sparring opponent (issue #181, ADR-0007).

`field_rival` is not a candidate agent — it is a *measuring instrument*. The five
current anchors are swept 20/20 by the submitted champion and none of them plants
a single strawberry, so no paired experiment run against them can distinguish a
better agent from a worse one (#181). This strategy reproduces the archetype
measured from 63 real ladder replays: melon-heavy through day ~8, pivoting to
strawberry from day ~10, with a livestock line running underneath.

These tests pin the pure schedule helpers that carry the calibration. The
end-to-end profile (does it actually hit 12 melon at day 8?) is a full-game
measurement, not a unit test, and lives in the issue's pass criterion.
"""

from __future__ import annotations

from strategies import field_rival as fr


# --- crop_for_day: the measured melon -> strawberry pivot ---

def test_plants_melon_before_the_pivot():
    # The field that beats us holds 11-12 melon tiles through day 8.
    for day in range(0, fr.PIVOT_DAY):
        assert fr.crop_for_day(day) == "MELON", day


def test_plants_strawberry_after_the_pivot():
    # From day ~10 the field swings to strawberry (13 tiles by day 12).
    assert fr.crop_for_day(fr.PIVOT_DAY) == "STRAWBERRY"
    assert fr.crop_for_day(16) == "STRAWBERRY"


def test_plants_nothing_once_the_horizon_closes():
    # A strawberry planted this late cannot reach first yield before the buzzer;
    # the measured field is down to 1 strawberry tile by day 28.
    assert fr.crop_for_day(fr.SEASON_DAYS - 1) is None
