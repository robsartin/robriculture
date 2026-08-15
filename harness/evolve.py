from __future__ import annotations
import argparse, json, os, random, sys
from kaggisim.strategy import make_agent
from harness.tournament import play_rewards as _play_rewards
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

def seeded_population(seed_genome, size, sigma, rng):
    """Population seeded from an existing champion: the seed itself, then mutants.

    A fresh random start throws away everything a previous run learned — the
    evolved champion earns ~20,000 reward where a random genome earns ~1,700, so
    an unseeded run spends its first generations re-deriving the basics (#70).
    Keeping the seed verbatim at index 0 means the run can never end up worse
    than where it began.
    """
    pop = [list(seed_genome)]
    while len(pop) < size:
        pop.append(mutate(seed_genome, sigma, rng))
    return pop[:size]


def load_genome(path):
    """Load a genome artifact for --seed-genome. Raise ValueError if unusable.

    Deliberately loud: a silent fallback to random weights is how a submission
    once shipped running on noise (Phase 4). A bad --seed-genome must stop the run.
    """
    try:
        with open(path) as fh:
            data = json.load(fh)
    except (OSError, ValueError) as exc:
        raise ValueError(f"could not read seed genome {path!r}: {exc}") from exc
    g = data.get("genome") if isinstance(data, dict) else data
    if not isinstance(g, list):
        raise ValueError(f"seed genome {path!r} has no 'genome' list")
    if len(g) != GENOME_LEN:
        raise ValueError(
            f"seed genome {path!r} has length {len(g)}, expected {GENOME_LEN}")
    return [float(w) for w in g]


def mutate(genome, sigma, rng):
    if sigma == 0.0:
        return list(genome)
    return [w + rng.gauss(0.0, sigma) for w in genome]

def share(mine, theirs) -> float:
    """Score share `mine / (mine + theirs)` — a smooth generalization of win-rate.

    0.5 at a tie, above 0.5 when ahead, and continuously informative when behind.
    Binary win/loss gives the search no gradient until it crosses the finish line;
    this does (#70). Each side is clamped to >= 0 independently so a negative
    reward can never push the result outside [0, 1].
    """
    a = max(0.0, float(mine or 0.0))
    b = max(0.0, float(theirs or 0.0))
    total = a + b
    return 0.5 if total == 0.0 else a / total

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

def opponent_record(agent, opponent, games, seed_base, rewards_fn=_play_rewards):
    """Play `games` games against one opponent; report the record and the score share.

    Both statistics come from the same rewards in a single pass — playing each game
    twice to collect them separately would double the cost for nothing. Sides
    alternate on odd games so first-player advantage cancels.

    Zero games returns the neutral 0.5 for both rates rather than 0: no evidence is
    not evidence of failure.
    """
    w = t = l = 0
    shares = []
    for g in range(games):
        seed = seed_base + g
        if g % 2 == 0:
            mine, theirs = rewards_fn(agent, opponent, seed)
        else:
            theirs, mine = rewards_fn(opponent, agent, seed)
        shares.append(share(mine, theirs))
        if mine > theirs:
            w += 1
        elif mine == theirs:
            t += 1
        else:
            l += 1
    n = len(shares)
    return {
        "w": w, "t": t, "l": l, "games": n,
        "win_rate": (w + 0.5 * t) / n if n else 0.5,
        "share": sum(shares) / n if n else 0.5,
    }


def match_share(agent, opponents, games, seed_base, rewards_fn=_play_rewards):
    """Mean score share across every opponent — each opponent weighted equally."""
    if not opponents:
        return 0.5
    return sum(
        opponent_record(agent, opp, games, seed_base + oi * 100000, rewards_fn)["share"]
        for oi, opp in enumerate(opponents)
    ) / len(opponents)


DEFAULT_ANCHOR_WEIGHT = 0.75


def blended_fitness(anchor_share, pool_share, anchor_weight=DEFAULT_ANCHOR_WEIGHT) -> float:
    """Combine the anchor and sibling-pool shares, anchors dominant.

    The anchors are the only opponents that stand in for the real field. Scoring
    them at equal weight with the population sample and Hall-of-Fame let
    sibling-beating supply all the gradient — and that component saturates, which
    is what pinned fitness at 0.5833 (#70).

    `pool_share` of None means there were no sibling opponents (generation 0, or a
    disabled Hall-of-Fame): fall back to the anchor share rather than scoring the
    absent pool as a loss.
    """
    if pool_share is None:
        return anchor_share
    return anchor_weight * anchor_share + (1.0 - anchor_weight) * pool_share

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
           anchor_names=DEFAULT_ANCHORS, seed=0, rewards_fn=_play_rewards,
           anchor_weight=DEFAULT_ANCHOR_WEIGHT, anchor_agents_override=None,
           seed_genome=None):
    """Run the neuroevolution loop; return best genome/fitness and per-generation history.

    Fitness is the anchor-dominant blend of score shares (#70), not win-rate:
    win/loss gives no gradient at all until the agent starts winning, and it was
    not winning.
    """
    rng = random.Random(seed)
    anchors = (anchor_agents_override if anchor_agents_override is not None
               else anchor_agents(anchor_names))
    population = (seeded_population(seed_genome, pop_size, sigma, rng)
                  if seed_genome is not None else initial_population(pop_size, seed))
    hof_genomes = []
    best_genome, best_fit, history = None, -1.0, []
    for gen in range(generations):
        pop_agents = [genome_agent(g) for g in population]
        hof_agents = [genome_agent(g) for g in hof_genomes]
        scored = []
        for i, g in enumerate(population):
            base = seed + gen * 7919 + i
            siblings = build_opponents([pa for j, pa in enumerate(pop_agents) if j != i],
                                       [], hof_agents, sample_k, rng)
            a_share = match_share(pop_agents[i], anchors, games, base, rewards_fn)
            p_share = (match_share(pop_agents[i], siblings, games, base + 50000, rewards_fn)
                       if siblings else None)
            scored.append((g, blended_fitness(a_share, p_share, anchor_weight)))
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
    ap.add_argument("--anchor-weight", type=float, default=DEFAULT_ANCHOR_WEIGHT,
                    help="weight on the anchor share vs the sibling pool (default 0.75)")
    ap.add_argument("--out", default=GENOME_ARTIFACT, help="where to save the champion genome")
    ap.add_argument("--dry-run", action="store_true", help="skip writing the genome artifact")
    ap.add_argument("--seed-genome", default=None,
                    help="start from this genome artifact instead of random init")
    args = ap.parse_args(argv)

    seed_genome = load_genome(args.seed_genome) if args.seed_genome else None

    result = evolve(
        generations=args.generations,
        pop_size=args.pop,
        games=args.games,
        sigma=args.sigma,
        sample_k=args.sample_k,
        hof_cap=args.hof_cap,
        anchor_names=args.anchors,
        seed=args.seed,
        anchor_weight=args.anchor_weight,
        seed_genome=seed_genome,
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
            "anchor_weight": args.anchor_weight,
            "seed_genome": args.seed_genome,
        })
        print(f"saved champion genome to {args.out} (fitness={result['best_fitness']:.4f})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
