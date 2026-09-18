# free_straw (#312) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The `free_straw` contender and its declared bench, exactly as `docs/superpowers/specs/2026-09-18-free-straw-design.md` and the declaration on #312.

**Architecture:** One strategy file setting one class attribute on `town_split`; one bench in the shape of `harness/four8b_bench.py`, judged with `rival_bench.decided_row`, no arm B.

**Tech Stack:** Python 3.12, `.venv/bin/python`, pytest.

## Global Constraints
- Pure TDD: failing tests first, RUN and observe, then the code; the report quotes the red.
- Never edit any existing file.
- `.venv/bin/python` only; every command blocking; do NOT run the full suite (the controller does) — only the targeted tests and the one controls smoke (~15 s).
- Stage by explicit path; never `git add -A`; never stage `.venv`, `external_agents`, `replays/`.
- Declared values verbatim: `CAPS_S = {"MELON": 10, "WHEAT": 24}`; `CONTENDER = "free_straw"`, `CHAMPION = "town_split"`, `SEEDS = tuple(range(1303, 1319))`, `CONTROL_SEED = 1303`, `CHAMPION_BAR = 0.60`, `ANCHOR_BAR = 0.90`, `TILE_DAY = 16`, `LATE_DAY = 20`.
- Commit trailer: `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.

---

### Task 1: The contender and the bench

**Files:**
- Create: `strategies/free_straw.py`, `harness/straw_bench.py`
- Test: `tests/test_free_straw.py`, `tests/test_straw_bench.py`

**Interfaces:**
- Consumes: `strategies.town_split.TownSplitStrategy`; `strategies.field_rival.crop_for_plot`, `standing_crops`; `harness.feed_bench.board_on_day`; `harness.episode_analysis.decompose`; `harness.four8_bench.escapes`; `harness.sheep_bench._seam_names`; `harness.rival_bench.criterion`, `decided_row`, `format_external`, `format_rows`, `paired_external_rows`; `harness.reserve_bench.MADHUR, PILKWANG, REFERENCE`; `harness.external_pool.EXTERNAL_ANCHORS`; `harness.evolve.DEFAULT_ANCHORS`; `harness.cashflow.play`; `harness.triage.head_to_head_rate`; `harness.tournament.play_rewards`; `strategies.field_pace.HERD_RAMP_F`.
- Produces: `free_straw.CAPS_S`, `FreeStrawStrategy`, `STRATEGY`; `straw_bench.reading`, `mechanism_failures`, `off_class`, `main`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_free_straw.py
"""free_straw (#312): the strawberry cap removed, nothing else."""

from __future__ import annotations

from strategies import field_rival as fr
from strategies import free_straw as fs
from strategies.town_split import TownSplitStrategy


def test_caps_drop_the_strawberry_key_and_keep_the_rest():
    assert fs.CAPS_S == {"MELON": 10, "WHEAT": 24}
    assert "STRAWBERRY" not in fs.CAPS_S
    assert fs.CAPS_S["MELON"] == TownSplitStrategy.CAPS["MELON"] and fs.CAPS_S["WHEAT"] == TownSplitStrategy.CAPS["WHEAT"]
    assert TownSplitStrategy.CAPS["STRAWBERRY"] == 38
    assert fs.FreeStrawStrategy.CAPS is fs.CAPS_S


def test_an_absent_key_means_no_cap_on_the_frozen_crop_rule():
    pivot = TownSplitStrategy().pivot_day()
    standing = {"STRAWBERRY": 40, "MELON": 10}
    assert fr.crop_for_plot(10, standing, caps=fs.CAPS_S, pivot=pivot) == "STRAWBERRY"
    assert fr.crop_for_plot(10, standing, caps=TownSplitStrategy.CAPS, pivot=pivot) == "WHEAT"
    assert fr.crop_for_plot(10, {"STRAWBERRY": 30}, caps=TownSplitStrategy.CAPS, pivot=pivot) == "STRAWBERRY"


def test_the_class_overrides_nothing_but_the_caps():
    from harness import sheep_bench as sb
    p = fs.FreeStrawStrategy()
    assert p.name == "free_straw" and isinstance(p, TownSplitStrategy) and p.FOURTH_DAY == 8 and p.benchmark is False
    assert set(fs.FreeStrawStrategy.__dict__) & set(sb._seam_names()) == set()
    assert not [k for k, v in fs.FreeStrawStrategy.__dict__.items() if callable(v)]
    q = TownSplitStrategy()
    assert p.pivot_day() == q.pivot_day() and p.livestock_workers(8) == q.livestock_workers(8) and p.buy_order() == q.buy_order()
    assert p.sheep_share(["YARN_STORE", "PIZZA_SHOP"]) == q.sheep_share(["YARN_STORE", "PIZZA_SHOP"])


def test_registered():
    from strategies import load
    assert load("free_straw") is fs.FreeStrawStrategy
```

```python
# tests/test_straw_bench.py
"""The free_straw experiment's declared constants and pure parts (#312)."""

from __future__ import annotations

import pytest

from harness import rival_bench as rb
from harness import straw_bench as sb
from strategies import field_pace as fp


def test_the_declared_constants():
    assert sb.CONTENDER == "free_straw" and sb.CHAMPION == "town_split"
    assert sb.SEEDS == tuple(range(1303, 1319)) and sb.CONTROL_SEED == 1303
    assert sb.CHAMPION_BAR == 0.60 and sb.ANCHOR_BAR == 0.90
    assert (sb.TILE_DAY, sb.LATE_DAY) == (16, 20)
    assert sb.LONESPEAR.startswith("lonespear")
    assert sb.criterion is rb.criterion and sb.decided_row is rb.decided_row and rb.MIN_DECIDED == 8


def test_the_seeds_are_fresh_against_every_range_already_spent():
    spent = set(range(100, 116)) | set(range(200, 216)) | set(range(300, 332)) \
        | set(range(400, 416)) | set(range(500, 516)) | set(range(600, 616)) \
        | set(range(700, 704)) | set(range(800, 960)) | set(range(960, 1303))
    assert not spent & set(sb.SEEDS)


def _board(straw, wheat=0, melon=0):
    tiles = [{"kind": "PLANT", "crop": "STRAWBERRY"}] * straw + [{"kind": "PLANT", "crop": "WHEAT"}] * wheat \
        + [{"kind": "PLANT", "crop": "MELON"}] * melon + [None, "LOCKED", {"animal": "COW"}, {"kind": "WEED"}]
    return {"tiles": [tiles]}


def test_reading_and_its_failure(monkeypatch):
    monkeypatch.setattr(sb, "board_on_day", lambda steps, seat, day: {16: _board(42, 0, 3), 20: _board(42, 4)}.get(day))
    monkeypatch.setattr(sb, "decompose", lambda steps, seat: {"revenue": {"STRAWBERRY": 36803, "WHEAT": 892, "MILK": 1}})
    assert sb.reading("s", 0) == {"straw_16": 42, "straw_20": 42, "strawberry": 36803, "wheat": 892}
    monkeypatch.setattr(sb, "board_on_day", lambda steps, seat, day: _board(38) if day == 16 else None)
    assert sb.reading("s", 0)["straw_20"] is None
    monkeypatch.setattr(sb, "board_on_day", lambda steps, seat, day: None)
    with pytest.raises(ValueError):
        sb.reading("s", 0)


def test_mechanism_failures_name_the_bars():
    champ = {"straw_16": 38, "straw_20": 38, "strawberry": 33393, "wheat": 2239}
    good = {"straw_16": 42, "straw_20": 42, "strawberry": 36803, "wheat": 892}
    assert sb.mechanism_failures(good, champ) == []
    assert sb.mechanism_failures({**good, "straw_16": 38}, champ) == ["straw_16"]
    assert sb.mechanism_failures({**good, "strawberry": 33393}, champ) == ["strawberry"]
    assert sb.mechanism_failures({**good, "straw_16": 30, "strawberry": 1}, champ) == ["straw_16", "strawberry"]


def test_the_identity_stub_switches_all_sixteen_seams_off_and_survives_a_turn():
    from harness.sheep_bench import _seam_names
    names = _seam_names()
    assert len(names) == 16
    cls = sb.off_class()
    for n in names:
        assert n in cls.__dict__, f"seam {n} not switched off"
    off = cls()
    assert off.herd_preference({"town": {"unlocked_shops": ["YARN_STORE"]}}) is None and off.herd_target(8) is None
    assert off.HERD_RAMP_F == fp.HERD_RAMP_F and off.CAPS == sb.load_reference().CAPS and "STRAWBERRY" in off.CAPS
    from kaggisim.state import parse
    from kaggle_environments import make
    env = make("kaggriculture", configuration={"seed": 1303, "episodeSteps": 3})
    out = off.act(parse(env.reset()[0].observation))
    assert set(out) >= {"farmer", "hands", "market"}


def test_play_and_the_reference_are_pinned():
    from harness.cashflow import play
    from harness.reserve_bench import MADHUR, PILKWANG, REFERENCE
    assert sb.play is play and sb.REFERENCE == REFERENCE == "dense_farm"
    assert sb.MADHUR == MADHUR and sb.PILKWANG == PILKWANG
```

- [ ] **Step 2: Run the tests and observe them fail**

Run: `.venv/bin/python -m pytest tests/test_free_straw.py tests/test_straw_bench.py -q 2>&1 | tail -6`
Expected: collection errors — `ImportError: cannot import name 'free_straw' from 'strategies'` and `... 'straw_bench' from 'harness'`. Quote the lines in the report.

- [ ] **Step 3: Write `strategies/free_straw.py`**

```python
"""free_straw: town_split with the strawberry cap removed (#312).

#288 found the strawberry-shop count predicts our strawberry revenue at
r = 0.72. A scratch probe of fixed caps against town_split's 38 read the
other way from the cap's own reasoning: caps of 20 and 28 lose every game
at every shop count, and the land (42 tiles at three quadrants) wins 15 of
16 by 1.4-8K, losing only the one town with no strawberry shop. Strawberry
revenue tracks tiles almost linearly -- at 38 tiles the farm is not
flooding its own price -- and the four tiles the cap sends to wheat earn a
third as much there.

One class attribute changes: `CAPS` has no STRAWBERRY key. The frozen crop
rule treats an absent key as no cap, so every empty crop tile after the
melon window is strawberry while strawberry can still finish, then wheat as
before. No method is overridden; everything else is town_split's.

Declared before measurement: `CAPS_S`, and the controls and criterion in
`harness/straw_bench.py` (posted to #312 before any code).
"""

from __future__ import annotations

from strategies.town_split import TownSplitStrategy

#: town_split's caps without the STRAWBERRY key: melon ten, wheat twenty-four,
#: strawberry to the land.
CAPS_S = {"MELON": 10, "WHEAT": 24}


class FreeStrawStrategy(TownSplitStrategy):
    """`town_split` with strawberry uncapped."""

    name = "free_straw"
    benchmark = False
    CAPS = CAPS_S


STRATEGY = FreeStrawStrategy
```

- [ ] **Step 4: Write `harness/straw_bench.py`**

```python
"""The free_straw experiment (#312): controls and criterion -- judged under
ADR-0007's amendment of 2026-09-16 as corrected 2026-09-17 (`decided_row`).

Declared on #312 before any code. Controls first -- identity (every seam off
is the frozen benchmark to the value) and mechanism (more standing strawberry
on day 16 than town_split and more strawberry revenue in the same game); a
failed control is a VOID run (exit 2). Then rival_bench's criterion on the
decided row: >= 60% of the decided games vs town_split (VOID if fewer than
MIN_DECIDED are decided), >= 90% vs each anchor, paired external
non-regression. No arm B.

    .venv/bin/python -m harness.straw_bench --controls
    .venv/bin/python -m harness.straw_bench --criterion
"""

from __future__ import annotations

import argparse
import os

from harness.cashflow import play  # noqa: F401  -- pinned by the tests
from harness.episode_analysis import decompose
from harness.evolve import DEFAULT_ANCHORS
from harness.external_pool import EXTERNAL_ANCHORS
from harness.feed_bench import board_on_day
from harness.four8_bench import escapes
from harness.reserve_bench import MADHUR, PILKWANG, REFERENCE  # noqa: F401  -- pinned by the tests
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

CONTENDER = "free_straw"
CHAMPION = "town_split"
SEEDS = tuple(range(1303, 1319))
CONTROL_SEED = 1303
CHAMPION_BAR = 0.60
ANCHOR_BAR = 0.90
TILE_DAY = 16
LATE_DAY = 20
LONESPEAR = EXTERNAL_ANCHORS[1]
assert LONESPEAR.startswith("lonespear"), LONESPEAR  # the pool order is the pin (review)


def load_reference():
    from strategies import load
    return load(REFERENCE)


def _straw(steps, seat, day):
    board = board_on_day(steps, seat, day)
    return None if board is None else fr.standing_crops(board["tiles"]).get("STRAWBERRY", 0)


def reading(steps, seat) -> dict:
    """One side's standing strawberry on days 16 and 20, and its strawberry and
    wheat revenue. Day 20 may be None (printed, never gated); day 16 may not."""
    straw_16 = _straw(steps, seat, TILE_DAY)
    if straw_16 is None:
        raise ValueError(f"no board for day {TILE_DAY}: the game ended early")
    rev = decompose(steps, seat)["revenue"]
    return {"straw_16": straw_16, "straw_20": _straw(steps, seat, LATE_DAY),
            "strawberry": rev.get("STRAWBERRY", 0), "wheat": rev.get("WHEAT", 0)}


def mechanism_failures(contender, champion) -> list:
    """Control 2's bars; the names of the ones that did not hold."""
    failed = []
    if not contender["straw_16"] > champion["straw_16"]:
        failed.append("straw_16")
    if not contender["strawberry"] > champion["strawberry"]:
        failed.append("strawberry")
    return failed


def off_class():
    """Every seam off (sixteen), the reference's caps, and the frozen herd ramp."""
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
    ap = argparse.ArgumentParser(description="free_straw: the strawberry cap removed")
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
              f"(declared: standing strawberry at day {TILE_DAY} > {CHAMPION}'s, strawberry revenue > {CHAMPION}'s)  "
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
              f"failing limbs: {v['failing'] or 'none'} -> {verdict}; "
              f"paired rows (contender, champion): madhur {v['external'].get(MADHUR)}, "
              f"pilkwang {v['external'].get(PILKWANG)}, lonespear {v['external'].get(LONESPEAR)}")
        if v["void"]:
            return 2
        return 0 if v["passed"] else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Run the targeted tests and observe them pass**

Run: `.venv/bin/python -m pytest tests/test_free_straw.py tests/test_straw_bench.py -q 2>&1 | tail -5`
Expected: all pass. If `test_an_absent_key_means_no_cap_on_the_frozen_crop_rule` disagrees with the frozen rule's actual answer, the frozen rule is the truth: fix the test's expected crop, not any production file, and say so in the report.

- [ ] **Step 6: Smoke the controls once (blocking, ~15 s), then commit**

Run: `.venv/bin/python -m harness.straw_bench --controls 2>&1 | grep -v Warning | tail -4`
Expected: `control identity: OK ...` and `control mechanism: OK ...` with the contender's `straw_16` above the champion's. Quote both lines in the report. If either says FAIL, do not change the bars: commit anyway and report DONE_WITH_CONCERNS with the lines quoted.

```bash
git add strategies/free_straw.py harness/straw_bench.py tests/test_free_straw.py tests/test_straw_bench.py
git commit -m "feat(#312): free_straw -- the strawberry cap removed, with its declared bench

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```
