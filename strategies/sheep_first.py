"""sheep_first: lean_feed with six sheep, bought first (#268).

#266 mined lean_feed's 47 rated games: opponents with four or more sheep placed
by day 8 beat it 11 of 12; against everyone else it wins 20 of 35. The winners
run 8 cows + 6 sheep at day 16 to our 8 + 3 and sell 138 wool units to our 77,
and wool is the one product with a double-consumption shop. lean_feed inherits
rival_aware's rule (#219: cows once the rival has two sheep), which answers a
sheep farm with cows -- into the milk market that farm is also flooding.

One decision changes: the herd's composition. `herd_preference` asks for SHEEP
until six sheep are placed or pending, then COW, and never reads the rival. The
ramp, the buy order, the feed sizing and everything else are lean_feed's.

Declared before measurement: `SHEEP_TARGET`, and the controls and criterion in
`harness/sheep_bench.py` (posted to #268 before any code).
"""

from __future__ import annotations

from strategies.lean_feed import LeanFeedStrategy

#: Sheep to own before the herd goes back to cows.
SHEEP_TARGET = 6


def our_sheep(tiles, shed) -> int:
    """Sheep on our tiles plus sheep waiting in the shed to be walked out.
    Counting the pending ones is what stops the ramp's per-turn loop from
    ordering the whole target again every turn (the benchmark's `pending`)."""
    placed = sum(1 for row in (tiles or []) for t in row
                 if isinstance(t, dict) and t.get("animal") == "SHEEP")
    return placed + int((shed or {}).get("SHEEP", 0) or 0)


class SheepFirstStrategy(LeanFeedStrategy):
    """`lean_feed` with sheep bought first, to six."""

    name = "sheep_first"
    benchmark = False

    def herd_preference(self, obs):
        """SHEEP until `SHEEP_TARGET` are ours, then COW. Reads only our own
        farm; a malformed observation degrades to SHEEP (ADR-0006)."""
        try:
            me = obs["farms"][obs["player"]]
            shed = (obs.get("private") or {}).get("shed") or {}
            have = our_sheep(me.get("tiles"), shed)
        except (LookupError, TypeError, AttributeError):
            return "SHEEP"
        return "SHEEP" if have < SHEEP_TARGET else "COW"


STRATEGY = SheepFirstStrategy
