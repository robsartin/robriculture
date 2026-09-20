# fert_sixteen (#324) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The `fert_sixteen` contender and its declared bench, exactly as `docs/superpowers/specs/2026-09-20-fert-sixteen-design.md` and the declaration on #324.

**Architecture:** One strategy file defining the two fertilizer seams on `twelve_head` with `fert_six`'s constants; one bench in the shape of `harness/twelve_bench.py` with `eight2_bench`'s readings, judged with `rival_bench.decided_row`, arm B recorded.

**Tech Stack:** Python 3.12, `.venv/bin/python`, pytest.

## Global Constraints
- Pure TDD: failing tests first, RUN and observe, then the code; the report quotes the red.
- Never edit any existing file.
- `.venv/bin/python` only; every command blocking; do NOT run the full suite (the controller does) — only the targeted tests and the one controls smoke (~20 s).
- Stage by explicit path; never `git add -A`; never stage `.venv`, `external_agents`, `replays/`.
- Declared values verbatim: `FERT_FROM = 16`; `CONTENDER = "fert_sixteen"`, `CHAMPION = "twelve_head"`, `SEEDS = tuple(range(1511, 1527))`, `CONTROL_SEED = 1511`, `CHAMPION_BAR = 0.60`, `ANCHOR_BAR = 0.90`, `FERTILIZE_BAR = 100`, `STRAWBERRY_FACTOR = 1.5`, `EARLY_DAYS = range(1, 17)`, `ARM_B = "from_twelve"`, `ARM_B_FROM = 12`.
- `fert_six.FERT_STOCK` and `fert_six.FERT_CROPS` are imported, never restated in production code.
- Commit trailer: `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.

---

### Task 1: The contender and the bench

**Files:**
- Create: `strategies/fert_sixteen.py`, `harness/sixteen_bench.py`
- Test: `tests/test_fert_sixteen.py`, `tests/test_sixteen_bench.py`

**Interfaces:**
- Consumes: `strategies.twelve_head.TwelveHeadStrategy`, `HERD_RAMP_T`; `strategies.free_straw.CAPS_S`; `strategies.fert_six.FERT_STOCK`, `FERT_CROPS`; `harness.fert_bench.action_counts`, `units_sold`; `harness.six_bench.dawn_cash`; `harness.four8_bench.escapes`; `harness.sheep_bench._seam_names`; `harness.rival_bench.criterion`, `decided_row`, `format_external`, `format_rows`, `paired_external_rows`; `harness.reserve_bench.MADHUR, REFERENCE`; `harness.external_pool.EXTERNAL_ANCHORS`; `harness.evolve.DEFAULT_ANCHORS`; `harness.cashflow.play`; `harness.triage.head_to_head_rate`, `_default_agents`; `harness.tournament.play_rewards`; `strategies.field_pace.HERD_RAMP_F`.
- Produces: `fert_sixteen.FERT_FROM`, `FertSixteenStrategy`, `STRATEGY`; `sixteen_bench.reading`, `mechanism_failures`, `off_class`, `arm_b_class`, `main`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_fert_sixteen.py
"""fert_sixteen (#324): the fertilizer line from day 16, nothing else."""

from __future__ import annotations

from strategies import fert_six as f6
from strategies import fert_sixteen as fs
from strategies import free_straw
from strategies import twelve_head as th
from strategies.twelve_head import TwelveHeadStrategy


def test_the_seams_fire_from_day_sixteen_with_fert_sixs_constants():
    p = fs.FertSixteenStrategy()
    assert fs.FERT_FROM == 16 and p.FERT_FROM == 16
    assert p.fertilizer_stock(None) is None and p.fertilize_crops(None) is None
    for d in (0, 8, 12, 15):
        assert p.fertilizer_stock(d) is None and p.fertilize_crops(d) is None
    for d in (16, 20, 29):
        assert p.fertilizer_stock(d) == f6.FERT_STOCK == 8
        assert p.fertilize_crops(d) == f6.FERT_CROPS == ("MELON", "STRAWBERRY")


def test_the_class_defines_exactly_the_two_fertilizer_seams():
    from harness import sheep_bench as sb
    p = fs.FertSixteenStrategy()
    assert p.name == "fert_sixteen" and isinstance(p, TwelveHeadStrategy) and p.benchmark is False
    assert set(fs.FertSixteenStrategy.__dict__) & set(sb._seam_names()) == {"fertilizer_stock", "fertilize_crops"}
    assert {k for k, v in fs.FertSixteenStrategy.__dict__.items() if callable(v)} == {"fertilizer_stock", "fertilize_crops"}
    assert p.HERD_RAMP_F is th.HERD_RAMP_T and p.CAPS is free_straw.CAPS_S and p.FOURTH_DAY == 8
    q = TwelveHeadStrategy()
    assert p.herd_target(20) == q.herd_target(20) == 12 and p.buy_order() == q.buy_order()


def test_registered():
    from strategies import load
    assert load("fert_sixteen") is fs.FertSixteenStrategy
```

```python
# tests/test_sixteen_bench.py
"""The fert_sixteen experiment's declared constants and pure parts (#324)."""

from __future__ import annotations

import pytest

from harness import rival_bench as rb
from harness import sixteen_bench as sb
from strategies import field_pace as fp


def test_the_declared_constants():
    assert sb.CONTENDER == "fert_sixteen" and sb.CHAMPION == "twelve_head" and sb.ARM_B == "from_twelve"
    assert sb.SEEDS == tuple(range(1511, 1527)) and sb.CONTROL_SEED == 1511
    assert sb.CHAMPION_BAR == 0.60 and sb.ANCHOR_BAR == 0.90
    assert (sb.FERTILIZE_BAR, sb.STRAWBERRY_FACTOR, sb.ARM_B_FROM) == (100, 1.5, 12)
    assert list(sb.EARLY_DAYS) == list(range(1, 17))
    assert sb.LONESPEAR.startswith("lonespear")
    from harness.reserve_bench import MADHUR
    assert sb.MADHUR == MADHUR
    assert sb.criterion is rb.criterion and sb.decided_row is rb.decided_row and rb.MIN_DECIDED == 8


def test_the_seeds_are_fresh_against_every_range_already_spent():
    spent = set(range(100, 116)) | set(range(200, 216)) | set(range(300, 332)) \
        | set(range(400, 416)) | set(range(500, 516)) | set(range(600, 616)) \
        | set(range(700, 704)) | set(range(800, 960)) | set(range(960, 1511))
    assert not spent & set(sb.SEEDS)


def test_reading_reads_counts_units_and_dawn_cash(monkeypatch):
    monkeypatch.setattr(sb, "action_counts", lambda steps, seat: {"FERTILIZE": 121, "WATER": 900})
    monkeypatch.setattr(sb, "units_sold", lambda steps, seat: {"STRAWBERRY": 278, "FERTILIZER": 110, "MILK": 1})
    monkeypatch.setattr(sb, "dawn_cash", lambda steps, seat, days: [d * 100 for d in days])
    got = sb.reading("s", 0)
    assert got == {"fertilize": 121, "strawberry": 278, "fertilizer_sold": 110, "dawn_1_16": [d * 100 for d in range(1, 17)]}


def test_mechanism_failures_name_the_bars():
    dawn = [d * 100 for d in range(1, 17)]
    champ = {"fertilize": 0, "strawberry": 167, "fertilizer_sold": 150, "dawn_1_16": dawn}
    good = {"fertilize": 121, "strawberry": 278, "fertilizer_sold": 110, "dawn_1_16": list(dawn)}
    assert sb.mechanism_failures(good, champ) == []
    assert sb.mechanism_failures({**good, "fertilize": 99}, champ) == ["fertilize"]
    assert sb.mechanism_failures({**good, "strawberry": 250}, champ) == ["strawberry"]      # 250 < 1.5 * 167
    assert sb.mechanism_failures({**good, "strawberry": 251}, champ) == []                  # 251 >= 250.5
    assert sb.mechanism_failures({**good, "dawn_1_16": dawn[:-1] + [1]}, champ) == ["dawn_1_16"]
    assert sb.mechanism_failures({**good, "fertilize": 0, "strawberry": 1, "dawn_1_16": []}, champ) == ["fertilize", "strawberry", "dawn_1_16"]


def test_the_identity_stub_switches_all_sixteen_seams_off_and_survives_a_turn():
    from harness.sheep_bench import _seam_names
    names = _seam_names()
    assert len(names) == 16
    cls = sb.off_class()
    for n in names:
        assert n in cls.__dict__, f"seam {n} not switched off"
    off = cls()
    assert off.fertilizer_stock(20) is None and off.fertilize_crops(20) is None and off.herd_target(12) is None
    assert off.HERD_RAMP_F == fp.HERD_RAMP_F and off.CAPS == sb.load_reference().CAPS
    from kaggisim.state import parse
    from kaggle_environments import make
    env = make("kaggriculture", configuration={"seed": 1511, "episodeSteps": 3})
    out = off.act(parse(env.reset()[0].observation))
    assert set(out) >= {"farmer", "hands", "market"}


def test_arm_b_is_the_same_line_from_day_twelve():
    from strategies import fert_six as f6
    from strategies import fert_sixteen as fs
    cls = sb.arm_b_class()
    assert issubclass(cls, fs.FertSixteenStrategy) and cls.__name__ == "FromTwelve" and cls.FERT_FROM == 12
    b = cls()
    assert b.fertilizer_stock(11) is None and b.fertilizer_stock(12) == f6.FERT_STOCK
    assert b.fertilize_crops(11) is None and b.fertilize_crops(12) == f6.FERT_CROPS
    assert fs.FertSixteenStrategy().fertilizer_stock(12) is None
    from strategies import REGISTRY
    assert "from_twelve" not in REGISTRY


def test_play_and_the_reference_are_pinned():
    from harness.cashflow import play
    from harness.reserve_bench import REFERENCE
    assert sb.play is play and sb.REFERENCE == REFERENCE == "dense_farm"
```

- [ ] **Step 2: Run the tests and observe them fail**

Run: `.venv/bin/python -m pytest tests/test_fert_sixteen.py tests/test_sixteen_bench.py -q 2>&1 | tail -6`
Expected: collection errors — `ImportError: cannot import name 'fert_sixteen' from 'strategies'` and `... 'sixteen_bench' from 'harness'`. Quote the lines in the report.

- [ ] **Step 3: Write `strategies/fert_sixteen.py`**

```python
"""fert_sixteen: twelve_head with the fertilizer line from day 16 (#324).

Fertilizer doubles a strawberry tile's yield on its production day (#277's
seam). Started on day 8 (#286) the line beat the champion 13/16 and lost on
the anchors: the walk for fertilizer delayed the second quadrant's planting
two days and the withheld sales starved days 1-7. From day 16 the field is
planted, cash is not scarce, and the fourteen days that earn most of the
strawberry money are ahead. Two scratch seed sets read day 16 at 15/16 and
15/16, +11K and +10K, strawberry units 1.66x, the early economy untouched.

One number: FERT_FROM is 16. The two seams are fert_six's, with its
constants; everything else is twelve_head's.

Declared before measurement: FERT_FROM, and the controls and criterion in
`harness/sixteen_bench.py` (posted to #324 before any code).
"""

from __future__ import annotations

from strategies.fert_six import FERT_CROPS, FERT_STOCK
from strategies.twelve_head import TwelveHeadStrategy

#: The day the fertilizer line starts: the third quadrant open, the field planted.
FERT_FROM = 16


class FertSixteenStrategy(TwelveHeadStrategy):
    """`twelve_head` with the fertilizer line from day sixteen."""

    name = "fert_sixteen"
    benchmark = False
    FERT_FROM = FERT_FROM

    def fertilizer_stock(self, day=None):
        """fert_six's stock from `FERT_FROM` on; the frozen sweep before."""
        return FERT_STOCK if (day or 0) >= self.FERT_FROM else None

    def fertilize_crops(self, day=None):
        """fert_six's crops from `FERT_FROM` on; never before."""
        return FERT_CROPS if (day or 0) >= self.FERT_FROM else None


STRATEGY = FertSixteenStrategy
```

- [ ] **Step 4: Write `harness/sixteen_bench.py`**

```python
"""The fert_sixteen experiment (#324): controls, criterion, arm B -- judged
under ADR-0007's amendment of 2026-09-16 as corrected 2026-09-17.

Declared on #324 before any code. Controls first -- identity (every seam off
is the frozen benchmark to the value) and mechanism (at least FERTILIZE_BAR
FERTILIZE actions, strawberry units at least STRAWBERRY_FACTOR times the
champion's, and dawn cash on days 1-16 equal to the champion's: the lever
must not touch the early economy); a failed control is a VOID run (exit 2).
Then rival_bench's criterion on the decided row: >= 60% of the decided games
vs twelve_head (VOID if fewer than MIN_DECIDED are decided), >= 90% vs each
anchor, paired external non-regression. Arm B (`from_twelve`) is recorded,
never gated.

    .venv/bin/python -m harness.sixteen_bench --controls
    .venv/bin/python -m harness.sixteen_bench --criterion
    .venv/bin/python -m harness.sixteen_bench --recorded
"""

from __future__ import annotations

import argparse
import os

from harness.cashflow import play  # noqa: F401  -- pinned by the tests
from harness.evolve import DEFAULT_ANCHORS
from harness.external_pool import EXTERNAL_ANCHORS
from harness.fert_bench import action_counts, units_sold
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
from harness.six_bench import dawn_cash
from strategies import field_pace as fp

CONTENDER = "fert_sixteen"
CHAMPION = "twelve_head"
SEEDS = tuple(range(1511, 1527))
CONTROL_SEED = 1511
CHAMPION_BAR = 0.60
ANCHOR_BAR = 0.90
FERTILIZE_BAR = 100
STRAWBERRY_FACTOR = 1.5
EARLY_DAYS = range(1, 17)
ARM_B = "from_twelve"
ARM_B_FROM = 12
LONESPEAR = EXTERNAL_ANCHORS[0]
assert LONESPEAR.startswith("lonespear"), LONESPEAR  # the pool order is the pin (review)


def load_reference():
    from strategies import load
    return load(REFERENCE)


def reading(steps, seat) -> dict:
    """One side's FERTILIZE count, strawberry and fertilizer units sold, and
    dawn cash on days 1-16."""
    a, u = action_counts(steps, seat), units_sold(steps, seat)
    return {"fertilize": a.get("FERTILIZE", 0), "strawberry": u.get("STRAWBERRY", 0),
            "fertilizer_sold": u.get("FERTILIZER", 0), "dawn_1_16": dawn_cash(steps, seat, EARLY_DAYS)}


def mechanism_failures(contender, champion) -> list:
    """Control 2's bars; the names of the ones that did not hold."""
    failed = []
    if contender["fertilize"] < FERTILIZE_BAR:
        failed.append("fertilize")
    if contender["strawberry"] < STRAWBERRY_FACTOR * champion["strawberry"]:
        failed.append("strawberry")
    if contender["dawn_1_16"] != champion["dawn_1_16"]:
        failed.append("dawn_1_16")
    return failed


def off_class():
    """Every seam off (sixteen), the reference's caps, and the frozen herd ramp."""
    from strategies import load
    body = {n: (lambda self, *a, **k: None) for n in _seam_names()}
    body["CAPS"] = load_reference().CAPS
    body["HERD_RAMP_F"] = fp.HERD_RAMP_F
    return type("Off", (load(CONTENDER),), body)


def arm_b_class():
    """`fert_sixteen` from day twelve. Never registered."""
    from strategies import load
    return type("FromTwelve", (load(CONTENDER),), {"FERT_FROM": ARM_B_FROM})


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


def run_recorded(seeds=SEEDS):  # pragma: no cover
    os.environ.setdefault("ROBRICULTURE_STRICT", "1")
    return decided_row(ARM_B, CHAMPION, seeds, agents=_arm_b_agents(ARM_B))


def main(argv=None):  # pragma: no cover
    os.environ.setdefault("ROBRICULTURE_STRICT", "1")
    ap = argparse.ArgumentParser(description="fert_sixteen: the fertilizer line from day 16")
    ap.add_argument("--controls", action="store_true")
    ap.add_argument("--criterion", action="store_true")
    ap.add_argument("--recorded", action="store_true", help="arm B (recorded, not gated)")
    args = ap.parse_args(argv)

    if args.recorded:
        row = run_recorded()
        print(format_rows([row]))
        decided = row["games"] - row["identical"]
        print(f"recorded, not gated: arm B ({ARM_B}: the line from day {ARM_B_FROM}) vs {CHAMPION}: "
              f"{row['wins']}W {row['ties']}T {row['losses']}L over {decided} decided ({row['identical']} identical)")
        return 0

    do_controls = args.controls or not args.criterion
    do_criterion = args.criterion or not args.controls

    if do_controls:
        ctl = run_controls()
        print(f"control identity: {'OK' if ctl['identity']['ok'] else 'FAIL -- RUN VOID'}  {ctl['identity']}")
        c, b = ctl["mechanism"]["contender"], ctl["mechanism"]["champion"]
        print(f"control mechanism: {'OK' if ctl['mechanism']['ok'] else 'FAIL -- RUN VOID'}  "
              f"(declared: FERTILIZE >= {FERTILIZE_BAR}, strawberry units >= {STRAWBERRY_FACTOR}x {CHAMPION}'s, "
              f"dawn cash days 1-16 equal)  contender {c}  {CHAMPION} {b}  failed={ctl['mechanism']['failed'] or 'none'}")
        if not all(r["ok"] for r in ctl.values()):
            print("a control failed: the run is VOID and arm B is NOT scored")
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
              f"paired rows (contender, champion): madhur {v['external'].get(MADHUR)}, lonespear {v['external'].get(LONESPEAR)}")
        if v["void"]:
            return 2
        return 0 if v["passed"] else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Run the targeted tests and observe them pass**

Run: `.venv/bin/python -m pytest tests/test_fert_sixteen.py tests/test_sixteen_bench.py -q 2>&1 | tail -5`
Expected: all pass. If `EXTERNAL_ANCHORS[0]` is not the lonespear entry, the pool's own order is the truth: use the index that is, in `harness/sixteen_bench.py` only, and say so in the report.

- [ ] **Step 6: Smoke the controls once (blocking, ~20 s), then commit**

Run: `.venv/bin/python -m harness.sixteen_bench --controls 2>&1 | grep -v Warning | tail -4`
Expected: `control identity: OK ...` and `control mechanism: OK ...`. Quote both lines in the report. If either says FAIL, do not change the bars: commit anyway and report DONE_WITH_CONCERNS with the lines quoted.

```bash
git add strategies/fert_sixteen.py harness/sixteen_bench.py tests/test_fert_sixteen.py tests/test_sixteen_bench.py
git commit -m "feat(#324): fert_sixteen -- the fertilizer line from day 16, with its declared bench

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```
