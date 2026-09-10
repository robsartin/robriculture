# dawn_reserve (#256) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the `capital_reserve` seam the day and the placed head, build the contender `dawn_reserve` (herd_first with the cash floor = tomorrow's wage bill + the herd's feed), and its declared bench `harness/reserve_bench.py`.

**Architecture:** The existing hook gains two optional arguments (`None` on the benchmark, ignored by `field_pace`), and `act` passes them — the frozen path is unchanged. The contender computes its floor from two pure helpers over the benchmark's own wage ladder and feed buffer. The bench reuses `order_bench`'s readers and `rival_bench`'s verdict, adds a crew bar beside the head bar, and pairs the crop line against `herd_first`.

**Tech Stack:** Python 3.12 in `.venv` (`.venv/bin/python`, never a bare python3), pytest `-n auto`, `kaggle-environments` 1.32.7. Spec: `docs/superpowers/specs/2026-09-10-dawn-reserve-design.md`.

## Global Constraints

- Pure TDD: write the failing tests, **run them and quote the failure**, then the minimal code, run green, commit. Every task: `.venv/bin/python -m pytest -q -n auto` green before the commit.
- `strategies/field_rival.py` is the frozen benchmark (#181): `capital_reserve(self, day=None, animals=None)` returns `None`; no existing assertion in `tests/test_field_rival.py` may change (the existing no-argument call must keep working).
- Declared values, verbatim, not to be tuned: `wage_bill(n) = Σ hand_wage(k), k=1..n`; `feed_cost(animals) = feed_buffer(animals) * CROPS["WHEAT"]["seed"]`; reserve = `wage_bill(hire_target(day + 1)) + feed_cost(animals)`; bench `CONTENDER = "dawn_reserve"`, `CHAMPION = "third_herder"`, `BASELINE = "herd_first"`, `SEEDS = tuple(range(928, 944))`, `CONTROL_SEED = 928`, `CHAMPION_BAR = 0.60`, `ANCHOR_BAR = 0.90`, `ARM_B = "wage_reserve"`, `HEAD_DAY = 8`, `HEAD_BAR = 8`, `HANDS_BAR = 8`, `CROP_DAY = 12`, `PLANTED_GAP_BAR = 12`.
- Never edit `strategies/__init__.py`. Test names `test_<the fact>` with a docstring/comment saying why. Stage by explicit path; never `git add -A`; never stage `.venv` / `external_agents`. Commit messages end with a blank line and `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.
- Live-game code carries `# pragma: no cover` at the `def`; do NOT run the bench's live games — the controller runs the declared bench after review.

---

### Task 1: The `capital_reserve` hook takes the day and the placed head

**Files:**
- Modify: `strategies/field_rival.py` — `FieldRivalStrategy.capital_reserve` (line ~685) and the `market_orders(...)` call in `act` (line ~765: `reserve=self.capital_reserve()`).
- Modify: `strategies/field_pace.py` — `capital_reserve(self)` → `capital_reserve(self, day=None, animals=None)`, still returning `self.RESERVE_F`.
- Test: `tests/test_field_rival.py` (append), `tests/test_field_pace.py` (append).

**Interfaces:**
- Produces: `FieldRivalStrategy.capital_reserve(self, day=None, animals=None) -> int | None`; `act` calls `self.capital_reserve(day, animals)` where `animals = count_animals(tiles)` (already computed in `act`).

- [ ] **Step 1: Write the failing tests** — append to `tests/test_field_rival.py`:

```python
# --- #256: the reserve hook learns the day and the placed head ---

def test_the_benchmarks_reserve_hook_takes_the_day_and_the_head_and_still_defers():
    # A contender's floor may depend on tomorrow's crew and today's herd; the
    # benchmark's answer is still `None` -- the frozen CAPITAL_RESERVE (#181).
    assert fr.FieldRivalStrategy().capital_reserve(8, 4) is None
    assert fr.FieldRivalStrategy().capital_reserve() is None


def test_act_hands_the_reserve_hook_the_day_and_the_placed_head():
    """The seam is only a seam if `act` feeds it: a recording subclass, run on
    a real reset observation, must see day 0 and zero head placed."""
    from kaggle_environments import make
    seen = []

    class Recording(fr.FieldRivalStrategy):
        def capital_reserve(self, day=None, animals=None):
            seen.append((day, animals))
            return None

    obs = make("kaggriculture", configuration={"seed": 1}).state[0].observation
    Recording().act(obs)
    assert seen == [(0, 0)]
```

and to `tests/test_field_pace.py`:

```python
def test_field_pace_ignores_the_day_and_the_head_and_keeps_its_zero_reserve():
    # #256 gives the hook arguments; field_pace's declared RESERVE_F is unchanged.
    s = fp.FieldPaceStrategy()
    assert s.capital_reserve(8, 4) == 0 and s.capital_reserve() == 0
```

- [ ] **Step 2: Run them and quote the failure**

Run: `.venv/bin/python -m pytest -q tests/test_field_rival.py tests/test_field_pace.py -k "reserve_hook_takes or hands_the_reserve_hook or ignores_the_day"`
Expected: 3 failed — `TypeError: FieldRivalStrategy.capital_reserve() takes 1 positional argument but 3 were given` (twice, the second via `seen == [(0, 0)]` failing as `[(None, None)]` or a TypeError at the `act` call) and `TypeError: FieldPaceStrategy.capital_reserve() takes 1 positional argument but 3 were given`.

- [ ] **Step 3: Minimal implementation**

`strategies/field_rival.py`:

```python
    def capital_reserve(self, day=None, animals=None):
        """Cash held back from the herd, or ``None`` for `CAPITAL_RESERVE`. A
        seam for contenders (#252); `day` and `animals` (head placed) let a
        floor follow tomorrow's crew and today's herd (#256). Never fires on
        the benchmark."""
        return None
```

In `act`: `reserve=self.capital_reserve(day, animals)`.

`strategies/field_pace.py`: `def capital_reserve(self, day=None, animals=None): return self.RESERVE_F`.

- [ ] **Step 4: Run green** — `.venv/bin/python -m pytest -q -n auto`.
- [ ] **Step 5: Commit**

```bash
git add strategies/field_rival.py strategies/field_pace.py tests/test_field_rival.py tests/test_field_pace.py
git commit -m "field_rival: the reserve hook takes the day and the placed head, still None on the benchmark (#256)

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 2: The contender `dawn_reserve`

**Files:**
- Create: `strategies/dawn_reserve.py`
- Test: `tests/test_dawn_reserve.py`

**Interfaces:**
- Consumes: Task 1's hook signature; `strategies.herd_first.HerdFirstStrategy`; `strategies.hired_hands.hand_wage`; `strategies.field_rival.feed_buffer`, `field_rival.CROPS`.
- Produces: `wage_bill(n) -> int`; `feed_cost(animals) -> int`; `DawnReserveStrategy(HerdFirstStrategy)` with `name = "dawn_reserve"`, `benchmark = False`, `capital_reserve(self, day=None, animals=None)`; `STRATEGY = DawnReserveStrategy`.

- [ ] **Step 1: Write the failing tests** — `tests/test_dawn_reserve.py`:

```python
"""dawn_reserve: herd_first with the cash floor set to tomorrow's wages plus the
herd's feed (#256).

#254's herd_first beat the champion 14/16 and lost the field: the sim clears the
hands every night and re-hires at dawn, and a zero reserve let the herd block
spend every coin before dawn -- 2-5 hands, no feed wheat, head placed 9 -> 3.
This arm keeps back exactly what dawn will need and changes nothing else.
"""

from __future__ import annotations

from strategies import dawn_reserve as dr
from strategies import field_rival as fr
from strategies import hired_hands as hh
from strategies.herd_first import HerdFirstStrategy


def test_the_wage_bill_is_the_benchmarks_own_ladder_summed():
    # 1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144: the sim's fib(hires_today) per hire.
    assert [dr.wage_bill(n) for n in (0, 1, 5, 8, 10, 12)] == [0, 1, 12, 54, 143, 376]
    assert dr.wage_bill(10) == sum(hh.hand_wage(k) for k in range(1, 11))


def test_the_feed_cost_is_the_feed_buffer_at_the_price_the_feed_block_budgets_with():
    # feed_buffer keeps 2 wheat per head (floor 8); the feed block divides its
    # budget by CROPS["WHEAT"]["seed"], so the floor is priced the same way.
    assert [dr.feed_cost(n) for n in (0, 4, 8, 13)] == [80, 80, 160, 260]
    assert dr.feed_cost(13) == fr.feed_buffer(13) * fr.CROPS["WHEAT"]["seed"]


def test_the_reserve_is_tomorrows_wages_plus_todays_feed():
    # Day 5 -> tomorrow's crew is 8 (54) + four head (80); day 7 -> 10 (143) + eight head (160).
    s = dr.DawnReserveStrategy()
    assert s.capital_reserve(5, 4) == 134
    assert s.capital_reserve(7, 8) == 303
    assert s.capital_reserve(29, 13) == dr.wage_bill(s.hire_target(30)) + 260


def test_it_is_a_registered_contender_that_inherits_herd_firsts_order_and_knobs():
    from strategies import REGISTRY, load
    assert "dawn_reserve" in REGISTRY and load("dawn_reserve") is dr.DawnReserveStrategy
    assert issubclass(dr.DawnReserveStrategy, HerdFirstStrategy)
    s, base = dr.DawnReserveStrategy(), HerdFirstStrategy()
    assert s.buy_order() == base.buy_order() == ("hires", "herd", "land", "seed")
    for day in (0, 6, 8, 15):
        assert s.hire_target(day) == base.hire_target(day)
        assert s.herd_target(day) == base.herd_target(day)
    assert s.layout() == base.layout() and s.CAPS == base.CAPS
    assert base.capital_reserve(5, 4) == 0          # herd_first keeps the zero it was rejected on
```

- [ ] **Step 2: Run them and quote the failure** — `.venv/bin/python -m pytest -q tests/test_dawn_reserve.py`; expected: collection `ImportError: cannot import name 'dawn_reserve' from 'strategies'`.

- [ ] **Step 3: Minimal implementation** — `strategies/dawn_reserve.py`:

```python
"""dawn_reserve: herd_first with the cash floor set to tomorrow's wages plus the herd's feed (#256).

#254's `herd_first` beat `third_herder` 14/16 and lost the field (madhur 5/16
against the champion's 11/16). The census said why: the sim clears
`farm["hands"]` every night and re-hires at dawn on the wage ladder (1, 1, 2,
3, 5, 8, 13, 21, 34, 55 -- 143 for ten hands), and with a zero reserve the herd
block, which runs on every hour, spends every coin before dawn: 2-20 in hand,
2-5 hands, the crop line stalled at 11 tiles for six days, no feed wheat
against a strong opponent and head placed 9 -> 3. The buy order was the right
knob; zero reserve is wrong under daily re-hiring -- it fires the crew at dusk.

One decision changes: the herd's cash floor is what dawn will need --
tomorrow's wage bill for the crew the ramp asks for, plus the wheat the feed
block keeps for the herd standing today -- through the `capital_reserve` seam
(#252, #256). The buy order, `field_pace`'s eight knobs and `third_herder`'s
rules are inherited unchanged.

Declared before measurement: `wage_bill`, `feed_cost`, and the controls and
criterion in `harness/reserve_bench.py` (posted to #256 before any code).
"""

from __future__ import annotations

from strategies import field_rival as fr
from strategies import hired_hands as hh
from strategies.herd_first import HerdFirstStrategy


def wage_bill(hands: int) -> int:
    """What dawn charges to hire `hands` in one day: the benchmark's own ladder
    (`hand_wage`, the sim's fib(hires_today) per hire), summed."""
    return sum(hh.hand_wage(k) for k in range(1, hands + 1))


def feed_cost(animals: int) -> int:
    """The wheat the feed block keeps for `animals` head, at the price it
    budgets with -- the same units and the same divisor, so the floor and the
    buy agree."""
    return fr.feed_buffer(animals) * fr.CROPS["WHEAT"]["seed"]


class DawnReserveStrategy(HerdFirstStrategy):
    """`herd_first` that keeps back what dawn will need."""

    name = "dawn_reserve"
    benchmark = False

    def capital_reserve(self, day=None, animals=None):
        """Tomorrow's wage bill plus today's feed; the herd buys from what is left."""
        return wage_bill(self.hire_target(day + 1)) + feed_cost(animals)


STRATEGY = DawnReserveStrategy
```

- [ ] **Step 4: Run green** — the whole suite (the no-crash gate now plays `dawn_reserve`): `.venv/bin/python -m pytest -q -n auto`.
- [ ] **Step 5: Commit**

```bash
git add strategies/dawn_reserve.py tests/test_dawn_reserve.py
git commit -m "dawn_reserve: herd_first with the cash floor set to tomorrow's wages plus the herd's feed (#256)

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 3: The declared bench `harness/reserve_bench.py`

**Files:**
- Create: `harness/reserve_bench.py`
- Test: `tests/test_reserve_bench.py`
- Reference (read, do not modify): `harness/order_bench.py` — copy its shape; import `order_reading`, `format_order_shape`, `crop_line_ok`, `HEAD_DAY`, `HEAD_BAR`, `CROP_DAY`, `PLANTED_GAP_BAR`; `harness/pace_bench.py` (`REFERENCE`, `PILKWANG`); `harness/rival_bench.py`; `harness/external_pool.py` (`EXTERNAL_ANCHORS` — madhur is the last entry, index 4).

**Interfaces:**
- Produces: the declared constants; `MADHUR = external_pool.EXTERNAL_ANCHORS[4]` (asserted to start with `"madhur"`); `crew_ok(reading) -> bool` (`reading["hands"] >= HANDS_BAR`); `mechanism_failures(reading) -> list[str]` (`["hands"]`, `["head_placed"]`, both, or `[]`); `arm_b_class() -> type` (unregistered subclass of `herd_first` whose `capital_reserve(day, animals)` returns `wage_bill(self.hire_target(day + 1))`); live `run_controls`, `run_criterion`, `run_recorded`, `main`.

- [ ] **Step 1: Write the failing tests** — `tests/test_reserve_bench.py`:

```python
"""The dawn_reserve experiment's declared constants and the pure parts it adds.

Readers are `harness.order_bench`'s and the verdict `harness.rival_bench`'s --
imported, not copied. New here: a crew bar beside the head bar (the crew is
what the reserve exists to keep) and the crop line paired against herd_first.
"""

from __future__ import annotations

from harness import order_bench as ob
from harness import pace_bench as pb
from harness import reserve_bench as rsb
from harness import rival_bench as rb


def test_the_declared_constants():
    # Declared on #256 before any code; not to be tuned.
    assert rsb.CONTENDER == "dawn_reserve" and rsb.CHAMPION == "third_herder"
    assert rsb.BASELINE == "herd_first"
    assert rsb.SEEDS == tuple(range(928, 944)) and rsb.CONTROL_SEED == 928
    assert rsb.CHAMPION_BAR == 0.60 and rsb.ANCHOR_BAR == 0.90
    assert rsb.ARM_B == "wage_reserve"
    assert rsb.HEAD_DAY == 8 and rsb.HEAD_BAR == 8 and rsb.HANDS_BAR == 8
    assert rsb.CROP_DAY == 12 and rsb.PLANTED_GAP_BAR == 12
    assert rsb.MADHUR == "madhur_sabherwal_hub_geometry_agent"


def test_the_seeds_are_fresh_against_every_range_already_spent():
    # 912-927 were #254's; everything through 927 is spent.
    spent = set(range(100, 116)) | set(range(200, 216)) | set(range(300, 332)) \
        | set(range(400, 416)) | set(range(500, 516)) | set(range(600, 616)) \
        | set(range(700, 704)) | set(range(800, 928))
    assert not spent & set(rsb.SEEDS)


def test_the_readers_and_the_verdict_are_imported_not_copied():
    assert rsb.order_reading is ob.order_reading and rsb.format_order_shape is ob.format_order_shape
    assert rsb.crop_line_ok is ob.crop_line_ok
    assert rsb.criterion is rb.criterion and rsb.paired_external_rows is rb.paired_external_rows
    assert rsb.REFERENCE == pb.REFERENCE and rsb.PILKWANG == pb.PILKWANG


def _reading(hands=9, head=8):
    return {"planted": 25, "quadrants": 2, "hands": hands, "head_placed": head, "head_held": 0,
            "pasture_free": 4, "strawberry": 10, "money_at_shape_day": 300.0,
            "planted_at_crop_day": 45, "money_at_crop_day": 4000.0, "payday": 11}


def test_each_mechanism_bar_can_fail_alone_and_names_itself():
    # herd_first had 2 hands and 8 head at day 8: the crew bar is the new one.
    assert rsb.crew_ok(_reading(hands=8)) is True and rsb.crew_ok(_reading(hands=7)) is False
    assert rsb.mechanism_failures(_reading()) == []
    assert rsb.mechanism_failures(_reading(hands=2)) == ["hands"]
    assert rsb.mechanism_failures(_reading(head=6)) == ["head_placed"]
    assert rsb.mechanism_failures(_reading(hands=2, head=6)) == ["hands", "head_placed"]


def test_arm_b_keeps_the_wages_only_and_is_not_registered():
    from strategies import REGISTRY
    from strategies.dawn_reserve import wage_bill
    from strategies.herd_first import HerdFirstStrategy
    cls = rsb.arm_b_class()
    assert issubclass(cls, HerdFirstStrategy)
    arm = cls()
    assert arm.capital_reserve(5, 4) == wage_bill(arm.hire_target(6)) == 54
    assert arm.capital_reserve(7, 8) == 143
    assert arm.buy_order() == ("hires", "herd", "land", "seed")
    assert rsb.ARM_B not in REGISTRY and rsb.CONTENDER in REGISTRY
```

- [ ] **Step 2: Run them and quote the failure** — `.venv/bin/python -m pytest -q tests/test_reserve_bench.py`; expected: collection `ImportError: cannot import name 'reserve_bench' from 'harness'`.

- [ ] **Step 3: Minimal implementation** — `harness/reserve_bench.py`:

```python
"""dawn_reserve: does keeping back dawn's wages and the herd's feed hold the crew, the herd and the field?

    python -m harness.reserve_bench --controls     # identity, crew and head at day 8, the paired crop line
    python -m harness.reserve_bench --criterion    # 16 seeds: champion, anchors, the external limb
    python -m harness.reserve_bench --recorded     # arm B (recorded, not gated)
    python -m harness.reserve_bench                # controls then criterion

Declared on #256 before any code: seeds 928-943 -- fresh; 100-115, 200-215,
300-331, 400-415, 500-515, 600-615, 700-703 and 800-927 are spent -- sides
alternated by list position (`harness.triage.head_to_head_rate`); PROMOTE
only at >= 60% of 16 vs the champion `third_herder` AND >= 90% vs each
DEFAULT_ANCHOR AND, for each `external_pool.EXTERNAL_ANCHORS` member, no fewer
wins than the champion on the same seeds in the same run (#152's paired limb);
a tie is not a win. Controls run first and a failed control voids the run --
arm B is then not scored either. Exit codes: 0 PROMOTE, 1 REJECTED, 2 VOID.
Runs under ROBRICULTURE_STRICT=1.

**The controls.** #254's herd_first stood 8 head by day 8 and beat the champion
14/16, then lost the field with 2 hands at dawn and no feed wheat. This arm
keeps back dawn's wages and the herd's feed, so the mechanism control is two
absolute bars at day 8 -- hands >= 8 (the crew the reserve exists to keep) and
head placed >= 8 (herd_first's gain, not to be given back) -- and the crop line
is PAIRED against herd_first on the same seed. The madhur row is the reading
the hypothesis lives on.

Readers are `harness.order_bench`'s; the verdict is `harness.rival_bench`'s.
"""

from __future__ import annotations

import argparse
import os

from harness import external_pool
from harness.evolve import DEFAULT_ANCHORS
from harness.order_bench import (  # noqa: F401  -- pinned by the tests to order_bench's own
    CROP_DAY,
    HEAD_BAR,
    HEAD_DAY,
    PLANTED_GAP_BAR,
    crop_line_ok,
    format_order_shape,
    order_reading,
)
from harness.pace_bench import PILKWANG, REFERENCE  # noqa: F401  -- pinned by the tests
from harness.rival_bench import (  # noqa: F401  -- pinned by the tests to rival_bench's own
    criterion,
    format_external,
    format_rows,
    paired_external_rows,
)

CONTENDER = "dawn_reserve"
CHAMPION = "third_herder"
BASELINE = "herd_first"

#: The reading the hypothesis lives on: herd_first regressed here, 5/16 vs 11/16.
MADHUR = external_pool.EXTERNAL_ANCHORS[4]
assert MADHUR.startswith("madhur")

#: Fresh. Everything through 927 is spent (912-927 were #254's).
SEEDS = tuple(range(928, 944))
CHAMPION_BAR = 0.60
ANCHOR_BAR = 0.90
CONTROL_SEED = 928

#: Arm B: the wage bill alone, no feed term. If B matches A, feed was not the
#: starving line. Never registered.
ARM_B = "wage_reserve"

#: The crew bar: herd_first had 2 hands at day 8 (field_pace 9).
HANDS_BAR = 8


def crew_ok(reading):
    """Control (ii-a): the crew the reserve exists to keep is at work at day 8."""
    return reading["hands"] >= HANDS_BAR


def mechanism_failures(reading):
    """Control (ii): both bars must hold; the names of the ones that did not."""
    failed = []
    if not crew_ok(reading):
        failed.append("hands")
    if reading["head_placed"] < HEAD_BAR:
        failed.append("head_placed")
    return failed


def arm_b_class():
    """`herd_first` keeping back tomorrow's wages only. Never registered."""
    from strategies import load
    from strategies.dawn_reserve import wage_bill

    def capital_reserve(self, day=None, animals=None):
        return wage_bill(self.hire_target(day + 1))

    return type("WageReserve", (load(BASELINE),), {"capital_reserve": capital_reserve})


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
    """Identity, then the two day-8 bars, then the paired crop line."""
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
        "capital_reserve": lambda self, day=None, animals=None: None,
        "buy_order": lambda self: None,
        "CAPS": load(REFERENCE).CAPS,
    })
    base = play_rewards(make_agent(load(REFERENCE)()), make_agent(load(REFERENCE)()), seed)
    got = play_rewards(make_agent(off()), make_agent(load(REFERENCE)()), seed)
    precondition_ok = base[0] > 0
    out["identity"] = {"ok": got == base and precondition_ok, "base": base, "got": got,
                       "precondition_ok": precondition_ok}

    ours, theirs = census_series(make_agent(load(CONTENDER)()), make_agent(load(CHAMPION)()), seed)
    base_turns, _ = census_series(make_agent(load(BASELINE)()), make_agent(load(CHAMPION)()), seed)
    contender = order_reading(ours)
    champion = order_reading(theirs)
    baseline = order_reading(base_turns)
    failed = mechanism_failures(contender)
    out["mechanism"] = {"ok": not failed, "failed": failed, "contender": contender,
                        "champion": champion, "baseline": baseline}
    out["crop_line"] = {"ok": crop_line_ok(contender, baseline),
                        "gap": abs(contender["planted_at_crop_day"] - baseline["planted_at_crop_day"])}
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
    ap = argparse.ArgumentParser(description="dawn_reserve: dawn's wages and the herd's feed kept back")
    ap.add_argument("--controls", action="store_true")
    ap.add_argument("--criterion", action="store_true")
    ap.add_argument("--recorded", action="store_true", help="arm B (recorded, not gated)")
    args = ap.parse_args(argv)

    if args.recorded:
        print(format_rows(run_recorded()))
        print(f"recorded, not gated: arm B ({ARM_B}: the wage bill alone) vs {CHAMPION}")
        return 0

    do_controls = args.controls or not args.criterion
    do_criterion = args.criterion or not args.controls

    if do_controls:
        ctl = run_controls()
        print(f"control identity: {'OK' if ctl['identity']['ok'] else 'FAIL -- RUN VOID'}"
              f"  {ctl['identity']}")
        c = ctl["mechanism"]["contender"]
        print(f"control mechanism: {'OK' if ctl['mechanism']['ok'] else 'FAIL -- RUN VOID'}  "
              f"(declared: at day {HEAD_DAY} hands >= {HANDS_BAR} and head placed >= {HEAD_BAR})  "
              f"hands={c['hands']} head_placed={c['head_placed']}  failed={ctl['mechanism']['failed'] or 'none'}")
        print(f"control crop line: {'OK' if ctl['crop_line']['ok'] else 'FAIL -- RUN VOID'}  "
              f"(declared: |planted at day {CROP_DAY} - herd_first's| <= {PLANTED_GAP_BAR})  "
              f"gap={ctl['crop_line']['gap']}")
        print(format_order_shape([(CONTENDER, c), (BASELINE, ctl["mechanism"]["baseline"]),
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
              f"madhur paired row (contender, champion): {v['external'].get(MADHUR)}; "
              f"pilkwang: {v['external'].get(PILKWANG)}")
        return 0 if v["passed"] else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run green, with coverage** — `.venv/bin/python -m pytest -q -n auto --cov --cov-branch --cov-report=term-missing 2>&1 | grep -E "reserve_bench|dawn_reserve|passed|failed"`.
- [ ] **Step 5: Commit**

```bash
git add harness/reserve_bench.py tests/test_reserve_bench.py
git commit -m "reserve_bench: #256's identity, crew-and-head and paired crop-line controls, criterion and arm B

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

## Self-review

- **Spec coverage.** Hook arguments and `act` → Task 1. `wage_bill`, `feed_cost`, the reserve, the contender → Task 2. Bench with the eleven-seam identity (the reserve lambda taking the new arguments), the two day-8 bars, the crop line paired against herd_first, the criterion with madhur and pilkwang named, arm B wages-only → Task 3. Run/record/PR → the controller.
- **Placeholders.** None.
- **Type consistency.** `capital_reserve(self, day=None, animals=None)` in Tasks 1 (benchmark, field_pace), 2 (contender) and 3 (arm B and the `off` lambda); `order_reading` keys (`hands`, `head_placed`, `planted_at_crop_day`) used by `crew_ok`, `mechanism_failures`, `crop_line_ok` and the tests.
