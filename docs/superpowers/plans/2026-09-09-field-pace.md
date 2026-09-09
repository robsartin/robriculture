# field_pace (#252) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Four new seams on the frozen benchmark (`hire_target`, `pivot_day`, `cluster_size`, `capital_reserve`), the contender `field_pace` (third_herder on the field's measured schedule, all eight knobs as one package), and its declared bench `harness/pace_bench.py`.

**Architecture:** Seams in the #202/#237/#246 shape — helpers gain keyword parameters defaulting to the frozen constants, the class gains hooks returning `None`, `act` threads them — so `field_rival` stays byte-identical. The contender answers every hook with a declared constant. The bench reuses `rival_bench`'s verdict/formatting/paired-external machinery and `farm_census`; it adds an absolute shape control read off the contender's own census.

**Tech Stack:** Python 3.12 in `.venv` (`.venv/bin/python`, never a bare python3), pytest `-n auto`, `kaggle-environments` 1.32.7. Spec: `docs/superpowers/specs/2026-09-09-field-pace-design.md`.

## Global Constraints

- Pure TDD: write the failing tests, **run them and quote the failure**, then the minimal code, run green, commit. Every task: `.venv/bin/python -m pytest -q -n auto` green before the commit.
- `strategies/field_rival.py` is the frozen benchmark (#181): every new parameter defaults to the frozen constant; every new hook returns `None` on `FieldRivalStrategy`; no existing assertion in `tests/test_field_rival.py` may change.
- Declared values, verbatim, not to be tuned: `HAND_RAMP_F = ((0, 5), (6, 8), (8, 10), (15, 12))`, `LAND_RAMP_F = ((0, 1), (6, 2), (11, 3))`, `PIVOT_F = 5`, `CAPS_F = {"MELON": 12, "STRAWBERRY": 38, "WHEAT": 24}`, `CLUSTER_F = 6`, `HERD_RAMP_F = ((0, 4), (6, 8), (8, 13))`, `PASTURE_BLOCK_F = tuple(fr._quadrant_tiles("NW")[1:15])`, `RESERVE_F = 0`; bench: `CONTENDER = "field_pace"`, `CHAMPION = "third_herder"`, `SEEDS = tuple(range(896, 912))`, `CONTROL_SEED = 896`, `CHAMPION_BAR = 0.60`, `ANCHOR_BAR = 0.90`, `ARM_B = "crop_pace"`, `SHAPE_DAY = 8`, `CROP_DAY = 12`, `SHAPE_BARS = {"planted": 30, "quadrants": 2, "hands": 8, "head_placed": 8}`, `PLANTED_AT_CROP_DAY_BAR = 45`, `PAYDAY_MONEY = 5000`.
- Never edit `strategies/__init__.py`. Test names `test_<the fact>` with a docstring/comment saying why. Stage by explicit path; never `git add -A`; never stage `.venv` / `external_agents`. Commit messages end with a blank line and `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.
- Live-game code carries `# pragma: no cover` at the `def`; do NOT run the bench's live games — the controller runs the declared bench after review.

---

### Task 1: The `hire_target` and `capital_reserve` seams (market_orders)

**Files:**
- Modify: `strategies/field_rival.py` — `market_orders` signature (~line 339) and its hire block / herd-buy reserve line; `FieldRivalStrategy` hooks after `land_target`; the `market_orders(...)` call in `act`.
- Test: `tests/test_field_rival.py` (append).

**Interfaces:**
- Produces: `market_orders(..., land=None, hire=None, reserve=None)` — `hire` is hands to have today (`None` = frozen `hire_target(day)`), `reserve` is cash held back from the herd (`None` = `CAPITAL_RESERVE`); `FieldRivalStrategy.hire_target(self, day) -> int | None`, `FieldRivalStrategy.capital_reserve(self) -> int | None`; `act` passes `hire=self.hire_target(day), reserve=self.capital_reserve()`.

- [ ] **Step 1: Write the failing tests** — append to `tests/test_field_rival.py`:

```python
# --- #252: the hire and reserve seams, and the frozen rules they default to ---

def test_the_benchmarks_hire_and_reserve_hooks_ask_for_the_frozen_rules():
    # `None` means "the benchmark's own rule", so field_rival stays frozen (#181).
    assert fr.FieldRivalStrategy().hire_target(0) is None
    assert fr.FieldRivalStrategy().hire_target(16) is None
    assert fr.FieldRivalStrategy().capital_reserve() is None


def _hires(day, hands, **kw):
    orders = fr.market_orders(day=day, hour=0, money=50_000, hands=hands, quadrants=1,
                              animals=0, shed={}, seeds={}, empty_plots=0, standing={}, **kw)
    return sum(1 for o in orders if o[0] == "HIRE")


def test_market_orders_with_hire_hires_to_that_crew():
    # Golden pin on the default first: day 0, no hands, the frozen ramp wants 6.
    assert _hires(0, 0) == 6
    assert _hires(0, 0, hire=5) == 5
    assert _hires(0, 4, hire=10) == 6
    assert _hires(0, 6, hire=5) == 0


def _herd_buys(money, **kw):
    orders = fr.market_orders(day=12, hour=1, money=money, hands=8, quadrants=2,
                              animals=0, shed={}, seeds={}, empty_plots=0, standing={}, **kw)
    return sum(1 for o in orders if o[0] == "BUY_ANIMAL")


def test_market_orders_with_reserve_keeps_that_much_back_from_the_herd():
    # Day 12 the frozen ramp wants 8 head. With 2,000 in hand the cow rule buys
    # sheep (500) while budget >= 1,500 and cows (400) below it: the frozen
    # reserve of 1,200 lets one sheep through (2,000 -> 1,500, then 1,000 <
    # 1,200 stops it); no reserve buys sheep, sheep, cow, cow (2,000 -> 1,500
    # -> 1,000 -> 600 -> 200); a reserve equal to the cash buys nothing.
    assert _herd_buys(2_000) == 1
    assert _herd_buys(2_000, reserve=0) == 4
    assert _herd_buys(2_000, reserve=2_000) == 0
```

- [ ] **Step 2: Run them and quote the failure**

Run: `.venv/bin/python -m pytest -q tests/test_field_rival.py -k "hire_and_reserve_hooks or with_hire or with_reserve"`
Expected: 3 failed — `AttributeError: 'FieldRivalStrategy' object has no attribute 'hire_target'`, `TypeError: market_orders() got an unexpected keyword argument 'hire'`, `TypeError: ... 'reserve'`. (If `_herd_buys(2_000) == 1` does not hold on the default, report NEEDS_CONTEXT with the number you got rather than adjusting the fixture.)

- [ ] **Step 3: Minimal implementation**

`market_orders` signature:

```python
def market_orders(day, hour, money, hands, quadrants, animals, shed, seeds,
                  empty_plots, standing=None, caps=None, prefer=None, target=None,
                  land=None, hire=None, reserve=None):
```

Docstring: add after the `land` line: `` `hire`: hands to have working today, or ``None`` for the frozen `hire_target` ramp (#252). `reserve`: cash held back from the herd, or ``None`` for `CAPITAL_RESERVE` (#252). ``

Hire block: `want = max(0, (hire_target(day) if hire is None else hire) - hands)`.
Herd block: before the `for _ in range(...)` loop add `keep = CAPITAL_RESERVE if reserve is None else reserve`, and the break becomes `if budget - cost < keep:`.

Hooks, after `land_target` in `FieldRivalStrategy`:

```python
    def hire_target(self, day):
        """Hands to have working on `day`, or ``None`` for the frozen
        `hire_target` ramp. A seam for contenders (#252); on the benchmark it
        never fires, so its crew schedule stays frozen (#181)."""
        return None

    def capital_reserve(self):
        """Cash held back from the herd, or ``None`` for `CAPITAL_RESERVE`. A
        seam for contenders (#252); never fires on the benchmark."""
        return None
```

`act`: the `market_orders(...)` call gains `hire=self.hire_target(day), reserve=self.capital_reserve()` after `land=self.land_target(day)`.

- [ ] **Step 4: Run green** — `.venv/bin/python -m pytest -q -n auto`.
- [ ] **Step 5: Commit**

```bash
git add strategies/field_rival.py tests/test_field_rival.py
git commit -m "field_rival: hire and reserve seams, frozen by default (#252)

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 2: The `pivot_day` and `cluster_size` seams (crop rule and clusters)

**Files:**
- Modify: `strategies/field_rival.py` — `crop_for_day` (~line 56), `crop_for_plot` (~line 97), `crop_cluster` (~line 205), `market_orders` (`pivot=None`, threaded to `crop_for_plot`), `FieldRivalStrategy` hooks, `act`.
- Test: `tests/test_field_rival.py` (append).

**Interfaces:**
- Produces: `crop_for_day(day, season_days=SEASON_DAYS, pivot=PIVOT_DAY)`; `crop_for_plot(day, standing, season_days=SEASON_DAYS, caps=None, pivot=None)` (`None` = `PIVOT_DAY`); `crop_cluster(worker, workers=LIVESTOCK_WORKERS, crops=CROP_TILES, cluster=CLUSTER)`; `market_orders(..., pivot=None)`; hooks `pivot_day(self) -> int | None`, `cluster_size(self) -> int | None`; `act` reads `pivot = self.pivot_day()`, `cluster = self.cluster_size() or CLUSTER` once per turn and threads `pivot=pivot` into both `crop_for_plot` calls (the per-worker one and via `market_orders`) and `cluster=cluster` into both `crop_cluster` calls.

- [ ] **Step 1: Write the failing tests** — append:

```python
# --- #252: the pivot and cluster seams, and the frozen rules they default to ---

def test_the_benchmarks_pivot_and_cluster_hooks_ask_for_the_frozen_rules():
    assert fr.FieldRivalStrategy().pivot_day() is None
    assert fr.FieldRivalStrategy().cluster_size() is None


def test_crop_for_day_with_a_pivot_swings_to_strawberry_on_that_day():
    # Golden pin on the default: melon on day 9, strawberry on day 10.
    assert fr.crop_for_day(9) == "MELON" and fr.crop_for_day(10) == "STRAWBERRY"
    assert fr.crop_for_day(4, pivot=5) == "MELON"
    assert fr.crop_for_day(5, pivot=5) == "STRAWBERRY"
    assert fr.crop_for_plot(5, {}, pivot=5) == "STRAWBERRY"
    assert fr.crop_for_plot(5, {}) == "MELON"


def test_market_orders_with_a_pivot_buys_that_days_seed():
    orders = fr.market_orders(day=5, hour=1, money=50_000, hands=6, quadrants=1, animals=0,
                              shed={}, seeds={}, empty_plots=4, standing={}, pivot=5)
    assert ["BUY_SEED", "STRAWBERRY", 4] in orders
    orders = fr.market_orders(day=5, hour=1, money=50_000, hands=6, quadrants=1, animals=0,
                              shed={}, seeds={}, empty_plots=4, standing={})
    assert ["BUY_SEED", "MELON", 4] in orders


def test_crop_cluster_with_a_cluster_size_slices_that_many_tiles():
    crops = tuple((x, 9) for x in range(30))
    assert fr.crop_cluster(0, crops=crops, cluster=6) == crops[0:6]
    assert fr.crop_cluster(5, crops=crops, cluster=6) == crops[18:24]      # slot 3
    assert fr.crop_cluster(5, crops=crops) == crops[12:16]                 # frozen 4
```

- [ ] **Step 2: Run them and quote the failure**

Run: `.venv/bin/python -m pytest -q tests/test_field_rival.py -k "pivot_and_cluster_hooks or with_a_pivot or with_a_cluster_size"`
Expected: 4 failed — `AttributeError: ... 'pivot_day'`, `TypeError: crop_for_day() got an unexpected keyword argument 'pivot'`, `TypeError: market_orders() ... 'pivot'`, `TypeError: crop_cluster() ... 'cluster'`.

- [ ] **Step 3: Minimal implementation**

```python
def crop_for_day(day: int, season_days: int = SEASON_DAYS, pivot: int = PIVOT_DAY):
    """The crop this farm plants on `day`, or ``None`` past the horizon.

    Melon before the pivot, strawberry after — the measured field's whole crop
    story. The horizon gate is the champion's own (`hired_hands.plantable`), so a
    seed is never spent on a plant that cannot reach first yield in time.
    `pivot` is the swing day (#252); the module default is the frozen `PIVOT_DAY`.
    """
    crop = "MELON" if day < pivot else "STRAWBERRY"
```

(rest of the body unchanged.) `crop_for_plot(day, standing, season_days=SEASON_DAYS, caps=None, pivot=None)` calls `crop_for_day(day, season_days, PIVOT_DAY if pivot is None else pivot)`; docstring gains one sentence: "`pivot` is the swing day for a contender (#252); ``None`` keeps the frozen one." `crop_cluster(worker, workers=LIVESTOCK_WORKERS, crops=CROP_TILES, cluster=CLUSTER)` slices `crops[slot * cluster:(slot + 1) * cluster]`; docstring: "`cluster` is tiles per crop worker (#252); the module default is the frozen `CLUSTER`." `market_orders` gains `pivot=None` (after `reserve`) and calls `crop_for_plot(day, standing, caps=caps, pivot=pivot)`; docstring line: `` `pivot`: the crop swing day, or ``None`` for the frozen `PIVOT_DAY` (#252). ``

Hooks after `capital_reserve`:

```python
    def pivot_day(self):
        """The day the crop line swings from melon to strawberry, or ``None``
        for the frozen `PIVOT_DAY`. A seam for contenders (#252); never fires
        on the benchmark."""
        return None

    def cluster_size(self):
        """Tiles per crop worker, or ``None`` for the frozen `CLUSTER`. A seam
        for contenders (#252); never fires on the benchmark."""
        return None
```

`act`: after `block, crops = ...` add `pivot = self.pivot_day()` and `cluster = self.cluster_size() or CLUSTER`; the per-worker line becomes `crop = crop_for_plot(day, standing, caps=self.CAPS, pivot=pivot)`; both `crop_cluster(i, workers, crops=crops)` calls gain `, cluster=cluster`; the `market_orders(...)` call gains `pivot=pivot`.

- [ ] **Step 4: Run green** — `.venv/bin/python -m pytest -q -n auto`.
- [ ] **Step 5: Commit**

```bash
git add strategies/field_rival.py tests/test_field_rival.py
git commit -m "field_rival: pivot and cluster seams, frozen by default (#252)

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 3: The contender `field_pace`

**Files:**
- Create: `strategies/field_pace.py`
- Test: `tests/test_field_pace.py`

**Interfaces:**
- Consumes: Tasks 1-2's hooks; `strategies.third_herder.ThirdHerderStrategy`; `fr._quadrant_tiles`, `fr.OWNED_QUADRANTS`, `fr._ramp`, `fr.animal_target`, `fr.PASTURE_TILES`.
- Produces: module constants `HAND_RAMP_F, LAND_RAMP_F, PIVOT_F, CAPS_F, CLUSTER_F, HERD_RAMP_F, PASTURE_BLOCK_F, CROP_TILES_F, RESERVE_F`; `FieldPaceStrategy(ThirdHerderStrategy)` with `name = "field_pace"`, `benchmark = False`, `CAPS = CAPS_F`, class attributes for every constant, hooks `hire_target`, `land_target`, `pivot_day`, `cluster_size`, `capital_reserve`, `herd_target`, `layout`, and `pasture_count`; `STRATEGY = FieldPaceStrategy`.

- [ ] **Step 1: Write the failing tests** — `tests/test_field_pace.py`:

```python
"""field_pace: the field's schedule on third_herder, as one package (#252).

A census of third_herder vs pilkwang on spent seeds 864-867 read the field's
schedule straight off both boards: 5 hands, 4 head and no cash reserve from
day 0, strawberry from day 5, NE on day 6, 10 hands and 13 head by day 8, SW
on day 11, 62 planted by day 12, 14 pasture tiles inside NW. #244 and #246
showed one knob at a time is cash-limited; this arm moves all of them at once,
every value declared on #252, none tuned.
"""

from __future__ import annotations

from strategies import field_rival as fr
from strategies import field_pace as fp
from strategies.third_herder import ThirdHerderStrategy


def test_the_declared_constants():
    assert fp.HAND_RAMP_F == ((0, 5), (6, 8), (8, 10), (15, 12))
    assert fp.LAND_RAMP_F == ((0, 1), (6, 2), (11, 3))
    assert fp.PIVOT_F == 5
    assert fp.CAPS_F == {"MELON": 12, "STRAWBERRY": 38, "WHEAT": 24}
    assert fp.CLUSTER_F == 6
    assert fp.HERD_RAMP_F == ((0, 4), (6, 8), (8, 13))
    assert fp.PASTURE_BLOCK_F == tuple(fr._quadrant_tiles("NW")[1:15])
    assert fp.RESERVE_F == 0
    s = fp.FieldPaceStrategy
    assert s.name == "field_pace" and s.benchmark is False and s.CAPS == fp.CAPS_F
    for attr in ("HAND_RAMP_F", "LAND_RAMP_F", "PIVOT_F", "CLUSTER_F", "HERD_RAMP_F",
                 "PASTURE_BLOCK_F", "CROP_TILES_F", "RESERVE_F"):
        assert getattr(s, attr) == getattr(fp, attr), attr


def test_every_hook_answers_with_the_declared_schedule():
    s = fp.FieldPaceStrategy()
    assert [s.hire_target(d) for d in (0, 5, 6, 8, 15, 29)] == [5, 5, 8, 10, 12, 12]
    assert [s.land_target(d) for d in (0, 5, 6, 11, 29)] == [1, 1, 2, 3, 3]
    assert s.pivot_day() == 5 and s.cluster_size() == 6 and s.capital_reserve() == 0
    assert [s.herd_target(d) for d in (0, 6, 8, 29)] == [4, 8, 13, 13]
    assert s.layout() == (fp.PASTURE_BLOCK_F, fp.CROP_TILES_F)


def test_the_herd_ramp_never_asks_for_fewer_head_than_the_frozen_ramp():
    s = fp.FieldPaceStrategy()
    for day in range(fr.SEASON_DAYS):
        assert s.herd_target(day) >= fr.animal_target(day), day


def test_the_block_is_fourteen_nw_tiles_keeping_the_frozen_shed_prefix():
    assert len(fp.PASTURE_BLOCK_F) == 14 and len(set(fp.PASTURE_BLOCK_F)) == 14
    assert all(fr.quadrant_of(x, y) == "NW" for x, y in fp.PASTURE_BLOCK_F)
    assert (4, 4) not in fp.PASTURE_BLOCK_F
    assert fp.PASTURE_BLOCK_F[:5] == fr.PASTURE_TILES[:5]


def test_crop_tiles_are_the_frozen_rule_with_the_block_removed():
    owned = [t for q in fr.OWNED_QUADRANTS for t in fr._quadrant_tiles(q)]
    assert not (set(fp.CROP_TILES_F) & set(fp.PASTURE_BLOCK_F))
    assert set(fp.CROP_TILES_F) | set(fp.PASTURE_BLOCK_F) == set(owned)
    assert fp.CROP_TILES_F[0] == (4, 4)


def test_pasture_count_caps_at_its_own_block_and_floors_at_its_own_ramp():
    # pasture_first caps at the frozen twelve (#246's deferred minor); this arm
    # runs fourteen tiles and must be allowed to stand them all.
    s = fp.FieldPaceStrategy()
    assert s.pasture_count(0, 0) == 4               # the ramp asks 4 on day 0
    assert s.pasture_count(8, 0) == 13
    assert s.pasture_count(8, 12) == 14             # placed + lead 3, capped at 14
    assert s.pasture_count(29, 14) == 14


def test_it_is_a_registered_contender_built_on_third_herder():
    from strategies import REGISTRY, load
    assert "field_pace" in REGISTRY and load("field_pace") is fp.FieldPaceStrategy
    assert issubclass(fp.FieldPaceStrategy, ThirdHerderStrategy)
    s = fp.FieldPaceStrategy()
    assert s.livestock_workers(8) == ThirdHerderStrategy().livestock_workers(8)
    assert fp.FieldPaceStrategy.LEAD_TILES == ThirdHerderStrategy.LEAD_TILES
    assert fp.FieldPaceStrategy.THRESHOLD == ThirdHerderStrategy.THRESHOLD
```

- [ ] **Step 2: Run them and quote the failure** — `.venv/bin/python -m pytest -q tests/test_field_pace.py`; expected: collection `ImportError: cannot import name 'field_pace' from 'strategies'`.

- [ ] **Step 3: Minimal implementation** — `strategies/field_pace.py`:

```python
"""field_pace: the field's schedule on third_herder, as one package (#252).

A census of `third_herder` vs `pilkwang_structured_economic_policy` on spent
seeds 864-867 read the field's schedule straight off both boards (medians):
5 hands, 4 head and no cash reserve from day 0; strawberry from day 5; NE on
day 6 with 8 hands; 10 hands, 37 planted and 13 head by day 8; SW on day 11;
62 planted (38 strawberry, 24 wheat) by day 12; 14 pasture tiles inside NW;
12 hands by day 15. Closing money 128,904 to our 46,228 on seed 864.

#244 fronted the herd alone and #246 opened the pasture alone; both were
cash-limited before the melon payday on day 10. The field's edge is that it
spends every coin on growth from day 0, on every knob at once. This arm moves
them together -- hands, land, crop pivot, crop caps, tiles per hand, herd,
pasture block and cash reserve -- through the seams on the frozen benchmark
(#181, #202, #237, #246, #252), every value the median above and none tuned.
Inherited unchanged: the third herder from day 8, the lead of 3, #219's cow
rule, the benchmark's sell and feed rules.

Declared before measurement: every constant below, and the controls and
criterion in `harness/pace_bench.py` (posted to #252 before any code).
"""

from __future__ import annotations

from strategies import field_rival as fr
from strategies.third_herder import ThirdHerderStrategy

HAND_RAMP_F = ((0, 5), (6, 8), (8, 10), (15, 12))
LAND_RAMP_F = ((0, 1), (6, 2), (11, 3))
PIVOT_F = 5
CAPS_F = {"MELON": 12, "STRAWBERRY": 38, "WHEAT": 24}
CLUSTER_F = 6
HERD_RAMP_F = ((0, 4), (6, 8), (8, 13))
RESERVE_F = 0

#: Fourteen NW tiles nearest the shed after the shed-access tile (4, 4); the
#: first five are the frozen block's own, so the herders' shed walk is unchanged.
PASTURE_BLOCK_F = tuple(fr._quadrant_tiles("NW")[1:15])

#: The frozen crop rule with this block removed: NW first, then NE, then SW.
CROP_TILES_F = tuple(
    t for q in fr.OWNED_QUADRANTS for t in fr._quadrant_tiles(q) if t not in PASTURE_BLOCK_F
)


class FieldPaceStrategy(ThirdHerderStrategy):
    """`third_herder` on the field's measured schedule."""

    name = "field_pace"
    benchmark = False

    CAPS = CAPS_F
    HAND_RAMP_F = HAND_RAMP_F
    LAND_RAMP_F = LAND_RAMP_F
    PIVOT_F = PIVOT_F
    CLUSTER_F = CLUSTER_F
    HERD_RAMP_F = HERD_RAMP_F
    PASTURE_BLOCK_F = PASTURE_BLOCK_F
    CROP_TILES_F = CROP_TILES_F
    RESERVE_F = RESERVE_F

    def hire_target(self, day):
        return fr._ramp(self.HAND_RAMP_F, day)

    def land_target(self, day):
        return fr._ramp(self.LAND_RAMP_F, day)

    def pivot_day(self):
        return self.PIVOT_F

    def cluster_size(self):
        return self.CLUSTER_F

    def capital_reserve(self):
        return self.RESERVE_F

    def herd_target(self, day):
        """The field's herd ramp, never fewer head than the frozen ramp asks."""
        return max(fr._ramp(self.HERD_RAMP_F, day), fr.animal_target(day))

    def layout(self):
        return (self.PASTURE_BLOCK_F, self.CROP_TILES_F)

    def pasture_count(self, day, animals):
        """Tiles to keep in play: the lead ahead of placed head, never fewer
        than this arm's ramp, never more than this arm's own block."""
        return min(len(self.PASTURE_BLOCK_F),
                   max(animals + self.LEAD_TILES, self.herd_target(day)))


STRATEGY = FieldPaceStrategy
```

- [ ] **Step 4: Run green** — the whole suite (the no-crash gate now plays `field_pace`): `.venv/bin/python -m pytest -q -n auto`.
- [ ] **Step 5: Commit**

```bash
git add strategies/field_pace.py tests/test_field_pace.py
git commit -m "field_pace: the field's schedule on third_herder, as one package (#252)

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 4: The declared bench `harness/pace_bench.py`

**Files:**
- Create: `harness/pace_bench.py`
- Test: `tests/test_pace_bench.py`
- Reference (read, do not modify): `harness/layout_bench.py` (module shape, `run_controls` identity, `run_criterion`, `main`), `harness/rival_bench.py` (`criterion`, `format_rows`, `format_external`, `paired_external_rows`, `first_day_at_or_above`), `harness/herder_bench.py` (`last_census_on_day`), `harness/farm_census.py` (`census_series`; a census has `planted_tiles`, `planted`, `quadrants`, `hands`, `head_placed`, `money`).

**Interfaces:**
- Produces: the declared constants; `shape_reading(turns, shape_day=SHAPE_DAY, crop_day=CROP_DAY) -> dict` with keys `planted, quadrants, hands, head_placed, strawberry, money_at_shape_day, planted_at_crop_day, money_at_crop_day, payday` (payday = first day money ≥ `PAYDAY_MONEY`, `None` if never; raises `ValueError` naming a day never reached); `shape_failures(reading) -> list[str]` (the bar names that failed, `[]` when all hold); `format_shape(rows) -> str`; `arm_b_class() -> type` (unregistered subclass of `field_pace` whose `herd_target`, `layout` and `pasture_count` are `ThirdHerderStrategy`'s); live `run_controls`, `run_criterion`, `run_recorded`, `main` with `--controls/--criterion/--recorded`, exit 0/1/2.

- [ ] **Step 1: Write the failing tests** — `tests/test_pace_bench.py`:

```python
"""The field_pace experiment's declared constants and the pure parts it adds.

The verdict, formatting and paired external rows are `harness.rival_bench`'s and
the census `harness.farm_census`'s -- imported, not copied. New here: an
ABSOLUTE shape control read off the contender's own census (the field's
medians less a margin), because a package that does not reproduce the shape it
was copied from has not tested the hypothesis, and a payday reading.
"""

from __future__ import annotations

import pytest

from harness import pace_bench as pb
from harness import rival_bench as rb


def test_the_declared_constants():
    assert pb.CONTENDER == "field_pace" and pb.CHAMPION == "third_herder"
    assert pb.SEEDS == tuple(range(896, 912)) and pb.CONTROL_SEED == 896
    assert pb.CHAMPION_BAR == 0.60 and pb.ANCHOR_BAR == 0.90
    assert pb.ARM_B == "crop_pace"
    assert pb.SHAPE_DAY == 8 and pb.CROP_DAY == 12
    assert pb.SHAPE_BARS == {"planted": 30, "quadrants": 2, "hands": 8, "head_placed": 8}
    assert pb.PLANTED_AT_CROP_DAY_BAR == 45 and pb.PAYDAY_MONEY == 5000


def test_the_seeds_are_fresh_against_every_range_already_spent():
    spent = set(range(100, 116)) | set(range(200, 216)) | set(range(300, 332)) \
        | set(range(400, 416)) | set(range(500, 516)) | set(range(600, 616)) \
        | set(range(700, 704)) | set(range(800, 896))
    assert not spent & set(pb.SEEDS)


def test_the_verdict_logic_is_rival_benchs_not_a_copy():
    assert pb.criterion is rb.criterion and pb.format_rows is rb.format_rows
    assert pb.format_external is rb.format_external
    assert pb.paired_external_rows is rb.paired_external_rows


def _census(planted, quadrants, hands, head, money, strawberry=0):
    planted_by = {"STRAWBERRY": strawberry, "MELON": planted - strawberry} if planted else {}
    return {"planted_tiles": planted, "planted": planted_by, "quadrants": ["NW", "NE", "SW"][:quadrants],
            "hands": hands, "head_placed": head, "money": float(money)}


def _turns():
    # Two turns a day, days 0..12: the shape lands on day 8, money crosses 5,000 on day 10.
    turns = []
    for day in range(13):
        planted = 20 if day < 6 else (37 if day < 11 else 62)
        quads = 1 if day < 6 else (2 if day < 11 else 3)
        hands = 5 if day < 6 else (8 if day < 8 else 10)
        head = 4 if day < 6 else (8 if day < 8 else 13)
        money = 600 if day < 10 else 18_000
        straw = 0 if day < 5 else 20
        turns.append((day, _census(planted - 1, quads, hands, head, money - 1, straw)))
        turns.append((day, _census(planted, quads, hands, head, money, straw)))
    return turns


def test_shape_reading_takes_the_closing_board_of_each_declared_day_and_the_payday():
    r = pb.shape_reading(_turns())
    assert r["planted"] == 37 and r["quadrants"] == 2 and r["hands"] == 10 and r["head_placed"] == 13
    assert r["strawberry"] == 20 and r["money_at_shape_day"] == 600
    assert r["planted_at_crop_day"] == 62 and r["money_at_crop_day"] == 18_000
    assert r["payday"] == 10


def test_shape_reading_reports_no_payday_when_money_never_crossed():
    turns = [(d, _census(20, 1, 6, 1, 900)) for d in range(13)]
    assert pb.shape_reading(turns)["payday"] is None


def test_shape_reading_raises_when_the_game_never_reached_a_declared_day():
    with pytest.raises(ValueError, match="day 12"):
        pb.shape_reading(_turns()[:20])


def test_each_shape_bar_can_fail_alone():
    good = pb.shape_reading(_turns())
    assert pb.shape_failures(good) == []
    assert pb.shape_failures(dict(good, planted=29)) == ["planted"]
    assert pb.shape_failures(dict(good, quadrants=1)) == ["quadrants"]
    assert pb.shape_failures(dict(good, hands=7)) == ["hands"]
    assert pb.shape_failures(dict(good, head_placed=7)) == ["head_placed"]
    assert pb.shape_failures(dict(good, planted_at_crop_day=44)) == ["planted_at_crop_day"]
    assert pb.shape_failures(dict(good, planted=0, hands=0)) == ["planted", "hands"]


def test_arm_b_is_the_crop_schedule_on_third_herders_herd_and_is_not_registered():
    from strategies import REGISTRY, field_rival as fr
    from strategies.field_pace import FieldPaceStrategy
    from strategies.third_herder import ThirdHerderStrategy
    cls = pb.arm_b_class()
    assert issubclass(cls, FieldPaceStrategy)
    arm, base = cls(), ThirdHerderStrategy()
    assert arm.hire_target(8) == 10 and arm.land_target(6) == 2 and arm.pivot_day() == 5
    assert arm.cluster_size() == 6 and arm.capital_reserve() == 0 and arm.CAPS == FieldPaceStrategy.CAPS
    for day in (0, 6, 8, 29):
        assert arm.herd_target(day) == base.herd_target(day), day
        assert arm.pasture_count(day, 0) == base.pasture_count(day, 0), day
    assert arm.layout() == base.layout() and fr.FieldRivalStrategy().layout() is None
    assert pb.ARM_B not in REGISTRY and pb.CONTENDER in REGISTRY


def test_format_shape_prints_both_sides_and_the_payday():
    r = pb.shape_reading(_turns())
    text = pb.format_shape([("field_pace", r), ("third_herder", dict(r, payday=None))])
    lines = text.splitlines()
    assert len(lines) == 3 and lines[1].startswith("field_pace") and "day 10" in lines[1]
    assert lines[2].rstrip().endswith("never")
```

- [ ] **Step 2: Run them and quote the failure** — `.venv/bin/python -m pytest -q tests/test_pace_bench.py`; expected: collection `ImportError: cannot import name 'pace_bench' from 'harness'`.

- [ ] **Step 3: Minimal implementation** — `harness/pace_bench.py`:

```python
"""field_pace: does the field's schedule, as one package, beat the champion?

    python -m harness.pace_bench --controls     # identity, then the absolute shape control
    python -m harness.pace_bench --criterion    # 16 seeds: champion, anchors, the external limb
    python -m harness.pace_bench --recorded     # arm B (recorded, not gated)
    python -m harness.pace_bench                # controls then criterion

Declared on #252 before any code: seeds 896-911 -- fresh; 100-115, 200-215,
300-331, 400-415, 500-515, 600-615, 700-703 and 800-895 are spent -- sides
alternated by list position (`harness.triage.head_to_head_rate`); PROMOTE
only at >= 60% of 16 vs the champion `third_herder` AND >= 90% vs each
DEFAULT_ANCHOR AND, for each `external_pool.EXTERNAL_ANCHORS` member, no fewer
wins than the champion on the same seeds in the same run (#152's paired limb);
a tie is not a win. Controls run first and a failed control voids the run --
arm B is then not scored either. Exit codes: 0 PROMOTE, 1 REJECTED, 2 VOID.
Runs under ROBRICULTURE_STRICT=1.

**The shape control is absolute, not paired.** The package was copied from the
field's medians; a contender that does not reproduce that shape on the board
has not tested the hypothesis, whatever the score says (#198's own necessary
condition, transplanted). The bars are the medians less a margin: by the close
of day 8 planted >= 30 (field 37), quadrants >= 2, hands >= 8 (field 10), head
placed >= 8 (field 13); by the close of day 12 planted >= 45 (field 62). A
miss names the knob that did not take. Recorded beside it: money at both days,
the first day money reaches 5,000 (the melon payday; the field's is day 10),
strawberry tiles at day 8, and the champion's readings from the same game.

The verdict, the row and external formatting and the paired external rows
are `harness.rival_bench`'s; the census is `harness.farm_census`'.
"""

from __future__ import annotations

import argparse
import os

from harness.evolve import DEFAULT_ANCHORS
from harness.herder_bench import last_census_on_day
from harness.rival_bench import (  # noqa: F401  -- re-exported on purpose
    criterion,
    first_day_at_or_above,
    format_external,
    format_rows,
    paired_external_rows,
)

CONTENDER = "field_pace"
CHAMPION = "third_herder"

#: Fresh. Everything through 895 is spent (see the module docstring).
SEEDS = tuple(range(896, 912))
CHAMPION_BAR = 0.60
ANCHOR_BAR = 0.90
CONTROL_SEED = 896

#: Arm B: the crop-and-land schedule with the herd left as third_herder's.
#: Never registered, so it cannot be promoted or packaged by accident.
ARM_B = "crop_pace"

SHAPE_DAY = 8
CROP_DAY = 12
SHAPE_BARS = {"planted": 30, "quadrants": 2, "hands": 8, "head_placed": 8}
PLANTED_AT_CROP_DAY_BAR = 45
PAYDAY_MONEY = 5000


def _closing(turns, day):
    census = last_census_on_day(turns, day)
    if census is None:
        span = f"the game covers days {turns[0][0]}-{turns[-1][0]}" if turns else "no turns at all"
        raise ValueError(f"no census recorded on day {day}: {span}")
    return census


def shape_reading(turns, shape_day=SHAPE_DAY, crop_day=CROP_DAY):
    """One side's shape off one game's census series ``[(day, census), ...]``:
    the closing board of `shape_day` and `crop_day`, and the payday."""
    at_shape, at_crop = _closing(turns, shape_day), _closing(turns, crop_day)
    money_series = [(day, c["money"]) for day, c in turns]
    return {
        "planted": at_shape["planted_tiles"],
        "quadrants": len(at_shape["quadrants"]),
        "hands": at_shape["hands"],
        "head_placed": at_shape["head_placed"],
        "strawberry": at_shape["planted"].get("STRAWBERRY", 0),
        "money_at_shape_day": at_shape["money"],
        "planted_at_crop_day": at_crop["planted_tiles"],
        "money_at_crop_day": at_crop["money"],
        "payday": first_day_at_or_above(money_series, PAYDAY_MONEY),
    }


def shape_failures(reading):
    """The declared bars that did not hold, in declaration order; ``[]`` passes."""
    failed = [name for name, bar in SHAPE_BARS.items() if reading[name] < bar]
    if reading["planted_at_crop_day"] < PLANTED_AT_CROP_DAY_BAR:
        failed.append("planted_at_crop_day")
    return failed


def format_shape(rows):
    """One line per side, contender above champion."""
    lines = [f"{'side':<16} {'planted@8':>9} {'quads@8':>8} {'hands@8':>8} {'head@8':>7} "
             f"{'straw@8':>8} {'money@8':>8} {'planted@12':>10} {'money@12':>9} {'payday':>8}"]
    for label, r in rows:
        payday = "never" if r["payday"] is None else f"day {r['payday']}"
        lines.append(f"{label:<16} {r['planted']:>9} {r['quadrants']:>8} {r['hands']:>8} "
                     f"{r['head_placed']:>7} {r['strawberry']:>8} {r['money_at_shape_day']:>8.0f} "
                     f"{r['planted_at_crop_day']:>10} {r['money_at_crop_day']:>9.0f} {payday:>8}")
    return "\n".join(lines)


def arm_b_class():
    """`field_pace` with the herd package returned to `third_herder`'s: the
    crop-and-land schedule alone. Built in-process and never registered."""
    from strategies import load
    from strategies.third_herder import ThirdHerderStrategy

    return type("CropPace", (load(CONTENDER),), {
        "herd_target": ThirdHerderStrategy.herd_target,
        "layout": ThirdHerderStrategy.layout,
        "pasture_count": ThirdHerderStrategy.pasture_count,
    })


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
    """Identity, then the absolute shape control. A failure voids the run."""
    os.environ.setdefault("ROBRICULTURE_STRICT", "1")
    from harness.farm_census import census_series
    from harness.tournament import play_rewards
    from kaggisim.strategy import make_agent
    from strategies import load
    out = {}

    off = type("Off", (load(CONTENDER),), {
        "herd_preference": lambda self, obs: None,
        "pasture_count": lambda self, day, animals: None,
        "herd_target": lambda self, day: None,
        "livestock_workers": lambda self, day: None,
        "layout": lambda self: None,
        "land_target": lambda self, day: None,
        "hire_target": lambda self, day: None,
        "pivot_day": lambda self: None,
        "cluster_size": lambda self: None,
        "capital_reserve": lambda self: None,
        "CAPS": load("dense_farm").CAPS,
    })
    base = play_rewards(make_agent(load("dense_farm")()), make_agent(load("dense_farm")()), seed)
    got = play_rewards(make_agent(off()), make_agent(load("dense_farm")()), seed)
    precondition_ok = base[0] > 0
    out["identity"] = {"ok": got == base and precondition_ok, "base": base, "got": got,
                       "precondition_ok": precondition_ok}

    ours, theirs = census_series(make_agent(load(CONTENDER)()),
                                 make_agent(load(CHAMPION)()), seed)
    contender, champion = shape_reading(ours), shape_reading(theirs)
    failed = shape_failures(contender)
    out["shape"] = {"ok": not failed, "failed": failed, "contender": contender, "champion": champion}
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
    ap = argparse.ArgumentParser(description="field_pace: the field's schedule as one package")
    ap.add_argument("--controls", action="store_true")
    ap.add_argument("--criterion", action="store_true")
    ap.add_argument("--recorded", action="store_true", help="arm B (recorded, not gated)")
    args = ap.parse_args(argv)

    if args.recorded:
        print(format_rows(run_recorded()))
        print(f"recorded, not gated: arm B ({ARM_B}: the crop-and-land schedule on "
              f"third_herder's herd) vs {CHAMPION}")
        return 0

    do_controls = args.controls or not args.criterion
    do_criterion = args.criterion or not args.controls

    if do_controls:
        ctl = run_controls()
        print(f"control identity: {'OK' if ctl['identity']['ok'] else 'FAIL -- RUN VOID'}"
              f"  {ctl['identity']}")
        print(f"control shape: {'OK' if ctl['shape']['ok'] else 'FAIL -- RUN VOID'}  "
              f"(declared: by day {SHAPE_DAY} {SHAPE_BARS}; by day {CROP_DAY} planted >= "
              f"{PLANTED_AT_CROP_DAY_BAR})  failed={ctl['shape']['failed'] or 'none'}")
        print(format_shape([(CONTENDER, ctl["shape"]["contender"]),
                            (CHAMPION, ctl["shape"]["champion"])]))
        if not all(r["ok"] for r in ctl.values()):
            print("a control failed: the run is VOID and arm B is NOT scored")
            return 2

    if do_criterion:
        champion_row, anchor_rows, pairs = run_criterion()
        print(format_rows([champion_row] + anchor_rows))
        print(format_external(pairs))
        v = criterion(champion_row, anchor_rows, CHAMPION_BAR, ANCHOR_BAR, external_pairs=pairs)
        pilkwang = pairs.get("pilkwang_structured_economic_policy") if isinstance(pairs, dict) else None
        print(f"champion {v['champion_rate']:.1%} (bar {CHAMPION_BAR:.0%}); failing limbs: "
              f"{v['failing'] or 'none'} -> {'PROMOTE' if v['passed'] else 'REJECTED'}; "
              f"pilkwang paired row (contender, champion): {pilkwang}")
        return 0 if v["passed"] else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Note for the implementer: check `paired_external_rows`' return shape in `harness/rival_bench.py` (a dict `{name: (contender_wins, champion_wins)}` or a list of rows) and make the `pilkwang` lookup in `main` match it — that line is the only place the shape matters; leave the rest as written.

- [ ] **Step 4: Run green, with coverage** — `.venv/bin/python -m pytest -q -n auto --cov --cov-branch --cov-report=term-missing 2>&1 | grep -E "pace_bench|field_pace|passed|failed"`.
- [ ] **Step 5: Commit**

```bash
git add harness/pace_bench.py tests/test_pace_bench.py
git commit -m "pace_bench: #252's identity and absolute shape controls, criterion and arm B

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

## Self-review

- **Spec coverage.** Four seams → Tasks 1-2. Contender with every declared constant, `pasture_count` on its own block → Task 3. Arm B, controls (identity over ten seams plus `CAPS` back to dense_farm's; absolute shape bars; payday and strawberry readings; champion contrast), criterion with the paired limb and the pilkwang row named, exit codes → Task 4. Full gate/preflight/run → the controller.
- **Placeholders.** None; the one open shape (`paired_external_rows`' return type) is called out as a check, with the only line it touches.
- **Type consistency.** Hook names (`hire_target`, `capital_reserve`, `pivot_day`, `cluster_size`) match between Tasks 1-2 (defined), 3 (answered) and 4 (switched off). `market_orders` keywords `hire`, `reserve`, `pivot` match `act`'s call. `shape_reading` keys match `shape_failures`, `format_shape` and the tests.
