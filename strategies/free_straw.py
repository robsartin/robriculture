"""free_straw: town_split with the strawberry cap removed (#312).

#288 found the strawberry-shop count predicts our strawberry revenue at
r = 0.72. A scratch probe of fixed caps against town_split's 38 read the
other way from the cap's own reasoning: caps of 20 and 28 lose every game
at every shop count, and the land (42 tiles at three quadrants) wins 15 of
16 by 1.4-8K, losing only the one town with no strawberry shop. Strawberry
revenue tracks tiles almost linearly -- at 38 tiles the farm is not
flooding its own price -- and the four tiles the cap sends to wheat earn a
third as much there.

One class attribute changes: `CAPS` has no STRAWBERRY key. The frozen crop
rule treats an absent key as no cap, so every empty crop tile after the
melon window is strawberry while strawberry can still finish, then wheat as
before. No method is overridden; everything else is town_split's.

Declared before measurement: `CAPS_S`, and the controls and criterion in
`harness/straw_bench.py` (posted to #312 before any code).
"""

from __future__ import annotations

from strategies.town_split import TownSplitStrategy

#: town_split's caps without the STRAWBERRY key: melon ten, wheat twenty-four,
#: strawberry to the land.
CAPS_S = {"MELON": 10, "WHEAT": 24}


class FreeStrawStrategy(TownSplitStrategy):
    """`town_split` with strawberry uncapped."""

    name = "free_straw"
    benchmark = False
    CAPS = CAPS_S


STRATEGY = FreeStrawStrategy
