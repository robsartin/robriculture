from __future__ import annotations
import argparse, json, os, random, sys
from kaggisim.strategy import make_agent
from harness.tournament import play_rewards as _play_rewards
from harness.tournament import build_agents
from harness import external_pool
from strategies import neuropilot as npilot

GENOME_LEN = npilot.genome_size(npilot.N_FEATURES, npilot.H1, npilot.N_KNOBS)
GENOME_ARTIFACT = os.path.join(os.path.dirname(__file__), "genomes", "champion_genome.json")


def save_genome(path, genome, meta):
    """Write a genome and metadata to a JSON file."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        json.dump({"genome": list(genome), "meta": meta}, fh, indent=2)
        fh.write("\n")

def checkpoint_genome(path, genome, fitness, history, settings=None):
    """Persist the best-so-far genome mid-run. Return True on success.

    `settings` carries the run's configuration (generations, pop, games, seed,
    anchors, ...) — the same fields the final save_genome() call records. If an
    8-hour run is interrupted, the checkpoint is the ONLY surviving artifact, so
    it must be reproducible and interpretable on its own, not just track progress
    (#70). checkpoint-specific fields (fitness, generations_completed, checkpoint,
    history) always take precedence over any same-named key in settings.

    Written to a temp file and moved into place with os.replace, so an interrupt
    can never leave a half-written artifact. Any failure to write the checkpoint —
    a disk error (OSError) or a value that json.dump can't serialize
    (TypeError/ValueError) — warns and returns False rather than raising: losing
    an 8-hour run to a checkpoint hiccup would be worse than a missing
    checkpoint (#70).
    """
    tmp = f"{path}.tmp"
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        meta = dict(settings or {})
        meta.update({
            "fitness": fitness,
            "generations_completed": len(history),
            "checkpoint": True,
            "history": history,
        })
        with open(tmp, "w") as fh:
            json.dump({"genome": list(genome), "meta": meta}, fh, indent=2)
            fh.write("\n")
        os.replace(tmp, path)
        return True
    except (OSError, TypeError, ValueError) as exc:
        print(f"warning: checkpoint to {path!r} failed ({exc}); continuing", file=sys.stderr)
        return False

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
    """Mean score share across every opponent — each opponent weighted equally.

    Opponent `oi` gets `seed_base + oi * 100000`, and evolve()'s own anchor vs.
    sibling-pool matches are separated by `+ 50000` (#72) — both rely on the
    unstated invariant `games < 50000` (the tighter of the two gaps) so that no
    two of these seed ranges ever overlap. Violating it reuses maps across
    opponents/pools rather than producing wrong scores, so there is no guard,
    just this note.
    """
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

    `pool_share` of None means there were no sibling opponents at all: sample_k
    <= 0 AND the Hall-of-Fame is empty or disabled. It is not specific to
    generation 0 — even there the sibling pool is a random sample of the
    population itself, non-empty whenever sample_k >= 1 and pop_size >= 2. Fall
    back to the anchor share rather than scoring the absent pool as a loss.
    """
    if pool_share is None:
        return anchor_share
    return anchor_weight * anchor_share + (1.0 - anchor_weight) * pool_share

#: The frozen comparability bar. `field_rival` joins the five original anchors
#: because the champion swept all five 20/20 and none of them plants a single
#: strawberry -- an instrument that cannot separate a better agent from a worse
#: one (#181). Adding an anchor breaks comparability with runs recorded before
#: this change; that is the intended cost.
DEFAULT_ANCHORS = ("meta_bot", "ranch_hands", "market_farmer", "ranch_adaptive",
                   "wheat_hands", "field_rival")

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
           seed_genome=None, checkpoint_fn=None):
    """Run the neuroevolution loop; return best genome/fitness and per-generation history.

    WITHIN a generation, genomes are ranked by the anchor-dominant blend of
    score shares (#70), not win-rate: win/loss gives no gradient at all until
    the agent starts winning, and it was not winning.

    ACROSS generations, `best_genome` is selected by anchor-only share, not
    the blend (#107): the blend is frequency-dependent (see blended_fitness),
    so a cross-generation `>` comparison against it systematically picks a
    generation-0 genome. `best_fitness` in the return value is therefore the
    anchor share of the selected genome (the comparable, interpretable
    figure); `best_fitness_blended` is that same genome's blend, kept for
    inspection only.
    """
    rng = random.Random(seed)
    anchors = (anchor_agents_override if anchor_agents_override is not None
               else anchor_agents(anchor_names))
    population = (seeded_population(seed_genome, pop_size, sigma, rng)
                  if seed_genome is not None else initial_population(pop_size, seed))
    hof_genomes = []
    best_genome, best_anchor, best_fit_blend, history = None, -1.0, -1.0, []
    for gen in range(generations):
        pop_agents = [genome_agent(g) for g in population]
        hof_agents = [genome_agent(g) for g in hof_genomes]
        scored = []
        for i, g in enumerate(population):
            # No `+ i` here: every genome in the generation shares the same seed
            # base, so all of them are scored on identical maps (a paired
            # comparison / common random numbers, #72). Seeds still rotate per
            # generation via `gen * 7919`.
            base = seed + gen * 7919
            siblings = build_opponents([pa for j, pa in enumerate(pop_agents) if j != i],
                                       [], hof_agents, sample_k, rng)
            a_share = match_share(pop_agents[i], anchors, games, base, rewards_fn)
            p_share = (match_share(pop_agents[i], siblings, games, base + 50000, rewards_fn)
                       if siblings else None)
            scored.append((g, blended_fitness(a_share, p_share, anchor_weight), a_share))
        # Sort by the blended figure (index 1): selection still optimizes the
        # blend, unchanged by #104 — only the *readout* below adds the
        # anchor-only share alongside it.
        scored.sort(key=lambda gf: gf[1], reverse=True)
        gen_best_g, gen_best_f, gen_best_a = scored[0]
        mean_f = sum(f for _, f, _ in scored) / len(scored)
        # anchor_share is comparable across generations and runs (unlike
        # `best`, the blend — see blended_fitness docstring and #104): the
        # sibling term collapses toward 0.5 as the population converges,
        # which is exactly when selection is working, so `best` can fall or
        # flatline while the agent is still improving. Plumbing the winner's
        # already-computed a_share through here (no extra evaluations) keeps
        # progress legible without changing what evolve() optimizes.
        history.append({"gen": gen, "best": gen_best_f, "anchor": gen_best_a, "mean": mean_f})
        # #107: the CROSS-generation comparison must use the anchor-only
        # share, not the blend. The blend is frequency-dependent (peaks at
        # generation 0, when the population is diverse, and collapses toward
        # a constant as it converges — see blended_fitness and #104), so a
        # `>` comparison against it across generations systematically keeps
        # generation 0's genome. Anchor share is comparable across
        # generations, so it is what "best" means here. Within a generation,
        # `scored` above is still sorted by the blend — that comparison is
        # apples-to-apples (every genome in a generation faces the same
        # pool) and the sibling pressure is deliberate (ADR-0008); this only
        # changes what evolve() *keeps*, not what it optimizes.
        if gen_best_a > best_anchor:
            best_anchor, best_fit_blend, best_genome = gen_best_a, gen_best_f, gen_best_g
        if checkpoint_fn is not None:
            checkpoint_fn(best_genome, best_anchor, list(history))
        elites = [g for g, *_ in scored[:max(1, pop_size // 4)]]
        hof_genomes = update_hof(hof_genomes, [gen_best_g], hof_cap)
        population = next_generation(elites, pop_size, sigma, rng)
    return {
        "best_genome": best_genome,
        "best_fitness": best_anchor,
        "best_fitness_blended": best_fit_blend,
        "history": history,
    }


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
    ap.add_argument("--include-external", action="store_true",
                    help="add the locally-fetched real competitor agents to the fitness "
                         "pool (#149). Off by default so the frozen bar stays comparable "
                         "across runs; raises if external_agents/ is empty.")
    ap.add_argument("--anchor-weight", type=float, default=DEFAULT_ANCHOR_WEIGHT,
                    help="weight on the anchor share vs the sibling pool (default 0.75)")
    ap.add_argument("--out", default=GENOME_ARTIFACT, help="where to save the champion genome")
    ap.add_argument("--dry-run", action="store_true", help="skip writing the genome artifact")
    ap.add_argument("--seed-genome", default=None,
                    help="start from this genome artifact instead of random init")
    args = ap.parse_args(argv)

    seed_genome = load_genome(args.seed_genome) if args.seed_genome else None

    run_settings = {
        "generations": args.generations,
        "pop": args.pop,
        "games": args.games,
        "sigma": args.sigma,
        "sample_k": args.sample_k,
        "hof_cap": args.hof_cap,
        "seed": args.seed,
        "anchors": args.anchors,
        "include_external": args.include_external,
        "anchor_weight": args.anchor_weight,
        "seed_genome": args.seed_genome,
    }

    ckpt = None if args.dry_run else (
        lambda g, f, h: checkpoint_genome(args.out, g, f, h, settings=run_settings))

    # Externals are opponents only. resolve_opponents raises rather than
    # silently handing back the internal-only pool, so a run can never report an
    # "external" number it did not measure (#149).
    anchor_override = (
        list(external_pool.resolve_opponents(args.anchors, include_external=True).values())
        if args.include_external else None)

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
        anchor_agents_override=anchor_override,
        seed_genome=seed_genome,
        checkpoint_fn=ckpt,
    )

    for h in result["history"]:
        # blended = what selection optimizes (frequency-dependent, #104);
        # anchor = comparable across generations/runs, the honest progress signal.
        print(f"gen {h['gen']}: blended={h['best']:.4f}  anchor={h['anchor']:.4f}  "
              f"mean={h['mean']:.4f}")

    if args.dry_run:
        print(f"dry-run: best_fitness={result['best_fitness']:.4f} (genome not saved)")
    else:
        # #107: "fitness" records the anchor-only share — the figure that is
        # actually comparable across runs and to genome_bench — with the
        # blend the selected genome scored kept alongside it under
        # "fitness_blended" so the artifact stays fully interpretable.
        save_genome(args.out, result["best_genome"], {
            "fitness": result["best_fitness"],
            "fitness_blended": result["best_fitness_blended"],
            **run_settings,
        })
        print(f"saved champion genome to {args.out} (fitness={result['best_fitness']:.4f})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
