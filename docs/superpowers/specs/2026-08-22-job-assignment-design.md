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

---

## Amendment, 2026-08-22: enumerate only tiles that have work

Task 5's review found that the crude-values decision above is not merely crude,
it is **degenerate**, and it makes this experiment unable to test its own
hypothesis.

Every crop job carries the same value, `CROP_JOB_VALUE = 1.0`, so
`_job_score(pos, job)` reduces to `1.0 - TRAVEL_COST * distance`. A worker
standing on any owned crop tile therefore scores that tile at exactly 1.0 and
every other crop tile strictly lower. Measured directly:

```
own tile       score=1.000
1 step away    score=0.950
4 steps away   score=0.800
```

Greedy assignment hands each worker the tile under its feet, forever. Once the
crew spreads over the tiles nearest the shed on the opening turns, **no worker
ever relocates again** — including a worker sitting on a watered live plant with
nothing to do while an empty plantable tile waits one step away. Planted tiles
are capped at roughly the worker count, which is the 10-11 ceiling this issue
exists to break, and a bought quadrant adds jobs nobody will ever walk to.

The evidence is already in the guard: of the four frozen scenarios, the only one
that moved is `mid_game_full_crew` — the only one whose workers are *scattered*
rather than stacked on `SHED_TILE`. It moved to four `PASS` actions, which is
this pathology rendered as data. The other three cannot distinguish the new
mechanism from the old index mapping at all, because when every worker stands on
`SHED_TILE` the distance ordering reproduces `CROP_PLOTS` exactly.

Run as specified, Task 8's hypothesis (**at least 15 planted tiles**) is
unreachable by construction, and its ~3.5 hours would buy a false negative.

### Decision

**`candidate_jobs` enumerates only work that actually exists.** A tile with
nothing to do is not a job. A worker whose tile has gone idle is then free to be
assigned real work elsewhere, because no zero-work job is competing for it.

This stays on the near side of the #119 boundary. #119 is about ranking jobs by
**what they are worth**; this is about whether a job **exists at all**, which is
enumeration — the thing #71 already owns. Job *values* remain uniform and crude,
so a null result still says "assignment did not help", not "our pricing was
wrong".

Two helpers, both position-independent so enumeration never depends on which
worker is asked:

- `_crop_tile_has_work(tile, day, crop)` — `_plot_action(tile, day, crop)[0] != "PASS"`.
  Covers digging a weed, planting an empty tile when a crop can still mature, and
  watering or harvesting a live plant.
- `_animal_tile_has_work(tile_pos, kind, tiles, shed, unlocked)` — true when a
  hungry animal stands there and the shed holds WHEAT to feed it, or when
  `_animal_chore(tile_pos, kind, tile_pos, tiles, {}, shed, unlocked)` is not
  `None`. The empty-inventory argument is deliberate: it asks "does this tile
  want something doing", not "can this particular worker do it". The hunger
  clause is required because `_animal_chore`'s feed branch is gated on the
  worker already holding WHEAT, so a hungry animal with an empty-handed worker
  would otherwise read as no work.

### This also repairs the livestock knob

`livestock_labor_share` had become near-binary: below roughly 0.55 no animal job
outscores a crop job, so all 13 herd tiles are ignored while
`_livestock_market_orders` keeps buying animals on the separate
`herd_target_scale` / `livestock_pace` knobs. Animals were bought, never placed,
never fed, and escaped. The old worker-peel guaranteed `round(share * n)`
tenders; nothing replaced that guarantee.

Filtering fixes the worst of it without touching values: a bought-but-unplaced
animal is a tile that *wants something done*, so it is enumerated as a job and
some worker takes it. Whether the knob then carries a usable gradient for
evolution is a question for the run itself, and is recorded here as a risk rather
than a claim.

### Testing this amendment

- A worker on an idle tile is reassigned: given a fully-watered live plant under
  the worker and an empty plantable tile nearby, the worker moves.
- A tile with nothing to do yields no job at all.
- A hungry animal is enumerated as work even when no worker is carrying WHEAT.
- A bought-but-unplaced animal is enumerated as work.
- **At `controller()` level, not just at the helpers**: with a quadrant newly
  owned, a worker is routed onto a tile outside the starting quadrant. Task 5's
  review found that two tests named `test_controller_*` never call `controller()`
  at all, so the branch's central claim currently has no end-to-end test.
