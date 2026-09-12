"""payday_herd: lean_feed's herd waits for payday (#274).

#270 named the mechanism behind lean_feed's escapes in 24 of 47 ladder games:
on days 7-11 dawn cash is 0-30, the crew is five or six hands, feed cannot be
topped up, and the herd bought on days 6-10 for 6,400 starves. A cash floor
and a delayed tenth hand are byte-identical to lean_feed on the probe seeds;
moving the herd's 13-head step from day 8 to day 12 -- the melon payday --
gave zero escapes, ten hands by day 9-10 and 2/2 wins.

One knob changes: `HERD_RAMP_F`'s last step is day 12, not day 8.
`field_pace.herd_target` and `pasture_count` read the attribute; no method
is overridden and everything else is lean_feed's.

Declared before measurement: `HERD_RAMP_P`, and the controls and criterion
in `harness/payday_bench.py` (posted to #274 before any code).
"""

from __future__ import annotations

from strategies.lean_feed import LeanFeedStrategy

#: lean_feed's herd ramp with the 13-head step on the payday.
HERD_RAMP_P = ((0, 4), (6, 8), (12, 13))


class PaydayHerdStrategy(LeanFeedStrategy):
    """`lean_feed` with the herd's last step on day 12."""

    name = "payday_herd"
    benchmark = False
    HERD_RAMP_F = HERD_RAMP_P


STRATEGY = PaydayHerdStrategy
