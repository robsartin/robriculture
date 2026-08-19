"""Tests for the parent/offspring mutation-correlation harness (#99).

#99's question: does an offspring genome's fitness resemble its parent's at
the mutation sigmas evolve() actually uses, or is a mutant effectively an
independent random draw? This module measures that directly: mutate a fixed
parent genome at a set of sigmas via the real `harness.evolve.mutate`, score
each offspring with an injected fitness_fn, and summarize the spread of
offspring fitness relative to the parent's own fitness. The pure aggregation
is tested here with a stub fitness_fn/mutate_fn (the same seam
`tests/test_flip_rate.py` and `tests/test_genome_bench.py` use), so these
tests need no real (slow) games.
"""

from __future__ import annotations

import random

import pytest

from harness import mutation_correlation as mc
from harness.mutation_correlation import SigmaResult


def _stub_mutate(genome, sigma, rng):
    """A fake mutate: nudge every weight by sigma * rng.random(), deterministic per rng."""
    return [w + sigma * rng.random() for w in genome]


# --- sample_offspring: generate n mutants at one sigma via an injected mutate_fn ---

def test_sample_offspring_returns_n_genomes():
    """Requesting 5 offspring yields exactly 5 mutant genomes."""
    parent = [0.0, 0.0, 0.0]
    offspring = mc.sample_offspring(parent, sigma=0.1, n=5, mutate_fn=_stub_mutate,
                                     rng=random.Random(1))
    assert len(offspring) == 5
    assert all(len(g) == len(parent) for g in offspring)


def test_sample_offspring_calls_mutate_fn_with_sigma_and_shared_rng():
    """Each offspring is produced by mutate_fn(parent, sigma, rng) — the real
    harness.evolve.mutate signature — so this measures the actual search."""
    calls = []

    def recording_mutate(genome, sigma, rng):
        calls.append((tuple(genome), sigma))
        return list(genome)

    parent = [1.0, 2.0]
    mc.sample_offspring(parent, sigma=0.05, n=3, mutate_fn=recording_mutate,
                         rng=random.Random(2))
    assert calls == [((1.0, 2.0), 0.05)] * 3


def test_sample_offspring_is_deterministic_given_a_seeded_rng():
    """Same rng seed, same mutate_fn => identical offspring, every time (ADR-0005)."""
    parent = [0.0] * 4
    a = mc.sample_offspring(parent, sigma=0.2, n=4, mutate_fn=_stub_mutate,
                             rng=random.Random(7))
    b = mc.sample_offspring(parent, sigma=0.2, n=4, mutate_fn=_stub_mutate,
                             rng=random.Random(7))
    assert a == b


# --- measure_sigma: mutate + score at one sigma, summarized against the parent ---

def test_measure_sigma_reports_offspring_fitness_per_genome():
    """One SigmaResult per sigma, carrying every offspring's fitness score."""
    parent = [0.0, 0.0]
    fitnesses = iter([0.5, 0.5, 0.5])

    def fake_fitness(genome):
        return next(fitnesses)

    result = mc.measure_sigma(parent, parent_fitness=0.5, sigma=0.1, n=3,
                              mutate_fn=_stub_mutate, fitness_fn=fake_fitness,
                              rng=random.Random(3))
    assert isinstance(result, SigmaResult)
    assert result.sigma == 0.1
    assert result.offspring_fitness == (0.5, 0.5, 0.5)
    assert result.parent_fitness == 0.5


def test_sigma_result_mean_and_stdev_summarize_the_spread():
    """Offspring fitness of 0.2, 0.4, 0.6 has mean 0.4 and a nonzero spread."""
    r = SigmaResult(sigma=0.1, parent_fitness=0.5, offspring_fitness=(0.2, 0.4, 0.6))
    assert r.mean == pytest.approx(0.4)
    assert r.stdev > 0.0


def test_sigma_result_stdev_is_zero_with_one_offspring():
    """A single offspring has no spread to measure — stdev is 0.0, not a crash."""
    r = SigmaResult(sigma=0.1, parent_fitness=0.5, offspring_fitness=(0.4,))
    assert r.stdev == 0.0


def test_sigma_result_band_fraction_counts_offspring_near_the_parent():
    """Within-band membership uses absolute distance from the parent's own fitness."""
    r = SigmaResult(sigma=0.1, parent_fitness=0.5, offspring_fitness=(0.48, 0.52, 0.9, 0.1))
    # band=0.05: 0.48 and 0.52 are within 0.02 of 0.5; 0.9 and 0.1 are not.
    assert r.band_fraction(band=0.05) == pytest.approx(0.5)


def test_sigma_result_band_fraction_is_zero_with_no_offspring():
    """No offspring measured means no evidence of clustering near the parent — 0.0, not a crash."""
    r = SigmaResult(sigma=0.1, parent_fitness=0.5, offspring_fitness=())
    assert r.band_fraction(band=0.05) == 0.0


def test_sigma_result_beat_parent_fraction_counts_strict_improvement():
    """Only offspring that strictly exceed the parent's fitness count as beating it."""
    r = SigmaResult(sigma=0.1, parent_fitness=0.5, offspring_fitness=(0.5, 0.51, 0.49, 0.6))
    assert r.beat_parent_fraction == pytest.approx(0.5)          # 0.51 and 0.6 of 4


def test_sigma_result_beat_parent_fraction_is_zero_with_no_offspring():
    """No offspring measured means no evidence of beating the parent — 0.0, not a crash."""
    r = SigmaResult(sigma=0.1, parent_fitness=0.5, offspring_fitness=())
    assert r.beat_parent_fraction == 0.0
    assert r.mean == 0.0
    assert r.stdev == 0.0


# --- measure_sigmas: run measure_sigma across every requested sigma ---

def test_measure_sigmas_returns_one_result_per_sigma_in_order():
    """Four requested sigmas yield four SigmaResults, in the order given."""
    parent = [0.0, 0.0]

    def fake_fitness(genome):
        return 0.5

    results = mc.measure_sigmas(parent, parent_fitness=0.5, sigmas=[0.01, 0.05, 0.1, 0.2],
                                n=2, mutate_fn=_stub_mutate, fitness_fn=fake_fitness,
                                rng=random.Random(4))
    assert [r.sigma for r in results] == [0.01, 0.05, 0.1, 0.2]
    assert all(len(r.offspring_fitness) == 2 for r in results)


def test_measure_sigmas_shares_one_rng_stream_across_sigmas():
    """A single rng threads through every sigma so the whole sweep is one
    reproducible draw, not independently-seeded sub-experiments."""
    parent = [0.0, 0.0]

    def fake_fitness(genome):
        return 0.5

    a = mc.measure_sigmas(parent, parent_fitness=0.5, sigmas=[0.1, 0.2], n=2,
                          mutate_fn=_stub_mutate, fitness_fn=fake_fitness,
                          rng=random.Random(9))
    b = mc.measure_sigmas(parent, parent_fitness=0.5, sigmas=[0.1, 0.2], n=2,
                          mutate_fn=_stub_mutate, fitness_fn=fake_fitness,
                          rng=random.Random(9))
    assert [r.offspring_fitness for r in a] == [r.offspring_fitness for r in b]
