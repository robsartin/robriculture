"""Calibrated sparring opponent — the ladder field, not a candidate (issue #181).

Measured, not guessed. Profiled from 63 downloaded ladder replays, the 43
opponents that actually beat the submitted champion converge on one shape
(medians, sampled mid-day):

    day   melon  straw  wheat  planted  animals  hands  quads
      4      11      0      3       18        3      6      1
      8      12      3      0       20        4      7      1
     12       3     13      1       26        8      9      2
     16       2     15      4       27       10     10      3
     24       0     14      5       22       11     10      3   reward 66,640

The 20 opponents the champion beats never exceed 6 melon or 4 strawberry and
median 35,607 — the two populations separate cleanly on crop mix alone.

This strategy exists to make the benchmark able to express that shape. The five
`DEFAULT_ANCHORS` are swept 20/20 by the champion and **not one of them plants a
single strawberry**, so every paired experiment recorded in this repository was
scored against a saturated instrument (#181).

It is flagged ``benchmark = True``: never packaged by ``scripts/submit.py``
(ADR-0005) and never eligible for promotion (``harness.promotion.top_contender``).
"""

from __future__ import annotations

from kaggisim.strategy import Strategy
from strategies import hired_hands as hh

CROPS = hh.CROPS
SEASON_DAYS = hh.SEASON_DAYS

#: Day the measured field swings off melon and into strawberry. In the replays
#: melon is still 12 tiles at day 8 and down to 3 by day 12, while strawberry
#: goes 3 -> 13 over the same span, so the crossover sits at day 10.
PIVOT_DAY = 10


def crop_for_day(day: int, season_days: int = SEASON_DAYS):
    """The crop this farm plants on `day`, or ``None`` past the horizon.

    Melon before the pivot, strawberry after — the measured field's whole crop
    story. The horizon gate is the champion's own (`hired_hands.plantable`), so a
    seed is never spent on a plant that cannot reach first yield in time.
    """
    crop = "MELON" if day < PIVOT_DAY else "STRAWBERRY"
    return crop if hh.plantable(crop, day, season_days) else None


class FieldRivalStrategy(Strategy):
    name = "field_rival"
    benchmark = True

    def act(self, obs) -> dict:
        return {"farmer": ["PASS"], "hands": [], "market": []}


STRATEGY = FieldRivalStrategy
