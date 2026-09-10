# herd_first (#254) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A `buy_order` seam on the frozen benchmark (the four buy blocks of `market_orders` as named steps run in a given order), the contender `herd_first` (field_pace with the herd funded before land and seed), and its declared bench `harness/order_bench.py`.

**Architecture:** `market_orders`' body is split into four inner steps closing over the shared budget, run in `BUY_ORDER` by default — a golden-pin test fixes the frozen dawn list before the split and holds through it. The contender answers `buy_order()` with one tuple. The bench reuses `pace_bench`'s readers and `rival_bench`'s verdict machinery, adding an absolute head-placed control and a paired crop-line control against `field_pace`.

**Tech Stack:** Python 3.12 in `.venv` (`.venv/bin/python`, never a bare python3), pytest `-n auto`, `kaggle-environments` 1.32.7. Spec: `docs/superpowers/specs/2026-09-10-herd-first-design.md`.

## Global Constraints

- Pure TDD: write the failing tests, **run them and quote the failure**, then the minimal code, run green, commit. Every task: `.venv/bin/python -m pytest -q -n auto` green before the commit.
- `strategies/field_rival.py` is the frozen benchmark (#181): `order=None` selects the frozen `BUY_ORDER`; `buy_order()` returns `None` on `FieldRivalStrategy`; no existing assertion in `tests/test_field_rival.py` may change; the golden pin written in Task 1 must pass on the unsplit code before the split (it is red only against the missing `order` keyword).
- Declared values, verbatim, not to be tuned: `BUY_ORDER = ("hires", "land", "seed", "herd")`; `ORDER_H = ("hires", "herd", "land", "seed")`; bench `CONTENDER = "herd_first"`, `CHAMPION = "third_herder"`, `PACE = "field_pace"`, `SEEDS = tuple(range(912, 928))`, `CONTROL_SEED = 912`, `CHAMPION_BAR = 0.60`, `ANCHOR_BAR = 0.90`, `ARM_B = "herd_mid"`, `ORDER_B = ("hires", "land", "herd", "seed")`, `HEAD_DAY = 8`, `HEAD_BAR = 8`, `CROP_DAY = 12`, `PLANTED_GAP_BAR = 12`.
- Never edit `strategies/__init__.py`. Test names `test_<the fact>` with a docstring/comment saying why. Stage by explicit path; never `git add -A`; never stage `.venv` / `external_agents`. Commit messages end with a blank line and `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.
- Live-game code carries `# pragma: no cover` at the `def`; do NOT run the bench's live games — the controller runs the declared bench after review.

---

### Task 1: The `buy_order` seam — `market_orders` as named steps

**Files:**
- Modify: `strategies/field_rival.py` — `BUY_ORDER` constant above `market_orders`; `market_orders` signature and body; `FieldRivalStrategy.buy_order` hook after `cluster_size`; the `market_orders(...)` call in `act`.
- Test: `tests/test_field_rival.py` (append).

**Interfaces:**
- Produces: `BUY_ORDER`; `market_orders(..., pivot=None, order=None)` — `order` is a tuple of block names from `{"hires", "land", "seed", "herd"}`, `None` = `BUY_ORDER`, an unknown name raises `KeyError`; `FieldRivalStrategy.buy_order(self) -> tuple | None`; `act` passes `order=self.buy_order()`.

- [ ] **Step 1: Write the failing tests** — append to `tests/test_field_rival.py`:

```python
# --- #254: the buy-order seam, and the frozen order it defaults to ---

def test_the_benchmarks_buy_order_hook_asks_for_the_frozen_order():
    # `None` means "the benchmark's own order", so field_rival stays frozen (#181).
    assert fr.FieldRivalStrategy().buy_order() is None
    assert fr.BUY_ORDER == ("hires", "land", "seed", "herd")


def _dawn_after_hires(money, **kw):
    # Hour 1 with the crew already hired: land, seed and herd are the only buys,
    # and with no shed there are no sells -- the list IS the buy order.
    return fr.market_orders(day=12, hour=1, money=money, hands=9, quadrants=1, animals=0,
                            shed={}, seeds={}, empty_plots=4, standing={}, **kw)


def test_market_orders_emits_the_frozen_order_by_default():
    """Golden pin, written BEFORE the body is split into steps and kept through it:
    with cash for everything the frozen order is land, seed, then the herd (day 12
    wants 8 head; every buy is a sheep at this budget). Exactly ten orders, so the
    cap does not truncate the pin."""
    assert _dawn_after_hires(50_000) == (
        [["BUY_LAND"], ["BUY_SEED", "STRAWBERRY", 4]] + [["BUY_ANIMAL", "SHEEP", 1]] * 8)


def test_market_orders_with_an_order_spends_the_same_cash_in_that_order():
    """The seam: the blocks are the same, the budget is shared, only the order
    moves. With 2,000 the frozen order buys land and seed and the herd starves;
    herd-first with the frozen reserve buys one sheep, then land, then seed;
    herd-first with no reserve buys four head and seed gets the change."""
    herd_first = ("hires", "herd", "land", "seed")
    assert _dawn_after_hires(2_000) == [["BUY_LAND"], ["BUY_SEED", "STRAWBERRY", 4]]
    assert _dawn_after_hires(2_000, order=herd_first) == (
        [["BUY_ANIMAL", "SHEEP", 1], ["BUY_LAND"], ["BUY_SEED", "STRAWBERRY", 4]])
    assert _dawn_after_hires(2_000, order=herd_first, reserve=0) == (
        [["BUY_ANIMAL", "SHEEP", 1], ["BUY_ANIMAL", "SHEEP", 1],
         ["BUY_ANIMAL", "COW", 1], ["BUY_ANIMAL", "COW", 1], ["BUY_SEED", "STRAWBERRY", 2]])


def test_market_orders_refuses_an_unknown_block_name():
    # A typo in a contender's order must not silently skip a block.
    import pytest
    with pytest.raises(KeyError):
        _dawn_after_hires(2_000, order=("hires", "herds"))
```

- [ ] **Step 2: Run them and quote the failure**

Run: `.venv/bin/python -m pytest -q tests/test_field_rival.py -k "buy_order_hook or frozen_order_by_default or spends_the_same_cash or unknown_block"`
Expected: `test_market_orders_emits_the_frozen_order_by_default` **passes** (the golden pin on the unsplit code — say so); the other three fail: `AttributeError: 'FieldRivalStrategy' object has no attribute 'buy_order'` / `AttributeError: module ... has no attribute 'BUY_ORDER'`, `TypeError: market_orders() got an unexpected keyword argument 'order'` (twice). If the golden pin does NOT pass on the unsplit code, report NEEDS_CONTEXT with the list you got — do not adjust it.

- [ ] **Step 3: Minimal implementation**

Above `market_orders` add:

```python
#: The frozen buy order: the crew, the land ramp, seed for every empty tile, and
#: the herd last out of the surplus. A contender may run the same four blocks in
#: another order through the `buy_order` seam (#254); sells stay first and feed
#: last either way.
BUY_ORDER = ("hires", "land", "seed", "herd")
```

Signature: `..., land=None, hire=None, reserve=None, pivot=None, order=None):` and a docstring line after `pivot`: `` `order`: the buy blocks to run and their order, or ``None`` for the frozen `BUY_ORDER` (#254). ``

Body: keep the sells sweep as is. Replace everything from `if hour == 0:` through the end of the herd loop with four inner steps and one loop — the step bodies are the existing blocks moved verbatim, each declaring `nonlocal budget`:

```python
    standing = standing or {}
    caps = CROP_CAP if caps is None else caps

    def hires():
        nonlocal budget
        if hour != 0:
            return
        want = max(0, (hire_target(day) if hire is None else hire) - hands)
        for k in range(1, want + 1):
            wage = hh.hand_wage(hands + k)
            if budget < wage:
                break
            buys.append(["HIRE"])
            budget -= wage

    def land_step():
        nonlocal budget
        want_land = land_target(day) if land is None else land
        if quadrants < want_land and quadrants - 1 < len(economy.LAND_COSTS):
            cost = economy.LAND_COSTS[quadrants - 1]
            if budget >= cost:
                buys.append(["BUY_LAND"])
                budget -= cost

    def seed():
        nonlocal budget
        crop = crop_for_plot(day, standing, caps=caps, pivot=pivot)
        if crop and empty_plots > 0:
            # (the existing comment and body, verbatim)
            ...

    def herd():
        nonlocal budget
        # (the existing comments and body, verbatim, including cash_floor)
        ...

    steps = {"hires": hires, "land": land_step, "seed": seed, "herd": herd}
    for name in (BUY_ORDER if order is None else order):
        steps[name]()
```

then the feed block and the dawn/sell ordering exactly as before. (`seed` and `herd` are the existing blocks; move them, do not rewrite them.)

Hook after `cluster_size`:

```python
    def buy_order(self):
        """The buy blocks to run and their order, or ``None`` for the frozen
        `BUY_ORDER`. A seam for contenders (#254); never fires on the benchmark."""
        return None
```

`act`: the `market_orders(...)` call gains `order=self.buy_order()` after `pivot=pivot`.

- [ ] **Step 4: Run green** — `.venv/bin/python -m pytest -q -n auto` (the golden pin must still pass after the split).
- [ ] **Step 5: Commit**

```bash
git add strategies/field_rival.py tests/test_field_rival.py
git commit -m "field_rival: the buy blocks as named steps behind a buy_order seam, frozen by default (#254)

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 2: The contender `herd_first`

**Files:**
- Create: `strategies/herd_first.py`
- Test: `tests/test_herd_first.py`

**Interfaces:**
- Consumes: Task 1's `buy_order` hook; `strategies.field_pace.FieldPaceStrategy`.
- Produces: `ORDER_H = ("hires", "herd", "land", "seed")`; `HerdFirstStrategy(FieldPaceStrategy)` with `name = "herd_first"`, `benchmark = False`, `ORDER_H` as a class attribute, `buy_order()` returning it; `STRATEGY = HerdFirstStrategy`.

- [ ] **Step 1: Write the failing tests** — `tests/test_herd_first.py`:

```python
"""herd_first: field_pace with the herd funded before land and seed (#254).

#252 stood 6 head by day 8 with 15 in cash: the benchmark's buy order funds land
and the whole strawberry seed bill before the herd. The herd is the field's
pre-payday cash engine -- one fertilizer per animal per day at ~100, wool from
day 6 -- so this arm moves it ahead of land and seed through the buy_order seam
and changes nothing else.
"""

from __future__ import annotations

from strategies import field_pace as fp
from strategies import herd_first as hf


def test_the_declared_order():
    # One decision on top of #252's package: the herd before land and seed.
    assert hf.ORDER_H == ("hires", "herd", "land", "seed")
    assert hf.HerdFirstStrategy.ORDER_H == hf.ORDER_H
    assert hf.HerdFirstStrategy.name == "herd_first"
    assert hf.HerdFirstStrategy.benchmark is False


def test_the_hook_answers_with_the_declared_order():
    assert hf.HerdFirstStrategy().buy_order() == hf.ORDER_H
    assert fp.FieldPaceStrategy().buy_order() is None      # field_pace keeps the frozen order


def test_it_is_a_registered_contender_that_inherits_every_field_pace_knob():
    from strategies import REGISTRY, load
    assert "herd_first" in REGISTRY and load("herd_first") is hf.HerdFirstStrategy
    assert issubclass(hf.HerdFirstStrategy, fp.FieldPaceStrategy)
    s, base = hf.HerdFirstStrategy(), fp.FieldPaceStrategy()
    for day in (0, 6, 8, 11, 15):
        assert s.hire_target(day) == base.hire_target(day)
        assert s.land_target(day) == base.land_target(day)
        assert s.herd_target(day) == base.herd_target(day)
        assert s.pasture_count(day, 0) == base.pasture_count(day, 0)
    assert s.pivot_day() == base.pivot_day() and s.cluster_size() == base.cluster_size()
    assert s.capital_reserve() == base.capital_reserve() and s.layout() == base.layout()
    assert hf.HerdFirstStrategy.CAPS == fp.FieldPaceStrategy.CAPS
```

- [ ] **Step 2: Run them and quote the failure** — `.venv/bin/python -m pytest -q tests/test_herd_first.py`; expected: collection `ImportError: cannot import name 'herd_first' from 'strategies'`.

- [ ] **Step 3: Minimal implementation** — `strategies/herd_first.py`:

```python
"""herd_first: field_pace with the herd funded before land and seed (#254).

#252 put the field's schedule on the benchmark's buy order and stood 6 head by
day 8 with 15 in cash: `market_orders` funds land and the whole strawberry seed
bill before the herd. The field funds its herd first, and the sim says why that
is self-funding -- every placed animal makes one fertilizer a day, fertilizer
sells from 100 and falls 0.2 a unit with no shop draining it, sheep add wool
from day 6. Four head from day 0 earn ~380 a day before any melon pays; thirteen
~1,200; lonespear takes 51% of its revenue from livestock and fertilizer (#234).

One decision changes: `buy_order` runs the herd block before land and seed,
through the seam on the frozen benchmark (#181, #202, #237, #246, #252, #254).
Every `field_pace` knob and every `third_herder` rule beneath it is inherited.

Declared before measurement: `ORDER_H`, and the controls and criterion in
`harness/order_bench.py` (posted to #254 before any code).
"""

from __future__ import annotations

from strategies.field_pace import FieldPaceStrategy

#: The herd ahead of land and seed; sells first and feed last as ever.
ORDER_H = ("hires", "herd", "land", "seed")


class HerdFirstStrategy(FieldPaceStrategy):
    """`field_pace` with the herd funded first."""

    name = "herd_first"
    benchmark = False

    ORDER_H = ORDER_H

    def buy_order(self):
        return self.ORDER_H


STRATEGY = HerdFirstStrategy
```

- [ ] **Step 4: Run green** — the whole suite (the no-crash gate now plays `herd_first`): `.venv/bin/python -m pytest -q -n auto`.
- [ ] **Step 5: Commit**

```bash
git add strategies/herd_first.py tests/test_herd_first.py
git commit -m "herd_first: field_pace with the herd funded before land and seed (#254)

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 3: The declared bench `harness/order_bench.py`

**Files:**
- Create: `harness/order_bench.py`
- Test: `tests/test_order_bench.py`
- Reference (read, do not modify): `harness/pace_bench.py` (`REFERENCE`, `PILKWANG`, `PAYDAY_MONEY`, `shape_reading(turns, shape_day, crop_day)` → keys `planted, quadrants, hands, head_placed, strawberry, money_at_shape_day, planted_at_crop_day, money_at_crop_day, payday`; `format_shape(rows)`; `run_controls`' `off` class and `main`'s shape), `harness/rival_bench.py` (`criterion`, `format_rows`, `format_external`, `paired_external_rows`), `harness/farm_census.py` (`census_series`).

**Interfaces:**
- Produces: the declared constants; `mechanism_ok(reading) -> bool` (`reading["head_placed"] >= HEAD_BAR`); `crop_line_ok(contender, pace) -> bool` (`abs(contender["planted_at_crop_day"] - pace["planted_at_crop_day"]) <= PLANTED_GAP_BAR`); `arm_b_class() -> type` (unregistered subclass of `field_pace` whose `buy_order` returns `ORDER_B`); live `run_controls`, `run_criterion`, `run_recorded`, `main` (`--controls/--criterion/--recorded`, exit 0/1/2).

- [ ] **Step 1: Write the failing tests** — `tests/test_order_bench.py`:

```python
"""The herd_first experiment's declared constants and the pure parts it adds.

The verdict machinery is `harness.rival_bench`'s and the census readers
`harness.pace_bench`'s -- imported, not copied. New here: an absolute head-placed
control at day 8 (the bar #252 failed) and a crop-line control PAIRED against
field_pace on the same seed, the cost the arm is allowed to pay.
"""

from __future__ import annotations

from harness import order_bench as ob
from harness import pace_bench as pb
from harness import rival_bench as rb


def test_the_declared_constants():
    # Declared on #254 before any code; not to be tuned.
    assert ob.CONTENDER == "herd_first" and ob.CHAMPION == "third_herder" and ob.PACE == "field_pace"
    assert ob.SEEDS == tuple(range(912, 928)) and ob.CONTROL_SEED == 912
    assert ob.CHAMPION_BAR == 0.60 and ob.ANCHOR_BAR == 0.90
    assert ob.ARM_B == "herd_mid" and ob.ORDER_B == ("hires", "land", "herd", "seed")
    assert ob.HEAD_DAY == 8 and ob.HEAD_BAR == 8
    assert ob.CROP_DAY == 12 and ob.PLANTED_GAP_BAR == 12


def test_the_seeds_are_fresh_against_every_range_already_spent():
    # 896 was #252's control seed; 897-911 were never played but are not reused.
    spent = set(range(100, 116)) | set(range(200, 216)) | set(range(300, 332)) \
        | set(range(400, 416)) | set(range(500, 516)) | set(range(600, 616)) \
        | set(range(700, 704)) | set(range(800, 912))
    assert not spent & set(ob.SEEDS)


def test_the_verdict_logic_and_the_readers_are_imported_not_copied():
    assert ob.criterion is rb.criterion and ob.format_rows is rb.format_rows
    assert ob.format_external is rb.format_external
    assert ob.paired_external_rows is rb.paired_external_rows
    assert ob.shape_reading is pb.shape_reading and ob.format_shape is pb.format_shape
    assert ob.REFERENCE == pb.REFERENCE and ob.PILKWANG == pb.PILKWANG


def _reading(head=8, planted_at_12=40):
    return {"planted": 25, "quadrants": 2, "hands": 9, "head_placed": head, "strawberry": 10,
            "money_at_shape_day": 300.0, "planted_at_crop_day": planted_at_12,
            "money_at_crop_day": 4000.0, "payday": 11}


def test_mechanism_gates_on_head_placed_at_the_bar():
    # The bar #252 failed at 6: eight placed passes, seven does not.
    assert ob.mechanism_ok(_reading(head=8)) is True
    assert ob.mechanism_ok(_reading(head=7)) is False


def test_crop_line_is_paired_against_field_pace_within_the_gap():
    # The cost the arm may pay: twelve tiles either side of field_pace's count.
    pace = _reading(planted_at_12=47)
    assert ob.crop_line_ok(_reading(planted_at_12=35), pace) is True
    assert ob.crop_line_ok(_reading(planted_at_12=34), pace) is False
    assert ob.crop_line_ok(_reading(planted_at_12=59), pace) is True
    assert ob.crop_line_ok(_reading(planted_at_12=60), pace) is False


def test_arm_b_is_herd_before_seed_after_land_and_is_not_registered():
    from strategies import REGISTRY
    from strategies.field_pace import FieldPaceStrategy
    cls = ob.arm_b_class()
    assert issubclass(cls, FieldPaceStrategy)
    arm, base = cls(), FieldPaceStrategy()
    assert arm.buy_order() == ob.ORDER_B and base.buy_order() is None
    assert arm.herd_target(8) == base.herd_target(8) and arm.layout() == base.layout()
    assert ob.ARM_B not in REGISTRY and ob.CONTENDER in REGISTRY
```

- [ ] **Step 2: Run them and quote the failure** — `.venv/bin/python -m pytest -q tests/test_order_bench.py`; expected: collection `ImportError: cannot import name 'order_bench' from 'harness'`.

- [ ] **Step 3: Minimal implementation** — `harness/order_bench.py`:

```python
"""herd_first: does funding the herd before land and seed stand the field's herd, and beat the champion?

    python -m harness.order_bench --controls     # identity, head placed at day 8, the paired crop line
    python -m harness.order_bench --criterion    # 16 seeds: champion, anchors, the external limb
    python -m harness.order_bench --recorded     # arm B (recorded, not gated)
    python -m harness.order_bench                # controls then criterion

Declared on #254 before any code: seeds 912-927 -- fresh; 100-115, 200-215,
300-331, 400-415, 500-515, 600-615, 700-703 and 800-896 are spent -- sides
alternated by list position (`harness.triage.head_to_head_rate`); PROMOTE
only at >= 60% of 16 vs the champion `third_herder` AND >= 90% vs each
DEFAULT_ANCHOR AND, for each `external_pool.EXTERNAL_ANCHORS` member, no fewer
wins than the champion on the same seeds in the same run (#152's paired limb);
a tie is not a win. Controls run first and a failed control voids the run --
arm B is then not scored either. Exit codes: 0 PROMOTE, 1 REJECTED, 2 VOID.
Runs under ROBRICULTURE_STRICT=1.

**The controls.** #252 VOIDed on head placed at day 8 (6 against a bar of 8)
because the benchmark's buy order funds land and seed before the herd. This
arm moves the herd first, so the mechanism control is that same bar, absolute,
read off the contender's own census. The cost it may pay is a later crop
line, so the crop control is PAIRED against `field_pace` on the same seed:
planted tiles at day 12 within `PLANTED_GAP_BAR` of field_pace's.

The verdict, the row and external formatting and the paired external rows
are `harness.rival_bench`'s; the census readers are `harness.pace_bench`'s.
"""

from __future__ import annotations

import argparse
import os

from harness.evolve import DEFAULT_ANCHORS
from harness.pace_bench import (  # noqa: F401  -- the tests pin these to pace_bench's own
    PAYDAY_MONEY,
    PILKWANG,
    REFERENCE,
    format_shape,
    shape_reading,
)
from harness.rival_bench import (  # noqa: F401  -- the tests pin these to rival_bench's own
    criterion,
    format_external,
    format_rows,
    paired_external_rows,
)

CONTENDER = "herd_first"
CHAMPION = "third_herder"
PACE = "field_pace"

#: Fresh. Everything through 896 is spent; 897-911 were declared for #252 and
#: never played, and are not reused.
SEEDS = tuple(range(912, 928))
CHAMPION_BAR = 0.60
ANCHOR_BAR = 0.90
CONTROL_SEED = 912

#: Arm B: the herd before seed but after land. If B matches A, land's priority
#: is not what moved. Never registered.
ARM_B = "herd_mid"
ORDER_B = ("hires", "land", "herd", "seed")

#: The mechanism: the bar #252 failed at 6.
HEAD_DAY = 8
HEAD_BAR = 8

#: The cost the arm may pay: planted tiles at day 12 within this many of
#: field_pace's on the same seed (field_pace measured 47 on seed 896).
CROP_DAY = 12
PLANTED_GAP_BAR = 12


def mechanism_ok(reading):
    """Control (ii): the herd the buy order was moved for is actually standing."""
    return reading["head_placed"] >= HEAD_BAR


def crop_line_ok(contender, pace):
    """Control (iii): the crop line paid no more than the declared gap."""
    return abs(contender["planted_at_crop_day"] - pace["planted_at_crop_day"]) <= PLANTED_GAP_BAR


def arm_b_class():
    """`field_pace` with the herd before seed, after land. Never registered."""
    from strategies import load

    return type("HerdMid", (load(PACE),), {"buy_order": lambda self: ORDER_B})


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
    """Identity, then head placed at day 8, then the paired crop line."""
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
        "buy_order": lambda self: None,
        "CAPS": load(REFERENCE).CAPS,
    })
    base = play_rewards(make_agent(load(REFERENCE)()), make_agent(load(REFERENCE)()), seed)
    got = play_rewards(make_agent(off()), make_agent(load(REFERENCE)()), seed)
    precondition_ok = base[0] > 0
    out["identity"] = {"ok": got == base and precondition_ok, "base": base, "got": got,
                       "precondition_ok": precondition_ok}

    ours, theirs = census_series(make_agent(load(CONTENDER)()), make_agent(load(CHAMPION)()), seed)
    pace_turns, _ = census_series(make_agent(load(PACE)()), make_agent(load(CHAMPION)()), seed)
    contender = shape_reading(ours, HEAD_DAY, CROP_DAY)
    champion = shape_reading(theirs, HEAD_DAY, CROP_DAY)
    pace = shape_reading(pace_turns, HEAD_DAY, CROP_DAY)
    out["mechanism"] = {"ok": mechanism_ok(contender), "contender": contender,
                        "champion": champion, "pace": pace}
    out["crop_line"] = {"ok": crop_line_ok(contender, pace),
                        "gap": abs(contender["planted_at_crop_day"] - pace["planted_at_crop_day"])}
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
    ap = argparse.ArgumentParser(description="herd_first: the herd funded before land and seed")
    ap.add_argument("--controls", action="store_true")
    ap.add_argument("--criterion", action="store_true")
    ap.add_argument("--recorded", action="store_true", help="arm B (recorded, not gated)")
    args = ap.parse_args(argv)

    if args.recorded:
        print(format_rows(run_recorded()))
        print(f"recorded, not gated: arm B ({ARM_B}: the herd before seed, after land) vs {CHAMPION}")
        return 0

    do_controls = args.controls or not args.criterion
    do_criterion = args.criterion or not args.controls

    if do_controls:
        ctl = run_controls()
        print(f"control identity: {'OK' if ctl['identity']['ok'] else 'FAIL -- RUN VOID'}"
              f"  {ctl['identity']}")
        c = ctl["mechanism"]["contender"]
        print(f"control mechanism: {'OK' if ctl['mechanism']['ok'] else 'FAIL -- RUN VOID'}  "
              f"(declared: head placed at day {HEAD_DAY} >= {HEAD_BAR})  head_placed={c['head_placed']}")
        print(f"control crop line: {'OK' if ctl['crop_line']['ok'] else 'FAIL -- RUN VOID'}  "
              f"(declared: |planted at day {CROP_DAY} - field_pace's| <= {PLANTED_GAP_BAR})  "
              f"gap={ctl['crop_line']['gap']}")
        print(format_shape([(CONTENDER, c), (PACE, ctl["mechanism"]["pace"]),
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
              f"{v['failing'] or 'none'} -> {'PROMOTE' if v['passed'] else 'REJECTED'}; "
              f"pilkwang paired row (contender, champion): {v['external'].get(PILKWANG)}")
        return 0 if v["passed"] else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Note for the implementer: `format_shape` prints one line per `(label, reading)` pair, so three rows is fine; check that `pace_bench.shape_reading`'s signature is `(turns, shape_day=..., crop_day=...)` and pass positionally as written.

- [ ] **Step 4: Run green, with coverage** — `.venv/bin/python -m pytest -q -n auto --cov --cov-branch --cov-report=term-missing 2>&1 | grep -E "order_bench|herd_first|passed|failed"`.
- [ ] **Step 5: Commit**

```bash
git add harness/order_bench.py tests/test_order_bench.py
git commit -m "order_bench: #254's identity, head-placed and paired crop-line controls, criterion and arm B

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

## Self-review

- **Spec coverage.** Seam + refactor + golden pin → Task 1. Contender → Task 2. Bench with eleven-seam identity, absolute head bar, paired crop line against field_pace, criterion with the pilkwang row, arm B → Task 3. Run/record/PR → the controller.
- **Placeholders.** The two `...` in Task 1's step bodies stand for "the existing block moved verbatim" and are labelled so; everything else is complete.
- **Type consistency.** `buy_order()` (Task 1 hook, Task 2 answer, Task 3 switch-off and arm B); `market_orders(order=)` keyword matches `act`'s call; `shape_reading` keys used by `mechanism_ok` / `crop_line_ok` / the tests are `pace_bench`'s.
