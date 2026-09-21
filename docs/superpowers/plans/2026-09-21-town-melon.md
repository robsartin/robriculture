# town_melon (#337) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The `crop_plan` seam on the frozen benchmark (off by default), then the `town_melon` contender and its declared bench, exactly as `docs/superpowers/specs/2026-09-21-town-melon-design.md` and the declaration on #337.

**Architecture:** Task 1 adds one hook on `FieldRivalStrategy` and reads it once in `act`, so the turn's caps and windows come from the hook when it fires. Task 2 is a contender on `second_melon` that reads the town through the hook, and a bench in the shape of `harness/melon2_bench.py` with a seed screen and a third control.

**Tech Stack:** Python 3.12, `.venv/bin/python`, pytest.

## Global Constraints
- Pure TDD: failing tests first, RUN and observe, then the code; the report quotes the red.
- `.venv/bin/python` only; every command blocking; do NOT run the full suite (the controller does) — only the targeted tests named in each task and the one controls smoke.
- Task 1 edits `strategies/field_rival.py`, `harness/feed_bench.py` and the fourteen seam-count pins ONLY as described; the frozen benchmark's behaviour with the seam off must be byte-identical (`tests/test_field_rival.py` and the identity control pin it). Task 2 creates exactly four new files and edits nothing.
- Stage by explicit path; never `git add -A`; never stage `.venv`, `external_agents`, `replays/`.
- Declared values verbatim: `DEAD_DAY = 9`, `LAST_MELON_DAY = 18`, `DEAD_WINDOWS = ((9, 18),)`, `DEAD_CAPS = {**CAPS_S, "MELON": 24, "STRAWBERRY": 0}`; `CONTENDER = "town_melon"`, `CHAMPION = "second_melon"`, `CHAMPION_BAR = 0.60`, `ANCHOR_BAR = 0.90`, `SCAN_FROM = 2359`, `SEED_COUNT = 16`, `MELON_UNITS_BAR = 100`.
- Commit trailer: `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.

---

### Task 1: The `crop_plan` seam

**Files:**
- Modify: `strategies/field_rival.py` (new hook `crop_plan` after `melon_windows`; `FieldRivalStrategy.act` reads it), `harness/feed_bench.py` (`off_class` stub), and the seam-count pins `assert len(names) == 17` → `18` in exactly these fourteen files: `tests/test_eight_bench.py`, `tests/test_even_bench.py`, `tests/test_fert_bench.py`, `tests/test_fertilize_seams.py`, `tests/test_fourth_bench.py`, `tests/test_melon_bench.py`, `tests/test_melon2_bench.py`, `tests/test_melon_windows_seam.py`, `tests/test_sixteen_bench.py`, `tests/test_split_bench.py`, `tests/test_six_bench.py`, `tests/test_straw_bench.py`, `tests/test_town_bench.py`, `tests/test_twelve_bench.py`. (`tests/test_fed_bench.py` and `tests/test_payday_bench.py` say `len(r["heads"]) == 17` — a herd reading, NOT a seam count: leave them.)
- Test: `tests/test_crop_plan_seam.py`

**Interfaces:**
- Produces: `FieldRivalStrategy.crop_plan(self, obs) -> None | tuple[dict, tuple | None]`; `act` uses `caps, windows = (self.CAPS, self.melon_windows()) if plan is None else plan`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_crop_plan_seam.py
"""The crop_plan seam on the frozen benchmark (#337): off by default; when it
fires, the turn's caps and melon windows are its pair."""

from __future__ import annotations

from strategies import field_rival as fr

DEAD_CAPS = {"MELON": 24, "WHEAT": 24, "STRAWBERRY": 0}
DEAD_WINDOWS = ((9, 18),)


def _obs(seed=1671, steps=3):
    from kaggisim.state import parse
    from kaggle_environments import make
    env = make("kaggriculture", configuration={"seed": seed, "episodeSteps": steps})
    return parse(env.reset()[0].observation)


def test_the_hook_returns_none_on_the_benchmark_and_is_a_seam():
    from harness.sheep_bench import _seam_names
    assert fr.FieldRivalStrategy().crop_plan(_obs()) is None
    names = _seam_names()
    assert "crop_plan" in names and len(names) == 18


def test_act_uses_the_plans_caps_and_windows_for_the_turn(monkeypatch):
    seen = []
    def spy(day, standing, season_days=fr.SEASON_DAYS, caps=None, pivot=None, windows=None):
        seen.append((caps, windows))
        return None
    monkeypatch.setattr(fr, "crop_for_plot", spy)
    on = type("On", (fr.FieldRivalStrategy,), {"crop_plan": lambda self, obs: (DEAD_CAPS, DEAD_WINDOWS)})()
    out = on.act(_obs())
    assert set(out) >= {"farmer", "hands", "market"}
    assert seen and all(c is DEAD_CAPS and w is DEAD_WINDOWS for c, w in seen)
    seen.clear()
    fr.FieldRivalStrategy().act(_obs())
    assert seen and all(c is fr.FieldRivalStrategy.CAPS and w is None for c, w in seen)


def test_market_orders_sees_the_plans_caps_and_windows(monkeypatch):
    seen = {}
    real = fr.market_orders
    def spy(*a, **k):
        seen["caps"], seen["windows"] = k.get("caps"), k.get("windows")
        return real(*a, **k)
    monkeypatch.setattr(fr, "market_orders", spy)
    on = type("On", (fr.FieldRivalStrategy,), {"crop_plan": lambda self, obs: (DEAD_CAPS, DEAD_WINDOWS)})()
    on.act(_obs())
    assert seen["caps"] is DEAD_CAPS and seen["windows"] is DEAD_WINDOWS


def test_the_stub_switches_it_off():
    from harness import feed_bench
    off = feed_bench.off_class()()
    assert off.crop_plan(_obs()) is None
```

- [ ] **Step 2: Run the tests and observe them fail**

Run: `.venv/bin/python -m pytest tests/test_crop_plan_seam.py -q 2>&1 | tail -8`
Expected: `AttributeError: 'FieldRivalStrategy' object has no attribute 'crop_plan'` in the first test; in the second, `seen` shows `caps` is `fr.FieldRivalStrategy.CAPS` not `DEAD_CAPS` (the hook is never read); the fourth fails on the missing attribute. Quote the lines.

- [ ] **Step 3: Add the hook and read it in `act`**

In `strategies/field_rival.py`, after `melon_windows` (before `cluster_size`):

```python
    def crop_plan(self, obs):
        """This turn's ``(caps, windows)`` pair in place of `CAPS` and
        `melon_windows`, or ``None`` for the frozen plan. A seam for
        contenders (#337) that read the observation -- the town's shops --
        into the crop plan; on the benchmark it never fires, so its crop plan
        stays frozen (#181).
        """
        return None
```

In `act`, replace

```python
        pivot = self.pivot_day()
        windows = self.melon_windows()
```

with

```python
        pivot = self.pivot_day()
        plan = self.crop_plan(obs)
        caps, windows = (self.CAPS, self.melon_windows()) if plan is None else plan
```

and change the two `caps=self.CAPS` arguments in `act` (the `crop_for_plot` call and the `market_orders` call) to `caps=caps`. Nothing else in the module changes.

In `harness/feed_bench.py`'s `off_class` body, after `"melon_windows": lambda self: None,` add `"crop_plan": lambda self, obs: None,`.

In each of the fourteen pin files, change `len(names) == 17` to `len(names) == 18` (one occurrence each; `tests/test_melon2_bench.py` and `tests/test_melon_windows_seam.py` also name `melon_windows` in the same assertion — keep that). Also rename `test_the_identity_stub_switches_all_seventeen_seams_off_and_survives_a_turn` in `tests/test_melon2_bench.py` to `..._all_eighteen_seams_...` and the docstring word "seventeen" in `harness/melon2_bench.py`'s `off_class` docstring and module docstring to "eighteen" — those two files' prose only.

- [ ] **Step 4: Run the targeted tests and observe them pass**

Run: `.venv/bin/python -m pytest tests/test_crop_plan_seam.py tests/test_field_rival.py tests/test_melon_windows_seam.py tests/test_melon2_bench.py tests/test_fert_bench.py tests/test_fertilize_seams.py tests/test_eight_bench.py tests/test_even_bench.py tests/test_fourth_bench.py tests/test_melon_bench.py tests/test_sixteen_bench.py tests/test_split_bench.py tests/test_six_bench.py tests/test_straw_bench.py tests/test_town_bench.py tests/test_twelve_bench.py tests/test_feed_bench.py -q 2>&1 | tail -4`
Expected: all pass. Then `.venv/bin/ruff check strategies/field_rival.py harness/feed_bench.py tests/test_crop_plan_seam.py && .venv/bin/ruff format --check strategies/field_rival.py harness/feed_bench.py tests/test_crop_plan_seam.py` clean (if the repo's ruff config excludes tests, say so).

- [ ] **Step 5: Commit**

```bash
git add strategies/field_rival.py harness/feed_bench.py harness/melon2_bench.py tests/test_crop_plan_seam.py tests/test_eight_bench.py tests/test_even_bench.py tests/test_fert_bench.py tests/test_fertilize_seams.py tests/test_fourth_bench.py tests/test_melon_bench.py tests/test_melon2_bench.py tests/test_melon_windows_seam.py tests/test_sixteen_bench.py tests/test_split_bench.py tests/test_six_bench.py tests/test_straw_bench.py tests/test_town_bench.py tests/test_twelve_bench.py
git commit -m "feat(#337): crop_plan seam -- the turn's caps and melon windows from the observation, off by default

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 2: The contender and the bench

**Files:**
- Create: `strategies/town_melon.py`, `harness/deadtown_bench.py`
- Test: `tests/test_town_melon.py`, `tests/test_deadtown_bench.py`

**Interfaces:**
- Consumes: `strategies.second_melon.SecondMelonStrategy`, `MELON_WINDOWS`; `strategies.free_straw.CAPS_S`; `kaggisim.economy.SHOP_DEMAND`; `strategies.field_rival.TURNS_PER_DAY`; `harness.town_bench.town_on_day`; `harness.fert_bench.units_sold`; `harness.sixteend_bench.first_divergence`; `harness.rival_bench.seat_actions`, `criterion`, `decided_row`, `format_external`, `format_rows`, `paired_external_rows`, `_default_steps`; `harness.triage._default_agents`, `head_to_head_rate`; `harness.sheep_bench._seam_names`; `harness.reserve_bench.MADHUR, REFERENCE`; `harness.external_pool.EXTERNAL_ANCHORS`; `harness.evolve.DEFAULT_ANCHORS`; `harness.cashflow.play`; `harness.tournament.play_rewards`; `strategies.field_pace.HERD_RAMP_F`.
- Produces: `town_melon.DEAD_DAY, LAST_MELON_DAY, DEAD_WINDOWS, DEAD_CAPS, STRAW_SHOPS, straw_dead, TownMelonStrategy, STRATEGY`; `deadtown_bench.screen, reading, mechanism_failures, live_failures, off_class, scan, main`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_town_melon.py
"""town_melon (#337): melon instead of strawberry from day 9 while the town has
no strawberry shop, and nothing else."""

from __future__ import annotations

from strategies import free_straw
from strategies import second_melon as sm
from strategies import town_melon as tm
from strategies.second_melon import SecondMelonStrategy


def _obs(day, shops):
    return {"day": day, "town": {"unlocked_shops": list(shops)}}


def test_the_declared_constants():
    assert tm.DEAD_DAY == 9 and tm.LAST_MELON_DAY == 18 and tm.DEAD_WINDOWS == ((9, 18),)
    assert tm.DEAD_CAPS == {**free_straw.CAPS_S, "MELON": 24, "STRAWBERRY": 0}
    assert tm.STRAW_SHOPS == {"BRUNCH_SPOT", "ICE_CREAM_SHOP", "SMOOTHIE_SHOP", "FARMERS_MARKET"}


def test_straw_dead_reads_the_sims_shop_table():
    assert tm.straw_dead([]) and tm.straw_dead(["YARN_STORE", "PET_CAFE", "BAKERY"])
    assert not tm.straw_dead(["YARN_STORE", "ICE_CREAM_SHOP"])
    assert not tm.straw_dead(["FARMERS_MARKET"]) and not tm.straw_dead(["BRUNCH_SPOT"]) and not tm.straw_dead(["SMOOTHIE_SHOP"])


def test_crop_plan_fires_from_day_nine_in_a_dead_town_and_reverts():
    p = tm.TownMelonStrategy()
    dead = ["YARN_STORE", "PET_CAFE", "BAKERY"]
    assert p.crop_plan(_obs(9, dead)) == (tm.DEAD_CAPS, tm.DEAD_WINDOWS)
    assert p.crop_plan(_obs(18, dead)) == (tm.DEAD_CAPS, tm.DEAD_WINDOWS)
    assert p.crop_plan(_obs(8, dead)) is None                                   # before the day
    assert p.crop_plan(_obs(9, dead + ["ICE_CREAM_SHOP"])) is None               # a strawberry shop: frozen
    assert p.crop_plan(_obs(12, dead + ["BRUNCH_SPOT"])) is None                # reverts when one unlocks
    assert p.crop_plan({"day": 9}) == (tm.DEAD_CAPS, tm.DEAD_WINDOWS)          # no town key: no shops
    assert p.crop_plan(_obs(9, dead))[0] is tm.DEAD_CAPS and p.crop_plan(_obs(9, dead))[1] is tm.DEAD_WINDOWS


def test_the_class_defines_only_crop_plan():
    from harness import sheep_bench as sb
    p = tm.TownMelonStrategy()
    assert p.name == "town_melon" and isinstance(p, SecondMelonStrategy) and p.benchmark is False
    assert set(tm.TownMelonStrategy.__dict__) & set(sb._seam_names()) == {"crop_plan"}
    assert {k for k, v in tm.TownMelonStrategy.__dict__.items() if callable(v)} == {"crop_plan"}
    assert p.CAPS is free_straw.CAPS_S and p.melon_windows() is sm.MELON_WINDOWS
    assert p.fertilize_crops(16) == SecondMelonStrategy().fertilize_crops(16)


def test_registered():
    from strategies import load
    assert load("town_melon") is tm.TownMelonStrategy
```

```python
# tests/test_deadtown_bench.py
"""The town_melon experiment's declared constants and pure parts (#337)."""

from __future__ import annotations

from harness import deadtown_bench as db
from harness import rival_bench as rb
from strategies import field_pace as fp
from strategies import field_rival as fr


def test_the_declared_constants():
    assert db.CONTENDER == "town_melon" and db.CHAMPION == "second_melon"
    assert db.CHAMPION_BAR == 0.60 and db.ANCHOR_BAR == 0.90
    assert db.SCAN_FROM == 2359 and db.SEED_COUNT == 16 and db.MELON_UNITS_BAR == 100
    assert db.DEAD_STEP == 9 * fr.TURNS_PER_DAY
    assert db.LONESPEAR.startswith("lonespear")
    assert db.criterion is rb.criterion and db.decided_row is rb.decided_row and rb.PAIRED_MAX_SHORTFALL == 1


def test_the_scan_starts_past_every_seed_already_spent():
    spent = set(range(100, 116)) | set(range(200, 216)) | set(range(300, 332)) \
        | set(range(400, 416)) | set(range(500, 516)) | set(range(600, 616)) \
        | set(range(700, 704)) | set(range(800, 960)) | set(range(960, 1687)) | set(range(1687, 2359))
    assert db.SCAN_FROM > max(spent)


def test_screen_keeps_the_first_dead_seeds_in_order_and_names_the_first_live_one():
    dead = {2359: True, 2360: False, 2361: True, 2362: True, 2363: False, 2364: True}
    out = db.screen(range(2359, 2400), dead.__getitem__, 3)
    assert out == {"seeds": (2359, 2361, 2362), "live_seed": 2360, "read": 4}
    out = db.screen(range(2359, 2365), lambda s: True, 2)
    assert out == {"seeds": (2359, 2360), "live_seed": None, "read": 2}


def test_screen_reads_every_seed_when_too_few_are_dead():
    out = db.screen(range(2359, 2363), lambda s: s == 2361, 2)
    assert out == {"seeds": (2361,), "live_seed": 2359, "read": 4}


def test_reading_and_its_failure(monkeypatch):
    monkeypatch.setattr(db, "units_sold", lambda steps, seat: {"MELON": 148, "STRAWBERRY": 40})
    assert db.reading("s", 0) == {"melon_units": 148, "strawberry_units": 40}
    monkeypatch.setattr(db, "units_sold", lambda steps, seat: {})
    assert db.reading("s", 0) == {"melon_units": 0, "strawberry_units": 0}


def test_mechanism_failures_name_the_bars():
    champ = {"melon_units": 68, "strawberry_units": 120}
    good = {"melon_units": 148, "strawberry_units": 40}
    ok = db.DEAD_STEP
    assert db.mechanism_failures(good, champ, first_diff=ok) == []
    assert db.mechanism_failures(good, champ, first_diff=ok + 50) == []
    assert db.mechanism_failures({**good, "melon_units": 99}, {**champ, "melon_units": 10}, first_diff=ok) == ["melon_units"]   # < bar
    assert db.mechanism_failures({**good, "melon_units": 148}, {**champ, "melon_units": 148}, first_diff=ok) == ["melon_units"]  # not > champion's
    assert db.mechanism_failures({**good, "strawberry_units": 120}, champ, first_diff=ok) == ["strawberry_units"]
    assert db.mechanism_failures(good, champ, first_diff=ok - 1) == ["first_divergence"]
    assert db.mechanism_failures(good, champ, first_diff=None) == ["first_divergence"]
    assert db.mechanism_failures({"melon_units": 0, "strawberry_units": 200}, champ, first_diff=None) == ["melon_units", "strawberry_units", "first_divergence"]


def test_live_failures_compare_the_seat_zero_streams(monkeypatch):
    monkeypatch.setattr(db, "seat_actions", lambda steps, seat: steps[seat])
    assert db.live_failures([["a", "b"], ["x"]], [["a", "b"], ["y"]]) == []
    assert db.live_failures([["a", "b"], ["x"]], [["a", "c"], ["x"]]) == ["live_identity"]
    assert db.live_failures([["a"], ["x"]], [["a", "b"], ["x"]]) == ["live_identity"]


def test_the_identity_stub_switches_all_eighteen_seams_off_and_survives_a_turn():
    from harness.sheep_bench import _seam_names
    names = _seam_names()
    assert len(names) == 18 and "crop_plan" in names
    cls = db.off_class()
    for n in names:
        assert n in cls.__dict__, f"seam {n} not switched off"
    off = cls()
    assert off.crop_plan({"day": 9}) is None and off.melon_windows() is None and off.herd_target(12) is None
    assert off.HERD_RAMP_F == fp.HERD_RAMP_F and off.CAPS == db.load_reference().CAPS
    from kaggisim.state import parse
    from kaggle_environments import make
    env = make("kaggriculture", configuration={"seed": 2359, "episodeSteps": 3})
    out = off.act(parse(env.reset()[0].observation))
    assert set(out) >= {"farmer", "hands", "market"}


def test_play_and_the_reference_are_pinned():
    from harness.cashflow import play
    from harness.reserve_bench import MADHUR, REFERENCE
    assert db.play is play and db.REFERENCE == REFERENCE == "dense_farm" and db.MADHUR == MADHUR
```

- [ ] **Step 2: Run the tests and observe them fail**

Run: `.venv/bin/python -m pytest tests/test_town_melon.py tests/test_deadtown_bench.py -q 2>&1 | tail -6`
Expected: collection errors — `ImportError: cannot import name 'town_melon' from 'strategies'` and `ModuleNotFoundError: No module named 'harness.deadtown_bench'`. Quote the lines.

- [ ] **Step 3: Write `strategies/town_melon.py`**

```python
"""town_melon: second_melon with melon instead of strawberry from day 9 while
the town has no shop that takes strawberry (#337).

Five of fert_sixteen's fourteen ladder losses, and none of its wins, were
towns with no strawberry shop by day 12: we held a full strawberry field the
town never bought while the opponent sold melon (#288, 2026-09-21). Shops
unlock on days 3, 6, 9, ... from eight kinds, four of which take strawberry;
12% of ladder towns have none at day 9. Scratch probes on seeds screened for
such towns read 16/16 (+11.9K) and 15/16 (+11.3K); a day-12 decision is a
null (the field is already full), a day-6 one loses on false positives.

One hook changes: `crop_plan` returns the dead-town caps and window from
`DEAD_DAY` while no unlocked shop lists STRAWBERRY, and ``None`` otherwise --
it reverts the turn a strawberry shop unlocks. The caps stop new strawberry
and let melon take the tiles the field frees, through day `LAST_MELON_DAY`,
the last day a melon can still finish. Everything else is second_melon's.

Declared before measurement: the constants below, and the screen, controls
and criterion in `harness/deadtown_bench.py` (posted to #337 before any code).
"""

from __future__ import annotations

from kaggisim import economy
from strategies.free_straw import CAPS_S
from strategies.second_melon import SecondMelonStrategy

#: The first day the rule can fire: three shops are known.
DEAD_DAY = 9

#: The last day a melon can still finish (`hired_hands.plantable`: first
#: yield on day 10 after planting, one day to sell, season of 30).
LAST_MELON_DAY = 18

DEAD_WINDOWS = ((DEAD_DAY, LAST_MELON_DAY),)

#: The dead-town caps: melon takes what the field frees, no new strawberry.
DEAD_CAPS = {**CAPS_S, "MELON": 24, "STRAWBERRY": 0}

#: The shop kinds that take strawberry, from the sim's own table.
STRAW_SHOPS = frozenset(name for name, products in economy.SHOP_DEMAND.items() if "STRAWBERRY" in products)


def straw_dead(shops) -> bool:
    """True when no unlocked shop takes strawberry."""
    return not any(shop in STRAW_SHOPS for shop in shops or ())


class TownMelonStrategy(SecondMelonStrategy):
    """`second_melon` with melon instead of strawberry from day 9 in a town
    with no strawberry shop."""

    name = "town_melon"
    benchmark = False

    def crop_plan(self, obs):
        """The dead-town caps and window from `DEAD_DAY` while the town has no
        strawberry shop; the frozen plan otherwise (#337)."""
        shops = (obs.get("town") or {}).get("unlocked_shops") or []
        if obs.get("day", 0) >= DEAD_DAY and straw_dead(shops):
            return DEAD_CAPS, DEAD_WINDOWS
        return None


STRATEGY = TownMelonStrategy
```

- [ ] **Step 4: Write `harness/deadtown_bench.py`**

```python
"""The town_melon experiment (#337): screen, controls and criterion -- judged
under ADR-0007 as amended 2026-09-16, 2026-09-20 and 2026-09-21, corrected
2026-09-17.

Declared on #337 before any code. The seeds are screened (2026-09-21): the
first SEED_COUNT seeds at or above SCAN_FROM whose day-9 town under the
champion's own self-play has no strawberry shop; LIVE_SEED is the first
whose town has one. Controls first -- identity (every seam off, eighteen, is
the frozen benchmark to the value), mechanism (melon units sold at least
MELON_UNITS_BAR and more than the champion's, fewer strawberry units, and
the contender's first divergence from the champion's own stream at or after
day 9) and live identity (on LIVE_SEED the contender's stream is the
champion's own); a failed control is a VOID run (exit 2). Then rival_bench's
criterion on the decided row over the screened seeds: >= 60% of the decided
games vs second_melon (VOID if fewer than MIN_DECIDED are decided), >= 90% vs
each anchor, the paired external limb as a whole.

    .venv/bin/python -m harness.deadtown_bench --scan
    .venv/bin/python -m harness.deadtown_bench --controls --seeds A,B,... --live-seed L
    .venv/bin/python -m harness.deadtown_bench --criterion --seeds A,B,... --live-seed L

Without --seeds/--live-seed the run scans first and prints the screen.
"""

from __future__ import annotations

import argparse
import itertools
import os

from harness.cashflow import play  # noqa: F401  -- pinned by the tests
from harness.evolve import DEFAULT_ANCHORS
from harness.external_pool import EXTERNAL_ANCHORS
from harness.fert_bench import units_sold
from harness.reserve_bench import MADHUR, REFERENCE  # noqa: F401  -- pinned by the tests
from harness.rival_bench import (  # noqa: F401  -- pinned by the tests to rival_bench's own
    criterion,
    decided_row,
    format_external,
    format_rows,
    paired_external_rows,
    seat_actions,
)
from harness.sheep_bench import _seam_names
from harness.sixteend_bench import first_divergence
from harness.town_bench import town_on_day
from strategies import field_pace as fp
from strategies import field_rival as fr
from strategies.town_melon import DEAD_DAY, straw_dead

CONTENDER = "town_melon"
CHAMPION = "second_melon"
CHAMPION_BAR = 0.60
ANCHOR_BAR = 0.90
SCAN_FROM = 2359
SEED_COUNT = 16
MELON_UNITS_BAR = 100
#: The first step of DEAD_DAY: the contender may not diverge before it.
DEAD_STEP = DEAD_DAY * fr.TURNS_PER_DAY
LONESPEAR = EXTERNAL_ANCHORS[0]
assert LONESPEAR.startswith("lonespear"), LONESPEAR  # the pool order is the pin (review)


def load_reference():
    from strategies import load
    return load(REFERENCE)


# --- the screen ---------------------------------------------------------------

def screen(seeds, dead_of, count) -> dict:
    """The first `count` seeds of `seeds`, in order, for which `dead_of(seed)`
    is true; the first for which it is false; and how many were read.
    Reads every seed when fewer than `count` are dead."""
    kept, live, read = [], None, 0
    for seed in seeds:
        read += 1
        if dead_of(seed):
            kept.append(seed)
            if len(kept) == count:
                break
        elif live is None:
            live = seed
    return {"seeds": tuple(kept), "live_seed": live, "read": read}


def _own_steps(seed):  # pragma: no cover
    from harness.rival_bench import _default_steps
    from harness.triage import _default_agents
    agents = _default_agents()
    return _default_steps()(agents(CHAMPION), agents(CHAMPION), seed)


def scan(start=SCAN_FROM, count=SEED_COUNT):  # pragma: no cover
    """The screen, live: the champion against itself from `start` in seed
    order, the day-DEAD_DAY town read from seat 0."""
    def dead_of(seed):
        shops = town_on_day(_own_steps(seed), 0, DEAD_DAY)
        if shops is None:
            raise ValueError(f"seed {seed}: no observation for day {DEAD_DAY}")
        return straw_dead(shops)
    return screen(itertools.count(start), dead_of, count)


# --- readings ---------------------------------------------------------------

def reading(steps, seat) -> dict:
    """One side's melon and strawberry units sold."""
    u = units_sold(steps, seat)
    return {"melon_units": u.get("MELON", 0), "strawberry_units": u.get("STRAWBERRY", 0)}


def mechanism_failures(contender, champion, *, first_diff) -> list:
    """Control 2's bars; the names of the ones that did not hold."""
    failed = []
    if contender["melon_units"] < MELON_UNITS_BAR or not contender["melon_units"] > champion["melon_units"]:
        failed.append("melon_units")
    if not contender["strawberry_units"] < champion["strawberry_units"]:
        failed.append("strawberry_units")
    if first_diff is None or first_diff < DEAD_STEP:
        failed.append("first_divergence")
    return failed


def live_failures(ours, own) -> list:
    """Control 3: the contender's seat-0 stream equals the champion's own."""
    return [] if seat_actions(ours, 0) == seat_actions(own, 0) else ["live_identity"]


def off_class():
    """Every seam off (eighteen), the reference's caps, and the frozen herd ramp."""
    from strategies import load
    body = {n: (lambda self, *a, **k: None) for n in _seam_names()}
    body["CAPS"] = load_reference().CAPS
    body["HERD_RAMP_F"] = fp.HERD_RAMP_F
    return type("Off", (load(CONTENDER),), body)


# --- live games -------------------------------------------------------------

def run_controls(control_seed, live_seed):  # pragma: no cover
    os.environ.setdefault("ROBRICULTURE_STRICT", "1")
    from harness.tournament import play_rewards
    from kaggisim.strategy import make_agent
    from strategies import load
    out = {}
    off = off_class()
    base = play_rewards(make_agent(load(REFERENCE)()), make_agent(load(REFERENCE)()), control_seed)
    got = play_rewards(make_agent(off()), make_agent(load(REFERENCE)()), control_seed)
    precondition_ok = base[0] > 0
    out["identity"] = {"ok": got == base and precondition_ok, "base": base, "got": got,
                       "precondition_ok": precondition_ok}
    steps = play(CONTENDER, CHAMPION, control_seed)
    own = _own_steps(control_seed)
    contender, champion = reading(steps, 0), reading(steps, 1)
    first_diff = first_divergence(steps, own, 0)
    failed = mechanism_failures(contender, champion, first_diff=first_diff)
    out["mechanism"] = {"ok": not failed, "failed": failed, "first_diff": first_diff,
                        "contender": contender, "champion": champion,
                        "town": town_on_day(steps, 0, DEAD_DAY)}
    live_steps = play(CONTENDER, CHAMPION, live_seed)
    failed = live_failures(live_steps, _own_steps(live_seed))
    out["live"] = {"ok": not failed, "failed": failed, "town": town_on_day(live_steps, 0, DEAD_DAY)}
    return out


def run_criterion(seeds):  # pragma: no cover
    os.environ.setdefault("ROBRICULTURE_STRICT", "1")
    from harness.triage import head_to_head_rate
    champion_row = decided_row(CONTENDER, CHAMPION, seeds)
    anchor_rows = [head_to_head_rate(CONTENDER, a, seeds) for a in DEFAULT_ANCHORS]
    pairs = paired_external_rows(CONTENDER, CHAMPION, seeds)
    return champion_row, anchor_rows, pairs


def main(argv=None):  # pragma: no cover
    os.environ.setdefault("ROBRICULTURE_STRICT", "1")
    ap = argparse.ArgumentParser(description="town_melon: melon from day 9 while the town has no strawberry shop")
    ap.add_argument("--scan", action="store_true")
    ap.add_argument("--controls", action="store_true")
    ap.add_argument("--criterion", action="store_true")
    ap.add_argument("--seeds", help="the screened seeds, comma-separated (from --scan)")
    ap.add_argument("--live-seed", type=int, help="the first live seed (from --scan)")
    args = ap.parse_args(argv)

    if args.scan or not (args.seeds and args.live_seed):
        got = scan()
        print(f"screen from {SCAN_FROM}: read {got['read']} seeds; dead at day {DEAD_DAY}: "
              f"{','.join(str(s) for s in got['seeds'])}; live seed {got['live_seed']}")
        if len(got["seeds"]) < SEED_COUNT or got["live_seed"] is None:
            print("the screen came up short: the run is VOID")
            return 2
        seeds, live_seed = got["seeds"], got["live_seed"]
        if args.scan and not (args.controls or args.criterion):
            return 0
    else:
        seeds = tuple(int(s) for s in args.seeds.split(","))
        live_seed = args.live_seed

    do_controls = args.controls or not args.criterion
    do_criterion = args.criterion or not args.controls

    if do_controls:
        ctl = run_controls(seeds[0], live_seed)
        print(f"control identity: {'OK' if ctl['identity']['ok'] else 'FAIL -- RUN VOID'}  {ctl['identity']}")
        m = ctl["mechanism"]
        print(f"control mechanism: {'OK' if m['ok'] else 'FAIL -- RUN VOID'}  "
              f"(declared: melon units >= {MELON_UNITS_BAR} and > {CHAMPION}'s, strawberry units < {CHAMPION}'s, "
              f"first divergence >= step {DEAD_STEP})  contender {m['contender']}  {CHAMPION} {m['champion']}  "
              f"first_diff={m['first_diff']}  town@{DEAD_DAY}={m['town']}  failed={m['failed'] or 'none'}")
        lv = ctl["live"]
        print(f"control live identity: {'OK' if lv['ok'] else 'FAIL -- RUN VOID'}  seed {live_seed} town@{DEAD_DAY}={lv['town']}  failed={lv['failed'] or 'none'}")
        if not all(r["ok"] for r in ctl.values()):
            print("a control failed: the run is VOID")
            return 2

    if do_criterion:
        champion_row, anchor_rows, pairs = run_criterion(seeds)
        print(format_rows([champion_row] + anchor_rows))
        print(format_external(pairs))
        v = criterion(champion_row, anchor_rows, CHAMPION_BAR, ANCHOR_BAR, external_pairs=pairs,
                      identical=champion_row["identical"])
        verdict = "VOID (under-powered)" if v["void"] else ("PROMOTE" if v["passed"] else "REJECTED")
        print(f"champion {champion_row['wins']}W {champion_row['ties']}T {champion_row['losses']}L over {v['decided']} decided "
              f"= {v['champion_rate']:.1%} (bar {CHAMPION_BAR:.0%}; {v['identical']} identical of {champion_row['games']}); "
              f"failing limbs: {v['failing'] or 'none'} -> {verdict}; external net {v['external_net']:+d}; "
              f"paired rows (contender, champion): madhur {v['external'].get(MADHUR)}, lonespear {v['external'].get(LONESPEAR)}")
        if v["void"]:
            return 2
        return 0 if v["passed"] else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Run the targeted tests and observe them pass**

Run: `.venv/bin/python -m pytest tests/test_town_melon.py tests/test_deadtown_bench.py tests/test_crop_plan_seam.py -q 2>&1 | tail -4`
Expected: all pass. Then `.venv/bin/ruff check strategies/town_melon.py harness/deadtown_bench.py && .venv/bin/ruff format --check strategies/town_melon.py harness/deadtown_bench.py` clean.

- [ ] **Step 6: Smoke the screen's pure part against one real game (blocking, ~10 s), then commit**

Run (blocking): `PYTHONPATH=. .venv/bin/python -c "from harness import deadtown_bench as db; from harness.town_bench import town_on_day; s = db._own_steps(2359); print(town_on_day(s, 0, 9))"`
Expected: a list of three shop names. Do NOT run `--scan`, `--controls` or `--criterion` (the controller does). Then:

```bash
git add strategies/town_melon.py harness/deadtown_bench.py tests/test_town_melon.py tests/test_deadtown_bench.py
git commit -m "feat(#337): town_melon -- melon instead of strawberry from day 9 in a strawberry-dead town, with its declared bench

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```
