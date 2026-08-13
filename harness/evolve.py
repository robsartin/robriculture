from __future__ import annotations
import argparse, json, os, random, sys
from kaggisim.strategy import make_agent
from harness.tournament import play as _play
from harness.tournament import build_agents
from strategies import neuropilot as npilot

GENOME_LEN = npilot.genome_size(npilot.N_FEATURES, npilot.H1, npilot.N_KNOBS)
GENOME_ARTIFACT = os.path.join(os.path.dirname(__file__), "genomes", "champion_genome.json")


def save_genome(path, genome, meta):
    """Write a genome and metadata to a JSON file."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        json.dump({"genome": list(genome), "meta": meta}, fh, indent=2)
        fh.write("\n")

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

DEFAULT_ANCHORS = ("meta_bot", "ranch_hands", "market_farmer", "ranch_adaptive", "wheat_hands", "spoiler")

def anchor_agents(names):
    """Return the agent callables for the given registered strategy names."""
    return list(build_agents(list(names)).values())

def build_opponents(pop_agents, anchor_agents_list, hof_agents, sample_k, rng):
    """Opponent pool for a match: all anchors, all Hall-of-Fame agents, plus a random sample of the population."""
    sample = rng.sample(pop_agents, min(sample_k, len(pop_agents))) if pop_agents else []
    return list(anchor_agents_list) + list(hof_agents) + sample

def update_hof(prev_hof, elites, cap):
    """Append newly-seen elite genomes to the Hall-of-Fame, dedup, and cap to the most recent `cap`.

    cap semantics: None = unbounded; <= 0 = Hall-of-Fame disabled (empty); positive = keep
    the most-recent `cap` genomes.
    """
    combined = list(prev_hof)
    for e in elites:
        if e not in combined:
            combined.append(e)
    if cap is None:
        return combined
    if cap <= 0:
        return []
    return combined[-cap:]

def evolve(generations, pop_size, games, sigma, sample_k, hof_cap,
           anchor_names=DEFAULT_ANCHORS, seed=0, play_fn=_play):
    """Run the neuroevolution loop; return best genome/fitness and per-generation history."""
    rng = random.Random(seed)
    anchors = anchor_agents(anchor_names)
    population = initial_population(pop_size, seed)
    hof_genomes = []
    best_genome, best_fit, history = None, -1.0, []
    for gen in range(generations):
        pop_agents = [genome_agent(g) for g in population]
        hof_agents = [genome_agent(g) for g in hof_genomes]
        scored = []
        for i, g in enumerate(population):
            opp = build_opponents([pa for j, pa in enumerate(pop_agents) if j != i],
                                  anchors, hof_agents, sample_k, rng)
            scored.append((g, match_winrate(pop_agents[i], opp, games, seed + gen * 7919 + i, play_fn)))
        scored.sort(key=lambda gf: gf[1], reverse=True)
        gen_best_g, gen_best_f = scored[0]
        mean_f = sum(f for _, f in scored) / len(scored)
        history.append({"gen": gen, "best": gen_best_f, "mean": mean_f})
        if gen_best_f > best_fit:
            best_fit, best_genome = gen_best_f, gen_best_g
        elites = [g for g, _ in scored[:max(1, pop_size // 4)]]
        hof_genomes = update_hof(hof_genomes, [gen_best_g], hof_cap)
        population = next_generation(elites, pop_size, sigma, rng)
    return {"best_genome": best_genome, "best_fitness": best_fit, "history": history}


def main(argv=None):  # pragma: no cover
    ap = argparse.ArgumentParser(description="robriculture neuroevolution (#66)")
    ap.add_argument("--generations", type=int, default=10)
    ap.add_argument("--pop", type=int, default=20)
    ap.add_argument("--games", type=int, default=4)
    ap.add_argument("--sigma", type=float, default=0.2)
    ap.add_argument("--sample-k", type=int, default=4)
    ap.add_argument("--hof-cap", type=int, default=5)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--anchors", nargs="*", default=list(DEFAULT_ANCHORS),
                     help="registered strategy names to use as fixed opponents")
    ap.add_argument("--out", default=GENOME_ARTIFACT, help="where to save the champion genome")
    ap.add_argument("--dry-run", action="store_true", help="skip writing the genome artifact")
    args = ap.parse_args(argv)

    result = evolve(
        generations=args.generations,
        pop_size=args.pop,
        games=args.games,
        sigma=args.sigma,
        sample_k=args.sample_k,
        hof_cap=args.hof_cap,
        anchor_names=args.anchors,
        seed=args.seed,
    )

    for h in result["history"]:
        print(f"gen {h['gen']}: best={h['best']:.4f} mean={h['mean']:.4f}")

    if args.dry_run:
        print(f"dry-run: best_fitness={result['best_fitness']:.4f} (genome not saved)")
    else:
        save_genome(args.out, result["best_genome"], {
            "fitness": result["best_fitness"],
            "generations": args.generations,
            "pop": args.pop,
            "games": args.games,
            "sigma": args.sigma,
            "sample_k": args.sample_k,
            "hof_cap": args.hof_cap,
            "seed": args.seed,
            "anchors": args.anchors,
        })
        print(f"saved champion genome to {args.out} (fitness={result['best_fitness']:.4f})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
