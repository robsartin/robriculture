# second_melon (#334) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The `melon_windows` seam on the frozen benchmark (off by default), then the `second_melon` contender and its declared bench, exactly as `docs/superpowers/specs/2026-09-21-second-melon-design.md` and the declaration on #334.

**Architecture:** Task 1 threads one keyword (`windows=None`) through `crop_for_day` → `crop_for_plot` → `market_orders` and adds one hook on `FieldRivalStrategy`; Task 2 is a one-attribute contender on `fert_sixteen` and a bench in the shape of `harness/straw_bench.py`.

**Tech Stack:** Python 3.12, `.venv/bin/python`, pytest.

## Global Constraints
- Pure TDD: failing tests first, RUN and observe, then the code; the report quotes the red.
- `.venv/bin/python` only; every command blocking; do NOT run the full suite (the controller does) — only the targeted tests named in each task and the one controls smoke.
- Task 1 edits `strategies/field_rival.py`, `harness/feed_bench.py` and the twelve seam-count pins ONLY as described; the frozen benchmark's behaviour with the seam off must be byte-identical (the identity control and `tests/test_field_rival.py` pin it). Task 2 creates exactly four new files and edits nothing.
- Stage by explicit path; never `git add -A`; never stage `.venv`, `external_agents`, `replays/`.
- Declared values verbatim: `MELON_WINDOWS = ((12, 13),)`; `CONTENDER = "second_melon"`, `CHAMPION = "fert_sixteen"`, `SEEDS = tuple(range(1671, 1687))`, `CONTROL_SEED = 1671`, `CHAMPION_BAR = 0.60`, `ANCHOR_BAR = 0.90`, `MELON_DAY = 14`, `LATE_DAY = 20`, `MELON_BAR = 5`.
- Commit trailer: `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.

---

### Task 1: The `melon_windows` seam

**Files:**
- Modify: `strategies/field_rival.py` (`crop_for_day`, `crop_for_plot`, `market_orders`, `FieldRivalStrategy.act`, new hook `melon_windows`), `harness/feed_bench.py` (`off_class` stub), and the seam-count pins `assert len(names) == 16` → `17` in: `tests/test_eight_bench.py`, `tests/test_even_bench.py`, `tests/test_fert_bench.py`, `tests/test_fertilize_seams.py` (its `len(names) == 16`), `tests/test_fourth_bench.py`, `tests/test_melon_bench.py`, `tests/test_sixteen_bench.py`, `tests/test_split_bench.py`, `tests/test_six_bench.py`, `tests/test_straw_bench.py`, `tests/test_town_bench.py`, `tests/test_twelve_bench.py`.
- Test: `tests/test_melon_windows_seam.py`

**Interfaces:**
- Produces: `field_rival.crop_for_day(day, season_days=SEASON_DAYS, pivot=PIVOT_DAY, windows=None)`; `crop_for_plot(day, standing, season_days=SEASON_DAYS, caps=None, pivot=None, windows=None)`; `market_orders(..., fert=None, windows=None)`; `FieldRivalStrategy.melon_windows(self) -> None`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_melon_windows_seam.py
"""The melon_windows seam on the frozen benchmark (#334): off by default, a
second melon wave inside a window when it is on."""

from __future__ import annotations

from strategies import field_rival as fr
from strategies import hired_hands as hh

WINDOW = ((12, 13),)


def test_crop_for_day_plants_melon_inside_a_window_and_is_frozen_outside_it():
    assert fr.crop_for_day(12, windows=WINDOW) == "MELON"
    assert fr.crop_for_day(13, windows=WINDOW) == "MELON"
    assert fr.crop_for_day(12, windows=WINDOW, pivot=5) == "MELON"
    for day in (0, 4, 11, 14, 20):
        assert fr.crop_for_day(day, windows=WINDOW) == fr.crop_for_day(day)
    assert fr.crop_for_day(12) == fr.crop_for_day(12, windows=None) == "STRAWBERRY"
    assert fr.crop_for_day(3, windows=WINDOW) == "MELON"           # before the pivot: the frozen answer
    late = ((26, 27),)
    assert not hh.plantable("MELON", 26, fr.SEASON_DAYS)
    assert fr.crop_for_day(26, windows=late) == fr.crop_for_day(26)  # past melon's horizon: frozen


def test_crop_for_plot_still_caps_melon_inside_the_window():
    caps = {"MELON": 10, "STRAWBERRY": 38, "WHEAT": 24}
    assert fr.crop_for_plot(12, {"MELON": 3}, caps=caps, pivot=5, windows=WINDOW) == "MELON"
    assert fr.crop_for_plot(12, {"MELON": 10}, caps=caps, pivot=5, windows=WINDOW) == "STRAWBERRY"
    assert fr.crop_for_plot(12, {"MELON": 3}, caps=caps, pivot=5) == "STRAWBERRY"


def _orders(windows):
    return fr.market_orders(12, 1, 5000, 10, 2, 8, {}, {}, 5, standing={}, caps={"MELON": 10, "STRAWBERRY": 38, "WHEAT": 24},
                            pivot=5, windows=windows)


def test_market_orders_buys_seed_for_the_windows_crop():
    with_window = [o for o in _orders(WINDOW) if o[0] == "BUY_SEED"]
    without = [o for o in _orders(None) if o[0] == "BUY_SEED"]
    assert with_window and with_window[0][1] == "MELON"
    assert without and without[0][1] == "STRAWBERRY"


def test_the_hook_returns_none_on_the_benchmark_and_is_a_seam():
    from harness.sheep_bench import _seam_names
    assert fr.FieldRivalStrategy().melon_windows() is None
    names = _seam_names()
    assert "melon_windows" in names and len(names) == 17


def test_a_contender_with_the_seam_on_survives_a_turn_and_the_stub_switches_it_off():
    from harness import feed_bench
    from kaggisim.state import parse
    from kaggle_environments import make
    on = type("On", (fr.FieldRivalStrategy,), {"melon_windows": lambda self: WINDOW})()
    env = make("kaggriculture", configuration={"seed": 1671, "episodeSteps": 3})
    out = on.act(parse(env.reset()[0].observation))
    assert set(out) >= {"farmer", "hands", "market"}
    off = feed_bench.off_class()()
    assert off.melon_windows() is None
```

- [ ] **Step 2: Run the tests and observe them fail**

Run: `.venv/bin/python -m pytest tests/test_melon_windows_seam.py -q 2>&1 | tail -8`
Expected: failures — `TypeError: crop_for_day() got an unexpected keyword argument 'windows'` and `AttributeError: 'FieldRivalStrategy' object has no attribute 'melon_windows'`. Quote them in the report.

- [ ] **Step 3: Thread the keyword through the frozen benchmark**

In `strategies/field_rival.py`, make exactly these edits (use the file's current text; the anchors below are verbatim):

(a) `crop_for_day`: change the signature to
```python
def crop_for_day(day: int, season_days: int = SEASON_DAYS, pivot: int = PIVOT_DAY, windows=None):
```
append to its docstring, before the closing quotes:
```
    `windows` (#334): inclusive ``(first, last)`` day pairs in which melon is
    planted again after the pivot, when it can still finish; ``None`` -- the
    benchmark -- never does.
```
and replace the line `    crop = "MELON" if day < pivot else "STRAWBERRY"` with
```python
    crop = "MELON" if day < pivot else "STRAWBERRY"
    if windows and any(first <= day <= last for first, last in windows) \
            and hh.plantable("MELON", day, season_days):
        return "MELON"
```

(b) `crop_for_plot`: signature `def crop_for_plot(day: int, standing, season_days: int = SEASON_DAYS, caps=None, pivot=None, windows=None):` and its call `crop = crop_for_day(day, season_days, PIVOT_DAY if pivot is None else pivot)` becomes `crop = crop_for_day(day, season_days, PIVOT_DAY if pivot is None else pivot, windows)`. Add to its docstring: `` `windows` is the second melon wave for a contender (#334); ``None`` keeps the frozen plan. ``

(c) `market_orders`: signature gains `windows=None` after `fert=None`; in `seed()` the line `crop = crop_for_plot(day, standing, caps=caps, pivot=pivot)` becomes `crop = crop_for_plot(day, standing, caps=caps, pivot=pivot, windows=windows)`. Add to its docstring: `` `windows`: the second melon wave, or ``None`` for the frozen plan (#334). ``

(d) The hook, placed directly after `pivot_day` on `FieldRivalStrategy`:
```python
    def melon_windows(self):
        """Inclusive ``(first, last)`` day pairs in which melon is planted again
        after the pivot, or ``None`` for never. A seam for contenders (#334);
        on the benchmark it never fires, so its crop plan stays frozen (#181).
        """
        return None
```

(e) `act`: after `pivot = self.pivot_day()` add `windows = self.melon_windows()`; the planting call becomes `crop = crop_for_plot(day, standing, caps=self.CAPS, pivot=pivot, windows=windows)`; the `market_orders(...)` call gains `windows=windows` after `fert=self.fertilizer_stock(day)`.

In `harness/feed_bench.py`, in `off_class`'s hand-written stub dictionary, add the line `"melon_windows": lambda self: None,` next to the other hooks.

In the twelve test files listed under **Files**, change `assert len(names) == 16` to `assert len(names) == 17` (and in `tests/test_fertilize_seams.py` the same count in its one assertion). Nothing else in those files.

- [ ] **Step 4: Run the targeted tests and observe them pass**

Run: `.venv/bin/python -m pytest tests/test_melon_windows_seam.py tests/test_field_rival.py tests/test_feed_bench.py tests/test_fertilize_seams.py tests/test_straw_bench.py tests/test_sixteen_bench.py -q 2>&1 | tail -3`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add strategies/field_rival.py harness/feed_bench.py tests/test_melon_windows_seam.py tests/test_eight_bench.py tests/test_even_bench.py tests/test_fert_bench.py tests/test_fertilize_seams.py tests/test_fourth_bench.py tests/test_melon_bench.py tests/test_sixteen_bench.py tests/test_split_bench.py tests/test_six_bench.py tests/test_straw_bench.py tests/test_town_bench.py tests/test_twelve_bench.py
git commit -m "feat(#334): melon_windows seam on the frozen benchmark -- a second melon wave inside declared day windows, off by default

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 2: The contender and the bench

**Files:**
- Create: `strategies/second_melon.py`, `harness/melon2_bench.py`
- Test: `tests/test_second_melon.py`, `tests/test_melon2_bench.py`

**Interfaces:**
- Consumes: `strategies.fert_sixteen.FertSixteenStrategy`; `strategies.free_straw.CAPS_S`; `strategies.twelve_head.HERD_RAMP_T`; `strategies.field_rival.standing_crops`; `harness.feed_bench.board_on_day`; `harness.fert_bench.units_sold`; `harness.four8_bench.escapes`; `harness.sheep_bench._seam_names`; `harness.rival_bench.criterion`, `decided_row`, `format_external`, `format_rows`, `paired_external_rows`; `harness.reserve_bench.MADHUR, REFERENCE`; `harness.external_pool.EXTERNAL_ANCHORS`; `harness.evolve.DEFAULT_ANCHORS`; `harness.cashflow.play`; `harness.triage.head_to_head_rate`; `harness.tournament.play_rewards`; `strategies.field_pace.HERD_RAMP_F`.
- Produces: `second_melon.MELON_WINDOWS`, `SecondMelonStrategy`, `STRATEGY`; `melon2_bench.reading`, `mechanism_failures`, `off_class`, `main`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_second_melon.py
"""second_melon (#334): a second melon wave on days 12-13, nothing else."""

from __future__ import annotations

from strategies import field_rival as fr
from strategies import free_straw
from strategies import second_melon as sm
from strategies import twelve_head as th
from strategies.fert_sixteen import FertSixteenStrategy


def test_the_window_is_days_twelve_and_thirteen():
    p = sm.SecondMelonStrategy()
    assert sm.MELON_WINDOWS == ((12, 13),) and p.melon_windows() is sm.MELON_WINDOWS
    assert FertSixteenStrategy().melon_windows() is None
    assert fr.crop_for_day(12, windows=p.melon_windows()) == "MELON"
    assert fr.crop_for_day(14, windows=p.melon_windows()) == "STRAWBERRY"


def test_the_class_defines_only_the_window():
    from harness import sheep_bench as sb
    p = sm.SecondMelonStrategy()
    assert p.name == "second_melon" and isinstance(p, FertSixteenStrategy) and p.benchmark is False
    assert set(sm.SecondMelonStrategy.__dict__) & set(sb._seam_names()) == {"melon_windows"}
    assert {k for k, v in sm.SecondMelonStrategy.__dict__.items() if callable(v)} == {"melon_windows"}
    assert p.CAPS is free_straw.CAPS_S and p.CAPS["MELON"] == 10 and p.HERD_RAMP_F is th.HERD_RAMP_T
    assert p.FERT_FROM == 16 and p.fertilize_crops(16) == FertSixteenStrategy().fertilize_crops(16)


def test_registered():
    from strategies import load
    assert load("second_melon") is sm.SecondMelonStrategy
```

```python
# tests/test_melon2_bench.py
"""The second_melon experiment's declared constants and pure parts (#334)."""

from __future__ import annotations

import pytest

from harness import melon2_bench as mb
from harness import rival_bench as rb
from strategies import field_pace as fp


def test_the_declared_constants():
    assert mb.CONTENDER == "second_melon" and mb.CHAMPION == "fert_sixteen"
    assert mb.SEEDS == tuple(range(1671, 1687)) and mb.CONTROL_SEED == 1671
    assert mb.CHAMPION_BAR == 0.60 and mb.ANCHOR_BAR == 0.90
    assert (mb.MELON_DAY, mb.LATE_DAY, mb.MELON_BAR) == (14, 20, 5)
    assert mb.LONESPEAR.startswith("lonespear")
    assert mb.criterion is rb.criterion and mb.decided_row is rb.decided_row and rb.PAIRED_MAX_SHORTFALL == 1


def test_the_seeds_are_fresh_against_every_range_already_spent():
    spent = set(range(100, 116)) | set(range(200, 216)) | set(range(300, 332)) \
        | set(range(400, 416)) | set(range(500, 516)) | set(range(600, 616)) \
        | set(range(700, 704)) | set(range(800, 960)) | set(range(960, 1671))
    assert not spent & set(mb.SEEDS)


def _board(melon, straw=0):
    return {"tiles": [[{"kind": "PLANT", "crop": "MELON"}] * melon + [{"kind": "PLANT", "crop": "STRAWBERRY"}] * straw + [None, "LOCKED", {"animal": "COW"}]]}


def test_reading_and_its_failure(monkeypatch):
    monkeypatch.setattr(mb, "board_on_day", lambda steps, seat, day: {14: _board(7, 30), 20: _board(7, 35)}.get(day))
    monkeypatch.setattr(mb, "units_sold", lambda steps, seat: {"MELON": 62, "STRAWBERRY": 250})
    assert mb.reading("s", 0) == {"melon_14": 7, "melon_20": 7, "melon_units": 62, "strawberry_units": 250}
    monkeypatch.setattr(mb, "board_on_day", lambda steps, seat, day: _board(0, 40) if day == 14 else None)
    assert mb.reading("s", 0)["melon_20"] is None
    monkeypatch.setattr(mb, "board_on_day", lambda steps, seat, day: None)
    with pytest.raises(ValueError):
        mb.reading("s", 0)


def test_mechanism_failures_name_the_bars():
    champ = {"melon_14": 0, "melon_20": 0, "melon_units": 40, "strawberry_units": 271}
    good = {"melon_14": 7, "melon_20": 7, "melon_units": 62, "strawberry_units": 250}
    assert mb.mechanism_failures(good, champ) == []
    assert mb.mechanism_failures({**good, "melon_14": 4}, champ) == ["melon_14"]                 # < MELON_BAR
    assert mb.mechanism_failures({**good, "melon_14": 6}, {**champ, "melon_14": 6}) == ["melon_14"]  # not > champion's
    assert mb.mechanism_failures({**good, "melon_units": 40}, champ) == ["melon_units"]
    assert mb.mechanism_failures({**good, "melon_14": 0, "melon_units": 1}, champ) == ["melon_14", "melon_units"]


def test_the_identity_stub_switches_all_seventeen_seams_off_and_survives_a_turn():
    from harness.sheep_bench import _seam_names
    names = _seam_names()
    assert len(names) == 17 and "melon_windows" in names
    cls = mb.off_class()
    for n in names:
        assert n in cls.__dict__, f"seam {n} not switched off"
    off = cls()
    assert off.melon_windows() is None and off.fertilize_crops(20) is None and off.herd_target(12) is None
    assert off.HERD_RAMP_F == fp.HERD_RAMP_F and off.CAPS == mb.load_reference().CAPS
    from kaggisim.state import parse
    from kaggle_environments import make
    env = make("kaggriculture", configuration={"seed": 1671, "episodeSteps": 3})
    out = off.act(parse(env.reset()[0].observation))
    assert set(out) >= {"farmer", "hands", "market"}


def test_play_and_the_reference_are_pinned():
    from harness.cashflow import play
    from harness.reserve_bench import MADHUR, REFERENCE
    assert mb.play is play and mb.REFERENCE == REFERENCE == "dense_farm" and mb.MADHUR == MADHUR
```

- [ ] **Step 2: Run the tests and observe them fail**

Run: `.venv/bin/python -m pytest tests/test_second_melon.py tests/test_melon2_bench.py -q 2>&1 | tail -6`
Expected: collection errors — `ImportError: cannot import name 'second_melon' from 'strategies'` and `... 'melon2_bench' from 'harness'`. Quote the lines.

- [ ] **Step 3: Write `strategies/second_melon.py`**

```python
"""second_melon: fert_sixteen with a second melon wave on days 12-13 (#334).

In 27 of fert_sixteen's 29 decomposable ladder games the opponent earned
15-22K from melon to our 8-11K (#288, 2026-09-21). We plant melon once, in
the eleven early tiles before the day-5 pivot; the second quadrant opens on
day 12 and a melon planted then matures by day 25. Two scratch seed sets
read a day 12-13 window at cap ten as 12/16 and 12/16, +1.3K and +1.9K; a
wider window lost on both.

One hook changes: `melon_windows` returns the day 12-13 window, through the
seam field_rival gained for it. The melon cap stays ten, so the wave takes at
most the tiles the first wave has freed; the fertilizer line from day 16
covers melon by fert_six's crops. Everything else is fert_sixteen's.

Declared before measurement: MELON_WINDOWS, and the controls and criterion
in `harness/melon2_bench.py` (posted to #334 before any code).
"""

from __future__ import annotations

from strategies.fert_sixteen import FertSixteenStrategy

#: The second wave: the two days after the second quadrant opens.
MELON_WINDOWS = ((12, 13),)


class SecondMelonStrategy(FertSixteenStrategy):
    """`fert_sixteen` with a second melon wave on days 12-13."""

    name = "second_melon"
    benchmark = False

    def melon_windows(self):
        """The declared window (#334)."""
        return MELON_WINDOWS


STRATEGY = SecondMelonStrategy
```

- [ ] **Step 4: Write `harness/melon2_bench.py`**

```python
"""The second_melon experiment (#334): controls and criterion -- judged under
ADR-0007 as amended 2026-09-16 and 2026-09-20, corrected 2026-09-17.

Declared on #334 before any code. Controls first -- identity (every seam
off, seventeen, is the frozen benchmark to the value) and mechanism (at
least MELON_BAR melon tiles standing on day 14 and more than the champion's;
more melon units sold than the champion's in the same game); a failed
control is a VOID run (exit 2). Then rival_bench's criterion on the decided
row: >= 60% of the decided games vs fert_sixteen (VOID if fewer than
MIN_DECIDED are decided), >= 90% vs each anchor, the paired external limb as
a whole. No arm B.

    .venv/bin/python -m harness.melon2_bench --controls
    .venv/bin/python -m harness.melon2_bench --criterion
"""

from __future__ import annotations

import argparse
import os

from harness.cashflow import play  # noqa: F401  -- pinned by the tests
from harness.evolve import DEFAULT_ANCHORS
from harness.external_pool import EXTERNAL_ANCHORS
from harness.feed_bench import board_on_day
from harness.fert_bench import units_sold
from harness.four8_bench import escapes
from harness.reserve_bench import MADHUR, REFERENCE  # noqa: F401  -- pinned by the tests
from harness.rival_bench import (  # noqa: F401  -- pinned by the tests to rival_bench's own
    criterion,
    decided_row,
    format_external,
    format_rows,
    paired_external_rows,
)
from harness.sheep_bench import _seam_names
from strategies import field_pace as fp
from strategies import field_rival as fr

CONTENDER = "second_melon"
CHAMPION = "fert_sixteen"
SEEDS = tuple(range(1671, 1687))
CONTROL_SEED = 1671
CHAMPION_BAR = 0.60
ANCHOR_BAR = 0.90
MELON_DAY = 14
LATE_DAY = 20
MELON_BAR = 5
LONESPEAR = EXTERNAL_ANCHORS[0]
assert LONESPEAR.startswith("lonespear"), LONESPEAR  # the pool order is the pin (review)


def load_reference():
    from strategies import load
    return load(REFERENCE)


def _melon(steps, seat, day):
    board = board_on_day(steps, seat, day)
    return None if board is None else fr.standing_crops(board["tiles"]).get("MELON", 0)


def reading(steps, seat) -> dict:
    """One side's standing melon on days 14 and 20, and its melon and strawberry
    units sold. Day 20 may be None (printed, never gated); day 14 may not."""
    melon_14 = _melon(steps, seat, MELON_DAY)
    if melon_14 is None:
        raise ValueError(f"no board for day {MELON_DAY}: the game ended early")
    u = units_sold(steps, seat)
    return {"melon_14": melon_14, "melon_20": _melon(steps, seat, LATE_DAY),
            "melon_units": u.get("MELON", 0), "strawberry_units": u.get("STRAWBERRY", 0)}


def mechanism_failures(contender, champion) -> list:
    """Control 2's bars; the names of the ones that did not hold."""
    failed = []
    if contender["melon_14"] < MELON_BAR or not contender["melon_14"] > champion["melon_14"]:
        failed.append("melon_14")
    if not contender["melon_units"] > champion["melon_units"]:
        failed.append("melon_units")
    return failed


def off_class():
    """Every seam off (seventeen), the reference's caps, and the frozen herd ramp."""
    from strategies import load
    body = {n: (lambda self, *a, **k: None) for n in _seam_names()}
    body["CAPS"] = load_reference().CAPS
    body["HERD_RAMP_F"] = fp.HERD_RAMP_F
    return type("Off", (load(CONTENDER),), body)


# --- live games -------------------------------------------------------------

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
    contender["escapes"], champion["escapes"] = escapes(steps, 0), escapes(steps, 1)
    failed = mechanism_failures(contender, champion)
    out["mechanism"] = {"ok": not failed, "failed": failed, "contender": contender, "champion": champion}
    return out


def run_criterion(seeds=SEEDS):  # pragma: no cover
    os.environ.setdefault("ROBRICULTURE_STRICT", "1")
    from harness.triage import head_to_head_rate
    champion_row = decided_row(CONTENDER, CHAMPION, seeds)
    anchor_rows = [head_to_head_rate(CONTENDER, a, seeds) for a in DEFAULT_ANCHORS]
    pairs = paired_external_rows(CONTENDER, CHAMPION, seeds)
    return champion_row, anchor_rows, pairs


def main(argv=None):  # pragma: no cover
    os.environ.setdefault("ROBRICULTURE_STRICT", "1")
    ap = argparse.ArgumentParser(description="second_melon: a second melon wave on days 12-13")
    ap.add_argument("--controls", action="store_true")
    ap.add_argument("--criterion", action="store_true")
    args = ap.parse_args(argv)

    do_controls = args.controls or not args.criterion
    do_criterion = args.criterion or not args.controls

    if do_controls:
        ctl = run_controls()
        print(f"control identity: {'OK' if ctl['identity']['ok'] else 'FAIL -- RUN VOID'}  {ctl['identity']}")
        c, b = ctl["mechanism"]["contender"], ctl["mechanism"]["champion"]
        print(f"control mechanism: {'OK' if ctl['mechanism']['ok'] else 'FAIL -- RUN VOID'}  "
              f"(declared: melon tiles at day {MELON_DAY} >= {MELON_BAR} and > {CHAMPION}'s, melon units > {CHAMPION}'s)  "
              f"contender {c}  {CHAMPION} {b}  failed={ctl['mechanism']['failed'] or 'none'}")
        if not all(r["ok"] for r in ctl.values()):
            print("a control failed: the run is VOID")
            return 2

    if do_criterion:
        champion_row, anchor_rows, pairs = run_criterion()
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

Run: `.venv/bin/python -m pytest tests/test_second_melon.py tests/test_melon2_bench.py tests/test_melon_windows_seam.py -q 2>&1 | tail -3`
Expected: all pass.

- [ ] **Step 6: Smoke the controls once (blocking, ~20 s), then commit**

Run: `.venv/bin/python -m harness.melon2_bench --controls 2>&1 | grep -v Warning | tail -4`
Expected: `control identity: OK ...` and `control mechanism: OK ...` with the contender's `melon_14` at or above 5 and the champion's 0. Quote both lines. If either says FAIL, do not change the bars: commit anyway and report DONE_WITH_CONCERNS.

```bash
git add strategies/second_melon.py harness/melon2_bench.py tests/test_second_melon.py tests/test_melon2_bench.py
git commit -m "feat(#334): second_melon -- a second melon wave on days 12-13, with its declared bench

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```
