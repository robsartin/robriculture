"""Parent/offspring mutation-correlation measurement (#99).

Three neuroevolution runs (#70, #97, two earlier) have all peaked at
generation 0 or 1: the population *mean* fitness climbs while the *best*
never improves on its initial draw. That is the signature of a population
converging on its best initial member rather than discovering anything new.

Before tuning any parameter, #99 asks the cheaper question first: **do
offspring resemble their parents at all** at the sigmas evolve() actually
uses? If a mutant's fitness is uncorrelated with its parent's, mutation is
producing an independent random genome, not a nearby neighbor — and the
search is doing random restarts, which would explain all three runs at once
regardless of population size, elitism, or fitness noise.

This module mutates one fixed parent genome at each of several sigmas via
the *real* `harness.evolve.mutate`, scores every offspring with an injected
`fitness_fn`, and summarizes the spread relative to the parent's own
fitness. With a single fixed parent, Pearson correlation is undefined (the
parent side of the pair has zero variance) — so the "spread of offspring
fitness around the parent's" the issue names as the more direct alternative
is what `SigmaResult` reports: mean, stdev, the fraction landing within a
small band of the parent, and the fraction that strictly beat it.

The game-playing stays injectable (`mutate_fn`, `fitness_fn`) so this pure
aggregation unit-tests against a stub, the same pattern
`harness.flip_rate` and `harness.genome_bench` use.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass


@dataclass(frozen=True)
class SigmaResult:
    """One sigma's offspring-fitness sample, summarized against the parent's fitness."""

    sigma: float
    parent_fitness: float
    offspring_fitness: tuple

    @property
    def mean(self) -> float:
        return statistics.fmean(self.offspring_fitness) if self.offspring_fitness else 0.0

    @property
    def stdev(self) -> float:
        """Population spread of offspring fitness. 0.0 with fewer than two samples
        rather than raising — a single offspring has no spread to measure."""
        if len(self.offspring_fitness) < 2:
            return 0.0
        return statistics.pstdev(self.offspring_fitness)

    def band_fraction(self, band: float) -> float:
        """Fraction of offspring within `band` absolute fitness of the parent.

        A high fraction here at a given sigma means offspring cluster near the
        parent (mutation is "nearby"); a low fraction means offspring scatter
        across the fitness range regardless of where the parent sits.
        """
        if not self.offspring_fitness:
            return 0.0
        near = sum(1 for f in self.offspring_fitness if abs(f - self.parent_fitness) <= band)
        return near / len(self.offspring_fitness)

    @property
    def beat_parent_fraction(self) -> float:
        """Fraction of offspring that strictly exceed the parent's fitness.

        Zero offspring measured means no evidence of beating the parent —
        report 0.0, not a ZeroDivisionError.
        """
        if not self.offspring_fitness:
            return 0.0
        beat = sum(1 for f in self.offspring_fitness if f > self.parent_fitness)
        return beat / len(self.offspring_fitness)


def sample_offspring(parent, sigma, n, mutate_fn, rng):
    """Generate `n` mutant genomes from `parent` at one `sigma`.

    `mutate_fn` is `harness.evolve.mutate`'s signature — (genome, sigma, rng)
    — so this exercises the actual mutation operator the search uses, not a
    model of it. All `n` draws share one `rng` stream, so the whole call is a
    single reproducible sample (ADR-0005), not `n` independently-seeded ones.
    """
    return [mutate_fn(parent, sigma, rng) for _ in range(n)]


def measure_sigma(parent, parent_fitness, sigma, n, mutate_fn, fitness_fn, rng):
    """Mutate `parent` `n` times at `sigma`, score each offspring, summarize vs. the parent."""
    offspring = sample_offspring(parent, sigma, n, mutate_fn, rng)
    fitnesses = tuple(fitness_fn(g) for g in offspring)
    return SigmaResult(sigma=sigma, parent_fitness=parent_fitness, offspring_fitness=fitnesses)


def measure_sigmas(parent, parent_fitness, sigmas, n, mutate_fn, fitness_fn, rng):
    """Run `measure_sigma` across every sigma in `sigmas`, in order.

    One `rng` threads through the whole sweep so it is a single reproducible
    draw rather than independently-seeded sub-experiments per sigma.
    """
    return [
        measure_sigma(parent, parent_fitness, sigma, n, mutate_fn, fitness_fn, rng)
        for sigma in sigmas
    ]


# --- CLI: thin glue over the tested functions above ---

def main(argv=None):  # pragma: no cover
    import argparse
    import random as _random

    from harness.evolve import (DEFAULT_ANCHORS, anchor_agents, genome_agent,
                                load_genome, match_share, mutate)
    from harness.tournament import play_rewards as _play_rewards

    ap = argparse.ArgumentParser(
        description="robriculture parent/offspring mutation-correlation measurement (#99)")
    ap.add_argument("--genome", default="strategies/champion_genome.json",
                    help="parent genome artifact (default: the baked champion)")
    ap.add_argument("--sigmas", type=float, nargs="*", default=[0.01, 0.05, 0.1, 0.2])
    ap.add_argument("--n", type=int, default=8, help="offspring per sigma")
    ap.add_argument("--games", type=int, default=2, help="games per anchor (matches evolve's default gate)")
    ap.add_argument("--anchors", nargs="*", default=list(DEFAULT_ANCHORS))
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--band", type=float, default=0.02, help="near-parent band width for band_fraction")
    args = ap.parse_args(argv)

    parent = load_genome(args.genome)
    anchors = anchor_agents(args.anchors)
    rng = _random.Random(args.seed)

    def fitness_fn(genome):
        return match_share(genome_agent(genome), anchors, args.games, seed_base=0,
                           rewards_fn=_play_rewards)

    parent_fitness = fitness_fn(parent)
    print(f"parent fitness (anchor share, games={args.games}): {parent_fitness:.4f}\n")

    results = measure_sigmas(parent, parent_fitness, args.sigmas, args.n,
                             mutate_fn=mutate, fitness_fn=fitness_fn, rng=rng)
    for r in results:
        print(f"sigma={r.sigma:<5} n={len(r.offspring_fitness)}  "
              f"mean={r.mean:.4f}  stdev={r.stdev:.4f}  "
              f"within_{args.band}={r.band_fraction(args.band):.2f}  "
              f"beat_parent={r.beat_parent_fraction:.2f}  "
              f"raw={[round(f, 4) for f in r.offspring_fitness]}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    import sys
    sys.exit(main())
