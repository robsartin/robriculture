# meta_rancher Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `meta_rancher`, a tuned contender version of the frozen `meta_bot` meta-comp benchmark, that improves on four known weaknesses and passes the ADR-0007 promotion gate — a ladder-submission candidate.

**Architecture:** A standalone `strategies/meta_rancher.py` (`benchmark = False`) that forks `meta_bot`'s structure. It reuses the same stable primitives from `ranch_hands`/`hired_hands`/`fertilized_hands`/`catch_hands`/`wide_hands`/`kaggisim` that `meta_bot` reuses, and re-implements the meta-specific logic — most of which it *tunes*. It does NOT import or modify `meta_bot` (which is frozen by a pin test); the small amount of unchanged helper code it re-declares is deliberate lifecycle isolation (frozen benchmark vs evolving contender). Decisions live in pure helpers; `act()` is thin.

**Tech Stack:** Python 3.12 (3.11 floor), `pytest` (+ `--cov --cov-branch`), `kaggle_environments` kaggriculture sim. No new deps.

**The template:** `strategies/meta_bot.py` (539 lines, on `main`) is the structural base. Read it first — every task below is expressed as a change *relative to* that file's helpers. Four tuning targets, each its own task, each a measurable improvement over `meta_bot`.

## Global Constraints

- **Python floor 3.11**; CI runs 3.12; develop with `ROBRICULTURE_STRICT=1` (surface bugs instead of the fail-safe PASS).
- **Adding a strategy = dropping `strategies/meta_rancher.py` + `tests/test_meta_rancher.py` only.** Do NOT edit `strategies/__init__.py` (auto-discovery). `name = "meta_rancher"`, `benchmark = False`, `STRATEGY = MetaRancherStrategy`.
- **Do NOT import or modify `strategies/meta_bot.py`.** It is frozen (pin test). `meta_rancher` is standalone; re-declaring the few unchanged meta-comp helpers is intentional (spec: lifecycle isolation).
- **All decisions in pure module-level helpers** (unit-testable without a 720-turn game); `act()` only wires helpers + clamps `market[:10]`.
- **Market-order cap = 10/turn; sells ordered first** so they are never truncated.
- **Coverage gate:** line ≥ 85%, branch ≥ 65% (bare `pytest --cov --cov-branch`). `# pragma: no cover` only on integration entrypoints (`main()`/live loops), never pure helpers.
- **CI is a bare `pytest`** (root `conftest.py` supplies the path). Tests pristine (no warnings).
- **Run from repo root, venv active** (`source .venv/bin/activate`; Homebrew python3.12).
- **The ANIMAL_TILES / land / cost constants are the Phase-0 values** (identical to `meta_bot`): `N_COW=9`, `N_SHEEP=4`, NE 3×3 cow block `(5..7, 0..2)`, SW sheep row `(0..3, 5)`, `LAND_PRICES=[1000,2000,4000]`, `ANIMAL_COST={"COW":400,"SHEEP":500}`.

---

## File Structure

- `strategies/meta_rancher.py` — **create.** The tuned contender. Forks meta_bot's helper set; tunes feed/care routing, hiring, seed-restock, and the labor split.
- `tests/test_meta_rancher.py` — **create.** Pure-helper unit tests for each tuned behavior + the composition/shape tests.
- No other files change. (The gate in Task 5 runs the existing `harness/promotion.py`; results are recorded on issue #61, not in code.)

---

### Task 1: `meta_rancher` baseline contender (fork + extract seed-restock)

Create a working contender that behaves like `meta_bot` but (a) is a contender (`benchmark = False`), and (b) folds in tuning target #3 — the seed-restock logic extracted from `act()` into a pure helper. This is the baseline the later tuning tasks improve on.

**Files:**
- Create: `strategies/meta_rancher.py`
- Test: `tests/test_meta_rancher.py`
- Read as template: `strategies/meta_bot.py` (fork its helpers verbatim EXCEPT the changes below)

**Interfaces:**
- Produces: `strategies.meta_rancher.STRATEGY` = `MetaRancherStrategy` (`name="meta_rancher"`, `benchmark=False`); the full meta-comp helper set forked from meta_bot (`land_orders`, `animal_buy_orders`, `fertilizer_orders`, `_sell_orders_keep_feed`, `wheat_orders`, `melon_plot_for`, `beat_active`, `animal_chore`, `livestock_action`, predicates, and the Phase-0 constants); PLUS a new pure helper `seed_restock_orders(tiles, seeds, melon_open, catch, n_workers, money, market_len) -> list` holding the logic currently inline in `meta_bot.act()` lines 495-510.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_meta_rancher.py
"""meta_rancher — tuned contender sibling of the frozen meta_bot benchmark (#61)."""

from __future__ import annotations

from strategies import meta_rancher as mr


def test_meta_rancher_is_a_contender_not_a_benchmark():
    assert mr.STRATEGY.benchmark is False
    assert mr.STRATEGY.name == "meta_rancher"


def test_composition_matches_the_phase0_comp():
    cows = [t for t in mr.ANIMAL_TILES if t[1] == "COW"]
    sheep = [t for t in mr.ANIMAL_TILES if t[1] == "SHEEP"]
    assert len(cows) == mr.N_COW == 9
    assert len(sheep) == mr.N_SHEEP == 4
    assert len({t[0] for t in mr.ANIMAL_TILES}) == len(mr.ANIMAL_TILES)


def test_seed_restock_orders_buys_melon_seed_for_empty_active_plots():
    # Extracted from act(): an empty active melon plot with no seed on hand and
    # money to spare yields a BUY_SEED MELON order.
    tiles = [[None for _ in range(10)] for _ in range(10)]
    orders = mr.seed_restock_orders(
        tiles=tiles, seeds={}, melon_open=True, catch=None,
        n_workers=3, money=100000, market_len=0,
    )
    assert ["BUY_SEED", "MELON", 3] in orders


def test_seed_restock_orders_respects_the_market_cap():
    tiles = [[None for _ in range(10)] for _ in range(10)]
    orders = mr.seed_restock_orders(
        tiles=tiles, seeds={}, melon_open=True, catch=None,
        n_workers=3, money=100000, market_len=10,
    )
    assert orders == []
```

- [ ] **Step 2: Run to verify they fail**

Run: `ROBRICULTURE_STRICT=1 pytest tests/test_meta_rancher.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'strategies.meta_rancher'`.

- [ ] **Step 3: Implement `strategies/meta_rancher.py`**

Fork `strategies/meta_bot.py` into `strategies/meta_rancher.py` with these exact changes, leaving all other helpers behaviorally identical:
1. Class: `class MetaRancherStrategy(Strategy)`, `name = "meta_rancher"`, `benchmark = False`; `STRATEGY = MetaRancherStrategy`.
2. Module docstring: state this is the tuned *contender* sibling of the frozen `meta_bot` (per #61), NOT a benchmark; note it must not import meta_bot (freeze isolation).
3. Extract the seed-restock block (meta_bot.py:495-510) into a pure helper:
```python
def seed_restock_orders(tiles, seeds, melon_open, catch, n_workers, money, market_len):
    """Seed BUY orders to keep active plots plantable — melon in the melon phase,
    the catch crop in the tail. Buys only the affordable shortfall for the plots a
    present worker can reach, never exceeding the 10-order market cap."""
    restock = MELON if melon_open else catch
    if restock is None or market_len >= 10:
        return []
    active_plots = min(len(MELON_PLOTS), n_workers)
    empty_active = sum(1 for plot in MELON_PLOTS[:active_plots] if hh.tile_at(tiles, plot) is None)
    if empty_active <= 0:
        return []
    want_seed = max(0, empty_active - seeds.get(restock, 0))
    if want_seed <= 0:
        return []
    affordable = int(money // CROPS[restock]["seed"])
    buy = min(want_seed, affordable, 10 - market_len)
    return [["BUY_SEED", restock, buy]] if buy > 0 else []
```
   and call it from `act()` in place of the inline block: `market.extend(seed_restock_orders(tiles, seeds, melon_open, catch, total_workers, money, len(market)))`.

- [ ] **Step 4: Run the helper tests to verify they pass**

Run: `ROBRICULTURE_STRICT=1 pytest tests/test_meta_rancher.py -v`
Expected: PASS.

- [ ] **Step 5: No-crash gate + baseline signal**

Run: `ROBRICULTURE_STRICT=1 pytest tests/test_no_crash.py -v` — Expected: PASS (meta_rancher stands up under full games).
Then capture a baseline (report the numbers, do not assert): a 3-seed head-to-head of `meta_rancher` vs `meta_bot` and vs `market_farmer` using the same in-process game runner the promotion harness uses (`from harness.tournament import build_agents, play`). This confirms the fork is viable before tuning and gives the tuning tasks a reference.

- [ ] **Step 6: Commit**

```bash
git add strategies/meta_rancher.py tests/test_meta_rancher.py
git commit -m "feat: meta_rancher baseline contender (fork of meta_bot, seed-restock extracted) (#61)"
```

---

### Task 2: Tuning target #1 — eliminate late-game animal escapes

`meta_bot` loses ~2/13 animals near the buzzer to feed/care routing gaps. Make `meta_rancher` keep the whole herd fed through the final day.

**Files:**
- Modify: `strategies/meta_rancher.py` (`livestock_action` / `animal_chore` / a new prioritization helper)
- Test: `tests/test_meta_rancher.py`

**Interfaces:**
- Produces: revised `livestock_action` that prioritizes the MOST at-risk animal (fewest days of feed left / already unfed) when a hand cannot feed its whole beat in one turn; a pure helper `most_at_risk(beat, tiles) -> tile_pos | None` returning the hungriest placed animal in a beat (an animal unfed today, ordered so the one closest to the 2-unfed-days escape threshold is first).

- [ ] **Step 1: Write the failing test**

```python
def test_most_at_risk_returns_the_hungriest_animal_first():
    # Two placed cows in a beat; one already went a day unfed (fed_today False and
    # a low/again-unfed marker), the other fed. The at-risk one is returned.
    tiles = [[None for _ in range(10)] for _ in range(10)]
    a, b = (5, 0), (6, 0)
    tiles[a[0]][a[1]] = {"kind": "PASTURE", "animal": "COW", "fed_today": False}
    tiles[b[0]][b[1]] = {"kind": "PASTURE", "animal": "COW", "fed_today": True}
    beat = [(a, "COW"), (b, "COW")]
    assert mr.most_at_risk(beat, tiles) == a


def test_most_at_risk_none_when_all_fed():
    tiles = [[None for _ in range(10)] for _ in range(10)]
    a = (5, 0)
    tiles[a[0]][a[1]] = {"kind": "PASTURE", "animal": "COW", "fed_today": True}
    assert mr.most_at_risk([(a, "COW")], tiles) is None
```

- [ ] **Step 2: Run to verify it fails**

Run: `ROBRICULTURE_STRICT=1 pytest tests/test_meta_rancher.py::test_most_at_risk_returns_the_hungriest_animal_first -v`
Expected: FAIL — `AttributeError: module 'strategies.meta_rancher' has no attribute 'most_at_risk'`.

- [ ] **Step 3: Implement the prioritization**

Add `most_at_risk(beat, tiles)` (return the hungriest placed, unfed animal in the beat, or None) and use it in `livestock_action`'s feed branch so, when the hand holds feed but cannot reach all hungry animals this turn, it heads to the most-at-risk one first. Keep the shed-load-the-whole-beat logic. If a single hand still cannot keep its beat alive in the end-game, also allow an idle non-livestock worker (its melon plot closed) to be reassigned to the nearest hungry beat — but only add that if the escape persists (verify in Step 4 before adding; YAGNI otherwise).

- [ ] **Step 4: Verify the escape is gone**

Run the helper tests (PASS), then measure: play 3 seeded full games of `meta_rancher` vs `starter` and count placed-animals-surviving-to-the-final-step (reuse the in-process runner; inspect `env.steps[-1]` farm tiles). Report the survivor count — target 13/13 (or a clear improvement over meta_bot's 11/13). Record the numbers in the commit body.

- [ ] **Step 5: Commit**

```bash
git add strategies/meta_rancher.py tests/test_meta_rancher.py
git commit -m "feat(meta_rancher): keep the whole herd fed to the buzzer (tuning #1) (#61)"
```

---

### Task 3: Tuning target #2 — hire never displaces a sell or herd-critical buy

`meta_bot` forces `n_hire = MAX_HANDS` once the herd exists, which on a heavy-sell morning can consume market slots that should carry sells / land / animal buys (the 10-cap truncates the tail). Reorder so hiring yields to the price-sensitive and herd-critical orders.

**Files:**
- Modify: `strategies/meta_rancher.py` (`act()` market assembly + a helper)
- Test: `tests/test_meta_rancher.py`

**Interfaces:**
- Produces: a pure helper `hire_orders(n_target, market_len, reserved) -> list` returning `[["HIRE"]] * k` where `k` is bounded so hires never push the total past `10 - reserved` (slots reserved for herd-critical land/animal buys this turn). `act()` assembles the market as: sells → seed/fertilizer/wheat/land/animal (herd-critical) → hires last with whatever slots remain, so a heavy-sell morning keeps all sells and the herd buys, deferring only surplus hires to the next morning.

- [ ] **Step 1: Write the failing test**

```python
def test_hire_orders_never_exceed_the_remaining_cap():
    # 8 orders already queued (e.g. sells + buys); at most 2 hire slots remain.
    assert mr.hire_orders(n_target=9, market_len=8, reserved=0) == [["HIRE"], ["HIRE"]]


def test_hire_orders_yield_slots_reserved_for_herd_buys():
    # 5 orders queued, but reserve 3 slots for land/animal buys -> only 2 hires.
    assert mr.hire_orders(n_target=9, market_len=5, reserved=3) == [["HIRE"], ["HIRE"]]


def test_hire_orders_empty_when_no_slots():
    assert mr.hire_orders(n_target=9, market_len=10, reserved=0) == []
```

- [ ] **Step 2: Run to verify it fails**

Run: `ROBRICULTURE_STRICT=1 pytest tests/test_meta_rancher.py -k hire_orders -v`
Expected: FAIL — `hire_orders` undefined.

- [ ] **Step 3: Implement**

Add `hire_orders(n_target, market_len, reserved)` (return `[["HIRE"]] * max(0, min(n_target, 10 - market_len - reserved))`). Restructure `act()`'s market assembly so hires are appended LAST (after sells, seed, fertilizer, wheat, land, animals), sized by `hire_orders` against the remaining cap. Preserve the "once the herd exists, target the full crew" intent — but as a *target* that yields slots this turn and catches up next morning, never truncating a sell or a herd buy. Note: hiring still only happens at `hour == 0`.

- [ ] **Step 4: Verify**

Helper tests PASS. Then a focused end-to-end check: construct a fresh-dawn obs with a full shed (many sell orders) once the herd exists, call `act()`, and assert every `SELL` and every herd-critical `BUY_LAND`/`BUY_ANIMAL` that would be emitted is present in `market[:10]` (i.e. none dropped by hiring). Add that as a test.

- [ ] **Step 5: Commit**

```bash
git add strategies/meta_rancher.py tests/test_meta_rancher.py
git commit -m "feat(meta_rancher): hires yield market slots to sells + herd buys (tuning #2) (#61)"
```

---

### Task 4: Tuning target #4 — tune the melon-vs-livestock labor split

`meta_bot` fixes `LIVESTOCK_INDICES = (5,6,7,8,9)` (5 hands) and a fixed beat partition. Revisit the split so melon income and herd upkeep are balanced for maximum bank, using the actual survivor + bank measurements from Tasks 2-3 as the guide.

**Files:**
- Modify: `strategies/meta_rancher.py` (the `LIVESTOCK_INDICES` / `BEATS` construction, ideally into a small pure builder)
- Test: `tests/test_meta_rancher.py`

**Interfaces:**
- Produces: a pure helper `build_beats(cow_tiles, sheep_tiles, livestock_indices) -> dict` that partitions the herd into contiguous per-hand beats (the current hard-coded `BEATS` becomes its output), so the split is data-driven and testable; `LIVESTOCK_INDICES` chosen by measured bank (keep 5 unless a different count measurably banks more with 13/13 survival).

- [ ] **Step 1: Write the failing test**

```python
def test_build_beats_partitions_every_animal_into_contiguous_beats():
    cows = [(5, 0), (6, 0), (7, 0)]
    sheep = [(0, 5), (1, 5)]
    beats = mr.build_beats(cows, sheep, livestock_indices=(8, 9))
    covered = [tp for b in beats.values() for tp, _ in b]
    assert sorted(covered) == sorted(cows + sheep)          # every animal covered once
    assert set(beats) <= {8, 9}                             # only livestock indices get beats
```

- [ ] **Step 2: Run to verify it fails**

Run: `ROBRICULTURE_STRICT=1 pytest tests/test_meta_rancher.py -k build_beats -v`
Expected: FAIL — `build_beats` undefined.

- [ ] **Step 3: Implement + tune**

Add `build_beats(...)` and derive `BEATS`/`LIVESTOCK_INDICES` through it. Then measure: for the candidate split(s) (start with the current 5 hands, and at least one alternative — e.g. 4 or 6 livestock hands), run 3-5 seeded `meta_rancher` vs `meta_bot` games and pick the split with the higher mean bank AND 13/13 survival. Keep the current split if nothing beats it (YAGNI). Record the measured comparison in the commit body.

- [ ] **Step 4: Verify**

Helper tests PASS; no-crash gate PASS (`ROBRICULTURE_STRICT=1 pytest tests/test_no_crash.py`).

- [ ] **Step 5: Commit**

```bash
git add strategies/meta_rancher.py tests/test_meta_rancher.py
git commit -m "feat(meta_rancher): data-driven, tuned labor split (tuning #4) (#61)"
```

---

### Task 5: The ADR-0007 gate + full CI + record on #61

Run the promotion gate and the reference matches, verify the full CI gate, and record the numbers. This task's deliverable is the recorded result (and a green CI), not new production code.

**Files:**
- No production code. Results recorded as a comment on issue #61 (the controller posts it) and summarized in the report.

- [ ] **Step 1: Full CI gate**

Run from repo root, venv active:
```bash
pytest -q --cov --cov-branch --cov-report=term-missing
```
Expected: all PASS; line ≥ 85%, branch ≥ 65%. Report the numbers verbatim. If meta_rancher's `act()` integration lines are the only gap, confirm the no-crash gate exercises them; `# pragma: no cover` only genuine integration entrypoints, never helpers.

- [ ] **Step 2: The promotion gate (foreground, verbatim)**

```bash
python -m harness.promotion meta_rancher --champion market_farmer --games 200
```
Record wins/losses/ties, win-rate, binomial p, PROMOTE/REJECT. (ADR-0007: promote iff win-rate ≥ 55% AND p < 0.05.)

- [ ] **Step 3: Reference matches (foreground, verbatim)**

```bash
python -m harness.promotion meta_rancher --champion meta_bot --games 200
python -m harness.promotion meta_rancher --champion ranch_hands --games 200
```
Record both. The `meta_bot` number is the key signal (tuned contender vs the frozen field-proxy).

- [ ] **Step 4: Write the results to the report file**

Write all four results (CI coverage + the three 200-game matches) verbatim into the task report so the controller can post them to issue #61 and decide PROMOTE/REJECT per ADR-0007. Do NOT post to GitHub yourself.

- [ ] **Step 5: No commit** (results are recorded on the issue by the controller; CI verification produced no code change). If any `# pragma: no cover` was genuinely needed on an integration entrypoint, commit only that one-line change with message `test(meta_rancher): mark act() integration entrypoint no-cover (#61)`.

---

## Self-Review

**Spec coverage:**
- Standalone file, meta_bot untouched → Task 1 (constraint restated in every task). ✅
- Tuning #1 late-game escapes → Task 2. ✅
- Tuning #2 hire-slot contention → Task 3. ✅
- Tuning #3 seed-restock extraction → folded into Task 1 (structural, needed for the baseline). ✅
- Tuning #4 labor split → Task 4. ✅
- ADR-0007 gate vs champion + report vs meta_bot & ranch_hands → Task 5. ✅
- No `__init__.py` edit; benchmark=False; sells-first; market[:10] → Global Constraints + Task 1. ✅
- Submission is Rob's (out of plan scope) → noted in spec; plan ends at the recorded gate result. ✅

**Placeholder scan:** Task 1 references `meta_bot.py` as a fork template rather than re-inlining 539 lines — a legitimate "adapt this existing file with these specific diffs" instruction, with the one genuinely-new helper (`seed_restock_orders`) given in full and every task's tuned helper specified by signature + tests. The measurement steps (survivor counts, bank comparisons) are report-and-decide, not vague requirements. No TBD/TODO.

**Type consistency:** `seed_restock_orders`, `most_at_risk`, `hire_orders`, `build_beats` signatures are defined once and used consistently. Constants (`N_COW`, `N_SHEEP`, `ANIMAL_TILES`, `MELON_PLOTS`, `CROPS`) match meta_bot's names (forked verbatim).

**Note for reviewers (justified, plan-mandated):** the unchanged meta-comp helpers `meta_rancher` re-declares are verbatim-similar to `meta_bot`'s by design (spec: frozen-vs-evolving lifecycle isolation; Rob chose standalone over sharing). This duplication is intentional, not a defect to fix.
