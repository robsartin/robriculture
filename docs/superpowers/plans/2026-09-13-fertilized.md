# fertilized (#277) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Two fertilizer seams on the frozen benchmark, the `fertilized` contender on `payday_herd`, and its declared bench — exactly as `docs/superpowers/specs/2026-09-13-fertilized-design.md` and the declaration on #277.

**Architecture:** Task 1 extends `strategies/field_rival.py` through keyword parameters defaulting to the frozen behaviour plus two class hooks returning `None` (the seam pattern of #246–#262). Task 2 adds one strategy file and one bench in the shape of `harness/payday_bench.py`.

**Tech Stack:** Python 3.12, `.venv/bin/python`, pytest.

## Global Constraints
- Pure TDD: failing tests first, RUN and observe, then the code; the report quotes the red.
- `strategies/field_rival.py` may change ONLY as Task 1 specifies (new keyword parameters with frozen defaults, two `None` hooks, the threading in `act`). `tests/test_field_rival.py` is not edited and must stay green.
- `.venv/bin/python` only; every command blocking; do NOT run the full suite (the controller does) — only the targeted tests named per task.
- Stage by explicit path; never `git add -A`; never stage `.venv`, `external_agents`, `replays/`.
- Declared values verbatim: `FERT_CARRY = 3`; `FERT_CROPS = ("STRAWBERRY", "MELON")`, `FERT_STOCK = 24`; bench `CONTENDER = "fertilized"`, `CHAMPION = "payday_herd"`, `SEEDS = tuple(range(1056, 1072))`, `CONTROL_SEED = 1056`, `CHAMPION_BAR = 0.60`, `ANCHOR_BAR = 0.90`, `FERTILIZE_BAR = 30`, `STRAWBERRY_FACTOR = 1.5`, `ARM_B = "melon_only"`.

---

### Task 1: The fertilizer seams on the frozen benchmark

**Files:**
- Modify: `strategies/field_rival.py` (`crop_worker_action` ~line 310; the sell sweep in `market_orders` ~line 383; the class hooks after `feed_stock` ~line 732; `act` ~lines 780–805)
- Test: `tests/test_fertilize_seams.py` (new)

**Interfaces:**
- Produces: `fr.FERT_CARRY`; `crop_worker_action(cluster, tiles, pos, inv, crop, day, hour, shed=None, fertilize=None, fert_carry=FERT_CARRY)`; `market_orders(..., fert=None)`; `FieldRivalStrategy.fertilizer_stock(self) -> None`, `FieldRivalStrategy.fertilize_crops(self) -> None`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_fertilize_seams.py
"""The two fertilizer seams on the frozen benchmark (#277): off by default and
byte-identical when off; pickup, the WATER->FERTILIZE intercept and the sweep's
hold-back when on."""

from __future__ import annotations

from strategies import field_rival as fr


def _blank():
    return [[None for _ in range(10)] for _ in range(10)]


def _plant(crop="STRAWBERRY", day=0, watered=False, fert_until=-1, ready=False):
    t = {"kind": "PLANT", "crop": crop, "planted_day": day, "watered_today": watered,
         "fertilized_until_day": fert_until, "yield_units": 0, "consecutive_unwatered": 0,
         "cared_today": False, "harvest_ready": ready, "max_lifespan_step": -1}
    return t


def test_the_constant():
    assert fr.FERT_CARRY == 3


def test_frozen_path_never_picks_up_or_fertilizes_even_with_fertilizer_everywhere():
    tiles = _blank()
    tiles[4][4] = _plant()
    # at the shed, empty-handed, shed stocked: the frozen call has no `shed` and no `fertilize`
    assert fr.crop_worker_action(((4, 4),), tiles, (4, 4), {}, "STRAWBERRY", 12, 3) == ["WATER"]
    # fertilizer in hand, standing on an unfertilized tile: still WATER when the seam is off
    assert fr.crop_worker_action(((4, 4),), tiles, (4, 4), {"FERTILIZER": 3}, "STRAWBERRY", 12, 3,
                                 shed={"FERTILIZER": 10}) == ["WATER"]


def test_pickup_at_the_shed_only_when_active_empty_handed_and_stocked():
    tiles = _blank()
    tiles[0][0] = _plant()
    on = ("STRAWBERRY", "MELON")
    assert fr.crop_worker_action(((0, 0),), tiles, (4, 4), {}, "STRAWBERRY", 12, 3,
                                 shed={"FERTILIZER": 10}, fertilize=on) == ["PICKUP", "FERTILIZER", 3]
    assert fr.crop_worker_action(((0, 0),), tiles, (4, 4), {}, "STRAWBERRY", 12, 3,
                                 shed={"FERTILIZER": 2}, fertilize=on) == ["PICKUP", "FERTILIZER", 2]
    assert fr.crop_worker_action(((0, 0),), tiles, (4, 4), {}, "STRAWBERRY", 12, 3,
                                 shed={"FERTILIZER": 10}, fertilize=on, fert_carry=1) == ["PICKUP", "FERTILIZER", 1]
    # already holding some: no pickup, go tend
    assert fr.crop_worker_action(((0, 0),), tiles, (4, 4), {"FERTILIZER": 1}, "STRAWBERRY", 12, 3,
                                 shed={"FERTILIZER": 10}, fertilize=on) in (["WEST"], ["NORTH"])
    # shed empty: go tend
    assert fr.crop_worker_action(((0, 0),), tiles, (4, 4), {}, "STRAWBERRY", 12, 3,
                                 shed={}, fertilize=on) in (["WEST"], ["NORTH"])
    # away from the shed: never a trip for fertilizer
    assert fr.crop_worker_action(((0, 0),), tiles, (1, 0), {}, "STRAWBERRY", 12, 3,
                                 shed={"FERTILIZER": 10}, fertilize=on) == ["WEST"]


def test_water_becomes_fertilize_when_the_tile_has_lapsed_and_the_worker_has_some():
    on = ("STRAWBERRY", "MELON")
    tiles = _blank()
    tiles[4][4] = _plant(fert_until=-1)
    inv = {"FERTILIZER": 1}
    assert fr.crop_worker_action(((4, 4),), tiles, (4, 4), inv, "STRAWBERRY", 12, 3,
                                 shed={}, fertilize=on) == ["FERTILIZE"]
    # still fertilized through today: water
    tiles[4][4] = _plant(fert_until=12)
    assert fr.crop_worker_action(((4, 4),), tiles, (4, 4), inv, "STRAWBERRY", 12, 3,
                                 shed={}, fertilize=on) == ["WATER"]
    # lapsed yesterday: fertilize
    tiles[4][4] = _plant(fert_until=11)
    assert fr.crop_worker_action(((4, 4),), tiles, (4, 4), inv, "STRAWBERRY", 12, 3,
                                 shed={}, fertilize=on) == ["FERTILIZE"]
    # crop not in the set: water
    tiles[4][4] = _plant(crop="WHEAT")
    assert fr.crop_worker_action(((4, 4),), tiles, (4, 4), inv, "STRAWBERRY", 12, 3,
                                 shed={}, fertilize=on) == ["WATER"]
    # nothing in hand: water
    tiles[4][4] = _plant()
    assert fr.crop_worker_action(((4, 4),), tiles, (4, 4), {}, "STRAWBERRY", 12, 3,
                                 shed={}, fertilize=on) == ["WATER"]
    # walks toward a lapsed tile it is not standing on
    assert fr.crop_worker_action(((4, 4),), tiles, (4, 6), inv, "STRAWBERRY", 12, 3,
                                 shed={}, fertilize=on) == ["NORTH"]


def test_harvest_is_never_displaced_by_fertilizing(monkeypatch):
    on = ("STRAWBERRY",)
    tiles = _blank()
    tiles[4][4] = _plant()
    monkeypatch.setattr(fr.hh, "harvest_ready", lambda tile, day: True)
    assert fr.crop_worker_action(((4, 4),), tiles, (4, 4), {"FERTILIZER": 2}, "STRAWBERRY", 12, 3,
                                 shed={}, fertilize=on) == ["HARVEST"]


def test_fertilizer_in_hand_is_not_a_load_only_when_the_seam_is_on():
    tiles = _blank()
    tiles[0][0] = _plant()
    inv = {"MELON": fr.CARRY_LIMIT - 1, "FERTILIZER": 3}
    # seam off: 8 items >= the limit -> head for the shed
    assert fr.crop_worker_action(((0, 0),), tiles, (0, 0), inv, "MELON", 12, 3) in (["EAST"], ["SOUTH"])
    # seam on: 5 produce < the limit -> tend the tile it stands on
    assert fr.crop_worker_action(((0, 0),), tiles, (0, 0), inv, "MELON", 12, 3,
                                 shed={}, fertilize=("MELON",)) in (["FERTILIZE"], ["WATER"])


def test_the_sweep_keeps_fert_units_of_fertilizer_and_sells_all_by_default():
    common = dict(day=20, hour=6, money=5_000, hands=10, quadrants=3, animals=0,
                  shed={"FERTILIZER": 30}, seeds={}, empty_plots=0)
    assert ["SELL", "FERTILIZER", 30] in fr.market_orders(**common)
    assert ["SELL", "FERTILIZER", 6] in fr.market_orders(**common, fert=24)
    assert not [o for o in fr.market_orders(**common, fert=40) if o[:2] == ["SELL", "FERTILIZER"]]


def test_the_two_hooks_return_none_on_the_benchmark_and_are_seams():
    s = fr.FieldRivalStrategy()
    assert s.fertilizer_stock() is None and s.fertilize_crops() is None
    from harness.sheep_bench import _seam_names
    names = _seam_names()
    assert {"fertilizer_stock", "fertilize_crops"} <= set(names) and len(names) == 16


def test_a_contender_with_the_seams_on_survives_a_turn():
    cls = type("Fert", (fr.FieldRivalStrategy,), {
        "fertilizer_stock": lambda self: 5, "fertilize_crops": lambda self: ("MELON",)})
    from kaggisim.state import parse
    from kaggle_environments import make
    env = make("kaggriculture", configuration={"seed": 1056, "episodeSteps": 3})
    out = cls().act(parse(env.reset()[0].observation))
    assert set(out) >= {"farmer", "hands", "market"}
```

- [ ] **Step 2: Run the tests and observe them fail**

Run: `.venv/bin/python -m pytest tests/test_fertilize_seams.py -q`
Expected: `AttributeError: module 'strategies.field_rival' has no attribute 'FERT_CARRY'`, `TypeError: crop_worker_action() got an unexpected keyword argument 'shed'`, `TypeError: market_orders() got an unexpected keyword argument 'fert'`, `AttributeError: ... 'fertilizer_stock'`. Quote them.

- [ ] **Step 3: Extend `strategies/field_rival.py`**

Add the constant next to `CARRY_LIMIT`:

```python
#: Fertilizer a crop worker takes from the shed per visit when a contender
#: fertilizes (#277); the frozen benchmark never does.
FERT_CARRY = 3
```

Replace `crop_worker_action` with:

```python
def crop_worker_action(cluster, tiles, pos, inv, crop, day, hour, shed=None,
                       fertilize=None, fert_carry=FERT_CARRY):
    """One crop worker's action: bank a full load, else tend the first tile in
    its cluster that wants something, else walk any leftovers back to the shed.

    `fertilize`: crops to fertilize before watering, or ``None`` for never
    (#277). When set, fertilizer in hand is a tool rather than a load, a worker
    already at the shed with none in hand takes `fert_carry` from `shed`, and a
    tile due for WATER whose crop is in the set and whose fertilizer has lapsed
    gets FERTILIZE first -- the next turn's WATER earns the bonus. The frozen
    benchmark never fertilizes, so with `fertilize` ``None`` nothing here moves.
    """
    inv = inv or {}
    shed_tile = nearest_shed(pos)
    at_shed = [pos[0], pos[1]] == [shed_tile[0], shed_tile[1]]
    carrying = sum(n for item, n in inv.items()
                   if fertilize is None or item != "FERTILIZER")

    if carrying >= CARRY_LIMIT:
        return ["DROP"] if at_shed else hh.step_toward(pos, shed_tile)

    if fertilize is not None and at_shed and not inv.get("FERTILIZER"):
        stock = int((shed or {}).get("FERTILIZER", 0) or 0)
        if stock > 0:
            return ["PICKUP", "FERTILIZER", min(stock, fert_carry)]

    # Nearest first, not cluster order: the cluster is sorted by distance from
    # the shed, which says nothing about where this worker is standing. Serving
    # the first tile in the list instead of the closest one put 52% of all
    # worker-turns into walking.
    best = None
    for tile in cluster:
        plot = _tile_at(tiles, tile)
        action = plot_action(plot, crop, day, hour)
        if action == ["PASS"]:
            continue
        if (fertilize is not None and action == ["WATER"] and inv.get("FERTILIZER", 0) > 0
                and isinstance(plot, dict) and plot.get("crop") in fertilize
                and plot.get("fertilized_until_day", -1) < day):
            action = ["FERTILIZE"]
        dist = abs(tile[0] - pos[0]) + abs(tile[1] - pos[1])
        if dist == 0:
            return action
        if best is None or dist < best[0]:
            best = (dist, tile)
    if best is not None:
        return hh.step_toward(pos, best[1])

    if carrying:
        return ["DROP"] if at_shed else hh.step_toward(pos, shed_tile)
    return ["PASS"]
```

In `market_orders`, add `fert=None` as the last keyword parameter, document it in the docstring (`` `fert`: fertilizer the shed keeps back from the sweep for the crop line, or ``None`` for none (#277). ``), and change the sweep's keep line to:

```python
        keep = reserved if item == "WHEAT" else (0 if fert is None else int(fert)) if item == "FERTILIZER" else 0
```

Add the two hooks to `FieldRivalStrategy` right after `feed_stock`:

```python
    def fertilizer_stock(self):
        """Fertilizer the shed keeps back from the sell sweep for the crop line,
        or ``None`` for none. A seam for contenders (#277); never fires on the
        benchmark, which sells every unit."""
        return None

    def fertilize_crops(self):
        """Crops a worker fertilizes before watering, or ``None`` for never. A
        seam for contenders (#277); never fires on the benchmark."""
        return None
```

In `act`, before the worker loop add `fertilize = self.fertilize_crops()`, pass `shed=shed, fertilize=fertilize` to `crop_worker_action(mine, tiles, pos, inv, crop, day, hour, shed=shed, fertilize=fertilize)`, and pass `fert=self.fertilizer_stock()` to `market_orders(...)` after `feed=feed`.

- [ ] **Step 4: Run the tests and observe them pass**

Run: `.venv/bin/python -m pytest tests/test_fertilize_seams.py tests/test_field_rival.py tests/test_lean_feed.py tests/test_feed_bench.py tests/test_sheep_bench.py tests/test_payday_bench.py -q`
Expected: all PASS. `test_field_rival.py` untouched and green proves the frozen defaults; `test_sheep_bench`'s seam-count assertions, if any pin 14, must be read: the brief says `_seam_names()` now yields 16 — if an existing test pins exactly 14, STOP and report BLOCKED with the test name (do not edit it).

- [ ] **Step 5: Commit**

```bash
git add strategies/field_rival.py tests/test_fertilize_seams.py
git commit -m "feat(#277): fertilizer seams on the frozen benchmark — sweep hold-back and FERTILIZE-before-WATER, off by default

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 2: The contender and the bench

**Files:**
- Create: `strategies/fertilized.py`, `harness/fert_bench.py`
- Test: `tests/test_fertilized.py`, `tests/test_fert_bench.py`

**Interfaces:**
- Consumes (from Task 1): `FieldRivalStrategy.fertilizer_stock`, `fertilize_crops`; `strategies.payday_herd.PaydayHerdStrategy`; `harness.sheep_bench._seam_names`; `harness.payday_bench.load_reference` (or `reserve_bench.REFERENCE`); `harness.episode_analysis._slot`; `harness.cashflow.play`; `harness.rival_bench.*`; `harness.reserve_bench.MADHUR, PILKWANG, REFERENCE`; `harness.external_pool.EXTERNAL_ANCHORS`; `harness.evolve.DEFAULT_ANCHORS`; `harness.triage.head_to_head_rate`, `_default_agents`; `harness.tournament.play_rewards`; `strategies.field_pace.HERD_RAMP_F`.
- Produces: `fertilized.FERT_CROPS`, `FERT_STOCK`, `FertilizedStrategy`, `STRATEGY`; `fert_bench.action_counts`, `units_sold`, `reading`, `mechanism_failures`, `off_class`, `arm_b_class`, `main`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_fertilized.py
"""fertilized (#277): the two seams on, nothing else."""

from __future__ import annotations

from strategies import fertilized as fz
from strategies.payday_herd import PaydayHerdStrategy


def test_the_declared_knobs():
    assert fz.FERT_CROPS == ("STRAWBERRY", "MELON") and fz.FERT_STOCK == 24


def test_only_the_two_fertilizer_seams_are_overridden():
    from harness.sheep_bench import _seam_names
    assert set(fz.FertilizedStrategy.__dict__) & set(_seam_names()) == {"fertilizer_stock", "fertilize_crops"}
    p, q = fz.FertilizedStrategy(), PaydayHerdStrategy()
    assert p.name == "fertilized" and isinstance(p, PaydayHerdStrategy)
    assert p.fertilizer_stock() == 24 and p.fertilize_crops() == ("STRAWBERRY", "MELON")
    assert q.fertilizer_stock() is None and q.fertilize_crops() is None
    assert p.herd_target(8) == q.herd_target(8) == 8 and p.feed_stock(animals=9) == q.feed_stock(animals=9)


def test_registered():
    from strategies import load
    assert load("fertilized") is fz.FertilizedStrategy
```

```python
# tests/test_fert_bench.py
"""The fertilized experiment's declared constants and pure parts (#277)."""

from __future__ import annotations

from harness import fert_bench as fb
from strategies import field_pace as fp


def test_the_declared_constants():
    assert fb.CONTENDER == "fertilized" and fb.CHAMPION == "payday_herd" and fb.ARM_B == "melon_only"
    assert fb.SEEDS == tuple(range(1056, 1072)) and fb.CONTROL_SEED == 1056
    assert fb.CHAMPION_BAR == 0.60 and fb.ANCHOR_BAR == 0.90
    assert fb.FERTILIZE_BAR == 30 and fb.STRAWBERRY_FACTOR == 1.5
    assert fb.LONESPEAR.startswith("lonespear") and fb.PILKWANG.startswith("pilkwang")


def test_the_seeds_are_fresh_against_every_range_already_spent():
    spent = set(range(100, 116)) | set(range(200, 216)) | set(range(300, 332)) \
        | set(range(400, 416)) | set(range(500, 516)) | set(range(600, 616)) \
        | set(range(700, 704)) | set(range(800, 960)) | set(range(960, 1056))
    assert not spent & set(fb.SEEDS)


def _step(seat_actions):
    """One step: a list of per-seat slots, each with an action dict."""
    return [{"action": a, "observation": {}, "reward": 0, "status": "ACTIVE"} for a in seat_actions]


STEPS = [
    _step([{"farmer": ["WATER"], "hands": [["FERTILIZE"], ["WATER"]], "market": [["SELL", "STRAWBERRY", 4], ["SELL", "FERTILIZER", 2]]},
           {"farmer": ["PASS"], "hands": [["WATER"]], "market": [["SELL", "MELON", 3]]}]),
    _step([{"farmer": ["FERTILIZE"], "hands": [["HARVEST"], ["FERTILIZE"]], "market": [["SELL", "STRAWBERRY", 6], ["BUY_SEED", "WHEAT", 1]]},
           {"farmer": ["WATER"], "hands": [], "market": [["SELL", "MELON", 5], ["SELL", "STRAWBERRY", 1]]}]),
]


def test_action_counts_and_units_sold_read_one_seat():
    assert fb.action_counts(STEPS, 0) == {"WATER": 2, "FERTILIZE": 3, "HARVEST": 1}
    assert fb.action_counts(STEPS, 1) == {"PASS": 1, "WATER": 2}
    assert fb.units_sold(STEPS, 0) == {"STRAWBERRY": 10, "FERTILIZER": 2}
    assert fb.units_sold(STEPS, 1) == {"MELON": 8, "STRAWBERRY": 1}


def test_reading_has_the_declared_fields():
    assert fb.reading(STEPS, 0) == {"fertilize": 3, "water": 2, "strawberry": 10, "melon": 0, "fertilizer_sold": 2}
    assert fb.reading(STEPS, 1) == {"fertilize": 0, "water": 2, "strawberry": 1, "melon": 8, "fertilizer_sold": 0}


def test_mechanism_failures_name_the_bars():
    champ = {"fertilize": 0, "water": 900, "strawberry": 150, "melon": 45, "fertilizer_sold": 230}
    good = {"fertilize": 40, "water": 850, "strawberry": 225, "melon": 45, "fertilizer_sold": 120}
    assert fb.mechanism_failures(good, champ) == []
    assert fb.mechanism_failures({**good, "fertilize": 29}, champ) == ["fertilize"]
    assert fb.mechanism_failures({**good, "strawberry": 224}, champ) == ["strawberry"]
    assert fb.mechanism_failures({**good, "melon": 44, "fertilize": 0}, champ) == ["fertilize", "melon"]


def test_the_identity_stub_switches_all_sixteen_seams_off_and_survives_a_turn():
    from harness.sheep_bench import _seam_names
    names = _seam_names()
    assert len(names) == 16
    cls = fb.off_class()
    for n in names:
        assert n in cls.__dict__, f"seam {n} not switched off"
    off = cls()
    assert off.fertilizer_stock() is None and off.fertilize_crops() is None and off.herd_target(8) is None
    assert off.HERD_RAMP_F == fp.HERD_RAMP_F and off.CAPS == fb.load_reference().CAPS
    from kaggisim.state import parse
    from kaggle_environments import make
    env = make("kaggriculture", configuration={"seed": 1056, "episodeSteps": 3})
    out = off.act(parse(env.reset()[0].observation))
    assert set(out) >= {"farmer", "hands", "market"}


def test_arm_b_fertilizes_melon_only():
    from strategies.fertilized import FertilizedStrategy
    b = fb.arm_b_class()()
    assert isinstance(b, FertilizedStrategy)
    assert b.fertilize_crops() == ("MELON",) and b.fertilizer_stock() == 24
```

- [ ] **Step 2: Run the tests and observe them fail**

Run: `.venv/bin/python -m pytest tests/test_fertilized.py tests/test_fert_bench.py -q`
Expected: two collection errors. Quote them.

- [ ] **Step 3: Write `strategies/fertilized.py`**

```python
"""fertilized: payday_herd that applies the fertilizer it collects (#277).

pilkwang, 0/16 against every contender of this line, opens like us and wins
the payday: 72 melon from 12 tiles and 269 strawberry from 38 to our 45 and
150. The sim doubles a watered day's yield growth and each strawberry
production while a tile is fertilized; FERTILIZE takes one unit from the
worker's hand and lasts three days. Our line collects fertilizer from the
pastures and sells every unit.

One decision changes: the crop line is fertilized. The shed keeps FERT_STOCK
units back from the sell sweep, a crop worker at the shed takes a few, and a
strawberry or melon tile due for water whose fertilizer has lapsed gets
FERTILIZE first (the two seams of #277). Everything else is payday_herd's.

Declared before measurement: FERT_CROPS and FERT_STOCK, and the controls and
criterion in `harness/fert_bench.py` (posted to #277 before any code).
"""

from __future__ import annotations

from strategies.payday_herd import PaydayHerdStrategy

#: The crops worth a unit of fertilizer: the two the payday is made of.
FERT_CROPS = ("STRAWBERRY", "MELON")
#: Fertilizer the shed keeps back from the sweep for the crop workers.
FERT_STOCK = 24


class FertilizedStrategy(PaydayHerdStrategy):
    """`payday_herd` with the crop line fertilized."""

    name = "fertilized"
    benchmark = False

    def fertilizer_stock(self):
        return FERT_STOCK

    def fertilize_crops(self):
        return FERT_CROPS


STRATEGY = FertilizedStrategy
```

- [ ] **Step 4: Write `harness/fert_bench.py`**

```python
"""The fertilized experiment (#277): controls, criterion, arm B.

Declared on #277 before any code. Controls first -- identity (every seam off,
sixteen of them now, is the frozen benchmark to the value) and mechanism (at
least FERTILIZE_BAR FERTILIZE actions, strawberry units at least
STRAWBERRY_FACTOR times the champion's, melon units at least the champion's,
both sides of one game); a failed control is a VOID run (exit 2). Then
rival_bench's criterion; the lonespear and pilkwang pairs print on the verdict
line whatever the result. Arm B (`melon_only`) is recorded, never gated.

    .venv/bin/python -m harness.fert_bench --controls
    .venv/bin/python -m harness.fert_bench --criterion
    .venv/bin/python -m harness.fert_bench --recorded
"""

from __future__ import annotations

import argparse
import os

from harness.cashflow import play  # noqa: F401  -- pinned by the tests
from harness.episode_analysis import _slot
from harness.evolve import DEFAULT_ANCHORS
from harness.external_pool import EXTERNAL_ANCHORS
from harness.reserve_bench import MADHUR, PILKWANG, REFERENCE  # noqa: F401  -- pinned by the tests
from harness.rival_bench import (  # noqa: F401  -- pinned by the tests to rival_bench's own
    criterion,
    format_external,
    format_rows,
    paired_external_rows,
)
from harness.sheep_bench import _seam_names
from strategies import field_pace as fp

CONTENDER = "fertilized"
CHAMPION = "payday_herd"
SEEDS = tuple(range(1056, 1072))
CONTROL_SEED = 1056
CHAMPION_BAR = 0.60
ANCHOR_BAR = 0.90
FERTILIZE_BAR = 30
STRAWBERRY_FACTOR = 1.5
ARM_B = "melon_only"
LONESPEAR = EXTERNAL_ANCHORS[1]
assert LONESPEAR.startswith("lonespear"), LONESPEAR


def load_reference():
    from strategies import load
    return load(REFERENCE)


def action_counts(steps, seat) -> dict:
    """Every farmer and hand action of one seat over the game, tallied by op."""
    counts: dict = {}
    for t in range(len(steps)):
        act = (_slot(steps, t, seat) or {}).get("action") or {}
        for a in [act.get("farmer")] + list(act.get("hands") or []):
            if isinstance(a, list) and a:
                counts[a[0]] = counts.get(a[0], 0) + 1
    return counts


def units_sold(steps, seat) -> dict:
    """Units in one seat's SELL orders over the game, by item."""
    units: dict = {}
    for t in range(len(steps)):
        act = (_slot(steps, t, seat) or {}).get("action") or {}
        for o in act.get("market") or []:
            if isinstance(o, list) and len(o) >= 3 and o[0] == "SELL":
                units[o[1]] = units.get(o[1], 0) + int(o[2])
    return units


def reading(steps, seat) -> dict:
    a, u = action_counts(steps, seat), units_sold(steps, seat)
    return {"fertilize": a.get("FERTILIZE", 0), "water": a.get("WATER", 0),
            "strawberry": u.get("STRAWBERRY", 0), "melon": u.get("MELON", 0),
            "fertilizer_sold": u.get("FERTILIZER", 0)}


def mechanism_failures(contender, champion) -> list:
    failed = []
    if contender["fertilize"] < FERTILIZE_BAR:
        failed.append("fertilize")
    if contender["strawberry"] < STRAWBERRY_FACTOR * champion["strawberry"]:
        failed.append("strawberry")
    if contender["melon"] < champion["melon"]:
        failed.append("melon")
    return failed


def off_class():
    """Every seam off (sixteen), the reference's caps, and the frozen herd ramp."""
    from strategies import load
    body = {n: (lambda self, *a, **k: None) for n in _seam_names()}
    body["CAPS"] = load_reference().CAPS
    body["HERD_RAMP_F"] = fp.HERD_RAMP_F
    return type("Off", (load(CONTENDER),), body)


def arm_b_class():
    """`fertilized` on melon only. Never registered."""
    from strategies import load
    return type("MelonOnly", (load(CONTENDER),), {"fertilize_crops": lambda self: ("MELON",)})


# --- live games -------------------------------------------------------------

def _arm_b_agents(name):  # pragma: no cover
    from harness.triage import _default_agents
    from kaggisim.strategy import make_agent
    arm_b = arm_b_class()
    default_agents = _default_agents()

    def agents(who):
        return make_agent(arm_b()) if who == name else default_agents(who)
    return agents


def run_controls(seed=CONTROL_SEED):  # pragma: no cover
    os.environ.setdefault("ROBRICULTURE_STRICT", "1")
    from harness.tournament import play_rewards
    from kaggisim.strategy import make_agent
    from strategies import load
    out = {}
    off = off_class()
    base = play_rewards(make_agent(load(REFERENCE)()), make_agent(load(REFERENCE)()), seed)
    got = play_rewards(make_agent(off()), make_agent(load(REFERENCE)()), seed)
    precondition_ok = base[0] > 0
    out["identity"] = {"ok": got == base and precondition_ok, "base": base, "got": got,
                       "precondition_ok": precondition_ok}
    steps = play(CONTENDER, CHAMPION, seed)
    contender, champion = reading(steps, 0), reading(steps, 1)
    failed = mechanism_failures(contender, champion)
    out["mechanism"] = {"ok": not failed, "failed": failed, "contender": contender, "champion": champion}
    return out


def run_criterion(seeds=SEEDS):  # pragma: no cover
    os.environ.setdefault("ROBRICULTURE_STRICT", "1")
    from harness.triage import head_to_head_rate
    champion_row = head_to_head_rate(CONTENDER, CHAMPION, seeds)
    anchor_rows = [head_to_head_rate(CONTENDER, a, seeds) for a in DEFAULT_ANCHORS]
    pairs = paired_external_rows(CONTENDER, CHAMPION, seeds)
    return champion_row, anchor_rows, pairs


def run_recorded(seeds=SEEDS):  # pragma: no cover
    os.environ.setdefault("ROBRICULTURE_STRICT", "1")
    from harness.triage import head_to_head_rate
    return [head_to_head_rate(ARM_B, CHAMPION, seeds, agents=_arm_b_agents(ARM_B))]


def main(argv=None):  # pragma: no cover
    os.environ.setdefault("ROBRICULTURE_STRICT", "1")
    ap = argparse.ArgumentParser(description="fertilized: apply the fertilizer we collect")
    ap.add_argument("--controls", action="store_true")
    ap.add_argument("--criterion", action="store_true")
    ap.add_argument("--recorded", action="store_true", help="arm B (recorded, not gated)")
    args = ap.parse_args(argv)

    if args.recorded:
        print(format_rows(run_recorded()))
        print(f"recorded, not gated: arm B ({ARM_B}: fertilized on melon only) vs {CHAMPION}")
        return 0

    do_controls = args.controls or not args.criterion
    do_criterion = args.criterion or not args.controls

    if do_controls:
        ctl = run_controls()
        print(f"control identity: {'OK' if ctl['identity']['ok'] else 'FAIL -- RUN VOID'}  {ctl['identity']}")
        c, b = ctl["mechanism"]["contender"], ctl["mechanism"]["champion"]
        print(f"control mechanism: {'OK' if ctl['mechanism']['ok'] else 'FAIL -- RUN VOID'}  "
              f"(declared: FERTILIZE >= {FERTILIZE_BAR}, strawberry >= {STRAWBERRY_FACTOR} x champion's, "
              f"melon >= champion's)  contender {c}  {CHAMPION} {b}  failed={ctl['mechanism']['failed'] or 'none'}")
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
              f"archetype pairs (contender, champion): lonespear {v['external'].get(LONESPEAR)}, "
              f"pilkwang {v['external'].get(PILKWANG)}; madhur {v['external'].get(MADHUR)}")
        return 0 if v["passed"] else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Run the targeted tests and observe them pass**

Run: `.venv/bin/python -m pytest tests/test_fertilized.py tests/test_fert_bench.py tests/test_fertilize_seams.py tests/test_payday_bench.py -q`
Expected: all PASS.

- [ ] **Step 6: Smoke the controls once (blocking, ~15 s), then commit**

Run: `.venv/bin/python -m harness.fert_bench --controls`; both control lines verbatim in the report. Identity FAIL → STOP, BLOCKED (the seams changed frozen behaviour). Mechanism FAIL → commit anyway, DONE_WITH_CONCERNS with the reading; never tune.

```bash
git add strategies/fertilized.py harness/fert_bench.py tests/test_fertilized.py tests/test_fert_bench.py
git commit -m "feat(#277): fertilized — payday_herd with the crop line fertilized, and its declared bench

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```
