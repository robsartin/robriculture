# twelve_head (#320) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The `twelve_head` contender and its declared bench, exactly as `docs/superpowers/specs/2026-09-19-twelve-head-design.md` and the declaration on #320.

**Architecture:** One strategy file setting one class attribute on `free_straw`; one bench in the shape of `harness/straw_bench.py`, judged with `rival_bench.decided_row`, no arm B.

**Tech Stack:** Python 3.12, `.venv/bin/python`, pytest.

## Global Constraints
- Pure TDD: failing tests first, RUN and observe, then the code; the report quotes the red.
- Never edit any existing file.
- `.venv/bin/python` only; every command blocking; do NOT run the full suite (the controller does) — only the targeted tests and the one controls smoke (~15 s).
- Stage by explicit path; never `git add -A`; never stage `.venv`, `external_agents`, `replays/`.
- Declared values verbatim: `HERD_RAMP_T = ((0, 4), (6, 8), (12, 12))`; `CONTENDER = "twelve_head"`, `CHAMPION = "free_straw"`, `SEEDS = tuple(range(1463, 1479))`, `CONTROL_SEED = 1463`, `CHAMPION_BAR = 0.60`, `ANCHOR_BAR = 0.90`, `HEAD_DAY = 20`.
- Commit trailer: `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.

---

### Task 1: The contender and the bench

**Files:**
- Create: `strategies/twelve_head.py`, `harness/twelve_bench.py`
- Test: `tests/test_twelve_head.py`, `tests/test_twelve_bench.py`

**Interfaces:**
- Consumes: `strategies.free_straw.FreeStrawStrategy`, `CAPS_S`; `strategies.payday_herd.HERD_RAMP_P`; `harness.feed_bench.board_on_day`; `harness.farm_census.animals_placed`; `harness.fourth_bench.pending_at`; `harness.episode_analysis.decompose`; `harness.four8_bench.escapes`; `harness.sheep_bench._seam_names`; `harness.rival_bench.criterion`, `decided_row`, `format_external`, `format_rows`, `paired_external_rows`; `harness.reserve_bench.MADHUR, PILKWANG, REFERENCE`; `harness.external_pool.EXTERNAL_ANCHORS`; `harness.evolve.DEFAULT_ANCHORS`; `harness.cashflow.play`; `harness.triage.head_to_head_rate`; `harness.tournament.play_rewards`; `strategies.field_pace.HERD_RAMP_F`.
- Produces: `twelve_head.HERD_RAMP_T`, `TwelveHeadStrategy`, `STRATEGY`; `twelve_bench.reading`, `mechanism_failures`, `off_class`, `main`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_twelve_head.py
"""twelve_head (#320): the herd ramp's last step is twelve, nothing else."""

from __future__ import annotations

from strategies import free_straw as fs
from strategies import twelve_head as th
from strategies.free_straw import FreeStrawStrategy
from strategies.payday_herd import HERD_RAMP_P


def test_the_ramp_is_payday_herds_with_its_last_step_at_twelve():
    assert th.HERD_RAMP_T == ((0, 4), (6, 8), (12, 12))
    assert th.HERD_RAMP_T[:2] == HERD_RAMP_P[:2] and HERD_RAMP_P[2] == (12, 13)
    assert th.TwelveHeadStrategy.HERD_RAMP_F is th.HERD_RAMP_T


def test_herd_target_reads_the_ramp_and_never_thirteen():
    p, q = th.TwelveHeadStrategy(), FreeStrawStrategy()
    assert [p.herd_target(d) for d in (0, 6, 12, 20, 29)] == [4, 8, 12, 12, 12]
    assert [q.herd_target(d) for d in (0, 6, 12, 20)] == [4, 8, 13, 13]
    assert all(p.herd_target(d) == q.herd_target(d) for d in range(0, 12))


def test_the_class_overrides_nothing_but_the_ramp():
    from harness import sheep_bench as sb
    p = th.TwelveHeadStrategy()
    assert p.name == "twelve_head" and isinstance(p, FreeStrawStrategy) and p.FOURTH_DAY == 8 and p.benchmark is False
    assert p.CAPS is fs.CAPS_S
    assert set(th.TwelveHeadStrategy.__dict__) & set(sb._seam_names()) == set()
    assert not [k for k, v in th.TwelveHeadStrategy.__dict__.items() if callable(v)]
    q = FreeStrawStrategy()
    assert p.livestock_workers(8) == q.livestock_workers(8) and p.buy_order() == q.buy_order() and p.pivot_day() == q.pivot_day()


def test_registered():
    from strategies import load
    assert load("twelve_head") is th.TwelveHeadStrategy
```

```python
# tests/test_twelve_bench.py
"""The twelve_head experiment's declared constants and pure parts (#320)."""

from __future__ import annotations

import pytest

from harness import rival_bench as rb
from harness import twelve_bench as tb
from strategies import field_pace as fp
from strategies import twelve_head as th


def test_the_declared_constants():
    assert tb.CONTENDER == "twelve_head" and tb.CHAMPION == "free_straw"
    assert tb.SEEDS == tuple(range(1463, 1479)) and tb.CONTROL_SEED == 1463
    assert tb.CHAMPION_BAR == 0.60 and tb.ANCHOR_BAR == 0.90 and tb.HEAD_DAY == 20
    assert tb.LONESPEAR.startswith("lonespear")
    assert tb.criterion is rb.criterion and tb.decided_row is rb.decided_row and rb.MIN_DECIDED == 8


def test_the_seeds_are_fresh_against_every_range_already_spent():
    spent = set(range(100, 116)) | set(range(200, 216)) | set(range(300, 332)) \
        | set(range(400, 416)) | set(range(500, 516)) | set(range(600, 616)) \
        | set(range(700, 704)) | set(range(800, 960)) | set(range(960, 1463))
    assert not spent & set(tb.SEEDS)


def _board(cows, sheep):
    return {"tiles": [[{"animal": "COW"}] * cows + [{"animal": "SHEEP"}] * sheep + [None, "LOCKED", {"kind": "PLANT", "crop": "STRAWBERRY"}]]}


def test_reading_and_its_failure(monkeypatch):
    monkeypatch.setattr(tb, "board_on_day", lambda steps, seat, day: _board(9, 3) if day == 20 else None)
    monkeypatch.setattr(tb, "pending_at", lambda steps, seat, day: {20: 0}[day])
    monkeypatch.setattr(tb, "decompose", lambda steps, seat: {"revenue": {"MILK": 30000, "WOOL": 12000, "STRAWBERRY": 1},
                                                              "spend": {"animal": 6300, "seed": 1}})
    assert tb.reading("s", 0) == {"head_20": 12, "pending_20": 0, "animal_spend": 6300, "milk_wool": 42000}
    monkeypatch.setattr(tb, "board_on_day", lambda steps, seat, day: None)
    with pytest.raises(ValueError):
        tb.reading("s", 0)


def test_mechanism_failures_name_the_bars():
    champ = {"head_20": 12, "pending_20": 1, "animal_spend": 6700, "milk_wool": 42000}
    good = {"head_20": 12, "pending_20": 0, "animal_spend": 6300, "milk_wool": 42500}
    assert tb.mechanism_failures(good, champ) == []
    assert tb.mechanism_failures({**good, "pending_20": 1}, champ) == ["pending_20"]
    assert tb.mechanism_failures({**good, "animal_spend": 6700}, champ) == ["animal_spend"]
    assert tb.mechanism_failures({**good, "pending_20": 2, "animal_spend": 7000}, champ) == ["pending_20", "animal_spend"]


def test_the_identity_stub_switches_all_sixteen_seams_off_and_survives_a_turn():
    from harness.sheep_bench import _seam_names
    names = _seam_names()
    assert len(names) == 16
    cls = tb.off_class()
    for n in names:
        assert n in cls.__dict__, f"seam {n} not switched off"
    off = cls()
    assert off.herd_target(12) is None and off.herd_preference({"town": {"unlocked_shops": ["YARN_STORE"]}}) is None
    assert off.HERD_RAMP_F == fp.HERD_RAMP_F and off.HERD_RAMP_F is not th.HERD_RAMP_T
    assert off.CAPS == tb.load_reference().CAPS and "STRAWBERRY" in off.CAPS
    from kaggisim.state import parse
    from kaggle_environments import make
    env = make("kaggriculture", configuration={"seed": 1463, "episodeSteps": 3})
    out = off.act(parse(env.reset()[0].observation))
    assert set(out) >= {"farmer", "hands", "market"}


def test_play_and_the_reference_are_pinned():
    from harness.cashflow import play
    from harness.reserve_bench import MADHUR, PILKWANG, REFERENCE
    assert tb.play is play and tb.REFERENCE == REFERENCE == "dense_farm"
    assert tb.MADHUR == MADHUR and tb.PILKWANG == PILKWANG
```

- [ ] **Step 2: Run the tests and observe them fail**

Run: `.venv/bin/python -m pytest tests/test_twelve_head.py tests/test_twelve_bench.py -q 2>&1 | tail -6`
Expected: collection errors — `ImportError: cannot import name 'twelve_head' from 'strategies'` and `... 'twelve_bench' from 'harness'`. Quote the lines in the report.

- [ ] **Step 3: Write `strategies/twelve_head.py`**

```python
"""twelve_head: free_straw with the herd target's last step at twelve (#320).

With four herders the herd is labour-bound at twelve head (#288): a
thirteenth costs milking and collecting time and produces nothing, and the
chain's ramp buys it anyway and leaves it pending in the shed. A scratch
probe of a twelve-head target against free_straw read 16/16 by a small,
consistent margin -- one animal fewer bought, and its feed.

One class attribute changes: `HERD_RAMP_F` ends at twelve on day 12
instead of thirteen. `field_pace.herd_target` reads it through the
`herd_target` seam; nothing else is overridden and everything else is
free_straw's.

Declared before measurement: `HERD_RAMP_T`, and the controls and criterion
in `harness/twelve_bench.py` (posted to #320 before any code).
"""

from __future__ import annotations

from strategies.free_straw import FreeStrawStrategy

#: payday_herd's ramp with its last step at twelve: the head four herders work.
HERD_RAMP_T = ((0, 4), (6, 8), (12, 12))


class TwelveHeadStrategy(FreeStrawStrategy):
    """`free_straw` with a twelve-head herd."""

    name = "twelve_head"
    benchmark = False
    HERD_RAMP_F = HERD_RAMP_T


STRATEGY = TwelveHeadStrategy
```

- [ ] **Step 4: Write `harness/twelve_bench.py`**

```python
"""The twelve_head experiment (#320): controls and criterion -- judged under
ADR-0007's amendment of 2026-09-16 as corrected 2026-09-17 (`decided_row`).

Declared on #320 before any code. Controls first -- identity (every seam off
is the frozen benchmark to the value) and mechanism (fewer animals pending
in the shed on day 20 than free_straw and less spent on animals in the same
game); a failed control is a VOID run (exit 2). Then rival_bench's criterion
on the decided row: >= 60% of the decided games vs free_straw (VOID if fewer
than MIN_DECIDED are decided), >= 90% vs each anchor, paired external
non-regression. No arm B.

    .venv/bin/python -m harness.twelve_bench --controls
    .venv/bin/python -m harness.twelve_bench --criterion
"""

from __future__ import annotations

import argparse
import os

from harness.cashflow import play  # noqa: F401  -- pinned by the tests
from harness.episode_analysis import decompose
from harness.evolve import DEFAULT_ANCHORS
from harness.external_pool import EXTERNAL_ANCHORS
from harness.farm_census import animals_placed
from harness.feed_bench import board_on_day
from harness.four8_bench import escapes
from harness.fourth_bench import pending_at
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

CONTENDER = "twelve_head"
CHAMPION = "free_straw"
SEEDS = tuple(range(1463, 1479))
CONTROL_SEED = 1463
CHAMPION_BAR = 0.60
ANCHOR_BAR = 0.90
HEAD_DAY = 20
LONESPEAR = EXTERNAL_ANCHORS[1]
assert LONESPEAR.startswith("lonespear"), LONESPEAR  # the pool order is the pin (review)


def load_reference():
    from strategies import load
    return load(REFERENCE)


def reading(steps, seat) -> dict:
    """One side's placed and pending head on day 20, its animal spend, and its
    milk and wool revenue."""
    board = board_on_day(steps, seat, HEAD_DAY)
    if board is None:
        raise ValueError(f"no board for day {HEAD_DAY}: the game ended early")
    d = decompose(steps, seat)
    rev, spend = d["revenue"], d["spend"]
    return {"head_20": sum(animals_placed(board["tiles"]).values()),
            "pending_20": pending_at(steps, seat, HEAD_DAY),
            "animal_spend": spend.get("animal", 0),
            "milk_wool": rev.get("MILK", 0) + rev.get("WOOL", 0)}


def mechanism_failures(contender, champion) -> list:
    """Control 2's bars; the names of the ones that did not hold."""
    failed = []
    if not contender["pending_20"] < champion["pending_20"]:
        failed.append("pending_20")
    if not contender["animal_spend"] < champion["animal_spend"]:
        failed.append("animal_spend")
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
    ap = argparse.ArgumentParser(description="twelve_head: the herd target's last step is twelve")
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
              f"(declared: pending head on day {HEAD_DAY} < {CHAMPION}'s, animal spend < {CHAMPION}'s)  "
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

Run: `.venv/bin/python -m pytest tests/test_twelve_head.py tests/test_twelve_bench.py -q 2>&1 | tail -5`
Expected: all pass. If `test_herd_target_reads_the_ramp_and_never_thirteen` disagrees with what `field_pace.herd_target` actually returns, the chain's code is the truth: fix the test's expected values, never a production file, and say so in the report.

- [ ] **Step 6: Smoke the controls once (blocking, ~15 s), then commit**

Run: `.venv/bin/python -m harness.twelve_bench --controls 2>&1 | grep -v Warning | tail -4`
Expected: `control identity: OK ...` and `control mechanism: OK ...`. Quote both lines in the report. If either says FAIL, do not change the bars: commit anyway and report DONE_WITH_CONCERNS with the lines quoted.

```bash
git add strategies/twelve_head.py harness/twelve_bench.py tests/test_twelve_head.py tests/test_twelve_bench.py
git commit -m "feat(#320): twelve_head -- the herd target's last step is twelve, with its declared bench

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```
