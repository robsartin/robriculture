# Job-Based Worker Assignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `neuropilot`'s `plot = CROP_PLOTS[i]` index mapping with per-turn job enumeration plus greedy value-minus-travel assignment, so the agent can convert bought land into work.

**Architecture:** Two new pure helpers — `candidate_jobs(state, knobs)` enumerates every piece of work the farm owns this turn, and `assign_workers(positions, jobs)` hands each worker its best unclaimed job. `controller()` dispatches the assigned job to the *existing* primitives (`_plot_action`, `_animal_chore`, `_fertilize_or_fetch`). The worker-index mapping and the `livestock_labor_share` worker-peel both disappear; every other subsystem (market budgeting, seed accounting, land purchase, fail-safe) is untouched.

**Tech Stack:** Python 3.12 (repo `.venv`), stdlib only (ADR-0004), pytest, `kaggle_environments` kaggriculture sim for the no-crash gate.

**Spec:** [docs/superpowers/specs/2026-08-22-job-assignment-design.md](../specs/2026-08-22-job-assignment-design.md)
**Issue:** [#71](https://github.com/robsartin/robriculture/issues/71)

## Global Constraints

- **Branch:** work on `71-job-assignment`, branched from `main`. Nothing lands on `main` directly; the branch ends at a PR for review, never auto-merged.
- **Stdlib only** in `strategies/` and `kaggisim/` (ADR-0004). No numpy, no third-party imports.
- **`neuropilot` imports no other strategy module** (ADR-0008). Constants mirroring another strategy's layout are re-declared BY VALUE.
- **Do not touch `features()`.** Its fixed denominators are the genome's input vocabulary; rescaling a feature reinterprets every weight trained against it. This is the exact trap that sank #113.
- **Do not change the genome interface.** `N_FEATURES = 20`, `H1 = 16`, `N_KNOBS = 8`, genome length 472. Adding a ninth knob restarts evolution from random (~35 generations to recover).
- **`MAX_HANDS` stays 9.** Hire-ceiling scaling is explicitly out of scope (it is #113's `_max_hands`, deferred until assignment is proven).
- **Develop under strict mode:** `ROBRICULTURE_STRICT=1` so a strategy exception surfaces instead of degrading to a silent PASS (ADR-0006).
- **Coverage gate:** line >= 85%, branch >= 65%. CLI `main()`s get `# pragma: no cover` at the `def`.
- **Stage commits by explicit path.** Never `git add -A` — this worktree is shared with parallel sessions.
- **Every commit message ends with the trailer:** `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`
- **Run tests as** `.venv/bin/python -m pytest` (the default `python3` on this Mac is 3.9 and will fail to import).
- **Measured baseline, taken 2026-08-22 on `main` before any of this work:** `python -m harness.genome_bench --genome strategies/champion_genome.json --games 4` reports **share = 0.3760**, matching the genome's recorded `meta.share`. This is the number Task 6 compares against.

---

### Task 1: Restore quadrant-derived crop plots

Bring back #113's plot generator so a job list can contain tiles outside NW. This task is deliberately **behaviour-preserving**: `crop_plots(("NW",))`'s first ten entries are byte-identical to today's hardcoded `CROP_PLOTS` (verified 2026-08-22), and with `MAX_HANDS = 9` at most ten workers exist, so `CROP_PLOTS[i]` returns exactly what it returned before. The champion regression guard must stay **green** through this task — if it goes red here, the ordering was reproduced wrong.

**Files:**
- Modify: `strategies/neuropilot.py` — insert after the `ANIMAL_TILES` / `SHED_TILE` block (around line 309-321), before `_needs_quadrant`
- Test: `tests/test_neuropilot.py`

**Interfaces:**
- Consumes: `ANIMAL_TILES`, `SHED_TILE` (already on `main`)
- Produces: `_manhattan(a, b) -> int`, `crop_plots(unlocked) -> list[tuple[int, int]]`, `CROP_PLOTS` (now derived, same value as before for the first 10 entries)

- [ ] **Step 1: Create the branch**

```bash
git checkout main && git pull && git checkout -b 71-job-assignment
```

- [ ] **Step 2: Write the failing tests**

Append to `tests/test_neuropilot.py`:

```python
# --- #71: quadrant-derived crop plots (restored from #113) ---

def test_crop_plots_prefix_matches_the_old_hardcoded_nw_crew():
    # The generator must reproduce the shipped NW ordering exactly for the
    # first 10 plots: with MAX_HANDS = 9 that is every plot the controller
    # could previously reach, so this task changes no behaviour.
    assert np.crop_plots(("NW",))[:10] == [
        (4, 4), (3, 4), (4, 3), (2, 4), (3, 3), (4, 2), (1, 4), (2, 3), (3, 2), (4, 1),
    ]


def test_crop_plots_grows_when_a_quadrant_unlocks():
    # Buying land must add workable tiles -- the whole point of #71.
    assert len(np.crop_plots(("NW", "NE"))) > len(np.crop_plots(("NW",)))


def test_crop_plots_never_yields_a_tile_on_unowned_land():
    # Every NW plot has x <= 4 and y <= 4; nothing from another quadrant leaks in.
    assert all(x <= 4 and y <= 4 for x, y in np.crop_plots(("NW",)))


def test_crop_plots_never_collides_with_an_animal_tile():
    # Structural, not checked at use-time: the herd's tiles are filtered out
    # at construction, so a crop job can never be sent onto a pasture.
    animal_positions = {pos for pos, _ in np.ANIMAL_TILES}
    everywhere = np.crop_plots(("NW", "NE", "SW", "SE"))
    assert animal_positions.isdisjoint(everywhere)


def test_crop_plots_is_deterministic_and_nearest_shed_first():
    # ADR-0005: same input, same list, every time; ordered by walk distance.
    plots = np.crop_plots(("NW", "NE"))
    assert plots == np.crop_plots(("NW", "NE"))
    dists = [np._manhattan(np.SHED_TILE, p) for p in plots]
    assert dists == sorted(dists)
    assert plots[0] == np.SHED_TILE


def test_crop_plots_returns_empty_for_no_quadrants():
    # Must degrade, not raise -- the controller turns this into all-PASS.
    assert np.crop_plots(()) == []


def test_manhattan_is_l1_distance():
    assert np._manhattan((0, 0), (3, 4)) == 7
    assert np._manhattan((4, 4), (4, 4)) == 0
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_neuropilot.py -k "crop_plots or manhattan" -v`
Expected: FAIL — `AttributeError: module 'strategies.neuropilot' has no attribute 'crop_plots'`

- [ ] **Step 4: Write the implementation**

In `strategies/neuropilot.py`, **delete** the existing `CROP_PLOTS` list literal (the ten-tile block around line 169-175, with its `#:` comment), and insert this block immediately after `SHED_TILE`'s definition:

```python
#: Board quadrant bounds (inclusive), mirroring the sim's own
#: `_quadrant_of(x, y, board_size)` (board_size=10, half=5): N/S splits on
#: y < half, W/E splits on x < half. SE is included for completeness even
#: though `_land_order` never buys it -- no ANIMAL_TILES tile lives there.
_QUADRANT_BOUNDS = {
    "NW": (0, 4, 0, 4), "NE": (5, 9, 0, 4), "SW": (0, 4, 5, 9), "SE": (5, 9, 5, 9),
}

#: Positions occupied by the herd -- never crop-workable.
_ANIMAL_POSITIONS = frozenset(pos for pos, _ in ANIMAL_TILES)


def _manhattan(a, b) -> int:
    """L1 distance between two board positions (turns to walk, obstacle-free)."""
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def _quadrant_tiles(quadrant: str) -> list:
    """Every tile in `quadrant` that isn't an animal structure's tile."""
    x0, x1, y0, y1 = _QUADRANT_BOUNDS[quadrant]
    return [
        (x, y) for y in range(y0, y1 + 1) for x in range(x0, x1 + 1)
        if (x, y) not in _ANIMAL_POSITIONS
    ]


#: Every quadrant's crop-eligible tiles, precomputed once at import -- pure
#: coordinates, no dependency on game state, so `crop_plots` only filters by
#: ownership and sorts each turn instead of rebuilding tile lists.
_ALL_QUADRANT_TILES = {q: _quadrant_tiles(q) for q in _QUADRANT_BOUNDS}


def crop_plots(unlocked) -> list:
    """Every crop-workable tile in the owned (`unlocked`) quadrants, nearest
    `SHED_TILE` first (#113 code, restored by #71 -- replaces the old
    hard-coded 10-tile NW-only `CROP_PLOTS`).

    Ordered by walking distance to the shed, ties broken by (x, y) for a
    deterministic layout. Distance, not quadrant, drives the order: a close
    NE/SW tile can sort ahead of a far NW one, so buying land can hand a
    worker a *shorter* walk than some NW tile it already had. `SHED_TILE` is
    always first (distance 0, and NW is always owned). Animal tiles are never
    included, so a crop plot can never collide with the herd; only tiles in
    `unlocked` quadrants appear, so a plot can never land on unbought land.
    Both properties are structural, not checked at use-time.
    """
    tiles = [t for q in unlocked for t in _ALL_QUADRANT_TILES.get(q, ())]
    tiles.sort(key=lambda t: (_manhattan(SHED_TILE, t), t[0], t[1]))
    return tiles


#: NW-only crop-plot ordering, nearest-first -- kept as a plain constant for
#: callers and tests that just need "the plot at index i with only the
#: starting quadrant owned". The controller calls `crop_plots(unlocked)`
#: fresh each turn, since ownership changes mid-game.
CROP_PLOTS = crop_plots(("NW",))
```

`ANIMAL_TILES` and `SHED_TILE` are defined around lines 309-321 on `main`, *after* the old `CROP_PLOTS` at line 169. Moving the plot block below them is required — `_ANIMAL_POSITIONS` reads `ANIMAL_TILES` at import time. Check that nothing between the old and new locations referenced `CROP_PLOTS` at module scope (only `controller()` does, at call time).

- [ ] **Step 5: Run the new tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_neuropilot.py -k "crop_plots or manhattan" -v`
Expected: PASS (7 tests)

- [ ] **Step 6: Run the full suite — the regression guard must stay green**

Run: `ROBRICULTURE_STRICT=1 .venv/bin/python -m pytest -q`
Expected: PASS, all tests, **including `tests/test_champion_genome_regression.py`**.

If the guard is red here, **stop**. This task is behaviour-preserving by construction; a red guard means `crop_plots(("NW",))`'s ordering does not reproduce the old list. Diff `np.crop_plots(("NW",))[:10]` against the ten tuples in Step 2's first test rather than editing `GOLDEN_ACTIONS`.

- [ ] **Step 7: Commit**

```bash
git add strategies/neuropilot.py tests/test_neuropilot.py
git commit -m "feat(neuropilot): derive crop plots from unlocked quadrants (#71)"
```

---

### Task 2: Enumerate this turn's jobs

**Files:**
- Modify: `strategies/neuropilot.py` — insert after `_needs_quadrant` / `_is_animal` and after `_is_fertilize_day` is defined. `_is_fertilize_day` lives near line 570 on `main`, well below the animal block, so place `candidate_jobs` **after** `_is_fertilize_day` (just before `_fertilizer_buy_order`) and keep the `Job`/constant declarations with it.
- Test: `tests/test_neuropilot.py`

**Interfaces:**
- Consumes: `crop_plots(unlocked)` and `_manhattan` (Task 1); `ANIMAL_TILES`, `SHED_TILE`, `_needs_quadrant`, `_is_fertilize_day`, `Knobs` (all on `main`)
- Produces: `Job = namedtuple("Job", ["pos", "kind", "value"])`, `candidate_jobs(state, knobs) -> list[Job]`, constants `CROP_JOB_VALUE`, `ANIMAL_JOB_SCALE`, `TRAVEL_COST`, `_ANIMAL_KINDS`

A `Job.kind` is one of `"CROP"`, `"FERTILIZE"`, `"COW"`, `"SHEEP"`. Animal species double as job kinds because `_animal_chore` already takes the species as its `kind` argument — no translation table needed.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_neuropilot.py`:

```python
# --- #71: job enumeration ---

def _knobs(**over):
    """A Knobs with every field at a mid value, overridable per test."""
    base = dict(sell_throttle=0.5, hire_target=0.5, livestock_pace=0.5,
                livestock_labor_share=0.5, herd_target_scale=0.5,
                fertilize_pref=0.0, capital_reserve=0.5, crop_mix=0.5)
    base.update(over)
    return np.Knobs(**base)


def test_candidate_jobs_has_one_crop_job_per_owned_plot():
    jobs = np.candidate_jobs(_obs(), _knobs())
    crop = [j for j in jobs if j.kind == "CROP"]
    assert len(crop) == len(np.crop_plots(("NW",)))


def test_candidate_jobs_grows_when_a_quadrant_unlocks():
    # More land must mean more work available -- the hypothesis under test.
    few = np.candidate_jobs(_obs(unlocked=("NW",)), _knobs())
    many = np.candidate_jobs(_obs(unlocked=("NW", "NE")), _knobs())
    assert len(many) > len(few)


def test_candidate_jobs_omits_animal_jobs_on_unowned_land():
    # Cows live in NE, sheep in SW; owning only NW means no animal work exists.
    jobs = np.candidate_jobs(_obs(unlocked=("NW",)), _knobs())
    assert not [j for j in jobs if j.kind in np._ANIMAL_KINDS]


def test_candidate_jobs_includes_animal_jobs_once_their_quadrant_is_owned():
    jobs = np.candidate_jobs(_obs(unlocked=("NW", "NE")), _knobs())
    cows = [j for j in jobs if j.kind == "COW"]
    assert len(cows) == sum(1 for _, k in np.ANIMAL_TILES if k == "COW")


def test_candidate_jobs_positions_are_unique():
    # No two workers can ever be routed to the same tile: the fertilize job
    # REPLACES the shed tile's crop job rather than sitting beside it.
    jobs = np.candidate_jobs(_obs(unlocked=("NW", "NE", "SW")), _knobs(fertilize_pref=1.0))
    positions = [j.pos for j in jobs]
    assert len(positions) == len(set(positions))


def test_candidate_jobs_replaces_the_shed_crop_job_with_fertilize_on_a_duty_day():
    jobs = np.candidate_jobs(_obs(day=0), _knobs(fertilize_pref=1.0))
    at_shed = [j for j in jobs if j.pos == np.SHED_TILE]
    assert len(at_shed) == 1 and at_shed[0].kind == "FERTILIZE"


def test_candidate_jobs_has_no_fertilize_job_when_the_knob_is_off():
    jobs = np.candidate_jobs(_obs(day=0), _knobs(fertilize_pref=0.0))
    assert not [j for j in jobs if j.kind == "FERTILIZE"]


def test_candidate_jobs_fertilize_value_rises_with_fertilize_pref():
    # The other reinterpreted knob: it now weights the fertilize job instead
    # of gating a duty cycle, so a keener setting must outbid more jobs.
    low = [j for j in np.candidate_jobs(_obs(day=0), _knobs(fertilize_pref=0.3))
           if j.kind == "FERTILIZE"]
    high = [j for j in np.candidate_jobs(_obs(day=0), _knobs(fertilize_pref=1.0))
            if j.kind == "FERTILIZE"]
    assert low and high and high[0].value > low[0].value


def test_candidate_jobs_animal_value_rises_with_livestock_labor_share():
    # The reinterpreted knob: it now weights animal work instead of peeling
    # a fixed fraction of workers off the crop crew.
    o = _obs(unlocked=("NW", "NE"))
    low = [j for j in np.candidate_jobs(o, _knobs(livestock_labor_share=0.1)) if j.kind == "COW"]
    high = [j for j in np.candidate_jobs(o, _knobs(livestock_labor_share=0.9)) if j.kind == "COW"]
    assert high[0].value > low[0].value


def test_candidate_jobs_is_sorted_best_first_and_deterministic():
    o = _obs(unlocked=("NW", "NE"))
    jobs = np.candidate_jobs(o, _knobs())
    assert jobs == np.candidate_jobs(o, _knobs())
    assert [j.value for j in jobs] == sorted((j.value for j in jobs), reverse=True)


def test_candidate_jobs_returns_empty_when_nothing_is_owned():
    # Degrades rather than raising; the controller turns this into all-PASS.
    assert np.candidate_jobs(_obs(unlocked=()), _knobs()) == []
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_neuropilot.py -k candidate_jobs -v`
Expected: FAIL — `AttributeError: module 'strategies.neuropilot' has no attribute 'candidate_jobs'`

- [ ] **Step 3: Write the implementation**

Insert into `strategies/neuropilot.py` after `_is_fertilize_day`:

```python
# --- #71: jobs replace the worker-index -> plot mapping ---------------------
#
# The old controller sent worker `i` to `CROP_PLOTS[i]`. There was no notion
# of travel cost, of which job was worth most this turn, or of who was
# nearest to what -- so a worker could walk past a harvest-ready melon to
# reach "its" bare tile, and a newly-bought quadrant's tiles were reachable
# only by workers whose index happened to land on them. Every agent we own
# peaks at 10-11 planted tiles regardless of land owned; `pilkwang` reaches
# 51. Enumerate the work, then assign it.

#: What one turn of a crop tile is nominally worth. Every other value is
#: expressed relative to this, so it is the unit rather than a tunable.
CROP_JOB_VALUE = 1.0

#: Animal-job value at `livestock_labor_share` = 1.0. At the midpoint 0.5 an
#: animal job is worth exactly one crop job, so the knob's old "what fraction
#: of effort goes to the herd" meaning survives the reinterpretation.
ANIMAL_JOB_SCALE = 2.0

#: Value lost per tile of walking. At 0.05 the longest walk on a 10x10 board
#: (18 tiles) costs 0.9 -- just under one crop job, so distance decides
#: between comparable jobs but never outranks a genuinely better one.
#: A constant, not a knob: a ninth knob would be a versioned genome interface
#: bump, restarting evolution from random to tune one scalar.
TRAVEL_COST = 0.05

#: Job kinds that mean "work the animal on this tile". The species doubles as
#: the job kind because `_animal_chore` already takes it as its `kind` arg.
_ANIMAL_KINDS = frozenset(("COW", "SHEEP"))

#: One piece of work: where it is, what kind, and what it is worth this turn.
Job = collections.namedtuple("Job", ["pos", "kind", "value"])


def candidate_jobs(state, knobs: Knobs) -> list:
    """Every piece of work the farm owns this turn, best-valued first.

    Pure and deterministic. Positions are unique across the returned list --
    animal tiles are excluded from `crop_plots` at construction, and the
    fertilize job *replaces* the shed tile's crop job rather than sitting
    beside it -- so `assign_workers` can never route two workers to one tile.

    Values are deliberately crude: this experiment tests whether *assignment*
    unlocks the land, not whether we can price work correctly. Ranking jobs by
    what they are actually worth is #119.
    """
    player = state.get("player", 0)
    me = state["farms"][player]
    day = state.get("day", 0)
    unlocked = me.get("unlocked_quadrants", ["NW"])

    fertilize_day = _is_fertilize_day(knobs.fertilize_pref, day)
    jobs = []
    for pos in crop_plots(unlocked):
        if pos == SHED_TILE and fertilize_day:
            # Only the shed-adjacent tile can PICKUP + FERTILIZE without
            # leaving, so it is the only tile this job can ever be at.
            jobs.append(Job(pos, "FERTILIZE", CROP_JOB_VALUE + knobs.fertilize_pref))
        else:
            jobs.append(Job(pos, "CROP", CROP_JOB_VALUE))
    for pos, kind in ANIMAL_TILES:
        if _needs_quadrant(kind) in unlocked:
            jobs.append(Job(pos, kind, ANIMAL_JOB_SCALE * knobs.livestock_labor_share))
    # Ties break positionally so the order never depends on how the lists
    # above happened to be built (ADR-0005).
    jobs.sort(key=lambda j: (-j.value, j.pos))
    return jobs
```

Confirm `import collections` is already at the top of the module (it is — `Knobs` uses it).

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_neuropilot.py -k candidate_jobs -v`
Expected: PASS (11 tests)

- [ ] **Step 5: Run the full suite**

Run: `ROBRICULTURE_STRICT=1 .venv/bin/python -m pytest -q`
Expected: PASS. `candidate_jobs` is not wired into `controller()` yet, so nothing else can have changed — the regression guard is still green.

- [ ] **Step 6: Commit**

```bash
git add strategies/neuropilot.py tests/test_neuropilot.py
git commit -m "feat(neuropilot): enumerate this turn's jobs (#71)"
```

---

### Task 3: Greedily assign workers to jobs

**Files:**
- Modify: `strategies/neuropilot.py` — immediately after `candidate_jobs`
- Test: `tests/test_neuropilot.py`

**Interfaces:**
- Consumes: `Job`, `TRAVEL_COST` (Task 2); `_manhattan` (Task 1)
- Produces: `_job_score(pos, job) -> float`, `assign_workers(positions, jobs) -> list[Job | None]` (one entry per worker, in worker order)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_neuropilot.py`:

```python
# --- #71: greedy worker assignment ---

def test_assign_workers_gives_each_worker_a_distinct_job():
    jobs = [np.Job((0, 0), "CROP", 1.0), np.Job((1, 1), "CROP", 1.0),
            np.Job((2, 2), "CROP", 1.0)]
    got = np.assign_workers([(0, 0), (1, 1), (2, 2)], jobs)
    assert len({j.pos for j in got}) == 3


def test_assign_workers_returns_none_when_jobs_run_out():
    # A worker with nothing to do passes; it must not crash or double-book.
    got = np.assign_workers([(0, 0), (5, 5)], [np.Job((0, 0), "CROP", 1.0)])
    assert got[0].pos == (0, 0) and got[1] is None


def test_assign_workers_returns_all_none_for_an_empty_job_list():
    assert np.assign_workers([(0, 0), (1, 1)], []) == [None, None]


def test_assign_workers_prefers_the_nearer_of_two_equal_jobs():
    near, far = np.Job((0, 1), "CROP", 1.0), np.Job((9, 9), "CROP", 1.0)
    assert np.assign_workers([(0, 0)], [far, near])[0] == near


def test_assign_workers_walks_to_a_job_worth_the_trip():
    # Travel cost is 0.05/tile: a job 10 tiles away costs 0.5, so a value
    # advantage of 1.0 must still win.
    near = np.Job((0, 1), "CROP", 1.0)
    far = np.Job((0, 10 + 1), "COW", 2.0)
    assert np.assign_workers([(0, 0)], [far, near])[0] == far


def test_assign_workers_declines_a_job_not_worth_the_trip():
    # The same distant job at a small value advantage loses to the near one.
    near = np.Job((0, 1), "CROP", 1.0)
    far = np.Job((0, 10 + 1), "COW", 1.2)
    assert np.assign_workers([(0, 0)], [far, near])[0] == near


def test_assign_workers_is_deterministic():
    jobs = [np.Job((0, 0), "CROP", 1.0), np.Job((0, 1), "CROP", 1.0)]
    positions = [(0, 0), (0, 1)]
    assert np.assign_workers(positions, jobs) == np.assign_workers(positions, jobs)


def test_job_score_discounts_distance():
    job = np.Job((0, 5), "CROP", 1.0)
    assert np._job_score((0, 0), job) == 1.0 - np.TRAVEL_COST * 5
    assert np._job_score((0, 5), job) == 1.0
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_neuropilot.py -k "assign_workers or job_score" -v`
Expected: FAIL — `AttributeError: module 'strategies.neuropilot' has no attribute 'assign_workers'`

- [ ] **Step 3: Write the implementation**

Insert into `strategies/neuropilot.py` immediately after `candidate_jobs`:

```python
def _job_score(pos, job: Job) -> float:
    """What `job` is worth to the worker standing at `pos`: its value less
    the walk needed to reach it."""
    return job.value - TRAVEL_COST * _manhattan(pos, job.pos)


def assign_workers(positions, jobs) -> list:
    """Give each worker its best remaining job; `None` when none is left.

    Greedy: workers are served in index order, each takes the unclaimed job
    maximising `_job_score`, and a claimed job is never reassigned. Returns
    one entry per worker, in worker order, so the caller can zip it against
    `positions`.

    Deterministic (ADR-0005): `jobs` arrives in a fixed order from
    `candidate_jobs` and `max` keeps the first of any tie, so the same state
    always produces the same assignment.

    Greedy rather than optimal (Hungarian) matching is deliberate: it is
    O(workers x jobs) on single-digit worker counts, stdlib-only, and easy to
    reason about. Optimal matching is not obviously worth the complexity
    before we know assignment helps at all.
    """
    remaining = list(jobs)
    assigned = []
    for pos in positions:
        if not remaining:
            assigned.append(None)
            continue
        best = max(remaining, key=lambda j: _job_score(pos, j))
        remaining.remove(best)
        assigned.append(best)
    return assigned
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_neuropilot.py -k "assign_workers or job_score" -v`
Expected: PASS (8 tests)

- [ ] **Step 5: Run the full suite**

Run: `ROBRICULTURE_STRICT=1 .venv/bin/python -m pytest -q`
Expected: PASS — still not wired in, so the regression guard stays green.

- [ ] **Step 6: Commit**

```bash
git add strategies/neuropilot.py tests/test_neuropilot.py
git commit -m "feat(neuropilot): greedy value-minus-travel worker assignment (#71)"
```

---

### Task 4: One action for one assigned animal tile

Assignment hands out a single tile at a time, so the beat-walking in `_livestock_worker_action` / `_assign_beats` no longer has a caller. Replace both with a per-tile handler.

This handler must cover **setup as well as tending**. `_animal_chore` already does (build pasture -> fetch the bought animal from the shed -> place it -> feed/harvest/collect/care), and it is the only path to that work. Removing the `livestock_labor_share` worker-peel removes the old route into it, so if the job handler skipped setup the herd could never be stood up at all — the champion currently has zero animals, so animal jobs would stay permanently empty and livestock would be unreachable.

This task is **purely additive**: the old `_assign_beats` / `_livestock_worker_action` pair stays in place until Task 5 stops calling it, so the suite is green at every step here and this task carries its own commit.

**Files:**
- Modify: `strategies/neuropilot.py` — add after `_livestock_worker_action` (around line 435)
- Test: `tests/test_neuropilot.py`

**Interfaces:**
- Consumes: `_animal_chore`, `_is_animal`, `_tile_at`, `_on`, `_step_toward`, `SHED_TILE`, `acts` (all on `main`)
- Produces: `_animal_job_action(tile_pos, kind, pos, tiles, inv, shed, unlocked) -> list` — a legal action list, **never `None`**

- [ ] **Step 1: Inventory what the old helpers guarantee**

Run: `grep -n "_assign_beats\|_livestock_worker_action" tests/test_neuropilot.py strategies/neuropilot.py`

Record what each existing test asserts. Every behaviour they pin — feed-leads-maintenance, fetching WHEAT from the shed, falling through to `_animal_chore`, never returning `None` — needs a replacement in Step 2, because Task 5 deletes those tests along with the helpers. Do not let an assertion disappear without one here.

- [ ] **Step 2: Write the failing tests**

Append to `tests/test_neuropilot.py`:

```python
# --- #71: per-tile animal job action (replaces beat-walking) ---

def _cow_tiles(**tile):
    """A board with a cow structure at (5, 0), the first COW animal tile."""
    board = [[None] * 10 for _ in range(10)]
    board[0][5] = {"kind": "PASTURE", "animal": "COW", **tile}
    return board


def test_animal_job_action_feeds_a_hungry_animal_it_is_standing_on():
    tiles = _cow_tiles(fed_today=False)
    got = np._animal_job_action((5, 0), "COW", (5, 0), tiles,
                                {"WHEAT": 1}, {}, ("NW", "NE"))
    assert got[0] == "FEED"


def test_animal_job_action_fetches_wheat_from_the_shed_when_it_holds_none():
    # Feed leads maintenance: an animal escapes after two unfed days.
    tiles = _cow_tiles(fed_today=False)
    got = np._animal_job_action((5, 0), "COW", np.SHED_TILE, tiles,
                                {}, {"WHEAT": 5}, ("NW", "NE"))
    assert got[0] == "PICKUP"


def test_animal_job_action_builds_a_pasture_on_a_bare_owned_tile():
    # Setup, not just tending -- without this the herd can never stand up.
    tiles = [[None] * 10 for _ in range(10)]
    got = np._animal_job_action((5, 0), "COW", (5, 0), tiles, {}, {}, ("NW", "NE"))
    assert got[0] == "BUILD_PASTURE"


def test_animal_job_action_places_an_animal_it_is_carrying():
    tiles = [[None] * 10 for _ in range(10)]
    tiles[0][5] = {"kind": "PASTURE"}
    got = np._animal_job_action((5, 0), "COW", (5, 0), tiles,
                                {"COW": 1}, {}, ("NW", "NE"))
    assert got[0] == "PLACE"


def test_animal_job_action_walks_toward_its_tile_when_nothing_else_applies():
    tiles = _cow_tiles(fed_today=True, cared_today=True)
    got = np._animal_job_action((5, 0), "COW", (0, 0), tiles, {}, {}, ("NW", "NE"))
    assert got[0] in ("EAST", "WEST", "NORTH", "SOUTH")


def test_animal_job_action_never_returns_none():
    # The controller appends this straight into the action list (ADR-0006).
    tiles = _cow_tiles(fed_today=True, cared_today=True)
    got = np._animal_job_action((5, 0), "COW", (5, 0), tiles, {}, {}, ("NW", "NE"))
    assert isinstance(got, list) and got
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_neuropilot.py -k animal_job_action -v`
Expected: FAIL — `AttributeError: module 'strategies.neuropilot' has no attribute '_animal_job_action'`

- [ ] **Step 4: Write the implementation**

Add to `strategies/neuropilot.py`, immediately after `_livestock_worker_action` (which stays for now — Task 5 removes it once nothing calls it):

```python
def _animal_job_action(tile_pos, kind: str, pos, tiles, inv: dict,
                       shed: dict, unlocked) -> list:
    """The action for the worker assigned to ONE animal tile (never `None`).

    Replaces `_livestock_worker_action` + `_assign_beats` (#71): assignment
    hands out one tile at a time, so there is no beat to walk.

    Feed still leads -- an animal escapes after two unfed days -- so a hungry
    animal whose worker holds no WHEAT sends that worker to the shed first.
    Everything else falls through to `_animal_chore`, which covers setup
    (build the pasture, fetch the bought animal, place it) as well as
    tending; that path is the *only* route to standing a herd up now that the
    `livestock_labor_share` worker-peel is gone.
    """
    tile = _tile_at(tiles, tile_pos)
    hungry = _is_animal(tile) and not tile.get("fed_today", False)
    if hungry and inv.get("WHEAT", 0) <= 0 and shed.get("WHEAT", 0) > 0:
        return acts.pickup("WHEAT", 1) if _on(pos, SHED_TILE) else _step_toward(pos, SHED_TILE)
    chore = _animal_chore(tile_pos, kind, pos, tiles, inv, shed, unlocked)
    if chore is not None:
        return chore
    return acts.pass_() if _on(pos, tile_pos) else _step_toward(pos, tile_pos)
```

- [ ] **Step 5: Run the new tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_neuropilot.py -k animal_job_action -v`
Expected: PASS (6 tests)

- [ ] **Step 6: Run the full suite**

Run: `ROBRICULTURE_STRICT=1 .venv/bin/python -m pytest -q`
Expected: PASS — nothing calls `_animal_job_action` yet, so the regression guard is still green.

- [ ] **Step 7: Commit**

```bash
git add strategies/neuropilot.py tests/test_neuropilot.py
git commit -m "feat(neuropilot): per-tile animal job action (#71)"
```

---

### Task 5: Wire the controller to jobs

**Files:**
- Modify: `strategies/neuropilot.py` — `controller()`, around lines 638-750
- Test: `tests/test_neuropilot.py`

**Interfaces:**
- Consumes: `candidate_jobs`, `assign_workers` (Tasks 2-3), `_animal_job_action` (Task 4), `crop_plots` (Task 1); `_plot_action`, `_fertilize_or_fetch`, `_sell_orders`, `_livestock_market_orders`, `_crop_for` (all on `main`)
- Produces: no new public names. `controller(knobs, state) -> dict` keeps its exact signature and return shape.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_neuropilot.py`:

```python
# --- #71: the controller dispatches assigned jobs ---

def test_controller_sends_a_worker_to_a_tile_outside_nw_once_it_is_owned():
    # The whole point of #71: with 10 workers and only NW owned every worker
    # stays in NW; owning NE must put at least one of them on an NE tile.
    hands = [[4, 4]] * 9
    o = _obs(hands=hands, unlocked=("NW", "NE"))
    jobs = np.candidate_jobs(o, _knobs())
    got = np.assign_workers([[4, 4]] + hands, jobs)
    assert any(j is not None and j.pos[0] >= 5 for j in got)


def test_controller_never_sends_two_workers_to_the_same_tile():
    hands = [[4, 4]] * 9
    o = _obs(hands=hands, unlocked=("NW", "NE", "SW"))
    got = [j for j in np.assign_workers([[4, 4]] + hands, np.candidate_jobs(o, _knobs()))
           if j is not None]
    assert len({j.pos for j in got}) == len(got)


def test_controller_returns_a_legal_shape_with_no_land_and_no_jobs():
    # Degenerate case: nothing owned -> every worker passes, no crash.
    o = _obs(hands=[[0, 0]], unlocked=())
    out = np.controller(_knobs(), o)
    assert out["farmer"] == ["PASS"]
    assert out["hands"] == [["PASS"]]


def test_controller_emits_one_action_per_worker():
    hands = [[4, 4]] * 5
    out = np.controller(_knobs(), _obs(hands=hands))
    assert len(out["hands"]) == len(hands)
    assert isinstance(out["farmer"], list) and out["farmer"]


def test_controller_respects_the_market_order_cap():
    # #117's budgeting must survive: a job-driven controller emits more
    # orders and presses the cap harder.
    cap = economy.CONFIG_DEFAULTS["maxMarketOrdersPerTurn"]
    out = np.controller(_knobs(hire_target=1.0), _obs(hands=[[4, 4]] * 9, money=99999))
    assert len(out["market"]) <= cap


def test_controller_buys_seed_for_assigned_tiles_not_every_owned_plot():
    # Seed accounting follows the assignment, not a prefix of CROP_PLOTS.
    # Farmer + 3 hands on an empty NW board: 4 workers take 4 empty crop
    # tiles, so exactly 4 seeds are wanted -- not the 25 tiles NW contains,
    # and not the 2 the old livestock_labor_share peel would have left.
    out = np.controller(_knobs(crop_mix=1.0), _obs(hands=[[4, 4]] * 3, money=99999))
    buys = [o for o in out["market"] if o[0] == "BUY_SEED"]
    assert buys == [["BUY_SEED", "MELON", 4]]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_neuropilot.py -k controller -v`
Expected: FAIL. Two of the six exercise Tasks 2-3 directly and already pass
(`..._sends_a_worker_to_a_tile_outside_nw_once_it_is_owned`,
`..._never_sends_two_workers_to_the_same_tile`). The controller-level ones fail
because `controller()` still maps `worker i -> CROP_PLOTS[i]` and still peels a
livestock crew: `..._returns_a_legal_shape_with_no_land_and_no_jobs` gets a real
plot action instead of `PASS` (the index mapping happily sends a worker to
`CROP_PLOTS[0]` on land the farm does not own), and
`..._buys_seed_only_for_assigned_empty_crop_tiles` counts empty tiles against a
prefix of `CROP_PLOTS` rather than against the assignment.

- [ ] **Step 3: Write the implementation**

In `controller()`, replace the worker-role block, the worker loop, and the seed-accounting block. Everything else in the function — the state unpacking above, `_sell_orders`, the hire budget, `_livestock_market_orders`, the `[:cap]` truncation, the return statement — stays exactly as it is.

Replace the docstring's "Worker roles" paragraph with:

```python
    """A legal `{"farmer", "hands", "market"}` turn from decoded knobs + state.

    Worker roles: `candidate_jobs` enumerates every piece of work the farm
    owns this turn and `assign_workers` gives each worker its best unclaimed
    one, discounted by the walk to reach it (#71). This replaced a fixed
    `worker i -> CROP_PLOTS[i]` mapping that could not route anyone onto
    newly-bought land, and a `livestock_labor_share` peel that split workers
    into crop and herd crews before either had been costed.
    Market: budgeted by priority against `maxMarketOrdersPerTurn` (#117) --
    sells lead and are never truncated, then the seed the assigned crop
    workers need this turn (skip it and planting stalls), then hires up to
    `hire_target * MAX_HANDS` new hands (mornings only, capped to whatever's
    left after sells + seed), then livestock/fertilizer orders fill the rest.
    """
```

Delete this block:

```python
    # --- Worker roles: the last `livestock_labor_share` fraction of workers
    # (farmer first, then hands) tend the herd; the rest farm crops. ---
    positions = [me["farmer"], *hands]
    n_workers = len(positions)
    n_livestock = min(n_workers, max(0, round(knobs.livestock_labor_share * n_workers)))
    n_crop = n_workers - n_livestock
    beats = _assign_beats(n_livestock)
```

and put in its place:

```python
    # --- Jobs: enumerate the work, then assign it (#71). ---
    positions = [me["farmer"], *hands]
    assignment = assign_workers(positions, candidate_jobs(state, knobs))
```

Replace the entire worker loop (`for i, pos in enumerate(positions):` through the `else:` branch that appends `_livestock_worker_action(...)`) with:

```python
    planted_this_turn: dict = {}
    actions = []
    for i, (pos, job) in enumerate(zip(positions, assignment)):
        inv = inventories[i] if i < len(inventories) else {}
        if job is None:
            # More workers than jobs: passing is legal and safe (ADR-0006).
            actions.append(acts.pass_())
            continue
        if job.kind in _ANIMAL_KINDS:
            actions.append(_animal_job_action(job.pos, job.kind, pos, tiles,
                                              inv, shed, unlocked))
            continue
        # CROP and FERTILIZE both work a crop tile; walk there first.
        if not _on(pos, job.pos):
            actions.append(_step_toward(pos, job.pos))
            continue
        tile = _tile_at(tiles, job.pos)
        action = None
        if job.kind == "FERTILIZE":
            # `_fertilize_or_fetch` returns None when there is nothing to
            # fertilize or fetch, in which case the tile is farmed normally --
            # the same fall-through the old duty-cycle gate had.
            action = _fertilize_or_fetch(tile, day, inv, shed)
        if action is None:
            action = _plot_action(tile, day, crop)
        if action[0] == "PLANT":
            # Only plant as many of `crop` this turn as we hold seed for, or
            # the sim's atomic-plant rule voids every plant of the crop at once.
            planted_crop = action[1]
            if planted_this_turn.get(planted_crop, 0) < seeds.get(planted_crop, 0):
                planted_this_turn[planted_crop] = planted_this_turn.get(planted_crop, 0) + 1
            else:
                action = ["WATER"] if _is_live_plant(tile) else ["PASS"]
        actions.append(action)
```

Replace the seed-accounting block. Delete:

```python
        active_plots = min(n_crop, len(CROP_PLOTS))
        empty_active = sum(
            1 for plot in CROP_PLOTS[:active_plots] if _tile_at(tiles, plot) is None
        )
```

and put in its place:

```python
        # Count the tiles workers are actually assigned to, not a prefix of
        # CROP_PLOTS: assignment decides who farms what, so it also decides
        # how much seed this turn needs.
        empty_active = sum(
            1 for j in assignment
            if j is not None and j.kind in ("CROP", "FERTILIZE")
            and _tile_at(tiles, j.pos) is None
        )
```

- [ ] **Step 4: Delete the now-dead livestock-crew helpers**

Nothing calls `_assign_beats` or `_livestock_worker_action` any more — assignment hands out one tile at a time, so there is no beat to split or walk. Delete both functions from `strategies/neuropilot.py`, and delete the tests inventoried in Task 4 Step 1 that call them. Their guarantees are already re-asserted by the `_animal_job_action` tests.

Confirm nothing is left referencing them:

```bash
grep -rn "_assign_beats\|_livestock_worker_action" strategies/ tests/ harness/
```

Expected: no output.

- [ ] **Step 5: Run the new tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_neuropilot.py -k controller -v`
Expected: PASS (6 tests)

- [ ] **Step 6: Run the full suite under strict mode**

Run: `ROBRICULTURE_STRICT=1 .venv/bin/python -m pytest -q`

Expected: `tests/test_neuropilot.py` and `tests/test_no_crash.py` **pass**; `tests/test_champion_genome_regression.py` **fails**.

That failure is expected and is the whole risk this design flagged: `livestock_labor_share` and `fertilize_pref` now mean something different, so the shipped weights are being read differently. Do **not** touch `GOLDEN_ACTIONS` here — Task 6 handles it, and re-blessing before re-benchmarking is exactly the #100 failure the guard exists to catch.

If `test_no_crash.py` fails, that is a real bug — an illegal or malformed action reached the sim. Fix it before continuing; do not proceed to Task 6 with the no-crash gate red.

- [ ] **Step 7: Check coverage**

Run: `.venv/bin/python -m pytest -q --cov --cov-branch --cov-report=term-missing --ignore=tests/test_champion_genome_regression.py`
Expected: line >= 85%, branch >= 65%. If a new branch is uncovered, add the test rather than a pragma.

- [ ] **Step 8: Commit**

```bash
git add strategies/neuropilot.py tests/test_neuropilot.py
git commit -m "feat(neuropilot): assign workers to jobs instead of plot indices (#71)"
```

Note in the commit body that `test_champion_genome_regression.py` is knowingly red pending Task 6's re-benchmark.

---

### Task 6: Re-benchmark the baked genome, then re-bless the guard

The guard is red with the genome file unchanged. Its own docstring calls that the **illegitimate** case for editing `GOLDEN_ACTIONS` — unless you first measure what the change did to the shipped agent and record the number. That measurement is the deliverable here; updating the goldens is a side effect of it.

**Files:**
- Modify: `tests/test_champion_genome_regression.py` — `GOLDEN_ACTIONS` only
- Modify: `strategies/champion_genome.json` — `meta` only, if the share moved

**Interfaces:**
- Consumes: `strategies/champion_genome.json` (unchanged weights), the Task 5 controller
- Produces: a recorded post-change share for #71's writeup

- [ ] **Step 1: Re-benchmark the shipped genome under the new controller**

```bash
.venv/bin/python -m harness.genome_bench --genome strategies/champion_genome.json --games 4
```

Expected runtime ~25 s. Record the `TOTAL ... share=` figure. **Baseline to compare against: 0.3760.**

- [ ] **Step 2: Judge the result before touching anything**

- **Share held or improved (>= ~0.37):** the reinterpretation was benign. Continue to Step 3.
- **Share dropped materially (say below 0.34):** the controller change degraded the shipped agent. That is information, not a blocker — the genome was evolved against the *old* knob meanings, so some drop is expected and Task 8's fresh evolution is the real test. Record the number, note it in the commit and in #71, and continue. Do not tune the controller to rescue an obsolete genome's score.
- **Share collapsed (below ~0.20, i.e. near the #110 regression level):** stop and investigate. A collapse that large usually means a wiring bug, not a reinterpretation — check that animal jobs are reachable and that workers are not all being assigned to a single quadrant.

- [ ] **Step 3: Regenerate the golden actions**

```bash
.venv/bin/python - <<'PY'
import tests.test_champion_genome_regression as t
for name in t._SCENARIOS:
    print(repr(name), ":", repr(t._ACT(name)), ",")
PY
```

If `_ACT` / `_SCENARIOS` are named differently, read the file — it documents its own re-blessing procedure near the top. Paste the output into `GOLDEN_ACTIONS`.

- [ ] **Step 4: Record why the goldens moved**

Add to the `GOLDEN_ACTIONS` re-blessing docstring, under the "Legitimate reasons" list:

```
  - #71 reinterpreted two knobs (`livestock_labor_share` -> animal-job
    weight, `fertilize_pref` -> fertilize-job weight) and replaced the
    worker-index plot mapping with job assignment. The shipped weights are
    unchanged but are now read differently, so the actions moved by design.
    Re-benchmarked before re-blessing: share <RECORDED> against a 0.3760
    baseline.
```

Replace `<RECORDED>` with Step 1's actual number.

- [ ] **Step 5: Update the genome's recorded share if it moved**

If Step 1's share differs from 0.376, add to `strategies/champion_genome.json`'s `meta` (do not edit `share`, which records what it scored when promoted):

```json
"share_under_71": <RECORDED>,
"share_under_71_note": "Re-measured after #71 reinterpreted livestock_labor_share and fertilize_pref as job-value weights. These weights were evolved against the old knob meanings; #71's own evolution run supersedes this figure."
```

- [ ] **Step 6: Run the full suite**

Run: `ROBRICULTURE_STRICT=1 .venv/bin/python -m pytest -q`
Expected: PASS, everything green including the regression guard.

- [ ] **Step 7: Commit**

```bash
git add tests/test_champion_genome_regression.py strategies/champion_genome.json
git commit -m "test: re-bless the champion guard after #71's knob reinterpretation"
```

Put the measured share in the commit body.

---

### Task 7: Multi-seed evaluation harness

One evolution run is one sample. #113 treated a single run's "it didn't buy land" as a verdict on the whole hypothesis. At ~1.2 s/game a default run costs ~3 hours serially, but this box scales near-linearly (12 concurrent jobs measured at ~11x throughput on 2026-08-22), so ten seeds cost roughly the same wall time as one. Report a **rate**, not an anecdote.

**Files:**
- Create: `harness/multi_seed.py`
- Test: `tests/test_multi_seed.py`

**Interfaces:**
- Consumes: `harness.evolve.evolve`, `harness.evolve.genome_agent`, `harness.genome_bench.benchmark_genome`, `harness.production_report.report_game` / `resolve_agent`
- Produces: `MIN_PLANTS_PEAK = 15`, `seed_verdict(row) -> bool`, `summarize_seeds(rows) -> dict`, `run_seed(seed, settings) -> dict` (integration, `# pragma: no cover`), `main(argv)` (`# pragma: no cover`)

A `row` is `{"seed": int, "share": float, "plants_peak": int, "land_purchases": list, "animals_peak": int, "hands_peak": int, "reward": float}`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_multi_seed.py`:

```python
"""Multi-seed experiment evaluation (#71)."""
from __future__ import annotations

from harness import multi_seed as ms


def _row(seed=0, share=0.4, plants_peak=20, land_purchases=(("NE", 12, 5000),)):
    return {"seed": seed, "share": share, "plants_peak": plants_peak,
            "land_purchases": list(land_purchases), "animals_peak": 0,
            "hands_peak": 9, "reward": 25000.0}


def test_seed_verdict_true_when_land_bought_and_enough_tiles_planted():
    assert ms.seed_verdict(_row()) is True


def test_seed_verdict_false_when_no_land_was_bought():
    # #113's outcome: the genome farmed fine but never expanded.
    assert ms.seed_verdict(_row(land_purchases=())) is False


def test_seed_verdict_false_when_planted_tiles_stay_under_the_bar():
    # 11 is the ceiling every agent we own already hits, so it proves nothing.
    assert ms.seed_verdict(_row(plants_peak=11)) is False


def test_seed_verdict_true_exactly_at_the_bar():
    assert ms.seed_verdict(_row(plants_peak=ms.MIN_PLANTS_PEAK)) is True


def test_summarize_seeds_reports_the_success_rate():
    rows = [_row(seed=0), _row(seed=1, land_purchases=()), _row(seed=2)]
    got = ms.summarize_seeds(rows)
    assert got["n"] == 3
    assert got["n_supported"] == 2
    assert got["rate"] == 2 / 3


def test_summarize_seeds_reports_share_spread():
    rows = [_row(seed=0, share=0.30), _row(seed=1, share=0.50)]
    got = ms.summarize_seeds(rows)
    assert got["share_mean"] == 0.40
    assert got["share_max"] == 0.50
    assert got["share_min"] == 0.30


def test_summarize_seeds_reports_the_best_planted_count():
    rows = [_row(seed=0, plants_peak=12), _row(seed=1, plants_peak=31)]
    assert ms.summarize_seeds(rows)["plants_peak_max"] == 31


def test_summarize_seeds_handles_no_rows():
    # A run where every seed crashed must report emptiness, not divide by zero.
    got = ms.summarize_seeds([])
    assert got["n"] == 0 and got["rate"] == 0.0
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_multi_seed.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'harness.multi_seed'`

- [ ] **Step 3: Write the implementation**

Create `harness/multi_seed.py`:

```python
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


def seed_verdict(row) -> bool:
    """Did this seed's genome both buy land and farm it?

    Both halves are required. Buying land without farming it is #113's
    result restated; planting 15 tiles without buying land is impossible
    (NW holds 25 tiles but the hire ceiling caps workers at 10), so the
    conjunction is what makes the claim non-trivial.
    """
    return bool(row["land_purchases"]) and row["plants_peak"] >= MIN_PLANTS_PEAK


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
          f"min {summary['share_min']:.4f}  max {summary['share_max']:.4f}")

    if args.out:
        with open(args.out, "w") as fh:
            json.dump({"settings": settings, "rows": rows, "summary": summary}, fh, indent=2)
        print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_multi_seed.py -v`
Expected: PASS (8 tests)

- [ ] **Step 5: Smoke-test the CLI end to end at a tiny size**

```bash
.venv/bin/python -m harness.multi_seed --seeds 2 --workers 2 --generations 1 --pop 4 --games 1 --sample-k 2 --hof-cap 0 --bench-games 1
```

Expected: ~60 s, two `seed N:` lines and a summary. The verdicts will be "not supported" (one generation of a random population plants nothing) — you are checking that it runs, parallelises, and prints, not that it succeeds.

If `ProcessPoolExecutor` workers fail to start, check that `run_seed` and `settings` contain only picklable data — genome lists and dicts are fine; agent callables are not, which is why agents are rebuilt inside the worker.

- [ ] **Step 6: Run the full suite and check coverage**

Run: `ROBRICULTURE_STRICT=1 .venv/bin/python -m pytest -q && .venv/bin/python -m pytest -q --cov --cov-branch --cov-report=term-missing`
Expected: all green, line >= 85%, branch >= 65%.

- [ ] **Step 7: Commit**

```bash
git add harness/multi_seed.py tests/test_multi_seed.py
git commit -m "feat(harness): multi-seed experiment evaluation (#71)"
```

---

### Task 8: Run the experiment and record the verdict

**Files:**
- Create: `harness/genomes/71-multi-seed.json` (gitignored output — do not commit)
- Modify: `strategies/champion_genome.json` **only if** a seed's genome beats the current champion's share
- Modify: `docs/superpowers/plans/2026-08-22-job-assignment.md` (this file) — nothing; the record goes in the issue

**Interfaces:**
- Consumes: everything above
- Produces: the (N, rate, share) record for issue #71

- [ ] **Step 1: Launch the multi-seed run**

```bash
nohup .venv/bin/python -m harness.multi_seed --seeds 10 --workers 10 --out harness/genomes/71-multi-seed.json > /tmp/71-multi-seed.log 2>&1 &
```

Expected wall time ~3-3.5 hours (10 default runs, 10 lanes). Poll with `tail -f /tmp/71-multi-seed.log`.

**If you are a subagent:** run this **blocking** — `nohup ... & wait $!` — not backgrounded. A backgrounded job is lost at a subagent's turn boundary with no notification.

- [ ] **Step 2: Read the summary against the hypothesis**

The hypothesis from the spec: *a seeded evolution run produces a genome that buys land and farms it — non-zero confirmed `land_purchases` and a peak planted-tile count of at least 15 — and whose `genome_bench` share exceeds the baseline.*

Multi-seed makes that a rate. Read it as:

**The bar is 0.3760, not Task 6's 0.3390.** Task 6 measured the *shipped* weights under the new controller and got 0.3390 — that is what our old genome does after its knobs were reinterpreted, not a standard to clear. Beating 0.3390 only recovers ground this branch itself gave up. A fresh genome has to beat **0.3760**, what we actually shipped before any of this, to be a real improvement. Quote both numbers in the writeup so the distinction cannot be lost.

- **rate >= 0.5 and `share_max` > 0.3760** — supported. Assignment unlocks the land.
- **rate between 0.1 and 0.5** — partially supported, and the interesting case. Assignment makes expansion *reachable* but not *reliable*; that points squarely at job valuation (#119), since crude values are exactly what would make the outcome seed-dependent. Say so plainly rather than rounding it up or down.
- **rate == 0** — a significant negative. The constraint is neither affordability (#100), nor routability (#113), nor assignment (#71). Record it as such: it makes #119 the next candidate and reopens the possibility that something not yet identified is the binding constraint.

- [ ] **Step 3: Record the result in the issue**

`harness/genomes/` is gitignored, so the issue is the durable record (ADR-0007: the issue is the lab notebook). Post a comment on #71 with:

- the exact command from Step 1
- the summary block (N seeds, rate, land-buying seeds, best planted tiles, share mean/min/max)
- Task 6's re-benchmarked baseline for comparison
- the per-seed table
- a one-paragraph root-cause reading: **why** it went the way it did, not just that it did

- [ ] **Step 4: Promote a genome only if it clears the bar**

`multi_seed` writes no per-seed genome files — every genome is a `rows[*].genome` list inside the `--out` JSON. Extract the winner into a genome artifact, substituting the winning seed number:

```bash
.venv/bin/python - <<'PY'
import json
WINNING_SEED = 0            # <- set to the seed with the best share
data = json.load(open("harness/genomes/71-multi-seed.json"))
row = next(r for r in data["rows"] if r["seed"] == WINNING_SEED)
out = {"genome": row["genome"],
       "meta": {"issue": 71, "share": row["share"], "seed": WINNING_SEED,
                "plants_peak": row["plants_peak"],
                "land_purchases": row["land_purchases"],
                "run": data["settings"]}}
json.dump(out, open("harness/genomes/71-winner.json", "w"), indent=2)
print("share", row["share"], "plants_peak", row["plants_peak"])
PY
cp harness/genomes/71-winner.json strategies/champion_genome.json
.venv/bin/python -m harness.genome_bench --genome strategies/champion_genome.json --games 4
```

The `genome_bench` figure must reproduce the recorded `share` — if it does not, the extraction grabbed the wrong row. Fix that before promoting.

Then fill out its `meta` to match the shape of the block it replaces — `issue`, `promoted` (today's date), `criterion` (`"genome_bench share vs the 5 fixed anchors, --games 4"`), `share`, `win_rate`, `run`, `run_note`, and `supersedes` (the previous champion's source and share). Re-bless `GOLDEN_ACTIONS` — a genome change is the guard's own *legitimate* re-blessing case — then run the full suite.

If no seed clears the bar, **do not promote**. The mechanism can still merge on green tests as an engine change; the strategy claim simply is not supported yet, and saying so is the point of the protocol.

- [ ] **Step 5: Full green gate before the PR**

```bash
ROBRICULTURE_STRICT=1 .venv/bin/python -m pytest -q
.venv/bin/python -m pytest -q --cov --cov-branch --cov-report=term-missing
```

Expected: all green, line >= 85%, branch >= 65%.

- [ ] **Step 6: Commit and open the PR**

```bash
git add strategies/champion_genome.json tests/test_champion_genome_regression.py
git commit -m "feat(neuropilot): promote the #71 job-assignment genome"
git push -u origin 71-job-assignment
gh pr create --title "Job-based worker assignment (#71)" --body "..."
```

Skip the first two commands if nothing was promoted. The PR body must carry the multi-seed numbers, the re-benchmarked baseline, and the verdict — a reviewer should not have to open the issue to see whether the hypothesis held.

**Stop at the PR.** It is reviewed, never auto-merged.

---

## Outcome handling (ADR-0007)

This branch mixes two tracks, and they merge on different rules:

- **Tasks 1-7 are engine/correctness work** — job enumeration, assignment, the per-tile animal handler, the multi-seed harness. Validated by green tests plus the no-crash gate. These merge on a normal green PR whichever way the experiment goes.
- **Task 8's promotion is a strategy claim** — it merges only if the numbers support it.

So a rejected hypothesis does **not** mean discarding the branch here. If the multi-seed run comes back at rate 0, open the PR with the mechanism and the honest negative result, and let the promotion be the only thing dropped. That is the salvage step ADR-0007 requires, done up front rather than after the fact.
