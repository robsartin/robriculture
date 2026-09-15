# four_herders (#289) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The `four_herders` contender and its declared bench, exactly as `docs/superpowers/specs/2026-09-15-four-herders-design.md` and the declaration on #289.

**Architecture:** One strategy file overriding one seam on `ten_melon`; one bench in the shape of `harness/melon_bench.py`.

**Tech Stack:** Python 3.12, `.venv/bin/python`, pytest.

## Global Constraints
- Pure TDD: failing tests first, RUN and observe, then the code; the report quotes the red.
- Never edit any existing file.
- `.venv/bin/python` only; every command blocking; do NOT run the full suite (the controller does) — only the targeted tests and the ~10 s controls smoke.
- Stage by explicit path; never `git add -A`; never stage `.venv`, `external_agents`, `replays/`.
- Declared values verbatim: `FOURTH_HERDER = 7`, `FOURTH_DAY = 12`; `CONTENDER = "four_herders"`, `CHAMPION = "ten_melon"`, `SEEDS = tuple(range(1122, 1138))`, `CONTROL_SEED = 1122`, `CHAMPION_BAR = 0.60`, `ANCHOR_BAR = 0.90`, `PLACED_DAY = 14`, `PLACED_BAR = 12`, `PENDING_DAYS = (14, 20)`, `PLANTED_DAY = 16`, `ARM_B = "from_eight"`, `ARM_B_FROM = 8`.

---

### Task 1: The contender and the bench

**Files:**
- Create: `strategies/four_herders.py`, `harness/fourth_bench.py`
- Test: `tests/test_four_herders.py`, `tests/test_fourth_bench.py`

**Interfaces:**
- Consumes: `strategies.ten_melon.TenMelonStrategy`; `strategies.third_herder` (`HERDER_DAY`, `THIRD_HERDER`); `strategies.field_rival.LIVESTOCK_WORKERS`; `harness.feed_bench.board_on_day`; `harness.farm_census.animals_placed`, `planted_by_crop`; `harness.fert_bench.units_sold`; `harness.episode_analysis._slot`; `harness.sheep_bench._seam_names`; `harness.rival_bench.*`; `harness.reserve_bench.MADHUR, PILKWANG, REFERENCE`; `harness.external_pool.EXTERNAL_ANCHORS`; `harness.evolve.DEFAULT_ANCHORS`; `harness.cashflow.play`; `harness.triage.head_to_head_rate`, `_default_agents`; `harness.tournament.play_rewards`; `strategies.field_pace.HERD_RAMP_F`.
- Produces: `four_herders.FOURTH_HERDER`, `FOURTH_DAY`, `FourHerdersStrategy`, `STRATEGY`; `fourth_bench.pending_at`, `reading`, `mechanism_failures`, `off_class`, `arm_b_class`, `main`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_four_herders.py
"""four_herders (#289): the livestock seam gains a fourth worker from day 12, nothing else."""

from __future__ import annotations

from strategies import field_rival as fr
from strategies import four_herders as fh
from strategies.third_herder import HERDER_DAY, THIRD_HERDER
from strategies.ten_melon import TenMelonStrategy


def test_the_declared_knobs():
    assert (fh.FOURTH_HERDER, fh.FOURTH_DAY) == (7, 12)
    assert (HERDER_DAY, THIRD_HERDER) == (8, 6) and fr.LIVESTOCK_WORKERS == (1, 2)


def test_the_seam_by_day_and_nothing_else_overridden():
    from harness.sheep_bench import _seam_names
    assert set(fh.FourHerdersStrategy.__dict__) & set(_seam_names()) == {"livestock_workers"}
    p, q = fh.FourHerdersStrategy(), TenMelonStrategy()
    assert p.name == "four_herders" and isinstance(p, TenMelonStrategy)
    for day in (0, 5, 7):
        assert p.livestock_workers(day) is None and q.livestock_workers(day) is None
    for day in (8, 11):
        assert p.livestock_workers(day) == (1, 2, 6) == q.livestock_workers(day)
    for day in (12, 16, 29):
        assert p.livestock_workers(day) == (1, 2, 6, 7) and q.livestock_workers(day) == (1, 2, 6)
    assert p.CAPS == q.CAPS and p.herd_target(12) == q.herd_target(12) == 13


def test_registered():
    from strategies import load
    assert load("four_herders") is fh.FourHerdersStrategy
```

```python
# tests/test_fourth_bench.py
"""The four_herders experiment's declared constants and pure parts (#289)."""

from __future__ import annotations

import pytest

from harness import fourth_bench as fb
from strategies import field_pace as fp


def test_the_declared_constants():
    assert fb.CONTENDER == "four_herders" and fb.CHAMPION == "ten_melon" and fb.ARM_B == "from_eight"
    assert fb.SEEDS == tuple(range(1122, 1138)) and fb.CONTROL_SEED == 1122
    assert fb.CHAMPION_BAR == 0.60 and fb.ANCHOR_BAR == 0.90
    assert (fb.PLACED_DAY, fb.PLACED_BAR, fb.PENDING_DAYS, fb.PLANTED_DAY, fb.ARM_B_FROM) == (14, 12, (14, 20), 16, 8)
    assert fb.LONESPEAR.startswith("lonespear")


def test_the_seeds_are_fresh_against_every_range_already_spent():
    spent = set(range(100, 116)) | set(range(200, 216)) | set(range(300, 332)) \
        | set(range(400, 416)) | set(range(500, 516)) | set(range(600, 616)) \
        | set(range(700, 704)) | set(range(800, 960)) | set(range(960, 1122))
    assert not spent & set(fb.SEEDS)


def _slot(day, hour, shed, seat_player=0):
    return {"action": {"farmer": ["PASS"], "hands": [], "market": []},
            "observation": {"day": day, "hour": hour, "player": seat_player,
                            "farms": [{"money": 0, "tiles": []}, {"money": 0, "tiles": []}],
                            "private": {"shed": shed}},
            "reward": 0, "status": "ACTIVE"}


def test_pending_at_reads_the_last_observation_of_the_day():
    steps = [[_slot(14, 0, {"COW": 1}), _slot(14, 0, {"SHEEP": 9}, 1)],
             [_slot(14, 23, {"COW": 3, "SHEEP": 1, "WHEAT": 5}), _slot(14, 23, {}, 1)],
             [_slot(15, 0, {"COW": 0}), _slot(15, 0, {}, 1)]]
    assert fb.pending_at(steps, 0, 14) == 4 and fb.pending_at(steps, 1, 14) == 0
    assert fb.pending_at(steps, 0, 15) == 0 and fb.pending_at(steps, 0, 20) is None


def _board(n_animals, n_plants=0):
    return {"tiles": [[{"animal": "COW"}] * n_animals + [{"kind": "PLANT", "crop": "MELON"}] * n_plants]}


def test_reading_and_its_failure(monkeypatch):
    monkeypatch.setattr(fb, "board_on_day", lambda steps, seat, day: {14: _board(12), 16: _board(12, 44)}.get(day))
    monkeypatch.setattr(fb, "units_sold", lambda steps, seat: {"MILK": 207, "WOOL": 96})
    monkeypatch.setattr(fb, "pending_at", lambda steps, seat, day: {14: 4, 20: 4}[day])
    assert fb.reading("s", 0) == {"placed_14": 12, "milk": 207, "pending": {14: 4, 20: 4}, "planted_16": 44}
    monkeypatch.setattr(fb, "board_on_day", lambda steps, seat, day: None)
    with pytest.raises(ValueError):
        fb.reading("s", 0)


def test_mechanism_failures_name_the_bars():
    champ = {"placed_14": 11, "milk": 177, "pending": {14: 5, 20: 5}, "planted_16": 47}
    good = {"placed_14": 12, "milk": 207, "pending": {14: 4, 20: 4}, "planted_16": 44}
    assert fb.mechanism_failures(good, champ) == []
    assert fb.mechanism_failures({**good, "placed_14": 11}, champ) == ["placed_14"]
    assert fb.mechanism_failures({**good, "milk": 177}, champ) == ["milk"]
    assert fb.mechanism_failures({**good, "placed_14": 12}, {**champ, "placed_14": 13}) == ["placed_14"]


def test_the_identity_stub_switches_all_sixteen_seams_off_and_survives_a_turn():
    from harness.sheep_bench import _seam_names
    names = _seam_names()
    assert len(names) == 16
    cls = fb.off_class()
    for n in names:
        assert n in cls.__dict__, f"seam {n} not switched off"
    off = cls()
    assert off.livestock_workers(12) is None and off.herd_target(8) is None
    assert off.HERD_RAMP_F == fp.HERD_RAMP_F and off.CAPS == fb.load_reference().CAPS
    from kaggisim.state import parse
    from kaggle_environments import make
    env = make("kaggriculture", configuration={"seed": 1122, "episodeSteps": 3})
    out = off.act(parse(env.reset()[0].observation))
    assert set(out) >= {"farmer", "hands", "market"}


def test_arm_b_starts_on_day_eight_and_changes_nothing_else():
    from strategies.four_herders import FourHerdersStrategy
    b = fb.arm_b_class()()
    assert isinstance(b, FourHerdersStrategy) and b.FOURTH_DAY == 8
    assert b.livestock_workers(7) is None and b.livestock_workers(8) == (1, 2, 6, 7)
```

- [ ] **Step 2: Run the tests and observe them fail**

Run: `.venv/bin/python -m pytest tests/test_four_herders.py tests/test_fourth_bench.py -q`
Expected: two collection errors. Quote them.

- [ ] **Step 3: Write `strategies/four_herders.py`**

```python
"""four_herders: ten_melon with a fourth herder from day 12 (#289).

#288 mined 102 rated games: opponents with twelve head by day 8 beat us 11
of 12, and our own herd ends every game at eleven placed with four animals
standing in the shed from day 12 on. payday_herd's ramp asks thirteen; the
herd block counts shed animals as pending and stops buying; the three
herders are saturated at eleven head and the per-herder scan never reaches
the tiles at the back of the block. A fourth herder from day 12 placed a
twelfth head and won 8/8 probe games, milk 171-177 -> 204-210.

One decision changes: from FOURTH_DAY, worker FOURTH_HERDER herds too (the
`livestock_workers` seam). It gives up its crop cluster, as third_herder's
did. Everything else is ten_melon's.

Declared before measurement: FOURTH_HERDER and FOURTH_DAY, and the controls
and criterion in `harness/fourth_bench.py` (posted to #289 before any code).
"""

from __future__ import annotations

from strategies import field_rival as fr
from strategies.ten_melon import TenMelonStrategy

#: The worker that joins the livestock line, and the day it does.
FOURTH_HERDER = 7
FOURTH_DAY = 12


class FourHerdersStrategy(TenMelonStrategy):
    """`ten_melon` with a fourth herder from day twelve."""

    name = "four_herders"
    benchmark = False
    FOURTH_HERDER = FOURTH_HERDER
    FOURTH_DAY = FOURTH_DAY

    def livestock_workers(self, day):
        """The parent's answer -- None before day 8, the trio from 8 -- with
        the fourth worker appended from FOURTH_DAY."""
        base = super().livestock_workers(day)
        if day < self.FOURTH_DAY:
            return base
        return tuple(base or fr.LIVESTOCK_WORKERS) + (self.FOURTH_HERDER,)


STRATEGY = FourHerdersStrategy
```

- [ ] **Step 4: Write `harness/fourth_bench.py`**

```python
"""The four_herders experiment (#289): controls, criterion, arm B.

Declared on #289 before any code. Controls first -- identity (every seam off,
sixteen of them, is the frozen benchmark to the value) and mechanism (placed
head at day 14 at least PLACED_BAR and at least the champion's, milk units
above the champion's, both sides of one game); a failed control is a VOID run
(exit 2). Then rival_bench's criterion. Arm B (`from_eight`) is recorded,
never gated. Animals pending in the shed and the day-16 planted count are
printed, never gated.

    .venv/bin/python -m harness.fourth_bench --controls
    .venv/bin/python -m harness.fourth_bench --criterion
    .venv/bin/python -m harness.fourth_bench --recorded
"""

from __future__ import annotations

import argparse
import os

from harness.cashflow import play  # noqa: F401  -- pinned by the tests
from harness.episode_analysis import _slot
from harness.evolve import DEFAULT_ANCHORS
from harness.external_pool import EXTERNAL_ANCHORS
from harness.farm_census import animals_placed, planted_by_crop
from harness.feed_bench import board_on_day
from harness.fert_bench import units_sold
from harness.reserve_bench import MADHUR, PILKWANG, REFERENCE  # noqa: F401  -- pinned by the tests
from harness.rival_bench import (  # noqa: F401  -- pinned by the tests to rival_bench's own
    criterion,
    format_external,
    format_rows,
    paired_external_rows,
)
from harness.sheep_bench import _seam_names
from strategies import field_pace as fp

CONTENDER = "four_herders"
CHAMPION = "ten_melon"
SEEDS = tuple(range(1122, 1138))
CONTROL_SEED = 1122
CHAMPION_BAR = 0.60
ANCHOR_BAR = 0.90
PLACED_DAY = 14
PLACED_BAR = 12
PENDING_DAYS = (14, 20)
PLANTED_DAY = 16
ARM_B = "from_eight"
ARM_B_FROM = 8
LONESPEAR = EXTERNAL_ANCHORS[1]
assert LONESPEAR.startswith("lonespear"), LONESPEAR


def load_reference():
    from strategies import load
    return load(REFERENCE)


def pending_at(steps, seat, day):
    """COW + SHEEP in the seat's shed on the last observation of `day`; None if unreached."""
    pending = None
    for t in range(len(steps)):
        obs = (_slot(steps, t, seat) or {}).get("observation") or {}
        if obs.get("day") != day:
            continue
        shed = (obs.get("private") or {}).get("shed") or {}
        pending = int(shed.get("COW", 0) or 0) + int(shed.get("SHEEP", 0) or 0)
    return pending


def reading(steps, seat) -> dict:
    b14 = board_on_day(steps, seat, PLACED_DAY)
    if b14 is None:
        raise ValueError(f"no board for day {PLACED_DAY}: the game ended early")
    b16 = board_on_day(steps, seat, PLANTED_DAY)
    return {"placed_14": sum(animals_placed(b14["tiles"]).values()),
            "milk": units_sold(steps, seat).get("MILK", 0),
            "pending": {d: pending_at(steps, seat, d) for d in PENDING_DAYS},
            "planted_16": None if b16 is None else sum(planted_by_crop(b16["tiles"]).values())}


def mechanism_failures(contender, champion) -> list:
    failed = []
    if contender["placed_14"] < PLACED_BAR or contender["placed_14"] < champion["placed_14"]:
        failed.append("placed_14")
    if contender["milk"] <= champion["milk"]:
        failed.append("milk")
    return failed


def off_class():
    """Every seam off (sixteen), the reference's caps, and the frozen herd ramp."""
    from strategies import load
    body = {n: (lambda self, *a, **k: None) for n in _seam_names()}
    body["CAPS"] = load_reference().CAPS
    body["HERD_RAMP_F"] = fp.HERD_RAMP_F
    return type("Off", (load(CONTENDER),), body)


def arm_b_class():
    """`four_herders` with the fourth herder from day eight. Never registered."""
    from strategies import load
    return type("FromEight", (load(CONTENDER),), {"FOURTH_DAY": ARM_B_FROM})


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
    ap = argparse.ArgumentParser(description="four_herders: a fourth herder from day 12")
    ap.add_argument("--controls", action="store_true")
    ap.add_argument("--criterion", action="store_true")
    ap.add_argument("--recorded", action="store_true", help="arm B (recorded, not gated)")
    args = ap.parse_args(argv)

    if args.recorded:
        print(format_rows(run_recorded()))
        print(f"recorded, not gated: arm B ({ARM_B}: the fourth herder from day {ARM_B_FROM}) vs {CHAMPION}")
        return 0

    do_controls = args.controls or not args.criterion
    do_criterion = args.criterion or not args.controls

    if do_controls:
        ctl = run_controls()
        print(f"control identity: {'OK' if ctl['identity']['ok'] else 'FAIL -- RUN VOID'}  {ctl['identity']}")
        c, b = ctl["mechanism"]["contender"], ctl["mechanism"]["champion"]
        print(f"control mechanism: {'OK' if ctl['mechanism']['ok'] else 'FAIL -- RUN VOID'}  "
              f"(declared: placed at day {PLACED_DAY} >= {PLACED_BAR} and >= champion's, milk > champion's)  "
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

Run: `.venv/bin/python -m pytest tests/test_four_herders.py tests/test_fourth_bench.py tests/test_melon_bench.py -q`
Expected: all PASS.

- [ ] **Step 6: Smoke the controls once (blocking, ~10 s), then commit**

Run: `.venv/bin/python -m harness.fourth_bench --controls`; both control lines verbatim in the report. Identity FAIL → STOP, BLOCKED. Mechanism FAIL → commit anyway, DONE_WITH_CONCERNS with the reading; never tune.

```bash
git add strategies/four_herders.py harness/fourth_bench.py tests/test_four_herders.py tests/test_fourth_bench.py
git commit -m "feat(#289): four_herders — a fourth herder from day 12 on ten_melon, and its declared bench

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```
