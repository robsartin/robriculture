"""fert_sixteen: twelve_head with the fertilizer line from day 16 (#324).

Fertilizer doubles a strawberry tile's yield on its production day (#277's
seam). Started on day 8 (#286) the line beat the champion 13/16 and lost on
the anchors: the walk for fertilizer delayed the second quadrant's planting
two days and the withheld sales starved days 1-7. From day 16 the field is
planted, cash is not scarce, and the fourteen days that earn most of the
strawberry money are ahead. Two scratch seed sets read day 16 at 15/16 and
15/16, +11K and +10K, strawberry units 1.66x, the early economy untouched.

One number: FERT_FROM is 16. The two seams are fert_six's, with its
constants; everything else is twelve_head's.

Declared before measurement: FERT_FROM, and the controls and criterion in
`harness/sixteen_bench.py` (posted to #324 before any code).
"""

from __future__ import annotations

from strategies.fert_six import FERT_CROPS, FERT_STOCK
from strategies.twelve_head import TwelveHeadStrategy

#: The day the fertilizer line starts: the third quadrant open, the field planted.
FERT_FROM = 16


class FertSixteenStrategy(TwelveHeadStrategy):
    """`twelve_head` with the fertilizer line from day sixteen."""

    name = "fert_sixteen"
    benchmark = False
    FERT_FROM = FERT_FROM

    def fertilizer_stock(self, day=None):
        """fert_six's stock from `FERT_FROM` on; the frozen sweep before."""
        return FERT_STOCK if (day or 0) >= self.FERT_FROM else None

    def fertilize_crops(self, day=None):
        """fert_six's crops from `FERT_FROM` on; never before."""
        return FERT_CROPS if (day or 0) >= self.FERT_FROM else None


STRATEGY = FertSixteenStrategy
