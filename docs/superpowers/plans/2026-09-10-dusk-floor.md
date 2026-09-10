# dusk_floor (#258) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A turn-wide `floor` on the frozen benchmark's land, seed and herd steps behind a `spend_floor` seam (hires and feed exempt), the contender `dusk_floor` (herd_first with the floor = tomorrow's wage bill + the feed shortfall at the market price), and its declared bench `harness/floor_bench.py`.

**Architecture:** `market_orders` gains `floor=None` (0 on the frozen path) read by the three spending steps; the class gains `spend_floor(day, animals, shed, prices)` returning `None`; `act` passes the four. The contender answers with two pure helpers. The bench imports `reserve_bench`'s bars and readers and adds only its constants, a twelve-hook identity stub and a wages-only arm B.

**Tech Stack:** Python 3.12 in `.venv` (`.venv/bin/python`, never a bare python3), pytest `-n auto`, `kaggle-environments` 1.32.7. Spec: `docs/superpowers/specs/2026-09-10-dusk-floor-design.md`.

## Global Constraints

- Pure TDD: write the failing tests, **run them and quote the failure**, then the minimal code, run green, commit. Every task: `.venv/bin/python -m pytest -q -n auto` green before the commit.
- `strategies/field_rival.py` is the frozen benchmark (#181): `floor=None` means 0 and every existing golden pin (the frozen dawn list, the reorder test, the reserve tests) must hold unchanged; `spend_floor` returns `None` on `FieldRivalStrategy`; `capital_reserve` and `cash_floor` are untouched; no existing assertion in `tests/test_field_rival.py` may change.
- Declared values, verbatim, not to be tuned: `feed_shortfall_cost(animals, shed, prices) = max(0, feed_buffer(animals) - shed.get("WHEAT", 0)) * prices.get("WHEAT", 25)`; floor = `wage_bill(hire_target(day + 1)) + feed_shortfall_cost(animals, shed, prices)`; bench `CONTENDER = "dusk_floor"`, `CHAMPION = "third_herder"`, `BASELINE = "herd_first"`, `SEEDS = tuple(range(944, 960))`, `CONTROL_SEED = 944`, `CHAMPION_BAR = 0.60`, `ANCHOR_BAR = 0.90`, `ARM_B = "wage_floor"`; bars imported from `reserve_bench` (`HEAD_DAY 8`, `HEAD_BAR 8`, `HANDS_BAR 8`, `CROP_DAY 12`, `PLANTED_GAP_BAR 12`).
- Never edit `strategies/__init__.py`. Test names `test_<the fact>` with a docstring/comment saying why. Stage by explicit path; never `git add -A`; never stage `.venv` / `external_agents`. Commit messages end with a blank line and `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.
- Live-game code carries `# pragma: no cover` at the `def`; do NOT run the bench's live games — the controller runs the declared bench after review.

---

### Task 1: The `spend_floor` seam — a turn-wide floor on land, seed and herd

**Files:**
- Modify: `strategies/field_rival.py` — `market_orders` signature (add `floor=None` after `order=None`), the `land_step`, `seed` and `herd` inner steps, the `FieldRivalStrategy.spend_floor` hook after `buy_order`, and the `market_orders(...)` call in `act`.
- Test: `tests/test_field_rival.py` (append).

**Interfaces:**
- Produces: `market_orders(..., order=None, floor=None)`; `FieldRivalStrategy.spend_floor(self, day=None, animals=None, shed=None, prices=None) -> int | None`; `act` computes `prices = (obs.get("market") or {}).get("prices") or {}` and passes `floor=self.spend_floor(day, animals, shed, prices)`.

- [ ] **Step 1: Write the failing tests** — append to `tests/test_field_rival.py`:

```python
# --- #258: the spend floor, a turn-wide floor on land, seed and herd ---

def test_the_benchmarks_spend_floor_hook_asks_for_no_floor():
    # `None` means "no floor" -- the benchmark keeps every decision it makes today (#181).
    assert fr.FieldRivalStrategy().spend_floor() is None
    assert fr.FieldRivalStrategy().spend_floor(8, 4, {"WHEAT": 3}, {"WHEAT": 25}) is None


def test_market_orders_with_no_floor_and_a_zero_floor_emit_the_frozen_list():
    # The golden pin (#254) must survive the new keyword: None and 0 are the same, frozen, list.
    frozen = [["BUY_LAND"], ["BUY_SEED", "STRAWBERRY", 4]] + [["BUY_ANIMAL", "SHEEP", 1]] * 8
    assert _dawn_after_hires(50_000) == frozen
    assert _dawn_after_hires(50_000, floor=0) == frozen


def test_a_floor_is_left_unspent_across_land_seed_and_herd_on_the_frozen_order():
    """The positive control for the seam: with 1,500 and a floor of 600 the land
    buy (1,000) would breach it and is skipped, seed buys from the 900 above it,
    and the herd stops at the frozen reserve. Without the floor the same cash
    buys land and seed and ends at 100."""
    assert _dawn_after_hires(1_500) == [["BUY_LAND"], ["BUY_SEED", "STRAWBERRY", 4]]
    assert _dawn_after_hires(1_500, floor=600) == [["BUY_SEED", "STRAWBERRY", 4]]


def test_a_floor_is_left_unspent_on_herd_firsts_order_too():
    """#256's defect, pinned: on herd_first's order with no reserve, the herd
    stops at the floor AND land and seed respect it -- 2,000 with a floor of 700
    buys two sheep (2,000 -> 1,500 -> 1,000), skips land (1,000 - 1,000 < 700)
    and buys three seed from the 300 above the floor; 700 survives."""
    herd_first = ("hires", "herd", "land", "seed")
    assert _dawn_after_hires(2_000, order=herd_first, reserve=0, floor=700) == (
        [["BUY_ANIMAL", "SHEEP", 1], ["BUY_ANIMAL", "SHEEP", 1], ["BUY_SEED", "STRAWBERRY", 3]])


def test_act_hands_the_spend_floor_hook_the_day_the_head_the_shed_and_the_prices():
    """The seam is only a seam if `act` feeds it: on a real reset observation the
    hook sees day 0, no head placed, the (empty) shed and the market's prices."""
    from kaggle_environments import make
    seen = []

    class Recording(fr.FieldRivalStrategy):
        def spend_floor(self, day=None, animals=None, shed=None, prices=None):
            seen.append((day, animals, shed, prices))
            return None

    obs = make("kaggriculture", configuration={"seed": 1}).state[0].observation
    Recording().act(obs)
    (day, animals, shed, prices), = seen
    assert day == 0 and animals == 0 and isinstance(shed, dict)
    assert prices["WHEAT"] == 25
```

- [ ] **Step 2: Run them and quote the failure**

Run: `.venv/bin/python -m pytest -q tests/test_field_rival.py -k "spend_floor or zero_floor or left_unspent or spend_floor_hook"`
Expected: 5 failed — `AttributeError: 'FieldRivalStrategy' object has no attribute 'spend_floor'` (twice) and `TypeError: market_orders() got an unexpected keyword argument 'floor'` (three times). `test_a_floor_is_left_unspent_across_land_seed_and_herd_on_the_frozen_order`'s first assertion (no floor) must hold on the unchanged code — if it does not, report NEEDS_CONTEXT with the list you got.

- [ ] **Step 3: Minimal implementation**

Signature: `..., pivot=None, order=None, floor=None):` and a docstring line after `order`:
`` `floor`: cash every spending block after hires leaves unspent this turn -- land, seed and the herd alike -- or ``None`` for no floor (#258). Independent of `reserve`, which is the herd's own. ``

Before the step definitions (next to `standing`/`caps`): `keep = 0 if floor is None else floor`.

`land_step`: `if budget - cost >= keep:` in place of `if budget >= cost:`.
`seed`: `buy = min(want, max(0, int((budget - keep) // seed_cost)))`.
`herd`: `if budget - cost < cash_floor or budget - cost < keep:`.

Hook after `buy_order`:

```python
    def spend_floor(self, day=None, animals=None, shed=None, prices=None):
        """Cash every spending block after hires leaves unspent this turn, or
        ``None`` for no floor. A seam for contenders (#258): `day`, the placed
        head, the shed and the market prices let a floor follow tomorrow's crew
        and today's feed. Never fires on the benchmark."""
        return None
```

`act`: before the `market_orders(...)` call add `prices = (obs.get("market") or {}).get("prices") or {}`, and the call gains `floor=self.spend_floor(day, animals, shed, prices)` after `order=self.buy_order()`.

- [ ] **Step 4: Run green** — `.venv/bin/python -m pytest -q -n auto`.
- [ ] **Step 5: Commit**

```bash
git add strategies/field_rival.py tests/test_field_rival.py
git commit -m "field_rival: a turn-wide spend floor on land, seed and herd behind a spend_floor seam, none by default (#258)

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 2: The contender `dusk_floor`

**Files:**
- Create: `strategies/dusk_floor.py`
- Test: `tests/test_dusk_floor.py`

**Interfaces:**
- Consumes: Task 1's hook; `strategies.herd_first.HerdFirstStrategy`; `strategies.dawn_reserve.wage_bill`; `strategies.field_rival.feed_buffer`; `kaggisim.economy.MARKET_PARAMS["WHEAT"]["base"]` (25).
- Produces: `WHEAT_BASE = 25`; `feed_shortfall_cost(animals, shed, prices) -> int`; `DuskFloorStrategy(HerdFirstStrategy)` with `name = "dusk_floor"`, `benchmark = False`, `spend_floor(self, day=None, animals=None, shed=None, prices=None)`; `STRATEGY = DuskFloorStrategy`.

- [ ] **Step 1: Write the failing tests** — `tests/test_dusk_floor.py`:

```python
"""dusk_floor: herd_first with a turn-wide spend floor (#258).

#254's herd_first beat the champion 14/16 and lost the field because a zero
reserve fires the crew at dusk; #256 put dawn's wages and feed behind the herd's
own reserve and VOIDed on the same bar, because land and seed spend after the
herd under herd_first's order. This arm puts the same quantity -- priced at the
market and reserving only the shortfall -- behind a floor that land, seed and
the herd all respect, and changes nothing else.
"""

from __future__ import annotations

from kaggisim import economy
from strategies import dusk_floor as df
from strategies import field_rival as fr
from strategies.dawn_reserve import wage_bill
from strategies.herd_first import HerdFirstStrategy


def test_the_feed_shortfall_is_priced_at_the_market_and_only_for_what_the_shed_lacks():
    # 8 head keep 16 wheat; 10 in the shed leaves 6 to buy at the day's price.
    assert df.WHEAT_BASE == economy.MARKET_PARAMS["WHEAT"]["base"] == 25
    assert df.feed_shortfall_cost(8, {"WHEAT": 10}, {"WHEAT": 30}) == 180
    assert df.feed_shortfall_cost(8, {"WHEAT": 20}, {"WHEAT": 30}) == 0
    assert df.feed_shortfall_cost(8, {}, {}) == 16 * 25          # base price when the market is unread
    assert df.feed_shortfall_cost(0, {}, {"WHEAT": 25}) == fr.feed_buffer(0) * 25   # FEED_CARRY floor


def test_the_floor_is_tomorrows_wages_plus_todays_feed_shortfall():
    # Day 5 -> tomorrow's crew is 8 (54) + four head with an empty shed (8 x 25 = 200).
    s = df.DuskFloorStrategy()
    assert s.spend_floor(5, 4, {}, {"WHEAT": 25}) == 254
    assert s.spend_floor(7, 8, {"WHEAT": 16}, {"WHEAT": 40}) == 143       # shed full: wages only
    assert s.spend_floor() == wage_bill(s.hire_target(0)) + 8 * 25           # the bare call answers


def test_it_is_a_registered_contender_that_inherits_herd_firsts_order_and_knobs():
    from strategies import REGISTRY, load
    assert "dusk_floor" in REGISTRY and load("dusk_floor") is df.DuskFloorStrategy
    assert issubclass(df.DuskFloorStrategy, HerdFirstStrategy)
    s, base = df.DuskFloorStrategy(), HerdFirstStrategy()
    assert s.buy_order() == base.buy_order() == ("hires", "herd", "land", "seed")
    assert s.capital_reserve(5, 4) == base.capital_reserve(5, 4) == 0      # the herd's own reserve stays 0
    for day in (0, 6, 8, 15):
        assert s.hire_target(day) == base.hire_target(day) and s.herd_target(day) == base.herd_target(day)
    assert s.layout() == base.layout() and s.CAPS == base.CAPS
    assert base.spend_floor(5, 4, {}, {}) is None                          # herd_first has no floor
```

- [ ] **Step 2: Run them and quote the failure** — `.venv/bin/python -m pytest -q tests/test_dusk_floor.py`; expected: collection `ImportError: cannot import name 'dusk_floor' from 'strategies'`.

- [ ] **Step 3: Minimal implementation** — `strategies/dusk_floor.py`:

```python
"""dusk_floor: herd_first with a turn-wide spend floor on land, seed and herd (#258).

#254's `herd_first` beat `third_herder` 14/16 and lost the field because a zero
reserve fires the crew at dusk: the sim clears the hands every night and
re-hires at dawn on the wage ladder, and the herd block, which runs on every
hour, spent every coin before dawn. #256 put dawn's wages and the herd's feed
behind `capital_reserve` and VOIDed on the same crew bar -- that reserve is a
floor inside the herd block only, and under herd_first's order the land and
seed blocks run after the herd and spend it.

One decision changes: the same quantity -- tomorrow's wage bill plus the feed
the herd is short of, at the price the feed block will pay -- goes behind the
`spend_floor` seam (#258), which land, seed and the herd all respect and hires
and the feed block are exempt from. The buy order, `field_pace`'s eight knobs
and `third_herder`'s rules are inherited unchanged; the herd's own reserve
stays 0.

Declared before measurement: `feed_shortfall_cost`, the floor, and the controls
and criterion in `harness/floor_bench.py` (posted to #258 before any code).
"""

from __future__ import annotations

from kaggisim import economy
from strategies import field_rival as fr
from strategies.dawn_reserve import wage_bill
from strategies.herd_first import HerdFirstStrategy

#: Wheat's anchor price: what the feed leg is priced at before the market is read.
WHEAT_BASE = economy.MARKET_PARAMS["WHEAT"]["base"]


def feed_shortfall_cost(animals: int, shed: dict, prices: dict) -> int:
    """What the feed block will spend to top the shed up to `feed_buffer` for
    `animals` head, at today's wheat price: the shortfall, not the buffer --
    the sell sweep already keeps the buffer, so most days this is 0."""
    short = max(0, fr.feed_buffer(animals) - int(shed.get("WHEAT", 0)))
    return short * int(prices.get("WHEAT", WHEAT_BASE))


class DuskFloorStrategy(HerdFirstStrategy):
    """`herd_first` that leaves dawn's needs unspent, whatever block is spending."""

    name = "dusk_floor"
    benchmark = False

    def spend_floor(self, day=None, animals=None, shed=None, prices=None):
        """Tomorrow's wage bill plus today's feed shortfall. A bare call (no day,
        no head, no shed, no prices) answers for the season's opening crew."""
        crew = self.hire_target(0 if day is None else day + 1)
        return wage_bill(crew) + feed_shortfall_cost(animals or 0, shed or {}, prices or {})


STRATEGY = DuskFloorStrategy
```

- [ ] **Step 4: Run green** — the whole suite (the no-crash gate now plays `dusk_floor`): `.venv/bin/python -m pytest -q -n auto`.
- [ ] **Step 5: Commit**

```bash
git add strategies/dusk_floor.py tests/test_dusk_floor.py
git commit -m "dusk_floor: herd_first with a turn-wide floor of tomorrow's wages plus the feed shortfall at market price (#258)

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 3: The declared bench `harness/floor_bench.py`

**Files:**
- Create: `harness/floor_bench.py`
- Test: `tests/test_floor_bench.py`
- Reference (read, do not modify): `harness/reserve_bench.py` — copy its shape; import `HEAD_DAY`, `HEAD_BAR`, `HANDS_BAR`, `CROP_DAY`, `PLANTED_GAP_BAR`, `MADHUR`, `crew_ok`, `mechanism_failures`, `order_reading`, `format_order_shape`, `crop_line_ok`, `REFERENCE`, `PILKWANG` from it (they are re-exported there) and the verdict names from `harness.rival_bench`.

**Interfaces:**
- Produces: the declared constants; `off_class() -> type` (twelve hooks off: `reserve_bench.off_class`'s eleven plus `"spend_floor": lambda self, day=None, animals=None, shed=None, prices=None: None`, and dense_farm's `CAPS`); `arm_b_class() -> type` (unregistered subclass of `herd_first` whose `spend_floor` returns `wage_bill(self.hire_target((0 if day is None else day) + 1))`); live `run_controls`, `run_criterion`, `run_recorded`, `main`.

- [ ] **Step 1: Write the failing tests** — `tests/test_floor_bench.py`:

```python
"""The dusk_floor experiment's declared constants and the pure parts it adds.

Bars, readers and the verdict are `harness.reserve_bench`'s / `order_bench`'s /
`rival_bench`'s -- imported, not copied. New here: the twelve-hook identity stub
(the floor seam switched off) and a wages-only arm B.
"""

from __future__ import annotations

from harness import floor_bench as fb
from harness import reserve_bench as rsb
from harness import rival_bench as rb


def test_the_declared_constants():
    # Declared on #258 before any code; not to be tuned.
    assert fb.CONTENDER == "dusk_floor" and fb.CHAMPION == "third_herder" and fb.BASELINE == "herd_first"
    assert fb.SEEDS == tuple(range(944, 960)) and fb.CONTROL_SEED == 944
    assert fb.CHAMPION_BAR == 0.60 and fb.ANCHOR_BAR == 0.90
    assert fb.ARM_B == "wage_floor"
    assert (fb.HEAD_DAY, fb.HEAD_BAR, fb.HANDS_BAR, fb.CROP_DAY, fb.PLANTED_GAP_BAR) == (8, 8, 8, 12, 12)


def test_the_seeds_are_fresh_against_every_range_already_spent():
    # 928 was #256's control seed; 929-943 were declared there and never played, not reused.
    spent = set(range(100, 116)) | set(range(200, 216)) | set(range(300, 332)) \
        | set(range(400, 416)) | set(range(500, 516)) | set(range(600, 616)) \
        | set(range(700, 704)) | set(range(800, 944))
    assert not spent & set(fb.SEEDS)


def test_the_bars_readers_and_verdict_are_imported_not_copied():
    assert fb.crew_ok is rsb.crew_ok and fb.mechanism_failures is rsb.mechanism_failures
    assert fb.order_reading is rsb.order_reading and fb.crop_line_ok is rsb.crop_line_ok
    assert fb.format_order_shape is rsb.format_order_shape
    assert fb.criterion is rb.criterion and fb.paired_external_rows is rb.paired_external_rows
    assert fb.MADHUR == rsb.MADHUR and fb.PILKWANG == rsb.PILKWANG and fb.REFERENCE == rsb.REFERENCE


def test_the_identity_stub_switches_every_seam_off_and_survives_a_turn():
    """Twelve hooks off, the floor among them, at their current arity; a real
    reset observation catches the next arity drift."""
    from kaggle_environments import make
    off = fb.off_class()()
    assert off.spend_floor(8, 4, {}, {}) is None and off.spend_floor() is None
    assert off.capital_reserve(8, 4) is None and off.buy_order() is None and off.layout() is None
    obs = make("kaggriculture", configuration={"seed": 1}).state[0].observation
    assert set(off.act(obs)) == {"farmer", "hands", "market"}


def test_arm_b_keeps_the_wages_only_and_is_not_registered():
    from strategies import REGISTRY
    from strategies.dawn_reserve import wage_bill
    from strategies.herd_first import HerdFirstStrategy
    cls = fb.arm_b_class()
    assert issubclass(cls, HerdFirstStrategy)
    arm = cls()
    assert arm.spend_floor(5, 4, {}, {"WHEAT": 25}) == wage_bill(arm.hire_target(6)) == 54
    assert arm.spend_floor(7, 8, {}, {}) == 143 and arm.spend_floor() == 12
    assert arm.buy_order() == ("hires", "herd", "land", "seed")
    assert fb.ARM_B not in REGISTRY and fb.CONTENDER in REGISTRY
```

- [ ] **Step 2: Run them and quote the failure** — `.venv/bin/python -m pytest -q tests/test_floor_bench.py`; expected: collection `ImportError: cannot import name 'floor_bench' from 'harness'`.

- [ ] **Step 3: Minimal implementation** — `harness/floor_bench.py`. Copy `harness/reserve_bench.py` and change exactly these things:
  - the module docstring: the title line becomes `"""dusk_floor: does a turn-wide floor of dawn's wages and the feed shortfall keep the crew, the herd and the field?`, the four usage lines name `harness.floor_bench`, the seeds sentence reads `seeds 944-959 -- fresh; 100-115, 200-215, 300-331, 400-415, 500-515, 600-615, 700-703 and 800-928 are spent, 929-943 were declared for #256 and never played`, and the "**The controls.**" paragraph reads: `#256's dawn_reserve VOIDed on the crew bar because its reserve was a floor on the herd block only; this arm's floor is respected by land, seed and the herd alike. The bars are #256's, unchanged: hands >= 8 and head placed >= 8 at day 8, and the crop line PAIRED against herd_first on the same seed. The madhur row is the reading the hypothesis lives on.`
  - imports: replace the `order_bench`/`pace_bench` import groups with one `from harness.reserve_bench import (  # noqa: F401  -- pinned by the tests to reserve_bench's own` listing `CROP_DAY, HANDS_BAR, HEAD_BAR, HEAD_DAY, MADHUR, PILKWANG, PLANTED_GAP_BAR, REFERENCE, crew_ok, crop_line_ok, format_order_shape, mechanism_failures, order_reading`; keep the `rival_bench` import and `from harness.evolve import DEFAULT_ANCHORS`; drop `from harness import external_pool` and the `MADHUR = ...`/`assert` lines (imported now).
  - constants: `CONTENDER = "dusk_floor"`, `BASELINE = "herd_first"` (unchanged), `SEEDS = tuple(range(944, 960))`, `CONTROL_SEED = 944`, `ARM_B = "wage_floor"`, and delete the local `HANDS_BAR`, `crew_ok`, `mechanism_failures` definitions (imported now); the `SEEDS` comment reads `#: Fresh. Everything through 928 is spent; 929-943 were declared for #256 and never played.`
  - `arm_b_class`:

    ```python
    def arm_b_class():
        """`herd_first` with the floor set to tomorrow's wages alone. Never registered."""
        from strategies import load
        from strategies.dawn_reserve import wage_bill

        def spend_floor(self, day=None, animals=None, shed=None, prices=None):
            return wage_bill(self.hire_target((0 if day is None else day) + 1))

        return type("WageFloor", (load(BASELINE),), {"spend_floor": spend_floor})
    ```
  - `off_class`: the same dict plus `"spend_floor": lambda self, day=None, animals=None, shed=None, prices=None: None`; docstring says twelve.
  - `main`: the `argparse` description becomes `"dusk_floor: a turn-wide floor of dawn's wages and the feed shortfall"`, and the `--recorded` line says `the wage bill alone as the floor`.
  Everything else (`run_controls` with `BASELINE`, `run_criterion`, `run_recorded`, the control printing, exit codes) stays as in `reserve_bench`.

- [ ] **Step 4: Run green, with coverage** — `.venv/bin/python -m pytest -q -n auto --cov --cov-branch --cov-report=term-missing 2>&1 | grep -E "floor_bench|dusk_floor|passed|failed"`.
- [ ] **Step 5: Commit**

```bash
git add harness/floor_bench.py tests/test_floor_bench.py
git commit -m "floor_bench: #258's identity, crew-and-head and paired crop-line controls, criterion and arm B

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

## Self-review

- **Spec coverage.** Seam semantics (land/seed/herd respect the floor, hires and feed exempt, `None` = 0, independent of `reserve`) and the positive control → Task 1. `feed_shortfall_cost`, the floor, the bare call, the contender inheriting herd_first with `capital_reserve` 0 → Task 2. Bench with the twelve-hook stub, #256's bars imported, the crop line paired against herd_first, arm B wages-only, madhur/pilkwang named → Task 3. Run/record/PR → the controller.
- **Placeholders.** None; Task 3's "copy and change exactly these" lists every change.
- **Type consistency.** `spend_floor(self, day=None, animals=None, shed=None, prices=None)` in Tasks 1 (benchmark), 2 (contender), 3 (arm B, `off_class`); `market_orders(floor=)` matches `act`'s call; `feed_shortfall_cost(animals, shed, prices)` signature matches its tests and the contender.
