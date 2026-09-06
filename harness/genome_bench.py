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

``--include-external`` additionally benchmarks against real competitor agents
fetched locally into the gitignored ``external_agents/`` directory (#78, see
``scripts/fetch_external_agents.py``). Off by default, and opt-in only: the
named anchors alone remain the frozen, reproducible comparability bar.
"""

from __future__ import annotations

import argparse
import sys

from harness import external_pool
from harness.evolve import (DEFAULT_ANCHORS, genome_agent, load_genome,
                            opponent_record)
from harness.tournament import build_agents
from harness.tournament import play_rewards as _play_rewards


def benchmark_genome(genome, anchor_names=DEFAULT_ANCHORS, games=4, seed_base=0,
                     rewards_fn=None, agents_override=None):
    """Play `genome` against each anchor and report the per-opponent breakdown.

    No Hall-of-Fame and no population sample: those are what let sibling-beating
    dominate the evolution fitness and saturate it at 0.5833 (#70). Seeds derive
    from the opponent index and game number, so the result reproduces exactly.

    `genome` is normally a genome list, turned into an agent via genome_agent().
    An already-built agent callable (the same seam agents_override provides for
    the opponent side) is used as-is, so tests can supply a lightweight stub
    instead of round-tripping through a real NeuroPilotStrategy.
    """
    rewards_fn = rewards_fn or _play_rewards
    agents = (agents_override if agents_override is not None
              else build_agents(list(anchor_names)))
    me = genome if callable(genome) else genome_agent(genome)

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


def build_bench_agents(anchor_names, include_external=False, discover_fn=None, build=build_agents,
                       allow_partial=False):
    """Resolve the opponent set for a genome_bench run.

    Default (``include_external=False``) is exactly the named anchors, built
    the normal way -- this is the reproducible frozen bar every evolution run
    is compared against (CLAUDE.md), and it must never depend on what
    happens to be sitting in the gitignored, un-fetched
    ``external_agents/`` directory. Discovery is not even attempted on this
    path.

    ``include_external=True`` additionally folds in whatever real competitor
    agents ``harness.external_pool.discover_external_agents`` finds locally
    (#78) -- opt-in only; never wired into ``DEFAULT_ANCHORS`` or
    ``harness.promotion.designate``. It raises when the pool is short of the
    manifest (including the fully-empty case) rather than quietly falling
    back to a shrunken or internal-only pool; ``allow_partial=True`` accepts
    that shortfall with a loud warning instead (#153).

    The composition itself lives in ``harness.external_pool.resolve_opponents``
    so the evolution fitness pool and this frozen bar cannot drift apart on who
    counts as an opponent (#149).
    """
    return external_pool.resolve_opponents(
        anchor_names, include_external=include_external,
        discover_fn=discover_fn, build=build, allow_partial=allow_partial)


def main(argv=None):  # pragma: no cover
    ap = argparse.ArgumentParser(description="benchmark one genome vs the fixed anchors (#70)")
    ap.add_argument("--genome", required=True, help="path to a genome artifact")
    ap.add_argument("--games", type=int, default=4)
    ap.add_argument("--seed-base", type=int, default=0)
    ap.add_argument("--anchors", nargs="*", default=list(DEFAULT_ANCHORS))
    ap.add_argument("--include-external", action="store_true",
                    help="also benchmark against real competitor agents fetched locally "
                         "into external_agents/ (#78); measurement only, off by default "
                         "so the frozen bar stays reproducible")
    args = ap.parse_args(argv)

    agents = build_bench_agents(args.anchors, include_external=args.include_external)
    out = benchmark_genome(load_genome(args.genome), anchor_names=args.anchors,
                           games=args.games, seed_base=args.seed_base,
                           agents_override=agents)
    for r in out["per_opponent"]:
        print(f"{r['name']:16s} W{r['w']} T{r['t']} L{r['l']}  "
              f"rate={r['win_rate']:.3f} share={r['share']:.3f}")
    print(f"{'TOTAL':16s} games={out['games']}  "
          f"rate={out['win_rate']:.4f} share={out['share']:.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
