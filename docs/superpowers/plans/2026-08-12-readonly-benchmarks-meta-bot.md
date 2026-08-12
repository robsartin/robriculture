# Readonly Benchmark Opponents + meta_bot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add "readonly" benchmark opponents to the harness — strategies always in the tournament/promotion opponent pool but never eligible to be champion — and ship the first one, `meta_bot`, frozen to the observed top-Elo Kaggriculture comp.

**Architecture:** A `benchmark = True` class flag on `Strategy` (default `False`). The registry auto-discovers it and records which names are benchmarks (`BENCHMARKS`). Both champion-selection paths (`harness/promotion.py` designate + `harness/rounds.py` windowed) pick the top-ranked *non-benchmark* label, so `champion.json` can never name a benchmark. `meta_bot` (`benchmark = True`) reuses the animal/feed machinery from `ranch_hands`, the fertilizer helpers from `fertilized_hands`, and hiring/navigation from `hired_hands`; its behavior is frozen by a seeded golden-trace test.

**Tech Stack:** Python 3.12 (Kaggle 3.11 floor), `pytest` (+ `--cov --cov-branch`), `kaggle_environments` kaggriculture sim. No new dependencies.

## Global Constraints

- **Python floor 3.11** (Kaggle runtime); CI runs 3.12; assume 3.10+ locally. Verbatim from CLAUDE.md.
- **Never edit `strategies/__init__.py`'s discovery for a new strategy** — adding a strategy is dropping `strategies/<name>.py` + `tests/test_<name>.py` only. (This plan *does* edit `__init__.py`, but to extend discovery infrastructure, not to register `meta_bot`.)
- **Adding a strategy = a module exposing module-level `STRATEGY`** (a `Strategy` subclass with a unique `name`). Keep decisions in **pure module-level helpers** so they unit-test without a 720-turn game.
- **Fail-safe, never crash (ADR-0006):** develop with `ROBRICULTURE_STRICT=1` so bugs surface instead of degrading to PASS.
- **Coverage gate:** line ≥ 85%, branch ≥ 65% (CI, bare `pytest --cov --cov-branch`). Mark integration entrypoints (`main()`, live-game loops) `# pragma: no cover` at the `def`.
- **Market-order cap = 10** per turn; order so sells are never the truncated ones.
- **Reproducibility (ADR-0005):** seeds fixed everywhere; the pin test depends on it.
- **CI is a bare `pytest`** — the root `conftest.py` supplies the import path; don't remove it.
- **Run from repo root with the venv active** (`source .venv/bin/activate`; the venv is Homebrew `python3.12`, not the system `python3`).

---

## File Structure

- `kaggisim/strategy.py` — **modify.** Add `benchmark: bool = False` to the `Strategy` base.
- `strategies/__init__.py` — **modify.** During discovery, also populate `BENCHMARKS: set[str]` (names whose `STRATEGY.benchmark` is truthy).
- `harness/promotion.py` — **modify.** Add `top_contender(ranking, benchmarks)`; make `designate_champion` pick the top non-benchmark; pass `BENCHMARKS` from the CLI.
- `harness/rounds.py` — **modify.** `run_and_record` picks the top non-benchmark via `top_contender`.
- `strategies/meta_bot.py` — **create.** The frozen benchmark agent (`benchmark = True`, `name = "meta_bot"`).
- `tests/test_benchmark_flag.py` — **create.** The flag + registry discovery.
- `tests/test_champion_excludes_benchmark.py` — **create.** The champion-never-a-benchmark invariant (both paths).
- `tests/test_meta_bot.py` — **create.** `meta_bot` pure-helper units + the seeded behavior-pin golden test.
- `docs/adr/` — no new ADR required; ADR-0007 already governs. (If Phase 0 forces a material deviation from the observed comp, add a short note to the Piece-1 issue, not an ADR.)

---

### Task 1: `benchmark` flag on Strategy + registry discovery

**Files:**
- Modify: `kaggisim/strategy.py:20-32` (the `Strategy` class body)
- Modify: `strategies/__init__.py:14-22` (the discovery loop)
- Test: `tests/test_benchmark_flag.py`

**Interfaces:**
- Consumes: the existing `REGISTRY: dict[str, str]` and `load(name)` from `strategies/__init__.py`.
- Produces: `Strategy.benchmark: bool` (class attribute, default `False`); `strategies.BENCHMARKS: set[str]` (registered names whose `STRATEGY.benchmark` is truthy).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_benchmark_flag.py
"""The benchmark flag: opt-in on a Strategy subclass, surfaced by the registry."""

from __future__ import annotations

from kaggisim.strategy import Strategy
from strategies import BENCHMARKS, REGISTRY


def test_strategy_base_defaults_to_not_a_benchmark():
    # Every ordinary strategy is a contender unless it opts in.
    assert Strategy.benchmark is False


def test_a_subclass_can_opt_in_to_benchmark():
    class Frozen(Strategy):
        name = "frozen"
        benchmark = True

    assert Frozen.benchmark is True


def test_benchmarks_is_a_subset_of_the_registry():
    # BENCHMARKS names are real, registered strategies.
    assert BENCHMARKS <= set(REGISTRY)


def test_existing_strategies_are_not_benchmarks_by_default():
    # Nothing shipped so far is a benchmark (meta_bot arrives in a later task).
    assert "ranch_hands" in REGISTRY
    assert "ranch_hands" not in BENCHMARKS
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `ROBRICULTURE_STRICT=1 pytest tests/test_benchmark_flag.py -v`
Expected: FAIL — `ImportError: cannot import name 'BENCHMARKS'` (and `AttributeError` on `Strategy.benchmark`).

- [ ] **Step 3: Add the flag to the base class**

In `kaggisim/strategy.py`, inside `class Strategy`, below the `name` attribute:

```python
    #: Human-readable name, shown in the tournament harness.
    name: str = "unnamed"

    #: When True, this strategy is a fixed "readonly" benchmark opponent: it is
    #: always available as a tournament/promotion opponent, but is never eligible
    #: to be designated champion (see harness.promotion.top_contender). Default
    #: False — ordinary strategies are champion contenders.
    benchmark: bool = False
```

- [ ] **Step 4: Populate `BENCHMARKS` in the registry**

In `strategies/__init__.py`, extend the discovery loop and export the set:

```python
REGISTRY: dict[str, str] = {}
BENCHMARKS: set[str] = set()

for _module in pkgutil.iter_modules(__path__):
    if _module.name.startswith("_"):
        continue
    _mod = importlib.import_module(f"{__name__}.{_module.name}")
    _strategy = getattr(_mod, "STRATEGY", None)
    if _strategy is not None:
        _name = getattr(_strategy, "name", _module.name)
        REGISTRY[_name] = f"{__name__}.{_module.name}"
        if getattr(_strategy, "benchmark", False):
            BENCHMARKS.add(_name)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `ROBRICULTURE_STRICT=1 pytest tests/test_benchmark_flag.py -v`
Expected: PASS (4 passed).

- [ ] **Step 6: Commit**

```bash
git add kaggisim/strategy.py strategies/__init__.py tests/test_benchmark_flag.py
git commit -m "feat: benchmark flag on Strategy + BENCHMARKS registry discovery (#59)"
```

---

### Task 2: Champion selection excludes benchmarks (both paths)

**Files:**
- Modify: `harness/promotion.py:150-159` (`designate_champion`), and the `--designate` CLI block `harness/promotion.py:224-234`
- Modify: `harness/rounds.py:87-96` (`run_and_record`), and its CLI default names `harness/rounds.py:110`
- Test: `tests/test_champion_excludes_benchmark.py`

**Interfaces:**
- Consumes: `round_robin_rank(agents, games, play_fn)` returning `list[(label, win_rate, wins, played)]` best-first; `strategies.BENCHMARKS`.
- Produces: `harness.promotion.top_contender(ranking, benchmarks) -> str` — the highest-ranked label not in `benchmarks`, raising `ValueError` if every label is a benchmark. `designate_champion(names, games=20, play_fn=play, build=build_agents, benchmarks=None) -> str` now returns the top *contender*. `run_and_record(...)` writes the top contender to `champion.json` while still recording the full ranking (benchmarks included).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_champion_excludes_benchmark.py
"""A benchmark opponent shapes the ranking but is never chosen as champion."""

from __future__ import annotations

import json

import pytest

from harness import promotion, rounds


def test_top_contender_skips_a_leading_benchmark():
    ranking = [("meta_bot", 0.9, 90, 100), ("ranch_hands", 0.7, 70, 100)]
    assert promotion.top_contender(ranking, {"meta_bot"}) == "ranch_hands"


def test_top_contender_returns_the_leader_when_no_benchmark_leads():
    ranking = [("ranch_hands", 0.8, 80, 100), ("meta_bot", 0.6, 60, 100)]
    assert promotion.top_contender(ranking, {"meta_bot"}) == "ranch_hands"


def test_top_contender_raises_when_every_label_is_a_benchmark():
    ranking = [("meta_bot", 0.9, 90, 100)]
    with pytest.raises(ValueError):
        promotion.top_contender(ranking, {"meta_bot"})


def test_designate_champion_never_returns_a_benchmark():
    # A stub round-robin where the benchmark wins outright; the champion must be
    # the strongest non-benchmark instead.
    def fake_play(a, b, seed=None):
        return 1 if a == "meta_bot" else (1 if a == "ranch_hands" else -1)

    def fake_build(names):
        return {n: n for n in names}

    champ = promotion.designate_champion(
        ["meta_bot", "ranch_hands", "wide_hands"],
        games=2, play_fn=fake_play, build=fake_build, benchmarks={"meta_bot"},
    )
    assert champ != "meta_bot"


def test_run_and_record_writes_a_non_benchmark_champion(tmp_path):
    # meta_bot dominates the round, but champion.json must name a contender.
    def fake_play(a, b, seed=None):
        return 1 if a == "meta_bot" else 0

    def fake_build(names):
        return {n: n for n in names}

    rounds_path = tmp_path / "rounds.json"
    champ_path = tmp_path / "champion.json"
    champ, ranking = rounds.run_and_record(
        ["meta_bot", "ranch_hands"], games=2,
        rounds_path=str(rounds_path), champion_path=str(champ_path),
        play_fn=fake_play, build=fake_build, benchmarks={"meta_bot"},
    )
    assert champ != "meta_bot"
    assert json.loads(champ_path.read_text())["champion"] != "meta_bot"
    # The benchmark still appears in the recorded ranking (it shaped the round).
    assert any(row[0] == "meta_bot" for row in ranking)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `ROBRICULTURE_STRICT=1 pytest tests/test_champion_excludes_benchmark.py -v`
Expected: FAIL — `AttributeError: module 'harness.promotion' has no attribute 'top_contender'`, and `run_and_record`/`designate_champion` reject the `benchmarks=` kwarg.

- [ ] **Step 3: Add `top_contender` and thread it through `designate_champion`**

In `harness/promotion.py`, add above `designate_champion`:

```python
def top_contender(ranking, benchmarks):
    """The highest-ranked label in `ranking` that is not a benchmark opponent.

    `ranking` is best-first `(label, win_rate, wins, played)` rows. Benchmarks
    shape the ranking (as opponents) but can never be champion, so we skip them.
    Raises ValueError if every label is a benchmark (no valid champion).
    """
    for label, *_rest in ranking:
        if label not in benchmarks:
            return label
    raise ValueError("no non-benchmark contender in ranking")
```

Then update `designate_champion`:

```python
def designate_champion(names, games=20, play_fn=play, build=build_agents, benchmarks=None):
    """Run a round-robin among `names` and return the strongest *non-benchmark* label.

    `build` maps names to agents (built-ins like "starter"/"random" pass through
    as strings); it is injectable so the ranking logic can be tested without
    running real games. `benchmarks` (a set of names) are opponents but never
    champion candidates.
    """
    benchmarks = benchmarks or set()
    ranking = round_robin_rank(build(names), games=games, play_fn=play_fn)
    return top_contender(ranking, benchmarks)
```

- [ ] **Step 4: Thread it through `run_and_record` (rounds.py)**

In `harness/rounds.py`, import `top_contender` and add the `benchmarks` kwarg:

```python
from harness.promotion import CHAMPION_PATH, round_robin_rank, save_champion, top_contender
```

```python
def run_and_record(names, games=20, window=DEFAULT_WINDOW, decay=None,
                   rounds_path=ROUNDS_PATH, champion_path=CHAMPION_PATH,
                   play_fn=play, build=build_agents, benchmarks=None):
    """Play a round, append it to history, re-designate the champion from the window.

    `benchmarks` (a set of names) are opponents in the round but never champion.
    """
    benchmarks = benchmarks or set()
    rnd = run_round(names, games=games, play_fn=play_fn, build=build)
    append_round(rounds_path, rnd)
    ranking = windowed_ranking(load_rounds(rounds_path), window=window, decay=decay)
    champion = top_contender(ranking, benchmarks)
    save_champion(champion_path, champion, games, ranking)
    return champion, ranking
```

- [ ] **Step 5: Pass `BENCHMARKS` from both CLIs**

In `harness/promotion.py` `main()`'s `--designate` block, replace `champ = ranking[0][0]` with the contender pick and keep the benchmarks as opponents in `names`:

```python
    if args.designate:
        from harness.tournament import BUILTINS
        from strategies import BENCHMARKS
        names = args.names or (list(REGISTRY) + list(BUILTINS))
        print(f"Designating champion among {names} ({args.games} games/pairing)...")
        ranking = round_robin_rank(build_agents(names), games=args.games)
        champ = top_contender(ranking, BENCHMARKS)
        save_champion(CHAMPION_PATH, champ, args.games, ranking)
        for name, wr, w, p in ranking:
            print(f"  {name:16s} {wr:6.1%}  ({w}/{p})")
        print(f"\nChampion: {champ}  -> {CHAMPION_PATH}")
        return 0
```

In `harness/rounds.py` `main()`, pass benchmarks through:

```python
    from strategies import BENCHMARKS, REGISTRY
    ...
    champion, ranking = run_and_record(
        names, games=args.games, window=args.window, decay=args.decay,
        benchmarks=BENCHMARKS,
    )
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `ROBRICULTURE_STRICT=1 pytest tests/test_champion_excludes_benchmark.py -v`
Expected: PASS (5 passed).

- [ ] **Step 7: Commit**

```bash
git add harness/promotion.py harness/rounds.py tests/test_champion_excludes_benchmark.py
git commit -m "feat: champion selection excludes benchmark opponents (#59)"
```

---

### Task 3: Phase 0 — feasibility spike for the target comp

**Goal:** Confirm the observed modal comp — **9 COW + 4 SHEEP + 1 WHEAT (feed) + 10 hands + FERTILIZER from day 2** — is legal and reachable in our installed sim *before* building `meta_bot` to it. This task produces a findings note, not shipped code.

**Files:**
- Create (throwaway, NOT committed): `scratch_phase0.py` at repo root, deleted at the end of the task.
- Reference: `kaggisim/economy.py` (crop/animal/product tables), `strategies/ranch_hands.py` (animal tiles `COW_TILE=(2,2)`, `SHEEP_TILE=(2,1)`, `ANIMAL_COST`), `strategies/hired_hands.py` (`MAX_HANDS`), and the installed sim source `kaggle_environments/envs/kaggriculture/kaggriculture.py`.

- [ ] **Step 1: Enumerate the constraints from the sim**

Run a one-off to answer, verbatim, into the issue:
```bash
source .venv/bin/activate && python scratch_phase0.py
```
`scratch_phase0.py` must print:
1. **Hand cap** — the sim's max simultaneous hired hands (compare to our `hired_hands.MAX_HANDS` and the field's 10). Grep the sim: `python -c "import kaggle_environments,inspect,kaggle_environments.envs.kaggriculture.kaggriculture as k; print(inspect.getsourcefile(k))"` then read the config for the hire cap.
2. **Animal tile capacity** — how many animals a farm can host at once and on which tiles (can we place 9 cows + 4 sheep = 13 animals? what are the legal animal tiles / land quadrants?). The field uses land `NE/NW/SW`.
3. **Fertilizer loop legality** — confirm `BUY_PRODUCT FERTILIZER` → shed → `PICKUP` → `FERTILIZE`/`COLLECT_FERTILIZER` works as `fertilized_hands` assumes, and whether fertilizer applies to animal feed or only crops.

- [ ] **Step 2: Record the reachable comp**

Write the answer as a comment on the Piece-1 issue (#59): the **actual reachable** cow/sheep/hand counts and the animal-tile layout `meta_bot` will use. If any target element is infeasible (e.g., a hard animal cap < 13), record the nearest legal comp and the delta from the observed meta. This comment is the source of truth for Task 4's constants.

- [ ] **Step 3: Clean up**

```bash
rm scratch_phase0.py
```
No commit (nothing shipped). The findings live on the issue.

---

### Task 4: `meta_bot` — the frozen benchmark agent

**Files:**
- Create: `strategies/meta_bot.py`
- Test: `tests/test_meta_bot.py` (helpers only in this task; the pin test is Task 5)
- Reference/reuse: `strategies/ranch_hands.py` (`livestock_action`, `choose_catch_crop`, `_sell_orders_keep_feed`, `ANIMAL_COST`, `COW_MONEY_BUFFER`, `SHEEP_MONEY_BUFFER`, `WHEAT_BUFFER`), `strategies/fertilized_hands.py` (`fertilize_or_fetch`, `should_buy_fertilizer`, `FERTILIZER`), `strategies/hired_hands.py` (`step_toward`, `tile_at`, `plan_hands`, `MAX_HANDS`, `TURNS_PER_DAY`).

**Interfaces:**
- Consumes: the reachable-comp constants recorded on issue #59 in Task 3 (cow/sheep counts, animal-tile list, hand count).
- Produces: `strategies.meta_bot.STRATEGY` = `MetaBotStrategy` with `name = "meta_bot"`, `benchmark = True`; pure module-level helpers, each independently unit-tested:
  - `ANIMAL_TILES: list[tuple[tuple[int,int], str]]` — the (tile, "COW"|"SHEEP") placement for the reachable comp (e.g. 9 cows + 4 sheep from Task 3).
  - `animal_buy_orders(tiles, shed, inventories, money) -> list[list]` — the market orders that stand up the herd in priority order (cows before sheep), respecting money buffers and the 10-order cap.
  - `fertilizer_orders(day, tiles, shed, inventories, money) -> list[list]` — day≥2 fertilizer buys, capped, reusing `should_buy_fertilizer` semantics.
  - `worker_action(i, pos, tiles, ...) -> list` — one action per worker: livestock hands tend their animal, crop/feed hands run the wheat-feed loop, fertilizer-capable farmer applies fertilizer.

- [ ] **Step 1: Write the failing composition test**

```python
# tests/test_meta_bot.py  (helpers portion)
"""meta_bot — a frozen benchmark hard-coded to the top-Elo modal comp (#59)."""

from __future__ import annotations

from strategies import meta_bot as mb


def test_meta_bot_is_a_readonly_benchmark():
    assert mb.STRATEGY.benchmark is True
    assert mb.STRATEGY.name == "meta_bot"


def test_composition_matches_the_reachable_meta_comp():
    # Counts come from Task 3's feasibility note on issue #59 (target 9 cow + 4 sheep).
    cows = [t for t in mb.ANIMAL_TILES if t[1] == "COW"]
    sheep = [t for t in mb.ANIMAL_TILES if t[1] == "SHEEP"]
    assert len(cows) == mb.N_COW      # == 9 unless Phase 0 found a lower legal cap
    assert len(sheep) == mb.N_SHEEP   # == 4
    # No two animals share a tile.
    assert len({t[0] for t in mb.ANIMAL_TILES}) == len(mb.ANIMAL_TILES)


def test_animal_buy_orders_stand_up_cows_before_sheep():
    orders = mb.animal_buy_orders(tiles=_bare_tiles(), shed={}, inventories=[{}], money=100000)
    kinds = [o[1] for o in orders if o[0] == "BUY_ANIMAL"]
    assert kinds and kinds[0] == "COW"
    assert len(orders) <= 10


def test_fertilizer_orders_start_on_day_two_not_before():
    assert mb.fertilizer_orders(day=1, tiles=_bare_tiles(), shed={}, inventories=[{}], money=100000) == []
    assert mb.fertilizer_orders(day=2, tiles=_bare_tiles(), shed={}, inventories=[{}], money=100000)


def _bare_tiles():
    return [[None for _ in range(10)] for _ in range(10)]
```

- [ ] **Step 2: Run to verify it fails**

Run: `ROBRICULTURE_STRICT=1 pytest tests/test_meta_bot.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'strategies.meta_bot'`.

- [ ] **Step 3: Implement `strategies/meta_bot.py`**

Build the module following the `ranch_hands` decomposition pattern (module docstring stating the comp + its recon provenance; pure helpers; a thin `act`). Fill `N_COW`/`N_SHEEP`/`ANIMAL_TILES`/hand count from the Task-3 issue note. Reuse the imported machinery listed under **Interfaces** rather than re-deriving it. Keep every decision in the four pure helpers above; `act` only wires them and clamps `market[:10]`. Set `benchmark = True` and `name = "meta_bot"`; export `STRATEGY = MetaBotStrategy`.

Key rules to encode (from the recon + sim):
- Land the herd first: `animal_buy_orders` emits `["BUY_ANIMAL","COW",1]` × up to `N_COW`, then sheep, gated by `money >= ANIMAL_COST[...] + buffer`, lowest market priority (never displace a sell).
- Fertilizer from day 2 only (`fertilizer_orders` returns `[]` for `day < 2`).
- One wheat-feed crew tile (feed for the herd), reusing `ranch_hands._sell_orders_keep_feed` so wheat is held back as feed.
- Sells lead the market list (price-sensitive orders before HIRE/BUY), per the 10-order cap rule.

- [ ] **Step 4: Run to verify the helper tests pass**

Run: `ROBRICULTURE_STRICT=1 pytest tests/test_meta_bot.py -v`
Expected: PASS.

- [ ] **Step 5: Run the no-crash gate for meta_bot under strict mode**

Run: `ROBRICULTURE_STRICT=1 pytest tests/test_no_crash.py -v`
Expected: PASS — `meta_bot` (auto-discovered) survives full games vs the built-ins with exceptions propagating.

- [ ] **Step 6: Commit**

```bash
git add strategies/meta_bot.py tests/test_meta_bot.py
git commit -m "feat: meta_bot readonly benchmark, frozen to the top-Elo comp (#59)"
```

---

### Task 5: Freeze meta_bot with a seeded behavior-pin test + full CI gate

**Files:**
- Modify: `tests/test_meta_bot.py` (add the pin test)

**Interfaces:**
- Consumes: `strategies.meta_bot.MetaBotStrategy`, a bare 10×10 board obs, and a fixed seed.
- Produces: a golden assertion on `meta_bot`'s dawn move for a fixed fresh observation, so any behavior change breaks CI ("can't be changed").

- [ ] **Step 1: Write the pin test with a placeholder golden**

```python
# appended to tests/test_meta_bot.py
import hashlib
import json


def _fresh_obs(hour=0, day=0, money=100000, hands=None):
    board = [[None for _ in range(10)] for _ in range(10)]
    hands = hands or []
    n_inv = 1 + len(hands)
    return {
        "player": 0, "day": day, "hour": hour,
        "farms": [
            {"money": money, "tiles": board, "farmer": [4, 4], "hands": hands},
            {"money": money, "tiles": [[None]*10 for _ in range(10)], "farmer": [4, 4], "hands": []},
        ],
        "market": {"inventory": {}, "prices": {}},
        "town": {"unlocked_shops": []},
        "private": {"shed": {}, "seeds": {}, "inventories": [{} for _ in range(n_inv)]},
    }


def test_meta_bot_dawn_move_is_frozen():
    # meta_bot is a readonly benchmark: its opening move is pinned so any edit
    # to its behavior breaks CI (the "can't be changed" contract, #59).
    action = mb.MetaBotStrategy().act(_fresh_obs(hour=0, day=0))
    digest = hashlib.sha256(json.dumps(action, sort_keys=True).encode()).hexdigest()
    assert digest == "PLACEHOLDER"
```

- [ ] **Step 2: Run to capture the real golden**

Run: `ROBRICULTURE_STRICT=1 pytest tests/test_meta_bot.py::test_meta_bot_dawn_move_is_frozen -v`
Expected: FAIL with an assertion showing the actual digest. Copy the real hex digest.

- [ ] **Step 3: Pin the golden**

Replace `"PLACEHOLDER"` with the captured digest. (If the reviewer wants the trace legible rather than hashed, assert on `action` directly instead of the digest — either satisfies the freeze.)

- [ ] **Step 4: Run to verify it passes**

Run: `ROBRICULTURE_STRICT=1 pytest tests/test_meta_bot.py -v`
Expected: PASS.

- [ ] **Step 5: Full CI gate (the repo's real gate set)**

Run, from repo root with the venv active:
```bash
pytest -q --cov --cov-branch --cov-report=term-missing
```
Expected: all tests PASS; **line ≥ 85%, branch ≥ 65%**. If `meta_bot`'s `act` integration lines are the coverage gap, confirm the no-crash gate exercises them; mark only genuine integration entrypoints `# pragma: no cover` at the `def` (never the pure helpers).

- [ ] **Step 6: Commit**

```bash
git add tests/test_meta_bot.py
git commit -m "test: freeze meta_bot behavior with a seeded golden-trace pin (#59)"
```

---

## Self-Review

**Spec coverage:**
- Readonly `benchmark = True` mechanism → Task 1. ✅
- Auto-discovered, no `__init__.py` registration edit for the strategy → `meta_bot` is dropped in as a file (Task 4); `__init__.py` is touched only to extend *discovery* (Task 1), which the spec's mechanism explicitly requires. ✅
- Always an opponent, never champion (`--designate`/`champion.json` exclude) → Task 2 covers **both** designation paths (`promotion.designate_champion` + `rounds.run_and_record`). ✅
- `meta_bot` frozen to 9 cow + 4 sheep + 1 wheat + 10 hands + fertilizer d2 → Task 4 (constants from Task 3). ✅
- Phase 0 feasibility before building → Task 3. ✅
- Behavior-pin "can't be changed" → Task 5. ✅
- No third-party code / license risk → `meta_bot` authored from recon; no vendored code (out of scope, per spec). ✅
- No economy/sim changes → none in any task. ✅

**Placeholder scan:** The only literal `"PLACEHOLDER"` is Task 5's golden, which is captured and replaced within the same task (Steps 2–3) — an intentional record-the-golden step, not an unfilled gap. Task 4's `meta_bot` body references constants produced by Task 3; this is a genuine task dependency (feasibility must run first), and the helper interfaces, tests, and reuse map are fully specified.

**Type consistency:** `top_contender(ranking, benchmarks) -> str` is defined in Task 2 and consumed by `designate_champion` and `run_and_record` in the same task with matching signatures. `BENCHMARKS: set[str]` is produced in Task 1 and consumed in Task 2. `Strategy.benchmark: bool` is produced in Task 1 and read in Tasks 1/2/4/5. Names are consistent across tasks.

---

## Piece 2 (not in this plan)

`meta_rancher` — the meta-matching *contender* gated against this improved pool — is a separate `experiment` issue opened after Piece 1 merges. See `docs/superpowers/specs/2026-08-12-meta-benchmark-and-rancher-design.md`.
