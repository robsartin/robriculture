# NW pasture block (#246) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `nw_pasture` contender (#244's front ramp with the twelve-tile pasture block moved into NW through a new `layout` seam), a `land_target` seam for its recorded arm B, and the declared bench `harness/layout_bench.py`.

**Architecture:** Two keyword-only seams are added to the frozen benchmark `strategies/field_rival.py` in the shape of #202/#237/#239 — helpers gain parameters defaulting to the frozen constants and the class gains hooks returning `None`, so `field_rival`'s own decisions are byte-identical. The contender is a subclass of `pasture_first` that answers the `layout` hook. The bench imports the verdict, formatting and paired-external machinery from `harness.rival_bench` and the census readers from `harness.front_bench` / `harness.farm_census`, and adds only the placed-head control and the first-day-pasture reading.

**Tech Stack:** Python 3.12 in `.venv` (`.venv/bin/python`, never a bare `python3`), pytest with `-n auto`, `kaggle-environments` 1.32.7. Spec: `docs/superpowers/specs/2026-09-08-nw-pasture-design.md`.

## Global Constraints

- Pure TDD: write the failing test, **run it and quote the failure**, then the minimal code, then run green, then commit. A test that never ran red proves nothing.
- Keep the build green at every commit (Mikado): `.venv/bin/python -m pytest -q -n auto` must pass before every commit in every task.
- `strategies/field_rival.py` is the **frozen benchmark** (#181): every new parameter defaults to the frozen constant; every new hook returns `None` on `FieldRivalStrategy`; no existing assertion in `tests/test_field_rival.py` may change.
- Never edit `strategies/__init__.py` (the registry auto-discovers `STRATEGY`).
- Test names are plain `snake_case` reading `test_<expected>_when_<condition>` or `test_<the fact>`, each with a one-line docstring or comment saying why (house style, see `tests/test_pasture_first.py`).
- Stage by explicit path (`git add <files>`); never `git add -A`. Never stage `.venv` or `external_agents` (symlinks in this worktree).
- Commit messages end with a blank line and `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.
- Coverage gate line ≥ 85% / branch ≥ 65%; live-game entrypoints carry `# pragma: no cover` at the `def`, pure helpers do not.
- Declared values (verbatim from the spec, not to be tuned): `CONTENDER = "nw_pasture"`, `CHAMPION = "third_herder"`, `SEEDS = tuple(range(880, 896))`, `CONTROL_SEED = 880`, `CHAMPION_BAR = 0.60`, `ANCHOR_BAR = 0.90`, `PLACED_DAY = 9`, `CROP_DAY = 16`, `PLACED_DELTA_BAR = 4`, `PLANTED_GAP_BAR = 5`, `PASTURE_STANDING = 8`, `ARM_B = "early_land"`, `LAND_RAMP_B = ((0, 1), (6, 2), (16, 3))`, `PASTURE_BLOCK = tuple(fr._quadrant_tiles("NW")[1:13])`.
- Do not run the bench's live games (`run_controls`, `run_criterion`, `run_recorded`, `main`) — the controller runs the declared bench after the branch is reviewed.

---

## File map

| File | Responsibility |
|---|---|
| `strategies/field_rival.py` (modify) | Task 1: `active_pastures(..., block=)`, `crop_cluster(..., crops=)`, `FieldRivalStrategy.layout()`, `act` threads the pair. Task 2: `market_orders(..., land=None)`, `FieldRivalStrategy.land_target()`, `act` passes it. |
| `tests/test_field_rival.py` (modify, append only) | Tasks 1-2: seam defaults pinned, seams honoured. |
| `strategies/nw_pasture.py` (create) | Task 3: `PASTURE_BLOCK`, `CROP_TILES`, `NwPastureStrategy`, `STRATEGY`. |
| `tests/test_nw_pasture.py` (create) | Task 3. |
| `harness/layout_bench.py` (create) | Task 4: constants, `mechanism_reading`, `mechanism_deltas`, `mechanism_ok`, `crop_line_ok`, `format_mechanism`, `arm_b_class`, live runners, `main`. |
| `tests/test_layout_bench.py` (create) | Task 4. |

---

### Task 1: The `layout` seam on the frozen benchmark

**Files:**
- Modify: `strategies/field_rival.py` — `active_pastures` (line ~514), `crop_cluster` (line ~205), `FieldRivalStrategy` (hooks after `livestock_workers`, ~line 605; `act` ~lines 630-665)
- Test: `tests/test_field_rival.py` (append at the end)

**Interfaces:**
- Consumes: module constants `PASTURE_TILES`, `CROP_TILES`, `LIVESTOCK_WORKERS`, `CLUSTER`; `_crop_slot(worker, workers)` (unchanged).
- Produces: `active_pastures(day, animals, count=None, block=PASTURE_TILES) -> tuple`; `crop_cluster(worker, workers=LIVESTOCK_WORKERS, crops=CROP_TILES) -> tuple`; `FieldRivalStrategy.layout(self) -> tuple[tuple, tuple] | None` (returns `None` on the benchmark); `act` reads `block, crops = self.layout() or (PASTURE_TILES, CROP_TILES)` once per turn.

- [ ] **Step 1: Write the failing tests** — append to `tests/test_field_rival.py`:

```python
# --- #246: the layout seam, and the frozen pair it defaults to ---

def test_the_benchmarks_layout_hook_asks_for_the_frozen_pair():
    # `None` means "the benchmark's own layout", so field_rival stays frozen (#181).
    assert fr.FieldRivalStrategy().layout() is None


def test_active_pastures_with_a_block_takes_its_prefix():
    # The seam: a contender's own block replaces PASTURE_TILES; the count rule
    # and the "prefix of the block" ORDER are untouched.
    block = ((9, 9), (8, 9), (7, 9), (6, 9))
    assert fr.active_pastures(0, 0, count=3, block=block) == block[:3]
    assert fr.active_pastures(0, 2, block=block) == block[:2]      # never fewer than placed head
    assert fr.active_pastures(0, 0, count=3) == fr.PASTURE_TILES[:3]  # default is the frozen block


def test_crop_cluster_with_crops_slices_that_layout():
    # Worker 5 is crop slot 3 under the frozen herder pair (1, 2): tiles 12-15.
    crops = tuple((x, 9) for x in range(20))
    assert fr.crop_cluster(5, crops=crops) == crops[12:16]
    assert fr.crop_cluster(0, crops=crops) == crops[0:4]
    assert fr.crop_cluster(1, crops=crops) == ()                     # a herder has no cluster
    assert fr.crop_cluster(5) == fr.CROP_TILES[12:16]                # default is the frozen layout
```

- [ ] **Step 2: Run them and quote the failure**

Run: `.venv/bin/python -m pytest -q tests/test_field_rival.py -k "layout_hook or with_a_block or with_crops"`
Expected: 3 failed — `AttributeError: 'FieldRivalStrategy' object has no attribute 'layout'`, `TypeError: active_pastures() got an unexpected keyword argument 'block'`, `TypeError: crop_cluster() got an unexpected keyword argument 'crops'`.

- [ ] **Step 3: Minimal implementation** in `strategies/field_rival.py`:

`crop_cluster` becomes:

```python
def crop_cluster(worker: int, workers=LIVESTOCK_WORKERS, crops=CROP_TILES):
    """The tiles worker `worker` is responsible for -- ``()`` for a herder.

    `crops` is the crop layout in slot order (#246); the module default is
    the frozen `CROP_TILES`, so `field_rival` stays frozen (#181). The slot
    LAYOUT still comes from `_crop_slot` -- a contender's layout changes which
    tiles a slot holds, never which worker holds a slot.
    """
    slot = _crop_slot(worker, workers)
    if slot is None:
        return ()
    return crops[slot * CLUSTER:(slot + 1) * CLUSTER]
```

`active_pastures` becomes (docstring keeps its text, one sentence added):

```python
def active_pastures(day: int, animals: int, count=None, block=PASTURE_TILES):
    """Pasture tiles in play today -- the ramp's target, never fewer than the
    head already on the board (an animal must keep being fed after the ramp
    flattens).

    `count`: how many tiles a contender wants standing this turn (#237);
    ``None`` keeps the benchmark's own rule, so field_rival stays frozen
    (#181). The tile ORDER is not a seam -- it is always the shed-adjacent
    prefix of the block either way. `block` is the pasture layout (#246); the
    module default is the frozen `PASTURE_TILES`.
    """
    if count is not None:
        return block[:count]
    return block[:max(animal_target(day), animals)]
```

In `FieldRivalStrategy`, after `livestock_workers`:

```python
    def layout(self):
        """``(pasture_tiles, crop_tiles)`` for this farm, or ``None`` for the
        frozen `(PASTURE_TILES, CROP_TILES)`. A seam for contenders (#246).

        The pasture block is what `active_pastures` takes its prefix from and
        the crop tiles are what `crop_cluster` slices by slot; the two must be
        disjoint. On the benchmark it never fires, so its layout stays frozen
        (#181).
        """
        return None
```

In `act`, replace

```python
        pastures = active_pastures(day, animals,
                                   count=self.pasture_count(day, animals))
```

with

```python
        block, crops = self.layout() or (PASTURE_TILES, CROP_TILES)
        pastures = active_pastures(day, animals,
                                   count=self.pasture_count(day, animals), block=block)
```

and both `crop_cluster(i, workers)` calls in `act` with `crop_cluster(i, workers, crops=crops)`.

- [ ] **Step 4: Run green**

Run: `.venv/bin/python -m pytest -q -n auto`
Expected: all pass (the 80 existing field_rival tests unchanged and green, including `test_early_crop_clusters_fall_inside_the_starting_quadrant` and `test_crop_clusters_partition_the_crop_tiles_without_repeats`).

- [ ] **Step 5: Commit**

```bash
git add strategies/field_rival.py tests/test_field_rival.py
git commit -m "field_rival: a layout seam -- pasture block and crop tiles, frozen by default (#246)

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 2: The `land_target` seam on the frozen benchmark

**Files:**
- Modify: `strategies/field_rival.py` — `market_orders` (signature line ~334, land block line ~375), `FieldRivalStrategy` (hook after `layout`), `act` (`market_orders(...)` call)
- Test: `tests/test_field_rival.py` (append)

**Interfaces:**
- Consumes: module function `land_target(day)` (unchanged), `economy.LAND_COSTS`.
- Produces: `market_orders(day, hour, money, hands, quadrants, animals, shed, seeds, empty_plots, standing=None, caps=None, prefer=None, target=None, land=None)`; `FieldRivalStrategy.land_target(self, day) -> int | None` (`None` on the benchmark); `act` passes `land=self.land_target(day)`.

- [ ] **Step 1: Write the failing tests** — append to `tests/test_field_rival.py`:

```python
# --- #246: the land seam, and the frozen ramp it defaults to ---

def _land_orders(day, quadrants, **kw):
    orders = fr.market_orders(day=day, hour=1, money=50_000, hands=8, quadrants=quadrants,
                              animals=0, shed={}, seeds={}, empty_plots=0, standing={}, **kw)
    return [o for o in orders if o[0] == "BUY_LAND"]


def test_the_benchmarks_land_hook_asks_for_the_frozen_ramp():
    # `None` means "the benchmark's own ramp", so field_rival stays frozen (#181).
    assert fr.FieldRivalStrategy().land_target(0) is None
    assert fr.FieldRivalStrategy().land_target(12) is None


def test_market_orders_without_land_buys_on_the_frozen_ramp():
    # Golden pin on the default: NE is bought on day 12 and not on day 6.
    assert _land_orders(12, 1) == [["BUY_LAND"]]
    assert _land_orders(6, 1) == []


def test_market_orders_with_land_buys_to_that_target():
    # The seam: a contender's own quadrant target replaces the ramp's.
    assert _land_orders(6, 1, land=2) == [["BUY_LAND"]]
    assert _land_orders(12, 1, land=1) == []
```

- [ ] **Step 2: Run them and quote the failure**

Run: `.venv/bin/python -m pytest -q tests/test_field_rival.py -k "land_hook or without_land or with_land"`
Expected: 2 failed — `AttributeError: 'FieldRivalStrategy' object has no attribute 'land_target'` and `TypeError: market_orders() got an unexpected keyword argument 'land'`; `test_market_orders_without_land_buys_on_the_frozen_ramp` passes already (it pins the frozen default).

- [ ] **Step 3: Minimal implementation** in `strategies/field_rival.py`:

Signature:

```python
def market_orders(day, hour, money, hands, quadrants, animals, shed, seeds,
                  empty_plots, standing=None, caps=None, prefer=None, target=None,
                  land=None):
```

Add one line to the end of the docstring's parameter notes (keep everything already there): `` `land`: quadrants to own today, or ``None`` for the frozen `land_target` ramp (#246). ``

The land block:

```python
    want_land = land_target(day) if land is None else land
    if quadrants < want_land and quadrants - 1 < len(economy.LAND_COSTS):
        cost = economy.LAND_COSTS[quadrants - 1]
        if budget >= cost:
            buys.append(["BUY_LAND"])
            budget -= cost
```

In `FieldRivalStrategy`, after `layout`:

```python
    def land_target(self, day):
        """Quadrants to own on `day`, or ``None`` for the frozen `land_target`
        ramp. A seam for contenders (#246); on the benchmark it never fires,
        so its land schedule stays frozen (#181)."""
        return None
```

In `act`, the `market_orders(...)` call gains `land=self.land_target(day)` after `target=self.herd_target(day)`.

- [ ] **Step 4: Run green**

Run: `.venv/bin/python -m pytest -q -n auto`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add strategies/field_rival.py tests/test_field_rival.py
git commit -m "field_rival: a land seam -- quadrants to own, frozen by default (#246)

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 3: The contender `nw_pasture`

**Files:**
- Create: `strategies/nw_pasture.py`
- Test: `tests/test_nw_pasture.py`

**Interfaces:**
- Consumes: `FieldRivalStrategy.layout()` (Task 1); `strategies.pasture_first.PastureFirstStrategy` and its `FRONT_RAMP`; `fr._quadrant_tiles`, `fr.OWNED_QUADRANTS`, `fr.quadrant_of`, `fr.PASTURE_TILES`.
- Produces: module constants `PASTURE_BLOCK` (12 NW tiles), `CROP_TILES`; class `NwPastureStrategy(PastureFirstStrategy)` with `name = "nw_pasture"`, `benchmark = False`, class attributes `PASTURE_BLOCK` and `CROP_TILES`, method `layout(self) -> (PASTURE_BLOCK, CROP_TILES)`; `STRATEGY = NwPastureStrategy`. Task 4 loads it by name via `strategies.load("nw_pasture")`.

- [ ] **Step 1: Write the failing tests** — `tests/test_nw_pasture.py`:

```python
"""NW pasture block: the pasture opened before the head (#246).

#244 fronted the herd ramp and owned 10 head by day 9 -- the cash was there
-- but placed 5 and spent 561 turns with head in the shed: `PASTURE_TILES`
runs into NE, which is bought on day 12, so pasture is land-capped at five
until then. `BUILD_PASTURE` is free and instant, and the ceiling (#234)
builds fourteen pasture tiles inside NW alone by day 7. This arm is
`pasture_first` with the twelve-tile block moved into NW through the layout
seam; the crop tiles follow the frozen rule with the block removed.
"""

from __future__ import annotations

from strategies import field_rival as fr
from strategies import nw_pasture as nw


def test_the_declared_constants():
    assert nw.PASTURE_BLOCK == tuple(fr._quadrant_tiles("NW")[1:13])
    assert nw.NwPastureStrategy.PASTURE_BLOCK == nw.PASTURE_BLOCK
    assert nw.NwPastureStrategy.CROP_TILES == nw.CROP_TILES
    assert nw.NwPastureStrategy.name == "nw_pasture"
    assert nw.NwPastureStrategy.benchmark is False


def test_the_block_is_twelve_nw_tiles_that_keep_the_frozen_shed_prefix():
    # Twelve is len(PASTURE_TILES): the ramp's ceiling and every inherited rule
    # reading the block length are unchanged; only WHERE the tiles are moves.
    assert len(nw.PASTURE_BLOCK) == len(fr.PASTURE_TILES) == 12
    assert all(fr.quadrant_of(x, y) == "NW" for x, y in nw.PASTURE_BLOCK)
    assert (4, 4) not in nw.PASTURE_BLOCK                       # the shed-access tile stays crop
    assert nw.PASTURE_BLOCK[:5] == fr.PASTURE_TILES[:5]        # the herders' walk is unchanged
    assert len(set(nw.PASTURE_BLOCK)) == 12


def test_crop_tiles_are_the_frozen_rule_with_the_block_removed():
    owned = [t for q in fr.OWNED_QUADRANTS for t in fr._quadrant_tiles(q)]
    assert not (set(nw.CROP_TILES) & set(nw.PASTURE_BLOCK))
    assert set(nw.CROP_TILES) | set(nw.PASTURE_BLOCK) == set(owned)
    assert nw.CROP_TILES[0] == (4, 4)
    assert sum(1 for x, y in nw.CROP_TILES if fr.quadrant_of(x, y) == "NW") == 13


def test_slot_three_straddles_nw_and_ne_and_the_first_three_slots_are_all_nw():
    # Slots are sliced from CROP_TILES by the frozen `_crop_slot`; worker 5 is
    # slot 3 under the herder pair (1, 2). Its hand works one NW tile until NE
    # opens on day 12 -- the declared, visible cost of the block.
    s = nw.NwPastureStrategy()
    block, crops = s.layout()
    assert block is nw.PASTURE_BLOCK and crops is nw.CROP_TILES
    for worker in (0, 3, 4):
        assert all(fr.quadrant_of(x, y) == "NW" for x, y in fr.crop_cluster(worker, crops=crops))
    assert fr.crop_cluster(5, crops=crops) == ((0, 0), (5, 4), (5, 3), (6, 4))


def test_it_is_a_registered_contender_built_on_pasture_first():
    from strategies import REGISTRY, load
    from strategies.pasture_first import PastureFirstStrategy
    assert "nw_pasture" in REGISTRY
    assert load("nw_pasture") is nw.NwPastureStrategy
    assert issubclass(nw.NwPastureStrategy, PastureFirstStrategy)
    # Inherited, not restated: the front ramp, the third herder, the lead,
    # #219's cow rule and the crop caps all come from the bases unchanged.
    s = nw.NwPastureStrategy()
    assert nw.NwPastureStrategy.FRONT_RAMP == PastureFirstStrategy.FRONT_RAMP
    assert s.herd_target(6) == 12 and s.pasture_count(6, 0) == 12
    assert s.livestock_workers(8) == PastureFirstStrategy().livestock_workers(8)
    assert s.land_target(12) is None                           # the frozen land ramp
```

- [ ] **Step 2: Run them and quote the failure**

Run: `.venv/bin/python -m pytest -q tests/test_nw_pasture.py`
Expected: collection error `ModuleNotFoundError: No module named 'strategies.nw_pasture'`.

- [ ] **Step 3: Minimal implementation** — `strategies/nw_pasture.py`:

```python
"""NW pasture block: the pasture opened before the head (#246).

#244 fronted the herd ramp on `third_herder` and was REJECTED 3/16. Its
census said why: the contender OWNED 10 head at day 9 against the champion's
4 -- the cash was there -- but PLACED 5 against 4 and spent 561 of 719 turns
with head in the shed. `field_rival.PASTURE_TILES` is five NW tiles followed
by seven NE tiles and `LAND_RAMP` buys NE on day 12, so pasture is
land-capped at five until then whatever the ramp asks.

Two facts make the layout the lever. `BUILD_PASTURE` is free and instant --
the sim op only sets the tile's kind -- so pasture is bounded by owned tiles,
not money. And the ceiling (#234, `lonespear_v21`) builds six pasture tiles
on day 0 and fourteen by day 7 inside NW alone.

One decision changes on top of `pasture_first`: the pasture block is the
twelve NW tiles nearest the shed after the shed-access tile, through the
`layout` seam on the frozen benchmark (#181, #202, #219, #237, #239, #246),
and the crop tiles follow the frozen rule with that block removed. Twelve is
`len(PASTURE_TILES)`, so the ramp's ceiling and every inherited rule reading
the block length are unchanged; the first five tiles are the frozen block's
own, so the herders' shed walk is unchanged. A layout change alone is inert
before day 12 -- the frozen ramp asks four head and five tiles hold it --
which is why #244's `FRONT_RAMP` rides along, inherited.

The visible cost: NW keeps thirteen crop tiles instead of the sixteen the
champion works before day 12; crop slot 3 is `(0, 0)` plus three NE tiles,
so its hand works one tile until NE opens. The crop-line control in
`harness/layout_bench.py` measures exactly that.

Declared before measurement: `PASTURE_BLOCK`, and the controls and criterion
in `harness/layout_bench.py` (posted to #246 before any code).
"""

from __future__ import annotations

from strategies import field_rival as fr
from strategies.pasture_first import PastureFirstStrategy

#: The twelve NW tiles nearest the shed after the shed-access tile (4, 4), in
#: the frozen nearest-to-shed order. Its first five are `PASTURE_TILES`' own.
PASTURE_BLOCK = tuple(fr._quadrant_tiles("NW")[1:13])

#: Everything else we will ever own, nearest-to-shed first, NW before NE
#: before SW -- the frozen rule with this block removed instead of the frozen one.
CROP_TILES = tuple(
    t for q in fr.OWNED_QUADRANTS for t in fr._quadrant_tiles(q) if t not in PASTURE_BLOCK
)


class NwPastureStrategy(PastureFirstStrategy):
    """`pasture_first` with the pasture block inside NW."""

    name = "nw_pasture"
    benchmark = False

    #: Class attributes so a test can read the declared layout off the agent
    #: itself, in the shape LEAD_TILES, HERDER_DAY and FRONT_RAMP use.
    PASTURE_BLOCK = PASTURE_BLOCK
    CROP_TILES = CROP_TILES

    def layout(self):
        """This arm's block and crop tiles; the count rules are inherited."""
        return (self.PASTURE_BLOCK, self.CROP_TILES)


STRATEGY = NwPastureStrategy
```

- [ ] **Step 4: Run green** — the whole suite, because the no-crash gate (`tests/test_no_crash.py`) now plays `nw_pasture` through full games under strict mode.

Run: `.venv/bin/python -m pytest -q -n auto`
Expected: all pass, including the no-crash gate for `nw_pasture`.

- [ ] **Step 5: Commit**

```bash
git add strategies/nw_pasture.py tests/test_nw_pasture.py
git commit -m "nw_pasture: the pasture block inside NW, on the front ramp (#246)

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 4: The declared bench `harness/layout_bench.py`

**Files:**
- Create: `harness/layout_bench.py`
- Test: `tests/test_layout_bench.py`
- Reference (read, do not modify): `harness/front_bench.py` — the #244 bench this one reuses; `harness/rival_bench.py` (`criterion`, `format_rows`, `format_external`, `paired_external_rows`, `first_day_at_or_above`); `harness/farm_census.py` (`aggregate` returns `pasture_series`, a list of `(day, pasture_total)` per turn).

**Interfaces:**
- Consumes: `front_bench.mechanism_reading(turns, owned_day, crop_day)` and `front_bench.mechanism_deltas(contender, champion)` (both pure; deltas has `owned_delta`, `placed_delta`, `shed_delta`, `planted_gap`); `rival_bench.first_day_at_or_above(series, threshold)`; `farm_census.aggregate(turns)["pasture_series"]`; `strategies.load("nw_pasture")` (Task 3); `FieldRivalStrategy.layout` / `land_target` hooks (Tasks 1-2); `fr._ramp`.
- Produces: the declared constants; `mechanism_reading(turns, placed_day=PLACED_DAY, crop_day=CROP_DAY) -> dict` = front_bench's keys plus `first_day_pasture_standing`; `mechanism_deltas` (re-exported from front_bench); `mechanism_ok(deltas) -> bool` on `placed_delta >= PLACED_DELTA_BAR`; `crop_line_ok(deltas) -> bool` on `planted_gap <= PLANTED_GAP_BAR`; `format_mechanism(rows) -> str`; `arm_b_class() -> type` (unregistered subclass of `nw_pasture` whose `land_target` reads `LAND_RAMP_B`); live runners `run_controls`, `run_criterion`, `run_recorded`, `main` with `--controls/--criterion/--recorded`, exit 0/1/2.

- [ ] **Step 1: Write the failing tests** — `tests/test_layout_bench.py`:

```python
"""The NW-pasture experiment's declared constants and the pure parts it adds.

The verdict, formatting and paired external rows are `harness.rival_bench`'s,
the census readings `harness.farm_census`'s and the day readings
`harness.front_bench`'s -- imported, not copied. New here: the mechanism is
read on head PLACED at day 9 (the number #244's control should have been on,
now that the block is inside NW and nothing land-caps it), and the first day
with eight pasture tiles standing is recorded beside it.
"""

from __future__ import annotations

import pytest

from harness import front_bench as fb
from harness import layout_bench as lb
from harness import rival_bench as rb


def test_the_declared_constants():
    assert lb.CONTENDER == "nw_pasture" and lb.CHAMPION == "third_herder"
    assert lb.SEEDS == tuple(range(880, 896))
    assert lb.CONTROL_SEED == 880
    assert lb.CHAMPION_BAR == 0.60 and lb.ANCHOR_BAR == 0.90
    assert lb.PLACED_DAY == 9 and lb.CROP_DAY == 16
    assert lb.PLACED_DELTA_BAR == 4
    assert lb.PLANTED_GAP_BAR == 5
    assert lb.PASTURE_STANDING == 8
    assert lb.ARM_B == "early_land"
    assert lb.LAND_RAMP_B == ((0, 1), (6, 2), (16, 3))


def test_the_seeds_are_fresh_against_every_range_already_spent():
    spent = set(range(100, 116)) | set(range(200, 216)) | set(range(300, 332)) \
        | set(range(400, 416)) | set(range(500, 516)) | set(range(600, 616)) \
        | set(range(700, 704)) | set(range(800, 880))
    assert not spent & set(lb.SEEDS)


def test_the_verdict_logic_is_rival_benchs_and_the_readers_are_front_benchs():
    assert lb.criterion is rb.criterion
    assert lb.format_rows is rb.format_rows
    assert lb.format_external is rb.format_external
    assert lb.paired_external_rows is rb.paired_external_rows
    assert lb.mechanism_deltas is fb.mechanism_deltas


def _census(head_placed, head_held, planted, pasture):
    return {"head_placed": head_placed, "head_held": head_held, "planted_tiles": planted,
            "structures": {"PASTURE": {"total": pasture, "occupied": 0, "empty": pasture}}}


def _turns():
    # Two turns a day for days 0..16: eight pasture stand from day 3, head is
    # placed on it from day 5, nothing waits in the shed after day 6.
    turns = []
    for day in range(17):
        pasture = 5 if day < 3 else 8
        placed = 0 if day < 5 else 8
        held = 2 if day in (5, 6) else 0
        turns.append((day, _census(placed, held, 13, pasture)))
        turns.append((day, _census(placed, held, 13 if day < 16 else 30, pasture)))
    return turns


def test_reading_takes_the_closing_board_and_the_first_day_the_block_stood():
    r = lb.mechanism_reading(_turns())
    assert r["head_placed_at_day"] == 8 and r["head_held_at_day"] == 0
    assert r["head_owned_at_day"] == 8
    assert r["planted_tiles_at_crop_day"] == 30
    assert r["turns_with_head_in_shed"] == 4     # days 5, 6 x 2 turns
    assert r["first_day_pasture_standing"] == 3


def test_reading_reports_none_when_the_block_never_stood():
    turns = [(d, _census(0, 0, 13, 5)) for d in range(17)]
    assert lb.mechanism_reading(turns)["first_day_pasture_standing"] is None


def test_reading_raises_when_the_game_never_reached_a_declared_day():
    with pytest.raises(ValueError, match="day 16"):
        lb.mechanism_reading(_turns()[:20])


def test_mechanism_gates_on_placed_head_and_the_crop_line_on_the_gap():
    c = {"head_owned_at_day": 10, "head_placed_at_day": 8, "planted_tiles_at_crop_day": 30,
         "turns_with_head_in_shed": 90}
    k = {"head_owned_at_day": 4, "head_placed_at_day": 4, "planted_tiles_at_crop_day": 30,
         "turns_with_head_in_shed": 212}
    d = lb.mechanism_deltas(c, k)
    assert d == {"owned_delta": 6, "placed_delta": 4, "shed_delta": 122, "planted_gap": 0}
    assert lb.mechanism_ok(d) is True and lb.crop_line_ok(d) is True
    assert lb.mechanism_ok(dict(d, placed_delta=3)) is False
    # Owned head no longer gates: #244's control passed on it and the arm lost.
    assert lb.mechanism_ok(dict(d, placed_delta=4, owned_delta=0)) is True
    assert lb.crop_line_ok(dict(d, planted_gap=6)) is False


def test_arm_b_buys_ne_on_day_six_and_is_not_registered():
    from strategies import REGISTRY, field_rival as fr
    from strategies.nw_pasture import NwPastureStrategy
    cls = lb.arm_b_class()
    assert issubclass(cls, NwPastureStrategy)
    arm = cls()
    assert arm.land_target(5) == 1 and arm.land_target(6) == 2 and arm.land_target(16) == 3
    assert arm.land_target(11) == 2 and fr.land_target(11) == 1     # the frozen ramp waits for 12
    assert arm.layout() == NwPastureStrategy().layout()              # the block rides along
    assert lb.ARM_B not in REGISTRY and lb.CONTENDER in REGISTRY


def test_format_mechanism_prints_both_sides_with_the_first_day_column():
    r = {"head_owned_at_day": 10, "head_placed_at_day": 8, "head_held_at_day": 2,
         "planted_tiles_at_crop_day": 30, "turns_with_head_in_shed": 90, "turns": 719,
         "max_head_placed": 12, "first_day_pasture_standing": 3}
    text = lb.format_mechanism([("nw_pasture", r), ("third_herder", dict(r, first_day_pasture_standing=None))])
    lines = text.splitlines()
    assert len(lines) == 3 and lines[1].startswith("nw_pasture") and "90/719" in lines[1]
    assert lines[2].rstrip().endswith("never")
```

- [ ] **Step 2: Run them and quote the failure**

Run: `.venv/bin/python -m pytest -q tests/test_layout_bench.py`
Expected: collection error `ModuleNotFoundError: No module named 'harness.layout_bench'`.

- [ ] **Step 3: Minimal implementation** — `harness/layout_bench.py`:

```python
"""NW pasture block: does opening the pasture before the head beat the champion?

    python -m harness.layout_bench --controls     # the three declared controls
    python -m harness.layout_bench --criterion    # 16 seeds: champion, anchors, the external limb
    python -m harness.layout_bench --recorded     # arm B (recorded, not gated)
    python -m harness.layout_bench                # controls then criterion

Declared before any code (#246's declaration comment): seeds 880-895 --
fresh; 100-115, 200-215, 300-331, 400-415, 500-515, 600-615, 700-703 and
800-879 are spent -- sides alternated by list position
(`harness.triage.head_to_head_rate`); PROMOTE only at >= 60% of 16 vs the
champion `third_herder` AND >= 90% vs each DEFAULT_ANCHOR AND, for each
`external_pool.EXTERNAL_ANCHORS` member, no fewer wins than the champion on
the same seeds in the same run (#152's paired limb); a tie is not a win.
Controls run first and a failed control voids the run -- arm B is then not
scored either. Exit codes: 0 PROMOTE, 1 REJECTED, 2 VOID. Runs under
ROBRICULTURE_STRICT=1.

The verdict, the row and external formatting and the paired external rows
are `harness.rival_bench`'s; the census is `harness.farm_census`'; the day
readings and the deltas are `harness.front_bench`'s -- imported rather than
re-implemented.

**What the mechanism control reads, and why.** #244's control read head
OWNED at day 9 because the frozen layout land-capped pasture at five tiles
until day 12; it passed (+6) and the arm lost, because the head it bought
sat in the shed. With the block inside NW nothing caps it, so this control
reads head PLACED at `PLACED_DAY` as a paired delta -- the number the arm
exists to move -- and records owned head, shed-turns and the first day
`PASTURE_STANDING` tiles stood beside it.
"""

from __future__ import annotations

import argparse
import os

from harness.evolve import DEFAULT_ANCHORS
from harness.farm_census import aggregate
from harness.front_bench import mechanism_deltas  # noqa: F401  -- re-exported on purpose
from harness.front_bench import mechanism_reading as _front_reading
from harness.rival_bench import (  # noqa: F401  -- re-exported on purpose
    criterion,
    first_day_at_or_above,
    format_external,
    format_rows,
    paired_external_rows,
)
from strategies import field_rival as fr

CONTENDER = "nw_pasture"
CHAMPION = "third_herder"

#: Fresh. 100-115 and 200-215 (#202), 300-331 (#211), 400-415 (#219), 500-515
#: (#222), 600-615 (#225), 700-703 (#229/#234), 800-815 (#237), 816-831
#: (#239), 832-847 (#239 A vs C), 848-863 (#152 baseline) and 864-879 (#244)
#: are spent.
SEEDS = tuple(range(880, 896))
CHAMPION_BAR = 0.60
ANCHOR_BAR = 0.90
CONTROL_SEED = 880

#: Arm B: the contender with NE bought on day 6 instead of 12 -- the day
#: FRONT_RAMP steps to twelve head. If B beats A, the pre-day-12 crop cost
#: was the binding term, not the block. Never registered, so it cannot be
#: promoted or packaged by accident.
ARM_B = "early_land"
LAND_RAMP_B = ((0, 1), (6, 2), (16, 3))

#: The day placed head is read: the ceiling has every head placed by day 9
#: (#234), and #244 read owned head on the same day, so the two benches
#: compare turn for turn.
PLACED_DAY = 9

#: The day the crop line is read: the last step of `HAND_RAMP`, as #239 and #244.
CROP_DAY = 16

#: Paired deltas against the champion on `CONTROL_SEED`. Placed head is the
#: mechanism (#244's arm owned 10 by day 9 under the cap; the champion places
#: 4); the crop gap is the cost the arm is allowed to pay before it stops
#: being one change.
PLACED_DELTA_BAR = 4
PLANTED_GAP_BAR = 5

#: Recorded, not gated: the first day this many pasture tiles stand. The
#: champion's is day 12 (NE); the contender's must be earlier or the block
#: is not being built.
PASTURE_STANDING = 8


def mechanism_reading(turns, placed_day=PLACED_DAY, crop_day=CROP_DAY):
    """One side's numbers off one game's census series ``[(day, census), ...]``:
    `front_bench`'s reading at `placed_day` plus the first day
    `PASTURE_STANDING` tiles stood (``None`` if never). Raises, as
    `front_bench` does, when a declared day was never reached."""
    reading = _front_reading(turns, placed_day, crop_day)
    series = aggregate(turns)["pasture_series"]
    reading["first_day_pasture_standing"] = first_day_at_or_above(series, PASTURE_STANDING)
    return reading


def mechanism_ok(deltas):
    """Control (ii): the arm actually STOOD UP head the champion had not."""
    return deltas["placed_delta"] >= PLACED_DELTA_BAR


def crop_line_ok(deltas):
    """Control (iii): the crop line did not collapse (or run away)."""
    return deltas["planted_gap"] <= PLANTED_GAP_BAR


def format_mechanism(rows):
    """One line per side, contender above champion."""
    lines = [f"{'side':<16} {'placed @9':>10} {'owned @9':>9} {'held @9':>8} "
             f"{'shed turns':>12} {'planted @16':>12} {'max head':>9} {'8 past by':>10}"]
    for label, r in rows:
        first = r["first_day_pasture_standing"]
        lines.append(f"{label:<16} {r['head_placed_at_day']:>10} {r['head_owned_at_day']:>9} "
                     f"{r['head_held_at_day']:>8} "
                     f"{r['turns_with_head_in_shed']:>5}/{r['turns']:<6} "
                     f"{r['planted_tiles_at_crop_day']:>12} {r['max_head_placed']:>9} "
                     f"{'never' if first is None else f'day {first}':>10}")
    return "\n".join(lines)


def arm_b_class():
    """`nw_pasture` buying NE on day 6, built in-process and never registered."""
    from strategies import load

    def land_target(self, day):
        return fr._ramp(LAND_RAMP_B, day)

    return type("EarlyLand", (load(CONTENDER),), {"land_target": land_target})


# --- live games -------------------------------------------------------------

def _arm_b_agents(name):  # pragma: no cover
    """`head_to_head_rate`'s `agents` hook, resolving arm B by name."""
    from harness.triage import _default_agents
    from kaggisim.strategy import make_agent
    arm_b = arm_b_class()
    default_agents = _default_agents()

    def agents(who):
        return make_agent(arm_b()) if who == name else default_agents(who)
    return agents


def run_controls(seed=CONTROL_SEED):  # pragma: no cover
    """The three declared controls, in order. A failure voids the run."""
    os.environ.setdefault("ROBRICULTURE_STRICT", "1")
    from harness.farm_census import census_series
    from harness.tournament import play_rewards
    from kaggisim.strategy import make_agent
    from strategies import load
    out = {}

    # 1. identity: every seam off must be `dense_farm` to the value (#244's
    #    control, two seams deeper).
    off = type("Off", (load(CONTENDER),),
               {"herd_preference": lambda self, obs: None,
                "pasture_count": lambda self, day, animals: None,
                "herd_target": lambda self, day: None,
                "livestock_workers": lambda self, day: None,
                "layout": lambda self: None,
                "land_target": lambda self, day: None})
    base = play_rewards(make_agent(load("dense_farm")()), make_agent(load("dense_farm")()), seed)
    got = play_rewards(make_agent(off()), make_agent(load("dense_farm")()), seed)
    precondition_ok = base[0] > 0
    out["identity"] = {"ok": got == base and precondition_ok, "base": base, "got": got,
                       "precondition_ok": precondition_ok}

    # 2 & 3. paired deltas off the same game.
    ours, theirs = census_series(make_agent(load(CONTENDER)()),
                                 make_agent(load(CHAMPION)()), seed)
    contender, champion = mechanism_reading(ours), mechanism_reading(theirs)
    deltas = mechanism_deltas(contender, champion)
    out["mechanism"] = {"ok": mechanism_ok(deltas), "deltas": deltas,
                        "contender": contender, "champion": champion}
    out["crop_line"] = {"ok": crop_line_ok(deltas), "deltas": deltas}
    return out


def run_criterion(seeds=SEEDS):  # pragma: no cover
    """The declared criterion: the champion row, the anchors, and the paired
    external limb -- the champion played on the same seeds in this run."""
    os.environ.setdefault("ROBRICULTURE_STRICT", "1")
    from harness.triage import head_to_head_rate
    champion_row = head_to_head_rate(CONTENDER, CHAMPION, seeds)
    anchor_rows = [head_to_head_rate(CONTENDER, a, seeds) for a in DEFAULT_ANCHORS]
    pairs = paired_external_rows(CONTENDER, CHAMPION, seeds)
    return champion_row, anchor_rows, pairs


def run_recorded(seeds=SEEDS):  # pragma: no cover
    """Recorded, never gated: arm B against the champion."""
    os.environ.setdefault("ROBRICULTURE_STRICT", "1")
    from harness.triage import head_to_head_rate
    return [head_to_head_rate(ARM_B, CHAMPION, seeds, agents=_arm_b_agents(ARM_B))]


def main(argv=None):  # pragma: no cover
    os.environ.setdefault("ROBRICULTURE_STRICT", "1")
    ap = argparse.ArgumentParser(description="NW pasture block: the pasture opened before the head")
    ap.add_argument("--controls", action="store_true")
    ap.add_argument("--criterion", action="store_true")
    ap.add_argument("--recorded", action="store_true", help="arm B (recorded, not gated)")
    args = ap.parse_args(argv)

    if args.recorded:
        print(format_rows(run_recorded()))
        print(f"recorded, not gated: arm B ({ARM_B}: NE bought on day 6) vs {CHAMPION}")
        return 0

    do_controls = args.controls or not args.criterion
    do_criterion = args.criterion or not args.controls

    if do_controls:
        ctl = run_controls()
        print(f"control identity: {'OK' if ctl['identity']['ok'] else 'FAIL -- RUN VOID'}"
              f"  {ctl['identity']}")
        d = ctl["mechanism"]["deltas"]
        print(f"control mechanism: {'OK' if ctl['mechanism']['ok'] else 'FAIL -- RUN VOID'}  "
              f"(declared: head placed at day {PLACED_DAY} minus the champion's >= "
              f"{PLACED_DELTA_BAR})  placed_delta={d['placed_delta']}  recorded: "
              f"owned_delta={d['owned_delta']} shed_delta={d['shed_delta']}")
        print(f"control crop line: {'OK' if ctl['crop_line']['ok'] else 'FAIL -- RUN VOID'}  "
              f"(declared: |planted tiles at day {CROP_DAY} - the champion's| <= "
              f"{PLANTED_GAP_BAR})  planted_gap={d['planted_gap']}")
        print(format_mechanism([(CONTENDER, ctl["mechanism"]["contender"]),
                                (CHAMPION, ctl["mechanism"]["champion"])]))
        if not all(r["ok"] for r in ctl.values()):
            print("a control failed: the run is VOID and arm B is NOT scored")
            return 2

    if do_criterion:
        champion_row, anchor_rows, pairs = run_criterion()
        print(format_rows([champion_row] + anchor_rows))
        print(format_external(pairs))
        v = criterion(champion_row, anchor_rows, CHAMPION_BAR, ANCHOR_BAR, external_pairs=pairs)
        print(f"champion {v['champion_rate']:.1%} (bar {CHAMPION_BAR:.0%}); failing limbs: "
              f"{v['failing'] or 'none'} -> {'PROMOTE' if v['passed'] else 'REJECTED'}")
        return 0 if v["passed"] else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run green, with coverage**

Run: `.venv/bin/python -m pytest -q -n auto --cov --cov-branch --cov-report=term-missing 2>&1 | grep -E "layout_bench|nw_pasture|passed|failed"`
Expected: all pass; `harness/layout_bench.py` and `strategies/nw_pasture.py` at 100% outside the `# pragma: no cover` runners.

- [ ] **Step 5: Commit**

```bash
git add harness/layout_bench.py tests/test_layout_bench.py
git commit -m "layout_bench: #246's declared controls, criterion and arm B

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

## Self-review

- **Spec coverage.** Contender block and crop tiles → Task 3. `layout` seam and helper parameters → Task 1. `land_target` seam and `market_orders(land=)` → Task 2. Arm B class with `LAND_RAMP_B` → Task 4. Bench constants, controls (identity with six seams, placed-head delta, crop gap), criterion with paired externals, exit codes, `first_day_pasture_standing` → Task 4. Tests listed in the spec's Testing section → Tasks 1-4. Full gate and preflight before push → the controller, after the final review.
- **Placeholders.** None: every step carries its code and its expected failure text.
- **Type consistency.** `layout()` returns `(pasture_tiles, crop_tiles)` in Task 1, is answered as `(self.PASTURE_BLOCK, self.CROP_TILES)` in Task 3, and is switched off with `lambda self: None` in Task 4. `active_pastures(..., block=)` / `crop_cluster(..., crops=)` keyword names match between Task 1 and Task 3's test. `land_target(self, day)` returns an int in Task 4's arm B and `None` on the benchmark in Task 2. `mechanism_deltas` keys (`owned_delta`, `placed_delta`, `shed_delta`, `planted_gap`) are `front_bench`'s and are what Task 4's `mechanism_ok` / `crop_line_ok` / `main` read.
