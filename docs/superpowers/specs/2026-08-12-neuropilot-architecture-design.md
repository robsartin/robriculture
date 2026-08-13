# Design: neuropilot — NN-guided agent architecture (neuroevolution Phase 1)

**Date:** 2026-08-12
**Issue:** #64. Phase 1 of the neuroevolution initiative (ADR-0008).
**Status:** approved (brainstorming), pending implementation plan.

## Goal

A legal, submittable `Strategy` whose per-turn decisions come from a small
pure-Python neural net feeding a fresh knob-driven controller. Phase 1 proves the
architecture end-to-end with **random** weights — it need not be strong. Strength
comes from Phase 2 (evolving the weights). The genome interface is designed here so
Phase 2 can plug evolved weights in without touching the agent.

## Non-goals (Phase 1)

- No evolution/training loop (Phase 2). No external opponents (Phase 3). No
  submission packaging (Phase 4). No claim of competitive strength — random-weight
  play is expected to be weak but must be *legal and crash-free*.

## Architecture

`strategies/neuropilot.py` (`name = "neuropilot"`, `benchmark = False`,
`STRATEGY = NeuroPilotStrategy`). Four pure, independently-testable units wired by a
thin fail-safe `act()`. **Stdlib only** (ADR-0004): the MLP is plain Python, no
numpy. The controller uses only low-level sim primitives (`kaggisim.state`,
`kaggisim.economy`, `kaggisim.actions`, and generic navigation/tile helpers) — never
`meta_bot`/`ranch_hands` *strategy* logic (ADR-0008: the controller is independent so
evolution has genuine control).

### 1. Feature extractor — `features(state) -> list[float]`

A **fixed-length** vector (call it `N_FEATURES`) of values normalized to roughly
`[0,1]` (or `[-1,1]`), pure function of the parsed state. Fixed ordering is part of
the contract (the genome's input layer depends on it). v1 feature groups:

- **Time:** `day/SEASON_DAYS`, `hour/TURNS_PER_DAY`, `season_fraction_remaining`.
- **Capital:** `log1p(money)` scaled to ~[0,1]; **money share** `mine/(mine+opp+1)`
  if the opponent's money is visible in the obs (else 0.5).
- **Prices (signals):** `price/base` for MELON, WHEAT, MILK, WOOL (clamped to a
  sane range) — reveals crashed/hot markets.
- **Board:** fractions over owned tiles of empty crop plots, live melon plants,
  weeds; `cows_placed/9`, `sheep_placed/4`, empty-pasture fraction.
- **Land:** NE-unlocked, SW-unlocked (0/1 flags).
- **Crew:** `hands/9`.
- **Shed:** normalized MELON, WHEAT, FERTILIZER quantities.

A `NEUTRAL_FEATURES` fallback (all mid-range) is returned if the obs is malformed,
so `features` never raises (belt-and-suspenders under the fail-safe).

### 2. Pure-Python MLP — the genome

- Shape: `N_FEATURES → H1 (tanh) → N_KNOBS (sigmoid)`, one hidden layer, `H1 = 16`
  for v1. `N_KNOBS = 8` (below). `N_FEATURES` is fixed by the enumerated feature
  list above — the plan pins the exact count and ordering as module constants. All
  weights + biases flattened into a single `list[float]` = **the genome**.
- `genome_size(n_in, h1, n_out) -> int` — the exact flat length (so Phase 2 knows
  how many genes to evolve).
- `class MLP`: constructed from a flat genome via `MLP.from_genome(genome, n_in,
  h1, n_out)`; `forward(features: list[float]) -> list[float]` returns `N_KNOBS`
  values in `[0,1]`. Pure Python (`math.tanh`, a sigmoid helper); deterministic.
- `random_genome(n_in, h1, n_out, seed) -> list[float]` — a seeded random genome
  (small weights, e.g. uniform in `[-1,1]`). Phase 1 ships one fixed
  `DEFAULT_GENOME` built from a fixed seed so `neuropilot` is deterministic and its
  no-crash behavior is reproducible.

### 3. Fresh knob controller — `controller(knobs, state) -> action_dict`

Self-contained; turns the `N_KNOBS` sigmoid outputs into a legal
`{"farmer", "hands", "market"}` dict. Each knob maps to a meaningful control via a
documented `knob → range` transform. v1 knobs (`N_KNOBS = 8`):

1. **sell_throttle** — min `price/base` at which to sell melon (hold when crashed).
2. **hire_target** — desired crew size `round(knob * MAX_HANDS)`.
3. **livestock_pace** — spend threshold (surplus over reserve) before buying
   land/animals.
4. **livestock_labor_share** — fraction of the crew assigned to livestock beats.
5. **herd_target_scale** — target herd size `round(knob * (N_COW+N_SHEEP))`.
6. **fertilize_pref** — whether/when to apply collected fertilizer to crops.
7. **capital_reserve** — working capital to protect (scaled money).
8. **crop_mix** — melon-vs-wheat split of the crop crew.

The controller supports the **full legal action vocabulary** so evolution can reach
any strategy: per-worker crop loop (plant/water/harvest, navigation), livestock
setup+upkeep (BUY_LAND → BUILD_PASTURE → PLACE → FEED/HARVEST/COLLECT/CARE), and
market shaping (sells first & throttled, hire to target, seed restock, land/animal
buys paced by knobs, fertilizer), clamped to 10 orders with sells never truncated.
It is deliberately *simpler* than `meta_bot` (a clean substrate, not an optimized
strategy) — v1 correctness is "legal + coherent", not "strong". Decisions live in
small pure helpers (worker-role assignment, market-order builders) so each is
unit-tested without a full game.

### 4. `act(state) -> action_dict`

Wires `features → MLP.forward → controller`, returns its dict. Runs under the
existing `make_agent` fail-safe (ADR-0006). Uses the module-level `DEFAULT_GENOME`
in Phase 1; a later phase sets the genome from an evolved artifact.

## Testing

- `features`: fixed length, all components in range, ordering stable, malformed obs
  → `NEUTRAL_FEATURES` (no raise).
- `MLP`: `genome_size` matches a constructed net; `from_genome` round-trips;
  `forward` is deterministic and all outputs in `[0,1]`; a fixed tiny genome yields
  hand-computed outputs (pins the math).
- `controller`: across knob extremes (all-0, all-1, mid) returns a **legal** action
  dict — ≤10 market orders, sells ordered first, one action per worker, no illegal
  ops for the given state; key knob behaviors asserted (e.g. sell_throttle=high
  suppresses a low-price melon sell; hire_target scales the HIRE count).
- **No-crash gate:** `neuropilot` (auto-discovered) survives full games vs the
  built-ins under `ROBRICULTURE_STRICT=1` with the default random genome.
- Full CI: line ≥ 85%, branch ≥ 65%.

## Interfaces Phase 2 will rely on (freeze these names)

- `N_FEATURES`, `N_KNOBS`, `H1`, `genome_size(...)`, `random_genome(...)`,
  `MLP.from_genome(genome, n_in, h1, n_out)`, `MLP.forward(features)`,
  `features(state)`, `controller(knobs, state)`, and a documented way to set the
  agent's genome (module-level `DEFAULT_GENOME`, plus the class accepting an
  explicit genome so the evolution loop can instantiate variants).

## Out of scope / YAGNI

- Multiple hidden layers, fancy activations, feature-normalization learned from data
  — a fixed one-hidden-layer MLP is enough to prove the pipeline and give Phase 2
  something to evolve.
- Tuning the controller for strength — that is what evolution is for.
