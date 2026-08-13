# Design: the neuroevolution harness (Phase 2)

**Date:** 2026-08-13
**Issue:** #66. Phase 2 of the neuroevolution initiative (ADR-0008).
**Status:** approved (brainstorming), pending implementation plan.

## Goal

Evolve `neuropilot`'s genome (its flat MLP weight vector, Phase 1 / #64) by
competition, and persist the best genome as a committed artifact `neuropilot` loads
for submission. Fitness is **win-rate** — the ladder's win/tie-only objective — so
the search optimizes for the thing the ladder actually rewards.

## Why competition + anchors

Self-play against our own bots is a broken signal (ADR-0008). So fitness combines
**co-evolution** (variants competing against each other) with **fixed anchors** that
prevent the self-play-in-a-vacuum drift (a population that gets strong against itself
but loses on the ladder — exactly what we diagnosed this session). Anchors: `meta_bot`
(the field-proxy benchmark) + a diverse slice of our shipped strategies + a
Hall-of-Fame of the best genomes found so far. The anchor set is **pluggable** so
Phase 3's vendored external agents slot in without touching the loop.

## Architecture — `harness/evolve.py`

Pure helpers (unit-tested without running games) + a thin loop + a CLI. Reuses the
existing `harness.tournament.play` (one seeded game → +1/-1/0) and the seeded-match
convention from `harness.promotion`.

### Genome & population

- A **genome** is `list[float]` of length `neuropilot.genome_size(N_FEATURES, H1, N_KNOBS)`
  (Phase-1 frozen). A genome instantiates an agent via
  `make_agent(NeuroPilotStrategy(genome=g))`.
- `initial_population(size, seed) -> list[genome]` — seeded random genomes
  (reuses `neuropilot.random_genome` with per-individual seeds derived from `seed`).

### Fitness

- `evaluate(genome, opponents, games, seed_base, play_fn) -> float` — instantiate the
  agent, play `games` seeded games vs each opponent agent (alternating sides, like
  `promotion.run_match`), return **win-rate counting ties as half**
  (`(wins + 0.5*ties) / total`) — a single scalar in `[0,1]` that rewards wins and
  mild-favours ties (both score on the ladder).
- **Opponents per generation** = fixed anchors + a sampled subset of the current
  population (co-evolution) + Hall-of-Fame elites. `build_opponents(population,
  anchors, hof, sample_k, rng)` returns the opponent agent list for a genome.
- Anchors are named strategies resolved via `harness.tournament.build_agents`
  (default anchor names: `meta_bot`, `ranch_hands`, `market_farmer`, `ranch_adaptive`,
  `wheat_hands`, `spoiler` — a spread of styles; overridable via CLI). Pluggable:
  Phase 3 adds external agents to this list.

### Selection & mutation

- `select_elites(scored, k) -> list[genome]` — truncation: the top `k` genomes by
  fitness (ties broken by index for determinism).
- `mutate(genome, sigma, rng) -> genome` — add Gaussian noise `N(0, sigma)` to every
  weight (pure; rng injected for reproducibility). Crossover is **out of scope v1**.
- `next_generation(elites, size, sigma, rng) -> list[genome]` — keep the elites
  verbatim (elitism), refill to `size` by mutating random elites.

### Hall-of-Fame

- `hall_of_fame(prev_hof, elites, cap) -> list[genome]` — retain up to `cap` best
  genomes across generations (best-of-run always kept), used as anchors so the
  population can't cycle to something that only beats its contemporaries.

### The loop & artifact

- `evolve(generations, pop_size, games, sigma, sample_k, hof_cap, anchor_names,
  seed, play_fn) -> dict` — runs the generational loop; returns
  `{"best_genome", "best_fitness", "history": [per-gen best/mean]}`. Deterministic
  under a fixed `seed` + `play_fn` (ADR-0005).
- **Artifact:** `save_genome(path, genome, meta)` writes
  `harness/genomes/champion_genome.json` = `{"genome": [...], "fitness": .., "config":
  {...}, "generations": N}` (a committed decision artifact, sibling to `champion.json`).
- **`neuropilot` loader:** `neuropilot` gains `load_champion_genome(path) -> list |
  None` and, at import, sets `DEFAULT_GENOME` to the loaded champion genome **if the
  artifact exists and its length matches `genome_size(...)`**, else the existing
  seeded-random default. This keeps the frozen interface (same names) while making the
  *evolved* agent the default one that `scripts/submit.py neuropilot` packages.
  Length-mismatch or malformed file → fall back to the random default (never crash).

### CLI

`python -m harness.evolve --generations G --pop N --games g --sigma s --sample-k k
--hof-cap h --seed S [--anchors a,b,c] [--out harness/genomes/champion_genome.json]
[--dry-run]` (`# pragma: no cover` on `main`). Prints per-generation best/mean
fitness. `--dry-run` runs the loop without writing the artifact. Defaults sized for a
short interactive smoke run; real runs pass larger `--generations/--pop` and run
unattended in the background.

## Compute

Games are ~2s. Cost/gen ≈ `pop × opponents × games × 2s`. Example: pop 24, ~10
opponents, 1 game each → ~480 games/gen ≈ 16 min/gen; a handful of generations is an
interactive check, dozens are an unattended background run. All parameterized; the
plan's smoke test uses a tiny pop/gens with a **stub `play_fn`** so unit tests never
run real games.

## Testing

- `initial_population`: right count/length, deterministic under seed.
- `mutate`: changes weights, preserves length, deterministic under rng, sigma=0 is a
  no-op.
- `select_elites`: returns the top-k by score, deterministic tie-break.
- `next_generation`: preserves elites, refills to size.
- `hall_of_fame`: keeps best-of-run, respects cap.
- `evaluate`: with a **stub `play_fn`** (deterministic winner) returns the expected
  win-rate (ties-as-half); no real games in unit tests.
- `evolve`: with a stub `play_fn`, a tiny run improves or holds best-fitness and is
  deterministic under seed.
- `neuropilot.load_champion_genome`: loads a valid artifact; returns None on
  missing/malformed/length-mismatch; `DEFAULT_GENOME` falls back safely.
- Full CI: line ≥85%, branch ≥65%. A real (non-stub) smoke evolution is run once
  manually and its improving-fitness numbers recorded on #66 (not in unit tests).

## Out of scope / YAGNI

- Crossover, adaptive sigma, novelty search, parallel game execution — v1 is
  truncation + fixed-sigma Gaussian mutation, single-process.
- External competitor agents in the anchor pool — Phase 3 (the anchor list is already
  pluggable).
- Submission automation — Phase 4 (Rob submits; `neuropilot` already packages the
  evolved genome once the artifact exists).
