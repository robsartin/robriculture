"""Breed the predator (#199, stage 1): a (mu+lambda) search over `predator`
schedule genomes whose fitness is beating the champion.

Fitness is the predator's mean score share against the champion over the
generation's games (smooth, like `evolve`'s); the in-run win-rate is recorded
next to it and never optimised. Every member of a generation plays the same
seeds -- `SEED_BASE + SEED_STRIDE * g + i` -- fresh each generation, and
`FROZEN` (the benchmark itself) is scored on them too as a reference row the
gate's "search moved" control reads. The generation's best is checkpointed
every generation; elitism carries it forward, so the last checkpoint is the
best re-measured on the latest seeds.

    .venv/bin/python -m harness.predator --generations 40 --pop 16 --games 4 \
        --sigma 0.15 --seed 0 --champion lean_feed --out harness/genomes/199-predator.json
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import random
import sys
import time

from harness.evolve import mutate, next_generation, select_elites, share
from harness.tournament import play_rewards
from kaggisim.strategy import make_agent
from strategies import load
from strategies import predator as pr

SEED_BASE = 10000
SEED_STRIDE = 100
DEFAULT_OUT = os.path.join(os.path.dirname(__file__), "genomes", "199-predator.json")


def generation_seeds(generation: int, games: int) -> tuple:
    return tuple(SEED_BASE + SEED_STRIDE * generation + i for i in range(games))


def clamp(genome) -> list:
    return [min(1.0, max(0.0, float(u))) for u in genome]


def random_genome(rng) -> list:
    return [rng.random() for _ in range(pr.GENOME_LEN)]


def initial_population(size: int, sigma: float, rng) -> list:
    """`FROZEN`, then (size - 1) // 2 mutants of it, then random genomes."""
    pop = [list(pr.FROZEN)]
    mutants = (size - 1) // 2
    for _ in range(mutants):
        pop.append(clamp(mutate(pr.FROZEN, sigma, rng)))
    while len(pop) < size:
        pop.append(random_genome(rng))
    return pop[:size]


def evaluate(genome, champion_fn, seeds, rewards_fn) -> dict:
    """The predator's record on `seeds`: seat 0 on even game indices."""
    wins = ties = 0
    shares = []
    for i, seed in enumerate(seeds):
        predator = make_agent(pr.PredatorStrategy(genome))
        champion = champion_fn()
        if i % 2 == 0:
            mine, theirs = rewards_fn(predator, champion, seed)
        else:
            theirs, mine = rewards_fn(champion, predator, seed)
        shares.append(share(mine, theirs))
        if mine > theirs:
            wins += 1
        elif mine == theirs:
            ties += 1
    n = len(shares)
    return {"fitness": sum(shares) / n if n else 0.5,
            "win_rate": (wins + 0.5 * ties) / n if n else 0.5,
            "wins": wins, "ties": ties, "games": n}


def write_checkpoint(path, genome, meta) -> bool:
    """Temp file + os.replace, as `evolve.checkpoint_genome`; never raises."""
    if not path:
        return False
    tmp = f"{path}.tmp"
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(tmp, "w") as fh:
            json.dump({"genome": list(genome), "meta": meta}, fh, indent=2)
            fh.write("\n")
        os.replace(tmp, path)
        return True
    except (OSError, TypeError, ValueError) as exc:
        print(f"warning: checkpoint to {path!r} failed ({exc}); continuing", file=sys.stderr)
        return False


def search(generations, pop_size, games, sigma, seed, champion, out,
           rewards_fn=play_rewards, log=print) -> dict:
    """Breed against `champion` for `generations`; return the final checkpoint
    (the last generation's best, re-measured on that generation's seeds)."""
    rng = random.Random(seed)
    champion_cls = load(champion)
    champion_fn = lambda: make_agent(champion_cls())  # noqa: E731
    settings = {"generations": generations, "pop": pop_size, "games": games,
                "sigma": sigma, "seed": seed, "champion": champion}
    population = initial_population(pop_size, sigma, rng)
    history, checkpoint = [], None
    for g in range(generations):
        t0 = time.time()
        seeds = generation_seeds(g, games)
        scored = [(genome, evaluate(genome, champion_fn, seeds, rewards_fn)) for genome in population]
        reference = evaluate(list(pr.FROZEN), champion_fn, seeds, rewards_fn)
        scored.sort(key=lambda gs: gs[1]["fitness"], reverse=True)
        best_genome, best = scored[0]
        history.append({"generation": g, "seeds": list(seeds), "best": best, "reference": reference,
                        "mean_fitness": sum(s["fitness"] for _, s in scored) / len(scored)})
        meta = dict(best)
        meta.update({"schedule": dataclasses.asdict(pr.decode(best_genome)), "reference": reference,
                     "generation": g, "generations_completed": g + 1, "seeds": list(seeds),
                     "settings": settings, "history": history})
        checkpoint = {"genome": list(best_genome), "meta": meta}
        write_checkpoint(out, best_genome, meta)
        log(f"gen {g:>3}  best fitness {best['fitness']:.3f} win-rate {best['win_rate']:.2f}  "
            f"reference {reference['fitness']:.3f}/{reference['win_rate']:.2f}  "
            f"mean {history[-1]['mean_fitness']:.3f}  {time.time() - t0:.0f}s")
        elites = select_elites([(genome, s["fitness"]) for genome, s in scored], max(1, pop_size // 4))
        population = [clamp(genome) for genome in next_generation(elites, pop_size, sigma, rng)]
    return checkpoint


def main(argv=None):  # pragma: no cover
    os.environ.setdefault("ROBRICULTURE_STRICT", "1")
    ap = argparse.ArgumentParser(description="breed the predator (#199 stage 1)")
    ap.add_argument("--generations", type=int, default=40)
    ap.add_argument("--pop", type=int, default=16)
    ap.add_argument("--games", type=int, default=4)
    ap.add_argument("--sigma", type=float, default=0.15)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--champion", default="lean_feed")
    ap.add_argument("--out", default=DEFAULT_OUT)
    args = ap.parse_args(argv)
    final = search(args.generations, args.pop, args.games, args.sigma, args.seed,
                   args.champion, args.out)
    m = final["meta"]
    print(f"done: best fitness {m['fitness']:.3f} win-rate {m['win_rate']:.2f} on seeds {m['seeds']}; "
          f"reference {m['reference']['fitness']:.3f}; schedule {m['schedule']}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
