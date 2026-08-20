"""Seed-only noise calibration across --games counts (#103).

#99/#102 measured that at the harness default `--games 2`, one *fixed*
genome's score wanders by stdev 0.0019 (spread 0.0073) purely from the seed
rotation `evolve()` applies per generation (`seed + gen*7919`) -- a size
comparable to the stdev 0.0071 that sigma-0.05 offspring actually differ
from their parent by. When those two are the same size, `evolve()` ranking
16 offspring is largely sorting seed luck, not genotype quality, and
selection cannot reliably compound.

#103 asks the calibration question: how many games per evaluation does it
take for that seed-only noise to sit *materially below* the spread mutation
actually produces? Noise falls as 1/sqrt(games), so this is a measure-first
question, not a guess. This module:

  - measures a fixed genome's score at the same ten seed bases evolve() uses
    (`seed_bases`, `measure_noise`), repeated across a sweep of --games
    counts (`measure_noise_by_games`) -- the direct games-count analogue of
    #99's `mutation_correlation.py` sigma sweep;
  - estimates how much a 12-generation `best` (a running maximum over noisy
    draws) drifts upward from noise alone, by bootstrap-resampling the
    measured noise samples (`bootstrap_max_drift`) rather than assuming a
    parametric (e.g. normal order-statistics) formula -- so a calibrated
    run's real gain can be judged against that baseline instead of eyeballed.

Game-playing stays injectable (`fitness_fn`, `rng`) so this pure aggregation
unit-tests against a stub, the same pattern `mutation_correlation.py`,
`flip_rate.py`, and `genome_bench.py` use. Kept as a sibling module rather
than folded into `mutation_correlation.py` because it sweeps a different
axis (--games, holding the genome and sigma fixed) with a different output
shape (NoiseResult has no parent/offspring distinction) -- the same
one-measurement-per-file split the harness already uses for flip_rate,
genome_bench, mutation_correlation, and ladder_correlation.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass

# The exact per-generation seed rotation harness.evolve.evolve() applies:
# `base = seed + gen * 7919`. Duplicated here (not imported) because it is a
# constant of evolve()'s scoring loop, not a function -- see harness/evolve.py.
GEN_SEED_STRIDE = 7919


@dataclass(frozen=True)
class NoiseResult:
    """One games-count's worth of a fixed genome's scores across seed bases."""

    games: int
    scores: tuple

    @property
    def mean(self) -> float:
        return statistics.fmean(self.scores) if self.scores else 0.0

    @property
    def spread(self) -> float:
        """Peak-to-trough range -- the #99/#102 scratch measurement's statistic,
        and the one that matters for ranking: selection sees the extremes of a
        population, not just its central tendency. 0.0 with no scores."""
        if not self.scores:
            return 0.0
        return max(self.scores) - min(self.scores)

    @property
    def stdev(self) -> float:
        """Sample stdev (statistics.stdev, ddof=1) -- matches the #99/#102
        scratch measurement's reported numbers exactly, so this tool's output
        is directly comparable/reproducible against them. 0.0 with fewer than
        two scores rather than raising -- a single score has no spread."""
        if len(self.scores) < 2:
            return 0.0
        return statistics.stdev(self.scores)


def seed_bases(seed: int, n: int) -> list:
    """The first `n` seed bases evolve() would use for generations 0..n-1.

    Mirrors `base = seed + gen * 7919` from harness.evolve.evolve() exactly,
    so noise measured here is the noise evolve() actually experiences.
    """
    return [seed + gen * GEN_SEED_STRIDE for gen in range(n)]


def measure_noise(games: int, seed_bases: list, fitness_fn) -> NoiseResult:
    """Score one fixed genome at `games` games, once per seed base in `seed_bases`.

    `fitness_fn(games, seed_base) -> float` is the real match_share call bound
    to a fixed genome and anchor set by the caller (see main() below) -- kept
    injectable so this stays a fast, pure-aggregation unit test target.
    """
    scores = tuple(fitness_fn(games, sb) for sb in seed_bases)
    return NoiseResult(games=games, scores=scores)


def measure_noise_by_games(games_counts: list, seed_bases: list, fitness_fn) -> list:
    """Run measure_noise across every games count in `games_counts`, in order.

    The same `seed_bases` are reused at every games count, so the sweep
    isolates the effect of --games rather than confounding it with a
    different set of seed draws.
    """
    return [measure_noise(g, seed_bases, fitness_fn) for g in games_counts]


def bootstrap_max_drift(samples, n_draws: int, trials: int, rng) -> float:
    """Estimate how far a max over `n_draws` noisy draws lands above the mean.

    `evolve()`'s reported `best` is a running maximum over `generations`
    noisy per-generation fitness draws. Even with zero learning, the max of
    N noisy draws of the same true fitness drifts upward as N grows --
    that's the "run-to-run noise" #99's follow-up flagged as the confound in
    a naive gen0-vs-peak comparison.

    Rather than assume a parametric shape (e.g. a normal order-statistics
    formula), this resamples `samples` (the measured seed-only noise, i.e.
    one NoiseResult's `.scores`) with replacement `trials` times, takes the
    max of each `n_draws`-sized resample, and reports how far the average of
    those maxima sits above the samples' own mean -- #103's "measure it
    directly by running the maximum over noise-only samples."

    No samples measured means no basis for an estimate: 0.0, not a crash.
    """
    if not samples:
        return 0.0
    baseline = statistics.fmean(samples)
    maxima = [max(rng.choices(samples, k=n_draws)) for _ in range(trials)]
    return statistics.fmean(maxima) - baseline


# --- CLI: thin glue over the tested functions above ---

def main(argv=None):  # pragma: no cover
    import argparse
    import random as _random

    from harness.evolve import DEFAULT_ANCHORS, anchor_agents, genome_agent, load_genome, match_share
    from harness.tournament import play_rewards as _play_rewards

    ap = argparse.ArgumentParser(
        description="robriculture seed-only noise calibration across --games counts (#103)")
    ap.add_argument("--genome", default="strategies/champion_genome.json",
                    help="fixed genome to measure (default: the committed champion)")
    ap.add_argument("--games", type=int, nargs="*", default=[2, 4, 8, 16],
                    help="--games counts to sweep")
    ap.add_argument("--n-seeds", type=int, default=10,
                    help="how many of evolve()'s seed bases to sample per games count")
    ap.add_argument("--seed", type=int, default=1,
                    help="seed_bases() base seed (1 matches the #99/#102 scratch measurement)")
    ap.add_argument("--anchors", nargs="*", default=list(DEFAULT_ANCHORS))
    ap.add_argument("--offspring-stdev", type=float, default=None,
                    help="sigma-0.05 offspring stdev to compare against, if known (#99: 0.0071)")
    ap.add_argument("--n-draws", type=int, default=12,
                    help="generations in the run this calibrates -- for the bootstrap max-drift estimate")
    ap.add_argument("--trials", type=int, default=20000,
                    help="bootstrap resamples for the max-drift estimate")
    args = ap.parse_args(argv)

    parent = load_genome(args.genome)
    anchors = anchor_agents(args.anchors)
    agent = genome_agent(parent)
    bases = seed_bases(args.seed, args.n_seeds)

    def fitness_fn(games, seed_base):
        return match_share(agent, anchors, games, seed_base, rewards_fn=_play_rewards)

    results = measure_noise_by_games(args.games, bases, fitness_fn)

    print(f"genome={args.genome}  seed_bases={bases}\n")
    for r in results:
        line = f"games={r.games:<3} mean={r.mean:.4f}  spread={r.spread:.4f}  stdev={r.stdev:.4f}"
        if args.offspring_stdev:
            line += f"  spread/offspring_stdev={r.spread / args.offspring_stdev:.2f}x"
        print(line)

    rng = _random.Random(args.seed)
    print(f"\nbootstrap max-drift over {args.n_draws} draws ({args.trials} trials):")
    for r in results:
        drift = bootstrap_max_drift(r.scores, args.n_draws, args.trials, rng)
        print(f"  games={r.games:<3} expected max-drift={drift:.4f}")

    return 0


if __name__ == "__main__":  # pragma: no cover
    import sys
    sys.exit(main())
