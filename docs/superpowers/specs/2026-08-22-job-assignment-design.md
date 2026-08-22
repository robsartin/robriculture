# Replacing index-based worker assignment with job assignment

- **Issue:** [#71](https://github.com/robsartin/robriculture/issues/71)
- **Date:** 2026-08-22
- **Status:** Approved (design)
- **Relates to:** ADR-0004 (stdlib-only), ADR-0006 (fail-safe), ADR-0008 (neuroevolution)

## Context

Our agent farms 8 tiles of a 10x10 board. `pilkwang`, a licensed external competitor
benchmarked locally, farms 51 and outscores us roughly 9:1.

| | ours | `pilkwang` |
|---|---|---|
| planted tiles | 8-11 | **51** |
| animals | 0 | 15 |
| hands | 9-10 | 13 |
| units sold | ~150 | **2,046** |
| distinct products | 3 | 7 |
| reward | ~19-23k | **147,862** |

Three cheaper explanations for that gap were tested and eliminated:

- **The optimiser is broken.** It is not. Evolution climbs, generalises (Spearman
  ~+0.9 on held-out map sets), and lifted the baked genome 0.2188 → 0.3760 once its
  readout (#104) and genome selection (#107) were repaired.
- **Land is unaffordable.** Fixed in #100 — a genome now buys near-broke, at $3,000
  on day 0 and $6,455 on day 11.
- **Land is unfarmable.** Tested in #113: plots derived from unlocked quadrants,
  workers routed to distinct tiles, hire ceiling scaled with owned land. Evolution
  **still refused to buy land** — 0 purchases, NW only, ~$22,000 idle, share flat at
  0.3761 against 0.3760. #113 closed `not_planned`.

So expansion is genuinely unprofitable under this controller, and evolution is
correct to decline it. What remains is *why*.

### The mechanism

`controller()` assigns workers to plots **by index**:

```python
plot = CROP_PLOTS[i] if i < len(CROP_PLOTS) else CROP_PLOTS[-1]
```

Worker `i` walks to plot `i`. There is no notion of travel cost, of which job is
worth most this turn, or of who is nearest to what. A worker can walk past a
harvest-ready melon to reach "its" assigned bare tile. A newly-unlocked NE tile
costs the same walk regardless of what that worker was doing.

The same ceiling appears in every agent we own: `meta_rancher` buys both extra
quadrants and still peaks at 10 planted tiles; #113's genome bought land and its
planted tiles *fell* from 10 to 7. **Every agent we have treats land as
decoration**, because none can convert space into work.

## Decision

Replace the index-based mapping with **job enumeration plus greedy assignment**,
keeping every existing job primitive.

The primitives already exist and are tested — `_plot_action`, `_animal_chore`,
`_fertilize_or_fetch`, `_harvest_ready`, `_plantable` all know how to do work at a
tile. Only the *assignment* is missing. This is a change to one mapping, not a
rewrite of the controller.

### Scope includes restoring #113's plot generation

`CROP_PLOTS` on `main` is ten hardcoded NW tiles. A job list built from it can only
ever contain NW jobs, so the hypothesis would not be testable — we would be
measuring "better assignment within NW".

`113-scale-workfields-to-land` carries tested code for this: `crop_plots(unlocked)`,
`_quadrant_tiles`, `_ALL_QUADRANT_TILES`, `_manhattan`, and `_ANIMAL_POSITIONS`.
Plots are filtered against `ANIMAL_TILES` **at construction**, so herd collision is
structurally impossible rather than checked, and unowned land cannot appear because
only quadrants present in `unlocked` are consulted. Both properties carry tests.

Restore those helpers. This is the minimum that makes #71's hypothesis testable.

### Scope deliberately excludes

- **#113's hire-ceiling scaling** (`_max_hands`). It carried a feature-rescale trap
  (see Risks), and more workers without better jobs to give them is not what is being
  tested. It can follow once assignment is proven.
- **Real job valuation.** Values here are deliberately crude. Ranking jobs by what
  they are actually worth is [#119](https://github.com/robsartin/robriculture/issues/119),
  explicitly split out so that a null result here is unambiguous about which half failed.

## Components

### `candidate_jobs(state, knobs) -> list[Job]`

`Job` is a `namedtuple("Job", "pos kind value")`.

- **Crop jobs** — one per plot from `crop_plots(unlocked)`.
- **Animal jobs** — one per position in `ANIMAL_TILES` lying in an unlocked quadrant.
  This must cover **setup as well as tending**: building a pasture and placing an
  animal are jobs, not just feeding one that already exists. Today that work lives in
  `_livestock_worker_action`, reached only via the `livestock_labor_share` worker-peel
  this design removes — so if setup is not enumerated as a job, the herd can never be
  stood up at all and animal jobs stay permanently empty (the champion currently has
  zero animals). Verify against `_livestock_worker_action` and `_animal_chore` that
  every action they can produce is reachable as some job kind.
- **Fertilize job** — at the shed-adjacent tile only, which is the sole plot that can
  `PICKUP` and `FERTILIZE` without leaving.

Pure, deterministic, ordered. Ordering is by `(-value, pos)` so ties break
positionally and the result never depends on dict iteration order.

### `assign_workers(positions, jobs) -> list[Job | None]`

Greedy: for each worker in index order, take the unclaimed job maximising
`value - TRAVEL_COST * _manhattan(worker_pos, job.pos)`. A claimed job is never
reassigned; a worker with no job left gets `None` and falls through to a safe `PASS`.

`TRAVEL_COST` is a fixed module constant, not a knob — see Knob reuse.

Greedy rather than optimal assignment is deliberate: it is O(workers x jobs) with
small numbers, easy to reason about, and stdlib-only. A Hungarian-style optimal
matching is not obviously worth the complexity before we know assignment helps at all.

### `controller()` changes

The worker loop replaces its index lookup with the assignment result, then dispatches
to the **existing** primitive for the job's `kind`. Everything downstream —
`planted_this_turn` seed accounting, market budgeting (#117), the fail-safe — is
untouched.

## Knob reuse — no interface bump

The genome stays 472 weights and `strategies/champion_genome.json` keeps loading.
Two knobs take new meanings:

| knob | was | becomes |
|---|---|---|
| `livestock_labor_share` | fraction of workers peeled off for the herd | **weight on animal-job value** |
| `fertilize_pref` | duty-cycle gate on fertilizing | **weight on fertilize-job value** |

`crop_mix`, `sell_throttle`, `hire_target`, `livestock_pace`, `herd_target_scale` and
`capital_reserve` keep their current meanings — they are economic rather than
assignment decisions and are not touched.

Travel cost is a **constant, not a knob**, because adding one would need a ninth knob
and a versioned interface bump. The current champion would stop loading and evolution
would restart from random, which we measured takes roughly 35 generations to reach
today's level. Not worth it to tune one scalar before knowing the approach works.

## Risks

**Reinterpreting knobs changes the baked genome's behaviour.** Two knobs mean
something new, so the champion's weights are being read differently — exactly the
class of problem that cost 0.14 silently in #100 and was caught by the guard in #113.
Expect `tests/test_champion_genome_regression.py` to go red, and expect the
re-benchmarked share to move.

Per that guard's own rule, a red with the genome unchanged is the **illegitimate**
case: re-benchmark and judge, do not re-bless goldens to make it pass. The honest
sequence is to land the mechanism, re-evolve seeded, and promote the result — the
same path #97 and #111 took.

**Do not repeat #113's feature rescale.** `features()` must keep its fixed
denominators. A feature is the genome's input vocabulary; changing its scale
reinterprets every weight trained against it. Nothing in this design touches
`features()`, and nothing should.

## Error handling

- A worker with no assignable job returns `PASS` — legal and safe under ADR-0006.
- `crop_plots(())` or an empty job list must not raise; the controller degrades to all
  workers passing rather than crashing.
- Assignment must never route two workers to one job, and never to a tile outside
  `unlocked`. Both are structural in `candidate_jobs`, not defensive checks.

## Testing

TDD throughout, red before green.

- `candidate_jobs`: job count grows when a quadrant unlocks; never yields a tile on
  unowned land; never collides with `ANIMAL_TILES`; deterministic ordering.
- `assign_workers`: no two workers share a job; a nearer worker wins an equal-value
  job; travel cost actually discounts distance (a distant high-value job loses to a
  near one at the right ratio); a worker with no jobs left gets `None`.
- Knob weighting: raising `livestock_labor_share` shifts assignments toward animal
  jobs; raising `fertilize_pref` shifts toward the fertilize job.
- Legality: the no-crash gate (`tests/test_no_crash.py`) under `ROBRICULTURE_STRICT=1`
  covers full games.

Coverage gate stays line >= 85% / branch >= 65%. Market-order budgeting from #117 must
remain green — a job-driven controller emits more orders and will press that cap harder.

## Hypothesis (ADR-0007)

With job assignment, a seeded evolution run produces a genome that **buys land and
farms it** — non-zero confirmed `land_purchases` and a peak planted-tile count of
**at least 15** — and whose `genome_bench` share exceeds the baseline measured on the
day the work starts.

The 15 is chosen against measurement, not taste: every agent we have peaks at 10-11
planted tiles regardless of land owned, and `pilkwang` reaches 51. Fifteen is the
smallest number that cannot be reached by the current NW-only ceiling, so clearing it
demonstrates the agent is genuinely working ground it could not work before.

State that baseline explicitly at implementation time. It is **0.3760** today, but
re-benchmark rather than assuming, since the knob reinterpretation will move it.

If evolution still declines land with assignment in place, that is a significant
negative: it would mean the constraint is neither affordability, nor routability, nor
assignment, and would point at job *valuation* (#119) or at something not yet
identified. Report it plainly.
