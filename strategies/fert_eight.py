"""fert_eight: fert_six from day 8 (#284).

#282 started the fertilizer line on day 6 and lost 7/16: the day NE opens,
the crop workers who should be planting it were walking fertilizer instead
-- 20 tiles at day 8 against 26. Its recorded arm, the same lever from day 8,
won 11/16. From day 10 the lever is a wash (#277); from day 0 it kills the
farm. Day 8 is the earliest start that leaves the expansion planted.

One number changes: FERT_FROM is 8. Stock, crops and everything else are
fert_six's, which is ten_melon's.

Declared before measurement: FERT_FROM_EIGHT, and the controls and criterion
in `harness/eight_bench.py` (posted to #284 before any code).
"""

from __future__ import annotations

from strategies.fert_six import FertSixStrategy

#: The day the fertilizer line starts: after the NE expansion is planted.
FERT_FROM_EIGHT = 8


class FertEightStrategy(FertSixStrategy):
    """`fert_six` from day eight."""

    name = "fert_eight"
    benchmark = False
    FERT_FROM = FERT_FROM_EIGHT


STRATEGY = FertEightStrategy
