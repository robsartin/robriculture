"""Frozen benchmark of a single genome against the fixed anchors (#70).

The evolution loop's own fitness is not comparable between runs — its opponent
pool contains a growing Hall-of-Fame and a random population sample, so the
number shifts underneath you. This module plays a genome against the named
anchors ONLY, at fixed seeds, so two runs can actually be compared.

It reports win-rate AND mean score share. Fitness optimizes share, but the
Kaggle ladder scores win/tie only — reporting both makes any divergence between
them visible instead of assumed away.

Usage:
    python -m harness.genome_bench --genome strategies/champion_genome.json --games 4
"""

from __future__ import annotations

import argparse
import sys

from harness.evolve import (DEFAULT_ANCHORS, genome_agent, load_genome,
                            opponent_record)
from harness.tournament import build_agents
from harness.tournament import play_rewards as _play_rewards


def _passer():
    """A do-nothing agent, used when no genome is supplied (tests)."""
    def agent(obs):
        return {"farmer": ["PASS"], "hands": [], "market": []}
    return agent


def benchmark_genome(genome, anchor_names=DEFAULT_ANCHORS, games=4, seed_base=0,
                     rewards_fn=None, agents_override=None):
    """Play `genome` against each anchor and report the per-opponent breakdown.

    No Hall-of-Fame and no population sample: those are what let sibling-beating
    dominate the evolution fitness and saturate it at 0.5833 (#70). Seeds derive
    from the opponent index and game number, so the result reproduces exactly.
    """
    rewards_fn = rewards_fn or _play_rewards
    agents = (agents_override if agents_override is not None
              else build_agents(list(anchor_names)))
    me = genome_agent(genome) if genome is not None else _passer()

    rows = []
    for oi, (name, opp) in enumerate(agents.items()):
        rec = opponent_record(me, opp, games, seed_base + oi * 100000, rewards_fn)
        rows.append({"name": name, **rec})

    n = len(rows)
    return {
        "per_opponent": rows,
        "win_rate": sum(r["win_rate"] for r in rows) / n if n else 0.5,
        "share": sum(r["share"] for r in rows) / n if n else 0.5,
        "games": sum(r["games"] for r in rows),
    }


def main(argv=None):  # pragma: no cover
    ap = argparse.ArgumentParser(description="benchmark one genome vs the fixed anchors (#70)")
    ap.add_argument("--genome", required=True, help="path to a genome artifact")
    ap.add_argument("--games", type=int, default=4)
    ap.add_argument("--seed-base", type=int, default=0)
    ap.add_argument("--anchors", nargs="*", default=list(DEFAULT_ANCHORS))
    args = ap.parse_args(argv)

    out = benchmark_genome(load_genome(args.genome), anchor_names=args.anchors,
                           games=args.games, seed_base=args.seed_base)
    for r in out["per_opponent"]:
        print(f"{r['name']:16s} W{r['w']} T{r['t']} L{r['l']}  "
              f"rate={r['win_rate']:.3f} share={r['share']:.3f}")
    print(f"{'TOTAL':16s} games={out['games']}  "
          f"rate={out['win_rate']:.4f} share={out['share']:.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
