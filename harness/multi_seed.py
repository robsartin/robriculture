"""Run one strategy experiment across many evolution seeds (#71).

One evolution run is one sample. #113 read a single run's "it never bought
land" as a verdict on the hypothesis, and that is how a noisy optimiser talks
you out of a real effect. At roughly 1.2 s/game a default `evolve` run costs
about three hours serially, but the box scales near-linearly across processes
(12 concurrent jobs measured at ~11x throughput, 2026-08-22), so N seeds cost
about the same wall time as one. This module runs them in parallel and reports
the *rate* at which the hypothesis holds.

Each seed produces a genome; each genome is then measured two ways:
  - `genome_bench` share against the fixed anchors -- the comparable
    cross-run number (#70), the same bar every other experiment uses;
  - a `production_report` game -- how many tiles it actually planted and
    whether it confirmably bought land, which is what #71 is about.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import sys

from harness.evolve import DEFAULT_ANCHORS, evolve, genome_agent
from harness.genome_bench import benchmark_genome
from harness.production_report import report_game, resolve_agent

#: The planted-tile count a run must reach for #71's hypothesis to hold.
#: Chosen against measurement, not taste: every agent we own peaks at 10-11
#: planted tiles regardless of land owned, and `pilkwang` reaches 51. Fifteen
#: is the smallest count unreachable under the old NW-only ceiling, so
#: clearing it shows the agent is working ground it genuinely could not before.
MIN_PLANTS_PEAK = 15

#: The share a fresh genome must beat to count as a real improvement. This is
#: what the agent shipped BEFORE this branch (measured on `main`, --games 4) --
#: deliberately not the 0.3390 the same shipped weights score under the new
#: controller. Beating 0.3390 would only recover ground this branch itself gave
#: up by reinterpreting two knobs; beating 0.3760 is a genuine gain.
PROMOTION_BAR = 0.3760


def seed_verdict(row) -> bool:
    """Did this seed's genome buy land, farm it, AND score better than before?

    All three are required. Buying land without farming it is #113's result
    restated; planting 15 tiles without buying land is impossible (NW holds
    25 tiles but the hire ceiling caps workers at 10). But this branch's own
    smoke test showed the land+plants pair alone is no longer demanding:
    once workers stop camping on idle tiles, even a random one-generation
    genome clears both (seeds reaching 21 and 62 planted tiles, both buying
    land). The `share` clause is what keeps the verdict meaningful -- it
    catches a genome that plants broadly but still scores below what shipped
    before this branch (those same two seeds scored 0.1850 and 0.3134,
    both under `PROMOTION_BAR`).
    """
    return (bool(row["land_purchases"])
            and row["plants_peak"] >= MIN_PLANTS_PEAK
            and row["share"] > PROMOTION_BAR)


def summarize_seeds(rows) -> dict:
    """Pure: fold per-seed rows into the experiment's headline numbers."""
    n = len(rows)
    if not n:
        return {"n": 0, "n_supported": 0, "rate": 0.0, "share_mean": 0.0,
                "share_min": 0.0, "share_max": 0.0, "plants_peak_max": 0,
                "land_buying_seeds": 0}
    supported = [r for r in rows if seed_verdict(r)]
    shares = [r["share"] for r in rows]
    return {
        "n": n,
        "n_supported": len(supported),
        "rate": len(supported) / n,
        "share_mean": sum(shares) / n,
        "share_min": min(shares),
        "share_max": max(shares),
        "plants_peak_max": max(r["plants_peak"] for r in rows),
        "land_buying_seeds": sum(1 for r in rows if r["land_purchases"]),
    }


def run_seed(seed, settings, opponent="wheat_hands"):  # pragma: no cover
    """Evolve one seed, then measure the winner. Integration -- no unit test.

    Returns a `row` dict for `summarize_seeds`. Runs in a worker process, so
    it takes plain data and returns plain data.
    """
    result = evolve(
        generations=settings["generations"], pop_size=settings["pop"],
        games=settings["games"], sigma=settings["sigma"],
        sample_k=settings["sample_k"], hof_cap=settings["hof_cap"],
        anchor_names=tuple(settings["anchors"]), seed=seed,
        anchor_weight=settings["anchor_weight"],
    )
    genome = result["best_genome"]
    bench = benchmark_genome(genome, anchor_names=tuple(settings["anchors"]),
                             games=settings["bench_games"])
    _, opp = resolve_agent(opponent)
    rep, _ = report_game(f"seed{seed}", genome_agent(genome), opponent, opp, seed=seed)
    return {
        "seed": seed,
        "share": bench["share"],
        "in_run_anchor": result["best_fitness"],
        "plants_peak": rep["plants_peak"],
        "land_purchases": rep["land_purchases"],
        "animals_peak": rep["animals_peak"],
        "hands_peak": rep["hands_peak"],
        "reward": rep["reward"],
        "genome": genome,
    }


def main(argv=None):  # pragma: no cover
    ap = argparse.ArgumentParser(description="multi-seed experiment evaluation (#71)")
    ap.add_argument("--seeds", type=int, default=10)
    ap.add_argument("--workers", type=int, default=10,
                    help="parallel evolution runs; keep below core count")
    ap.add_argument("--generations", type=int, default=10)
    ap.add_argument("--pop", type=int, default=20)
    ap.add_argument("--games", type=int, default=4)
    ap.add_argument("--sigma", type=float, default=0.2)
    ap.add_argument("--sample-k", type=int, default=4)
    ap.add_argument("--hof-cap", type=int, default=5)
    ap.add_argument("--anchor-weight", type=float, default=0.75)
    ap.add_argument("--bench-games", type=int, default=4)
    ap.add_argument("--anchors", nargs="*", default=list(DEFAULT_ANCHORS))
    ap.add_argument("--opponent", default="wheat_hands")
    ap.add_argument("--out", default=None, help="write the full result JSON here")
    args = ap.parse_args(argv)

    settings = {
        "generations": args.generations, "pop": args.pop, "games": args.games,
        "sigma": args.sigma, "sample_k": args.sample_k, "hof_cap": args.hof_cap,
        "anchors": args.anchors, "anchor_weight": args.anchor_weight,
        "bench_games": args.bench_games,
    }

    rows = []
    with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(run_seed, s, settings, args.opponent): s
                   for s in range(args.seeds)}
        for fut in concurrent.futures.as_completed(futures):
            seed = futures[fut]
            try:
                row = fut.result()
            except Exception as exc:
                print(f"seed {seed}: FAILED ({exc})", file=sys.stderr)
                continue
            rows.append(row)
            print(f"seed {row['seed']}: share={row['share']:.4f} "
                  f"plants_peak={row['plants_peak']} "
                  f"land={row['land_purchases']} "
                  f"verdict={'SUPPORTED' if seed_verdict(row) else 'not supported'}")

    rows.sort(key=lambda r: r["seed"])
    summary = summarize_seeds(rows)
    print("\n--- summary ---")
    print(f"seeds                 {summary['n']}")
    print(f"hypothesis supported  {summary['n_supported']}/{summary['n']} "
          f"(rate {summary['rate']:.2f})")
    print(f"seeds that bought land {summary['land_buying_seeds']}")
    print(f"best planted tiles    {summary['plants_peak_max']} (bar: {MIN_PLANTS_PEAK})")
    print(f"share  mean {summary['share_mean']:.4f}  "
          f"min {summary['share_min']:.4f}  max {summary['share_max']:.4f} "
          f"(bar: {PROMOTION_BAR})")

    if args.out:
        with open(args.out, "w") as fh:
            json.dump({"settings": settings, "rows": rows, "summary": summary}, fh, indent=2)
        print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
