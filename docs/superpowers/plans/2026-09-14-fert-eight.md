# fert_eight (#284) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The `fert_eight` contender and its declared bench, exactly as `docs/superpowers/specs/2026-09-14-fert-eight-design.md` and the declaration on #284.

**Architecture:** One strategy file setting one class attribute on `fert_six`; one bench in the shape of `harness/six_bench.py`, importing its `dawn_cash`.

**Tech Stack:** Python 3.12, `.venv/bin/python`, pytest.

## Global Constraints
- Pure TDD: failing tests first, RUN and observe, then the code; the report quotes the red.
- Never edit any existing file.
- `.venv/bin/python` only; every command blocking; do NOT run the full suite (the controller does) — only the targeted tests and the ~15 s controls smoke.
- Stage by explicit path; never `git add -A`; never stage `.venv`, `external_agents`, `replays/`.
- Declared values verbatim: `FERT_FROM_EIGHT = 8`; `CONTENDER = "fert_eight"`, `CHAMPION = "ten_melon"`, `SEEDS = tuple(range(1104, 1120))`, `CONTROL_SEED = 1104`, `CHAMPION_BAR = 0.60`, `ANCHOR_BAR = 0.90`, `FERTILIZE_BAR = 100`, `STRAWBERRY_FACTOR = 1.5`, `EARLY_DAYS = range(1, 8)`, `PLANTED_DAY = 8`, `ARM_B = "from_ten"`, `ARM_B_FROM = 10`.

---

### Task 1: The contender and the bench

**Files:**
- Create: `strategies/fert_eight.py`, `harness/eight_bench.py`
- Test: `tests/test_fert_eight.py`, `tests/test_eight_bench.py`

**Interfaces:**
- Consumes: `strategies.fert_six.FertSixStrategy` (`FERT_STOCK`, `FERT_CROPS`, seam overrides reading `self.FERT_FROM`); `harness.six_bench.dawn_cash(steps, seat, days)`; `harness.fert_bench.action_counts`, `units_sold`; `harness.feed_bench.board_on_day`; `harness.farm_census.planted_by_crop`; `harness.sheep_bench._seam_names`; `harness.rival_bench.*`; `harness.reserve_bench.MADHUR, PILKWANG, REFERENCE`; `harness.external_pool.EXTERNAL_ANCHORS`; `harness.evolve.DEFAULT_ANCHORS`; `harness.cashflow.play`; `harness.triage.head_to_head_rate`, `_default_agents`; `harness.tournament.play_rewards`; `strategies.field_pace.HERD_RAMP_F`.
- Produces: `fert_eight.FERT_FROM_EIGHT`, `FertEightStrategy`, `STRATEGY`; `eight_bench.reading`, `mechanism_failures`, `off_class`, `arm_b_class`, `main`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_fert_eight.py
"""fert_eight (#284): fert_six from day 8, nothing else."""

from __future__ import annotations

from strategies import fert_eight as fe
from strategies.fert_six import FERT_CROPS, FERT_STOCK, FertSixStrategy


def test_only_the_start_day_changes():
    assert fe.FERT_FROM_EIGHT == 8
    assert set(fe.FertEightStrategy.__dict__) - {"__module__", "__doc__", "__qualname__", "__firstlineno__", "__static_attributes__"} \
        <= {"name", "benchmark", "FERT_FROM"}
    p = fe.FertEightStrategy()
    assert p.name == "fert_eight" and isinstance(p, FertSixStrategy) and p.FERT_FROM == 8
    for day in (0, 6, 7):
        assert p.fertilizer_stock(day) is None and p.fertilize_crops(day) is None
    for day in (8, 12, 29):
        assert p.fertilizer_stock(day) == FERT_STOCK == 8 and p.fertilize_crops(day) == FERT_CROPS == ("MELON", "STRAWBERRY")
    assert FertSixStrategy().fertilizer_stock(7) == 8      # the parent still starts on day 6


def test_registered():
    from strategies import load
    assert load("fert_eight") is fe.FertEightStrategy
```

```python
# tests/test_eight_bench.py
"""The fert_eight experiment's declared constants and pure parts (#284)."""

from __future__ import annotations

import pytest

from harness import eight_bench as eb
from strategies import field_pace as fp


def test_the_declared_constants():
    assert eb.CONTENDER == "fert_eight" and eb.CHAMPION == "ten_melon" and eb.ARM_B == "from_ten"
    assert eb.SEEDS == tuple(range(1104, 1120)) and eb.CONTROL_SEED == 1104
    assert eb.CHAMPION_BAR == 0.60 and eb.ANCHOR_BAR == 0.90
    assert eb.FERTILIZE_BAR == 100 and eb.STRAWBERRY_FACTOR == 1.5
    assert list(eb.EARLY_DAYS) == list(range(1, 8)) and eb.PLANTED_DAY == 8 and eb.ARM_B_FROM == 10
    assert eb.LONESPEAR.startswith("lonespear")


def test_the_seeds_are_fresh_against_every_range_already_spent():
    spent = set(range(100, 116)) | set(range(200, 216)) | set(range(300, 332)) \
        | set(range(400, 416)) | set(range(500, 516)) | set(range(600, 616)) \
        | set(range(700, 704)) | set(range(800, 960)) | set(range(960, 1104))
    assert not spent & set(eb.SEEDS)


def test_reading_has_the_declared_fields(monkeypatch):
    monkeypatch.setattr(eb, "action_counts", lambda steps, seat: {"FERTILIZE": 160, "WATER": 800})
    monkeypatch.setattr(eb, "units_sold", lambda steps, seat: {"STRAWBERRY": 262, "MELON": 38})
    monkeypatch.setattr(eb, "board_on_day", lambda steps, seat, day: {"tiles": [[{"kind": "PLANT", "crop": "MELON"}] * 26]})
    monkeypatch.setattr(eb, "dawn_cash", lambda steps, seat, days: [104, 175, 632, 912, 1140, 1401, 11])
    assert eb.reading("s", 0) == {"fertilize": 160, "strawberry": 262, "melon": 38, "planted_8": 26,
                                  "dawn_1_7": [104, 175, 632, 912, 1140, 1401, 11]}
    monkeypatch.setattr(eb, "board_on_day", lambda steps, seat, day: None)
    with pytest.raises(ValueError):
        eb.reading("s", 0)


def test_mechanism_failures_name_the_four_bars():
    champ = {"fertilize": 0, "strawberry": 149, "melon": 40, "planted_8": 26, "dawn_1_7": [1, 2, 3, 4, 5, 6, 7]}
    good = {"fertilize": 160, "strawberry": 262, "melon": 38, "planted_8": 26, "dawn_1_7": [1, 2, 3, 4, 5, 6, 7]}
    assert eb.mechanism_failures(good, champ) == []
    assert eb.mechanism_failures({**good, "fertilize": 99}, champ) == ["fertilize"]
    assert eb.mechanism_failures({**good, "strawberry": 223}, champ) == ["strawberry"]
    assert eb.mechanism_failures({**good, "dawn_1_7": [1, 2, 3, 4, 5, 6, 8]}, champ) == ["dawn_1_7"]
    assert eb.mechanism_failures({**good, "planted_8": 25}, champ) == ["planted_8"]
    assert eb.mechanism_failures({**good, "fertilize": 0, "planted_8": 20}, champ) == ["fertilize", "planted_8"]


def test_the_identity_stub_switches_all_sixteen_seams_off_and_survives_a_turn():
    from harness.sheep_bench import _seam_names
    names = _seam_names()
    assert len(names) == 16
    cls = eb.off_class()
    for n in names:
        assert n in cls.__dict__, f"seam {n} not switched off"
    off = cls()
    assert off.fertilize_crops(8) is None and off.fertilizer_stock(8) is None and off.herd_target(8) is None
    assert off.HERD_RAMP_F == fp.HERD_RAMP_F and off.CAPS == eb.load_reference().CAPS
    from kaggisim.state import parse
    from kaggle_environments import make
    env = make("kaggriculture", configuration={"seed": 1104, "episodeSteps": 3})
    out = off.act(parse(env.reset()[0].observation))
    assert set(out) >= {"farmer", "hands", "market"}


def test_arm_b_starts_on_day_ten_and_changes_nothing_else():
    from strategies.fert_eight import FertEightStrategy
    b = eb.arm_b_class()()
    assert isinstance(b, FertEightStrategy) and b.FERT_FROM == 10
    assert b.fertilizer_stock(9) is None and b.fertilizer_stock(10) == 8 and b.fertilize_crops(10) == ("MELON", "STRAWBERRY")
```

- [ ] **Step 2: Run the tests and observe them fail**

Run: `.venv/bin/python -m pytest tests/test_fert_eight.py tests/test_eight_bench.py -q`
Expected: two collection errors. Quote them.

- [ ] **Step 3: Write `strategies/fert_eight.py`**

```python
"""fert_eight: fert_six from day 8 (#284).

#282 started the fertilizer line on day 6 and lost 7/16: the day NE opens,
the crop workers who should be planting it were walking fertilizer instead
-- 20 tiles at day 8 against 26. Its recorded arm, the same lever from day 8,
won 11/16. From day 10 the lever is a wash (#277); from day 0 it kills the
farm. Day 8 is the earliest start that leaves the expansion planted.

One number changes: FERT_FROM is 8. Stock, crops and everything else are
fert_six's, which is ten_melon's.

Declared before measurement: FERT_FROM_EIGHT, and the controls and criterion
in `harness/eight_bench.py` (posted to #284 before any code).
"""

from __future__ import annotations

from strategies.fert_six import FertSixStrategy

#: The day the fertilizer line starts: after the NE expansion is planted.
FERT_FROM_EIGHT = 8


class FertEightStrategy(FertSixStrategy):
    """`fert_six` from day eight."""

    name = "fert_eight"
    benchmark = False
    FERT_FROM = FERT_FROM_EIGHT


STRATEGY = FertEightStrategy
```

- [ ] **Step 4: Write `harness/eight_bench.py`**

```python
"""The fert_eight experiment (#284): controls, criterion, arm B.

Declared on #284 before any code. Controls first -- identity (every seam off,
sixteen of them, is the frozen benchmark to the value) and mechanism (at
least FERTILIZE_BAR FERTILIZE actions, strawberry at least STRAWBERRY_FACTOR
times the champion's, dawn cash on days 1-7 equal to the champion's, and at
least the champion's planted tiles on day 8 -- #282's failure mode, gated);
a failed control is a VOID run (exit 2). Then rival_bench's criterion. Arm B
(`from_ten`) is recorded, never gated.

    .venv/bin/python -m harness.eight_bench --controls
    .venv/bin/python -m harness.eight_bench --criterion
    .venv/bin/python -m harness.eight_bench --recorded
"""

from __future__ import annotations

import argparse
import os

from harness.cashflow import play  # noqa: F401  -- pinned by the tests
from harness.evolve import DEFAULT_ANCHORS
from harness.external_pool import EXTERNAL_ANCHORS
from harness.farm_census import planted_by_crop
from harness.feed_bench import board_on_day
from harness.fert_bench import action_counts, units_sold
from harness.reserve_bench import MADHUR, PILKWANG, REFERENCE  # noqa: F401  -- pinned by the tests
from harness.rival_bench import (  # noqa: F401  -- pinned by the tests to rival_bench's own
    criterion,
    format_external,
    format_rows,
    paired_external_rows,
)
from harness.sheep_bench import _seam_names
from harness.six_bench import dawn_cash
from strategies import field_pace as fp

CONTENDER = "fert_eight"
CHAMPION = "ten_melon"
SEEDS = tuple(range(1104, 1120))
CONTROL_SEED = 1104
CHAMPION_BAR = 0.60
ANCHOR_BAR = 0.90
FERTILIZE_BAR = 100
STRAWBERRY_FACTOR = 1.5
EARLY_DAYS = range(1, 8)
PLANTED_DAY = 8
ARM_B = "from_ten"
ARM_B_FROM = 10
LONESPEAR = EXTERNAL_ANCHORS[1]
assert LONESPEAR.startswith("lonespear"), LONESPEAR


def load_reference():
    from strategies import load
    return load(REFERENCE)


def reading(steps, seat) -> dict:
    board = board_on_day(steps, seat, PLANTED_DAY)
    if board is None:
        raise ValueError(f"no board for day {PLANTED_DAY}: the game ended early")
    a, u = action_counts(steps, seat), units_sold(steps, seat)
    return {"fertilize": a.get("FERTILIZE", 0), "strawberry": u.get("STRAWBERRY", 0),
            "melon": u.get("MELON", 0), "planted_8": sum(planted_by_crop(board["tiles"]).values()),
            "dawn_1_7": dawn_cash(steps, seat, EARLY_DAYS)}


def mechanism_failures(contender, champion) -> list:
    failed = []
    if contender["fertilize"] < FERTILIZE_BAR:
        failed.append("fertilize")
    if contender["strawberry"] < STRAWBERRY_FACTOR * champion["strawberry"]:
        failed.append("strawberry")
    if contender["dawn_1_7"] != champion["dawn_1_7"]:
        failed.append("dawn_1_7")
    if contender["planted_8"] < champion["planted_8"]:
        failed.append("planted_8")
    return failed


def off_class():
    """Every seam off (sixteen), the reference's caps, and the frozen herd ramp."""
    from strategies import load
    body = {n: (lambda self, *a, **k: None) for n in _seam_names()}
    body["CAPS"] = load_reference().CAPS
    body["HERD_RAMP_F"] = fp.HERD_RAMP_F
    return type("Off", (load(CONTENDER),), body)


def arm_b_class():
    """`fert_eight` starting on day ten. Never registered."""
    from strategies import load
    return type("FromTen", (load(CONTENDER),), {"FERT_FROM": ARM_B_FROM})


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
    ap = argparse.ArgumentParser(description="fert_eight: fertilize from day 8")
    ap.add_argument("--controls", action="store_true")
    ap.add_argument("--criterion", action="store_true")
    ap.add_argument("--recorded", action="store_true", help="arm B (recorded, not gated)")
    args = ap.parse_args(argv)

    if args.recorded:
        print(format_rows(run_recorded()))
        print(f"recorded, not gated: arm B ({ARM_B}: the same from day {ARM_B_FROM}) vs {CHAMPION}")
        return 0

    do_controls = args.controls or not args.criterion
    do_criterion = args.criterion or not args.controls

    if do_controls:
        ctl = run_controls()
        print(f"control identity: {'OK' if ctl['identity']['ok'] else 'FAIL -- RUN VOID'}  {ctl['identity']}")
        c, b = ctl["mechanism"]["contender"], ctl["mechanism"]["champion"]
        print(f"control mechanism: {'OK' if ctl['mechanism']['ok'] else 'FAIL -- RUN VOID'}  "
              f"(declared: FERTILIZE >= {FERTILIZE_BAR}, strawberry >= {STRAWBERRY_FACTOR} x champion's, "
              f"dawn cash days 1-7 == champion's, planted at day {PLANTED_DAY} >= champion's)  "
              f"contender {c}  {CHAMPION} {b}  failed={ctl['mechanism']['failed'] or 'none'}")
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
              f"paired rows (contender, champion): madhur {v['external'].get(MADHUR)}, "
              f"pilkwang {v['external'].get(PILKWANG)}, lonespear {v['external'].get(LONESPEAR)}")
        return 0 if v["passed"] else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Run the targeted tests and observe them pass**

Run: `.venv/bin/python -m pytest tests/test_fert_eight.py tests/test_eight_bench.py tests/test_fert_six.py tests/test_six_bench.py -q`
Expected: all PASS. If the `__dict__` subset assertion in `test_only_the_start_day_changes` fails on a dunder the interpreter adds, extend the excluded-dunder set in the test (say which) — the intent is "only name, benchmark and FERT_FROM".

- [ ] **Step 6: Smoke the controls once (blocking, ~15 s), then commit**

Run: `.venv/bin/python -m harness.eight_bench --controls`; both control lines verbatim in the report. Identity FAIL → STOP, BLOCKED. Mechanism FAIL → commit anyway, DONE_WITH_CONCERNS with the reading; never tune.

```bash
git add strategies/fert_eight.py harness/eight_bench.py tests/test_fert_eight.py tests/test_eight_bench.py
git commit -m "feat(#284): fert_eight — fert_six from day 8, and its declared bench

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```
