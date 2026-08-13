from __future__ import annotations
import random
from kaggisim.strategy import make_agent
from harness.tournament import play as _play
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

def genome_agent(genome):
    """Return the agent callable for a genome."""
    return make_agent(npilot.NeuroPilotStrategy(genome=genome))

def match_winrate(agent, opponents, games, seed_base, play_fn=_play):
    """Calculate win-rate (ties count as 0.5) playing agent against all opponents.

    Plays agent against each opponent for `games` games, alternating sides.
    Ties count as 0.5 wins. Returns (wins + 0.5*ties) / total.
    """
    wins = ties = total = 0
    for oi, opp in enumerate(opponents):
        for g in range(games):
            seed = seed_base + oi * 100000 + g
            r = play_fn(agent, opp, seed) if g % 2 == 0 else -play_fn(opp, agent, seed)
            total += 1
            if r > 0: wins += 1
            elif r == 0: ties += 1
    return (wins + 0.5 * ties) / total if total else 0.5

def evaluate_population(population, opponents, games, seed_base, play_fn=_play):
    """Evaluate all genomes in population; return [(genome, fitness), ...]."""
    return [(g, match_winrate(genome_agent(g), opponents, games, seed_base + i, play_fn))
            for i, g in enumerate(population)]
