from __future__ import annotations
import random
from strategies import neuropilot as npilot

GENOME_LEN = npilot.genome_size(npilot.N_FEATURES, npilot.H1, npilot.N_KNOBS)

def initial_population(size, seed):
    return [npilot.random_genome(npilot.N_FEATURES, npilot.H1, npilot.N_KNOBS, seed=seed * 1000 + i)
            for i in range(size)]

def mutate(genome, sigma, rng):
    if sigma == 0.0:
        return list(genome)
    return [w + rng.gauss(0.0, sigma) for w in genome]

def select_elites(scored, k):
    ranked = sorted(scored, key=lambda gf: gf[1], reverse=True)
    return [g for g, _ in ranked[:k]]

def next_generation(elites, size, sigma, rng):
    gen = [list(e) for e in elites]                 # elitism: carry survivors verbatim
    while len(gen) < size:
        parent = elites[rng.randrange(len(elites))]
        gen.append(mutate(parent, sigma, rng))
    return gen[:size]
