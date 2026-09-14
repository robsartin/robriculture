"""fert_six: ten_melon with the crop line fertilized from day 6 (#282).

#277 found that a fertilizer hold-back from day 0 kills the farm -- days 1-5
run on fertilizer sales -- and that a day-10 start is a wash. Started on day
6 with a stock of 8, the probe against ten_melon gave +13K and +7K: the
strawberry doubles (149 -> 260), melon's growth window is caught, and the
early economy is untouched to the coin.

One decision changes: from FERT_FROM the shed keeps FERT_STOCK units back
from the sell sweep and the crop workers fertilize melon and strawberry (the
#277 seams, which take the day since #282). Everything else is ten_melon's.

Declared before measurement: FERT_FROM, FERT_STOCK, FERT_CROPS, and the
controls and criterion in `harness/six_bench.py` (posted to #282 before any code).
"""

from __future__ import annotations

from strategies.ten_melon import TenMelonStrategy

#: The day the fertilizer line starts; before it the sweep sells every unit.
FERT_FROM = 6
#: Fertilizer the shed keeps back from the sweep from FERT_FROM on.
FERT_STOCK = 8
#: The crops worth a unit: the two the payday is made of.
FERT_CROPS = ("MELON", "STRAWBERRY")


class FertSixStrategy(TenMelonStrategy):
    """`ten_melon` with the crop line fertilized from day six."""

    name = "fert_six"
    benchmark = False
    FERT_FROM = FERT_FROM

    def fertilizer_stock(self, day=None):
        return FERT_STOCK if (day or 0) >= self.FERT_FROM else None

    def fertilize_crops(self, day=None):
        return FERT_CROPS if (day or 0) >= self.FERT_FROM else None


STRATEGY = FertSixStrategy
