"""fertilized: payday_herd that applies the fertilizer it collects (#277).

pilkwang, 0/16 against every contender of this line, opens like us and wins
the payday: 72 melon from 12 tiles and 269 strawberry from 38 to our 45 and
150. The sim doubles a watered day's yield growth and each strawberry
production while a tile is fertilized; FERTILIZE takes one unit from the
worker's hand and lasts three days. Our line collects fertilizer from the
pastures and sells every unit.

One decision changes: the crop line is fertilized. The shed keeps FERT_STOCK
units back from the sell sweep, a crop worker at the shed takes a few, and a
strawberry or melon tile due for water whose fertilizer has lapsed gets
FERTILIZE first (the two seams of #277). Everything else is payday_herd's.

Declared before measurement: FERT_CROPS and FERT_STOCK, and the controls and
criterion in `harness/fert_bench.py` (posted to #277 before any code).
"""

from __future__ import annotations

from strategies.payday_herd import PaydayHerdStrategy

#: The crops worth a unit of fertilizer: the two the payday is made of.
FERT_CROPS = ("STRAWBERRY", "MELON")
#: Fertilizer the shed keeps back from the sweep for the crop workers.
FERT_STOCK = 24


class FertilizedStrategy(PaydayHerdStrategy):
    """`payday_herd` with the crop line fertilized."""

    name = "fertilized"
    benchmark = False

    def fertilizer_stock(self, day=None):
        return FERT_STOCK

    def fertilize_crops(self, day=None):
        return FERT_CROPS


STRATEGY = FertilizedStrategy
