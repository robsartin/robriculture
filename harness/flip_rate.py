"""Flip-rate measurement (#77) — how much of ADR-0007's N=200 is real evidence?

The promotion gate (`harness/promotion.py`) treats 200 seeded games as ~200
independent trials and feeds their win/loss tally to a binomial test. That is
only true if the *outcome* (not just the reward) actually varies with the
seed. This module measures that directly: for every pairing among a set of
agents, play a fixed sequence of seeds and count how many *distinct* outcomes
occur. A pairing with `distinct_outcomes == 1` never flips — its 200 games are
one repeated observation wearing 200 different seeds, and the gate's p-value
is not measuring what it claims to.

This does not change what the gate measures (that decision is closed, #77);
it measures the gate's own assumption so ADR-0007 can say plainly what is and
isn't established.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass

from harness.tournament import build_agents, play as _play


@dataclass(frozen=True)
class PairingFlips:
    """One pairing's outcome sequence across a fixed set of seeds.

    `outcomes` is from `a`'s point of view: 1 = a wins, -1 = b wins, 0 = tie
    (the same convention as `harness.tournament.play`). Sides are not
    alternated here — unlike `promotion.run_match`, the question is not "who
    wins on average" but "does the outcome ever change," so every seed is
    played with the same fixed assignment of sides.
    """

    a: str
    b: str
    outcomes: tuple[int, ...]

    @property
    def distinct_outcomes(self) -> int:
        return len(set(self.outcomes))

    @property
    def flipped(self) -> bool:
        """True iff at least two seeds produced different outcomes."""
        return self.distinct_outcomes > 1


@dataclass(frozen=True)
class FlipSummary:
    """Aggregate flip rate across a set of measured pairings."""

    pairings: int
    flipped_pairings: int

    @property
    def flip_rate(self) -> float:
        return self.flipped_pairings / self.pairings


def measure_pairing(agent_a, agent_b, seeds, play_fn=_play):
    """Play `agent_a` vs `agent_b` at each seed; return the raw outcome sequence."""
    return tuple(play_fn(agent_a, agent_b, seed) for seed in seeds)


def measure_flip_rate(agents, seeds, play_fn=_play):
    """Measure every unordered pairing among `agents` (a {label: agent} map).

    Returns a list of `PairingFlips`, one per pairing, in `itertools.combinations`
    order. `seeds` is shared across every pairing so the same seed set backs
    every comparison (ADR-0005 reproducibility).
    """
    labels = list(agents)
    results = []
    for a, b in itertools.combinations(labels, 2):
        outcomes = measure_pairing(agents[a], agents[b], seeds, play_fn=play_fn)
        results.append(PairingFlips(a, b, outcomes))
    return results


def summarize(results):
    """Aggregate `measure_flip_rate`'s output into a `FlipSummary`.

    Raises on an empty `results` rather than silently reporting a 0.0 flip
    rate, which would read as "measured: never flips" instead of "measured
    nothing."
    """
    if not results:
        raise ValueError("cannot summarize an empty list of pairings")
    flipped = sum(1 for r in results if r.flipped)
    return FlipSummary(pairings=len(results), flipped_pairings=flipped)


# --- CLI: thin glue over the tested functions above ---

def main(argv=None):  # pragma: no cover
    import argparse

    ap = argparse.ArgumentParser(
        description="robriculture flip-rate measurement (#77): how often does a "
                    "pairing's outcome change across seeds?"
    )
    ap.add_argument("names", nargs="*", help="agent names (default: the DEFAULT_ANCHORS pool)")
    ap.add_argument("--seeds", type=int, default=10, help="number of seeds per pairing (default 10)")
    args = ap.parse_args(argv)

    if args.names:
        names = args.names
    else:
        from harness.evolve import DEFAULT_ANCHORS
        names = list(DEFAULT_ANCHORS)

    agents = build_agents(names)
    seeds = list(range(args.seeds))
    print(f"Flip-rate measurement: {names}  ({args.seeds} seeds/pairing, "
          f"{len(names) * (len(names) - 1) // 2} pairings)\n")

    results = measure_flip_rate(agents, seeds)
    for r in sorted(results, key=lambda r: (-r.distinct_outcomes, r.a, r.b)):
        marker = "FLIPPED" if r.flipped else "constant"
        print(f"  {r.a:16s} vs {r.b:16s}  outcomes={r.outcomes}  "
              f"distinct={r.distinct_outcomes}  {marker}")

    summary = summarize(results)
    print(f"\n{summary.flipped_pairings}/{summary.pairings} pairings flipped "
          f"across {args.seeds} seeds  (flip-rate={summary.flip_rate:.1%})")
    return 0


if __name__ == "__main__":  # pragma: no cover
    import sys
    sys.exit(main())
