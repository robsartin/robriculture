"""twelve_head: free_straw with the herd target's last step at twelve (#320).

With four herders the herd is labour-bound at twelve head (#288): a
thirteenth costs milking and collecting time and produces nothing, and the
chain's ramp buys it anyway and leaves it pending in the shed. A scratch
probe of a twelve-head target against free_straw read 16/16 by a small,
consistent margin -- one animal fewer bought, and its feed.

One class attribute changes: `HERD_RAMP_F` ends at twelve on day 12
instead of thirteen. `field_pace.herd_target` reads it through the
`herd_target` seam; nothing else is overridden and everything else is
free_straw's.

Declared before measurement: `HERD_RAMP_T`, and the controls and criterion
in `harness/twelve_bench.py` (posted to #320 before any code).
"""

from __future__ import annotations

from strategies.free_straw import FreeStrawStrategy

#: payday_herd's ramp with its last step at twelve: the head four herders work.
HERD_RAMP_T = ((0, 4), (6, 8), (12, 12))


class TwelveHeadStrategy(FreeStrawStrategy):
    """`free_straw` with a twelve-head herd."""

    name = "twelve_head"
    benchmark = False
    HERD_RAMP_F = HERD_RAMP_T


STRATEGY = TwelveHeadStrategy
