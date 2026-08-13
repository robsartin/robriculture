"""Neuroevolution harness (Phase 2, #66)."""
from __future__ import annotations
import random
from harness import evolve as ev


def test_initial_population_shape_and_determinism():
    pop = ev.initial_population(5, seed=1)
    assert len(pop) == 5
    assert all(len(g) == ev.GENOME_LEN for g in pop)
    assert ev.initial_population(5, seed=1) == pop            # deterministic
    assert ev.initial_population(5, seed=2) != pop            # seed matters


def test_mutate_preserves_length_changes_weights_deterministically():
    g = [0.0] * ev.GENOME_LEN
    m1 = ev.mutate(g, sigma=0.1, rng=random.Random(7))
    assert len(m1) == ev.GENOME_LEN and m1 != g
    assert m1 == ev.mutate(g, sigma=0.1, rng=random.Random(7))  # same rng seed => same


def test_mutate_sigma_zero_is_a_noop():
    g = [0.3] * ev.GENOME_LEN
    assert ev.mutate(g, sigma=0.0, rng=random.Random(1)) == g


def test_select_elites_returns_top_k_by_fitness():
    scored = [(["a"], 0.2), (["b"], 0.9), (["c"], 0.5)]
    assert ev.select_elites(scored, 2) == [["b"], ["c"]]


def test_next_generation_keeps_elites_and_refills_to_size():
    elites = [[0.0]*ev.GENOME_LEN, [1.0]*ev.GENOME_LEN]
    gen = ev.next_generation(elites, size=5, sigma=0.1, rng=random.Random(3))
    assert len(gen) == 5
    assert gen[0] in elites and gen[1] in elites               # elitism: elites carried verbatim
