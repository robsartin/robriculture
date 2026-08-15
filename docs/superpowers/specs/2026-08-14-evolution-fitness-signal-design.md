# Escaping the 0.5833 plateau: fixing the evolution fitness signal

- **Issue:** [#70](https://github.com/robsartin/robriculture/issues/70)
- **Date:** 2026-08-14
- **Status:** Approved (design)
- **Relates to:** ADR-0008 (neuroevolution against a diverse pool), ADR-0005
  (reproducibility), ADR-0007 (experiment-driven process)

## Context

Two neuroevolution runs (10 generations at `--games 1`, 20 generations at
`--games 2`) both peaked at fitness exactly **0.5833** by roughly generation 4 and
never improved. Issue #70 framed this as weak search operators — mutation-only
truncation selection getting stuck — and proposed crossover, bigger populations,
and adaptive sigma.

Two diagnostics run against the baked champion (`strategies/champion_genome.json`,
the genome shipped in the 2026-08-14 submission) show the cause is elsewhere.

### Diagnostic 1 — per-opponent record vs the fixed anchors, 4 games each

| opponent | W-T-L | rate |
|---|---|---|
| meta_bot | 0-0-4 | 0.000 |
| ranch_hands | 0-0-4 | 0.000 |
| market_farmer | 0-0-4 | 0.000 |
| ranch_adaptive | 0-0-4 | 0.000 |
| wheat_hands | 0-0-4 | 0.000 |
| spoiler | 4-0-0 | 1.000 |
| **total** | **4-0-20** | **0.167** |

The champion beats exactly one anchor. The 0.5833 figure reproduces arithmetically:
a match evaluates against 6 anchors + 3 Hall-of-Fame + 3 population-sample
opponents at `--games 2` = 24 games. The anchors contribute ~2 wins (spoiler); the
6 *neuropilot* opponents contribute ~12. `14/24 = 0.5833`.

### Diagnostic 2 — reward margins, champion vs a random genome, 2 games each

| opponent | champion | opponent | ratio | random-genome ratio |
|---|---|---|---|---|
| meta_bot | 20,570 | 59,136 | 0.35 | 0.03 |
| ranch_hands | 19,817 | 35,195 | 0.56 | 0.04 |
| market_farmer | 21,474 | 40,163 | 0.53 | 0.04 |
| ranch_adaptive | 19,874 | 34,466 | 0.58 | 0.04 |
| wheat_hands | 19,609 | 31,553 | 0.62 | 0.05 |
| spoiler | 20,876 | 20,280 | 1.03 | 0.07 |

### What the numbers mean

1. **Evolution worked.** A random genome earns ~1,700; the evolved champion earns
   ~20,000 — a 12× gain. The controller substrate is not visibly exhausted, so
   #71 (widening the knob controller) is **not** yet demonstrated to be the blocker.
2. **The losses are climbable, not catastrophic.** Score ratios of 0.35–0.62 vary
   informatively across opponents. The win-rate those games feed into is a flat
   0.000 for every one of them.
3. **Therefore the entire 12× gain came from beating siblings**, the only component
   of fitness with any gradient. That component saturated at 12/12 by generation 4
   — which *is* the plateau.

**The plateau is the fitness function, not the operators.** Crossover and adaptive
sigma search a flat landscape faster; they do not make it less flat. Approach B
(the issue as literally written) was considered and deferred on this basis.

## Decision

Fix the signal. Five changes, all confined to `harness/` — nothing in this spec
alters the submitted artifact. `strategies/neuropilot.py` and the baked
`strategies/champion_genome.json` are untouched; baking a new champion is a
separate, later decision.

| # | change | defect it addresses |
|---|---|---|
| 1 | Shaped **score share** fitness `me/(me+opp)` | binary win/loss has no gradient below the finish line |
| 2 | **0.75 anchor / 0.25 sibling** weighted blend | sibling matches dominate and saturate |
| 3 | Frozen **`genome_bench`** benchmark | runs are not comparable to each other |
| 4 | **Per-generation checkpointing** | a long run that is interrupted loses everything |
| 5 | **`--seed-genome`** | every run restarts from ~1,700 instead of ~20,000 |

### Why score share

`me/(me+opp)` is a smooth generalization of win-rate: 0.5 at a tie, above 0.5 when
winning, and continuously informative when losing. It converts the 0.35→0.62
ratios above into exactly the gradient the search has been missing.

The Kaggle ladder scores win/tie only, so margin is a **proxy**, and maximizing
average margin is not identical to maximizing wins. That gap is not a live risk at
a 0% win-rate, but it is real: `genome_bench` therefore reports **both** win-rate
and mean share, so any divergence between them is visible rather than assumed away.

## Components

### `harness/tournament.py`

Extract `play_rewards(agent_a, agent_b, seed) -> (ra, rb)`. `play()` becomes the
sign of its result. A pure refactor — no behavior change, no additional game cost.
Both are live-game entrypoints and keep `# pragma: no cover`.

### `harness/evolve.py`

New pure helpers, each unit-testable against a fake `play_fn` following the
existing pattern in `tests/test_evolve.py`:

- `share(mine, theirs) -> float` — clamp each of `mine` and `theirs` to `>= 0`
  independently, then return `mine/(mine+theirs)`. If both are zero after
  clamping (including falsy/`None` rewards), return 0.5. Opponent zero with a
  positive own score → 1.0.
- `match_share(agent, opponents, games, seed_base, play_fn) -> float` — mean
  per-game share, alternating sides on odd games exactly as `match_winrate` does.
  No opponents / zero games → 0.5.
- `blended_fitness(anchor_share, pool_share, anchor_weight) -> float` —
  `w·anchor + (1-w)·pool`. When the sibling pool is empty (generation 0, or
  `--hof-cap 0` with `--sample-k 0`), returns `anchor_share` alone rather than
  scoring the missing pool as a loss.
- `seeded_population(seed_genome, size, sigma, rng) -> list` — the seed genome
  verbatim as element 0, then `size-1` mutants of it.

`match_winrate` is **kept unchanged** and does not become dead code: `genome_bench`
calls it per opponent (with a single-element opponent list) to produce that
opponent's win-rate, exactly as `match_share` produces that opponent's share. Its
existing tests stay green.

`evolve()` computes anchor share and sibling share separately per genome, blends
them, and uses the blend as fitness. Selection, elitism, Hall-of-Fame, and
determinism are otherwise unchanged.

### `harness/genome_bench.py` (new)

The frozen, reproducible success bar. Plays one genome against the named anchors
**only** — no Hall-of-Fame, no population sample — at fixed seeds.

Returns per-opponent W/T/L, win-rate, and mean share, plus the totals. CLI:
`python -m harness.genome_bench --genome <path> --games N`.

Seeds are derived deterministically from the opponent index and game number (the
same `seed_base + oi * 100000 + g` scheme `match_winrate` already uses), so two
invocations with the same arguments reproduce the same numbers exactly, per
ADR-0005.

Named `genome_bench` deliberately: `harness/market_bench.py` already exists and is
unrelated, and `tournament.benchmark_names()` already means the readonly
external-opponent flag from #59.

This is what makes "0.5833 is a plateau" a falsifiable claim, and it is the agreed
success criterion for this issue.

### Checkpointing

After each generation, write the best-so-far genome to `--out` using
write-to-temp-then-`os.replace`, so an interrupted run always leaves a valid
artifact and never a half-written one. Suppressed under `--dry-run`.

### CLI additions

- `--seed-genome PATH` — start from an existing champion instead of random init.
- `--anchor-weight FLOAT` — default `0.75`.

Both are recorded in the saved genome's `meta` block so a run remains reproducible
per ADR-0005.

## Known limitation

The champion is still selected as `argmax` over generations of a noisy per-generation
estimate, which biases toward a lucky generation. Anchor-dominant weighting makes
those per-generation numbers substantially more comparable than the old shifting-pool
fitness, and `genome_bench` is the arbiter after the run. This spec does not claim
the bias is eliminated.

## Error handling

- A missing, unreadable, or wrong-length `--seed-genome` **fails loudly and exits
  non-zero**. It must not silently fall back to random initialization — that is
  exactly the failure mode that produced a submitted agent running on random
  weights before the Phase 4 fix.
- A checkpoint write failure warns and lets the run continue. Losing an overnight
  run to a transient disk error would be worse than a missing checkpoint.
- `share()` never raises on degenerate inputs (both zero, negative, `None`-ish
  falsy rewards); it returns 0.5 or a clamped value.
- ADR-0006's fail-safe is untouched. Nothing in this change ships in the tarball.

## Testing

TDD throughout — a failing test before each implementation, per the repo's standing
rule. Unit tests cover:

- `share`: tie → 0.5; both zero → 0.5; negative clamped; opponent zero → 1.0.
- `match_share`: side alternation cancels first-player advantage; empty opponents
  and zero games → 0.5.
- `blended_fitness`: the weighting arithmetic, and the empty-sibling-pool fallback.
- `seeded_population`: element 0 is the seed verbatim; correct length; deterministic
  under a seeded `rng`.
- Checkpointing: an artifact exists after each generation, and is valid JSON after a
  simulated interruption (`tmp_path`).
- `genome_bench`: per-opponent breakdown against a fake `play_fn`; no Hall-of-Fame or
  population sample in its pool.
- `evolve` determinism: the existing test still passes.

CLI `main()` entrypoints and live-game loops carry `# pragma: no cover`. The CI gate
stays line ≥ 85% / branch ≥ 65%.

## Sizing

Runs are sized to finish **overnight (~8h)**. At roughly 2s per game that is a
budget of about **14,000 games**, and the run must satisfy:

```
generations × population × games × (anchors + hof_cap + sample_k)  ≲  14,000
```

The implementation plan picks the specific default `--generations` / `--pop` /
`--games` from that inequality; the budget itself is fixed here.

## Out of scope — deferred to a follow-up issue

Crossover between elites, adaptive/annealed sigma, larger populations and more
elites, and novelty search. These are approach B from the brainstorm. They are
worth revisiting **after** a shaped-fitness run shows whether the search stalls for
genuinely search-related reasons; on the current flat landscape they would optimize
a component already pinned at its maximum.

Widening the knob controller (#71) also stays out of scope, and this work informs
it: the substrate delivered a 12× reward gain while never being properly steered,
so its ceiling has not yet been established.
