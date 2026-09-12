# payday_herd (#274) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The `payday_herd` contender and its declared bench, exactly as `docs/superpowers/specs/2026-09-12-payday-herd-design.md` and the declaration on #274.

**Architecture:** One strategy file setting one class attribute on `lean_feed`; one bench in the shape of `harness/fed_bench.py`, reusing its census helpers.

**Tech Stack:** Python 3.12, `.venv/bin/python`, pytest.

## Global Constraints
- Pure TDD: failing tests first, RUN and observe, then the code; the report quotes the red.
- Never edit any existing file.
- `.venv/bin/python` only; every command blocking; do NOT run the full suite (the controller does) — only the targeted tests and the ~10 s controls smoke.
- Stage by explicit path; never `git add -A`; never stage `.venv`, `external_agents`, `replays/`.
- Declared values verbatim: `HERD_RAMP_P = ((0, 4), (6, 8), (12, 13))`; `CONTENDER = "payday_herd"`, `CHAMPION = "lean_feed"`, `SEEDS = tuple(range(1040, 1056))`, `CONTROL_SEED = 1040`, `CHAMPION_BAR = 0.60`, `ANCHOR_BAR = 0.90`, `CENSUS_DAYS = range(0, 17)`, `HEAD_LOST_BAR = 0`, `CREW_DAY = 10`, `CREW_BAR = 10`, `HEAD_DAY = 16`, `ARM_B = "hold6"`, `HOLD6_RAMP = ((0, 4), (6, 6), (12, 13))`.

---

### Task 1: The contender and the bench

**Files:**
- Create: `strategies/payday_herd.py`, `harness/payday_bench.py`
- Test: `tests/test_payday_herd.py`, `tests/test_payday_bench.py`

**Interfaces:**
- Consumes: `strategies.lean_feed.LeanFeedStrategy`; `strategies.field_pace` (`HERD_RAMP_F`, `FieldPaceStrategy.LEAD_TILES`, `PASTURE_BLOCK_F`); `harness.fed_bench.head_by_day(steps, seat, days)`, `head_lost(heads)`, `census_summary(games)`; `harness.feed_bench.board_on_day`, `hands_on_day(steps, seat, day)`; `harness.sheep_bench._seam_names()`; `harness.rival_bench.criterion / format_rows / format_external / paired_external_rows`; `harness.reserve_bench.MADHUR, PILKWANG, REFERENCE`; `harness.evolve.DEFAULT_ANCHORS`; `harness.cashflow.play`; `harness.triage.head_to_head_rate`, `_default_agents`; `harness.tournament.play_rewards`; `kaggle_environments.make`.
- Produces: `payday_herd.HERD_RAMP_P`, `PaydayHerdStrategy`, `STRATEGY`; `payday_bench.reading`, `mechanism_failures`, `off_class`, `arm_b_class`, `run_census`, `main`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_payday_herd.py
"""payday_herd (#274): one ramp step moved to payday, nothing else."""

from __future__ import annotations

from strategies import field_pace as fp
from strategies import field_rival as fr
from strategies import payday_herd as ph
from strategies.lean_feed import LeanFeedStrategy


def test_the_ramp_is_lean_feeds_with_the_last_step_on_day_12():
    assert ph.HERD_RAMP_P == ((0, 4), (6, 8), (12, 13))
    assert fp.HERD_RAMP_F == ((0, 4), (6, 8), (8, 13))
    assert ph.PaydayHerdStrategy.HERD_RAMP_F == ph.HERD_RAMP_P


def test_no_seam_is_overridden_and_the_targets_follow_the_ramp():
    from harness.sheep_bench import _seam_names
    assert set(ph.PaydayHerdStrategy.__dict__) & set(_seam_names()) == set()
    p, q = ph.PaydayHerdStrategy(), LeanFeedStrategy()
    assert p.name == "payday_herd" and isinstance(p, LeanFeedStrategy)
    assert [p.herd_target(d) for d in (0, 6, 8, 11, 12, 16)] == [4, 8, 8, 8, 13, 13]
    assert [q.herd_target(d) for d in (0, 6, 8, 11, 12, 16)] == [4, 8, 13, 13, 13, 13]
    assert p.herd_target(24) == max(13, fr.animal_target(24))
    assert p.pasture_count(8, 8) == min(len(fp.PASTURE_BLOCK_F), max(8 + p.LEAD_TILES, 8))
    assert p.pasture_count(12, 8) == min(len(fp.PASTURE_BLOCK_F), 13)
    assert p.feed_stock(animals=9) == q.feed_stock(animals=9) and p.buy_order() == q.buy_order()


def test_registered():
    from strategies import load
    assert load("payday_herd") is ph.PaydayHerdStrategy
```

```python
# tests/test_payday_bench.py
"""The payday_herd experiment's declared constants and pure parts (#274)."""

from __future__ import annotations

import pytest

from harness import payday_bench as pb
from strategies import field_pace as fp


def test_the_declared_constants():
    assert pb.CONTENDER == "payday_herd" and pb.CHAMPION == "lean_feed" and pb.ARM_B == "hold6"
    assert pb.SEEDS == tuple(range(1040, 1056)) and pb.CONTROL_SEED == 1040
    assert pb.CHAMPION_BAR == 0.60 and pb.ANCHOR_BAR == 0.90
    assert list(pb.CENSUS_DAYS) == list(range(0, 17)) and pb.HEAD_LOST_BAR == 0
    assert (pb.CREW_DAY, pb.CREW_BAR, pb.HEAD_DAY) == (10, 10, 16)
    assert pb.HOLD6_RAMP == ((0, 4), (6, 6), (12, 13))


def test_the_seeds_are_fresh_against_every_range_already_spent():
    spent = set(range(100, 116)) | set(range(200, 216)) | set(range(300, 332)) \
        | set(range(400, 416)) | set(range(500, 516)) | set(range(600, 616)) \
        | set(range(700, 704)) | set(range(800, 960)) | set(range(960, 1040))
    assert not spent & set(pb.SEEDS)


def _board(n):
    return {"tiles": [[{"animal": "COW"}] * n]}


def test_reading_and_its_failure(monkeypatch):
    heads = {d: (4 if d < 6 else 8 if d < 12 else 13) for d in range(0, 17)}
    monkeypatch.setattr(pb, "board_on_day", lambda steps, seat, day: _board(heads[day]))
    monkeypatch.setattr(pb, "hands_on_day", lambda steps, seat, day: {10: 10}.get(day, 6))
    r = pb.reading("s", 0)
    assert r["lost"] == 0 and r["hands_10"] == 10 and r["head_16"] == 13 and len(r["heads"]) == 17
    monkeypatch.setattr(pb, "board_on_day", lambda steps, seat, day: None if day >= 16 else _board(4))
    with pytest.raises(ValueError):
        pb.reading("s", 0)


def test_mechanism_failures_name_the_bars():
    champ = {"lost": 3, "hands_10": 6, "head_16": 11}
    assert pb.mechanism_failures({"lost": 0, "hands_10": 10, "head_16": 11}, champ) == []
    assert pb.mechanism_failures({"lost": 1, "hands_10": 10, "head_16": 11}, champ) == ["lost"]
    assert pb.mechanism_failures({"lost": 0, "hands_10": 9, "head_16": 10}, champ) == ["hands_10", "head_16"]


def test_the_identity_stub_switches_every_seam_off_resets_the_ramp_and_survives_a_turn():
    from harness.sheep_bench import _seam_names
    cls = pb.off_class()
    for n in _seam_names():
        assert n in cls.__dict__, f"seam {n} not switched off"
    off = cls()
    assert off.herd_target(8) is None and off.pasture_count(8, 8) is None and off.layout() is None
    assert off.HERD_RAMP_F == fp.HERD_RAMP_F and off.CAPS == pb.load_reference().CAPS
    from kaggisim.state import parse
    from kaggle_environments import make
    env = make("kaggriculture", configuration={"seed": 1040, "episodeSteps": 3})
    out = off.act(parse(env.reset()[0].observation))
    assert set(out) >= {"farmer", "hands", "market"}


def test_arm_b_holds_at_six_and_changes_nothing_else():
    from harness.sheep_bench import _seam_names
    from strategies.lean_feed import LeanFeedStrategy
    cls = pb.arm_b_class()
    b = cls()
    assert isinstance(b, LeanFeedStrategy) and b.HERD_RAMP_F == pb.HOLD6_RAMP
    assert set(cls.__dict__) & set(_seam_names()) == set()
    assert [b.herd_target(d) for d in (6, 11, 12)] == [6, 6, 13]
```

- [ ] **Step 2: Run the tests and observe them fail**

Run: `.venv/bin/python -m pytest tests/test_payday_herd.py tests/test_payday_bench.py -q`
Expected: two collection errors. Quote them.

- [ ] **Step 3: Write `strategies/payday_herd.py`**

```python
"""payday_herd: lean_feed's herd waits for payday (#274).

#270 named the mechanism behind lean_feed's escapes in 24 of 47 ladder games:
on days 7-11 dawn cash is 0-30, the crew is five or six hands, feed cannot be
topped up, and the herd bought on days 6-10 for 6,400 starves. A cash floor
and a delayed tenth hand are byte-identical to lean_feed on the probe seeds;
moving the herd's 13-head step from day 8 to day 12 -- the melon payday --
gave zero escapes, ten hands by day 9-10 and 2/2 wins.

One knob changes: `HERD_RAMP_F`'s last step is day 12, not day 8.
`field_pace.herd_target` and `pasture_count` read the attribute; no method
is overridden and everything else is lean_feed's.

Declared before measurement: `HERD_RAMP_P`, and the controls and criterion
in `harness/payday_bench.py` (posted to #274 before any code).
"""

from __future__ import annotations

from strategies.lean_feed import LeanFeedStrategy

#: lean_feed's herd ramp with the 13-head step on the payday.
HERD_RAMP_P = ((0, 4), (6, 8), (12, 13))


class PaydayHerdStrategy(LeanFeedStrategy):
    """`lean_feed` with the herd's last step on day 12."""

    name = "payday_herd"
    benchmark = False
    HERD_RAMP_F = HERD_RAMP_P


STRATEGY = PaydayHerdStrategy
```

- [ ] **Step 4: Write `harness/payday_bench.py`**

```python
"""The payday_herd experiment (#274): controls, criterion, census and arm B.

Declared on #274 before any code. Controls first -- identity (every seam off
and the frozen ramp is the frozen benchmark to the value) and mechanism (no
head lost over days 0-16, ten hands on day 10, at least the champion's head
at day 16, both sides of one game); a failed control is a VOID run (exit 2).
Then rival_bench's criterion. `--recorded` plays the escape census and arm B
(`hold6`: the herd held at six until day 12); neither is gated.

    .venv/bin/python -m harness.payday_bench --controls
    .venv/bin/python -m harness.payday_bench --criterion
    .venv/bin/python -m harness.payday_bench --recorded
"""

from __future__ import annotations

import argparse
import os

from harness.cashflow import play  # noqa: F401  -- pinned by the tests
from harness.evolve import DEFAULT_ANCHORS
from harness.fed_bench import census_summary, head_by_day, head_lost
from harness.feed_bench import board_on_day, hands_on_day  # noqa: F401  -- board_on_day pinned by the tests
from harness.reserve_bench import MADHUR, PILKWANG, REFERENCE  # noqa: F401  -- pinned by the tests
from harness.rival_bench import (  # noqa: F401  -- pinned by the tests to rival_bench's own
    criterion,
    format_external,
    format_rows,
    paired_external_rows,
)
from harness.sheep_bench import _seam_names
from strategies import field_pace as fp

CONTENDER = "payday_herd"
CHAMPION = "lean_feed"
SEEDS = tuple(range(1040, 1056))
CONTROL_SEED = 1040
CHAMPION_BAR = 0.60
ANCHOR_BAR = 0.90
CENSUS_DAYS = range(0, 17)
HEAD_LOST_BAR = 0
CREW_DAY = 10
CREW_BAR = 10
HEAD_DAY = 16
ARM_B = "hold6"
HOLD6_RAMP = ((0, 4), (6, 6), (12, 13))


def load_reference():
    from strategies import load
    return load(REFERENCE)


def reading(steps, seat) -> dict:
    """One side's head lost over the census days, crew on CREW_DAY, head at HEAD_DAY."""
    heads = head_by_day(steps, seat, CENSUS_DAYS)
    idx = list(CENSUS_DAYS).index(HEAD_DAY)
    if heads[idx] is None:
        raise ValueError(f"no board for day {HEAD_DAY}: the game ended early")
    return {"lost": head_lost(heads), "hands_10": hands_on_day(steps, seat, CREW_DAY),
            "head_16": heads[idx], "heads": heads}


def mechanism_failures(contender, champion) -> list:
    failed = []
    if contender["lost"] > HEAD_LOST_BAR:
        failed.append("lost")
    if (contender["hands_10"] or 0) < CREW_BAR:
        failed.append("hands_10")
    if contender["head_16"] < champion["head_16"]:
        failed.append("head_16")
    return failed


def off_class():
    """Every seam off, the reference's caps, and the frozen ramp."""
    from strategies import load
    body = {n: (lambda self, *a, **k: None) for n in _seam_names()}
    body["CAPS"] = load_reference().CAPS
    body["HERD_RAMP_F"] = fp.HERD_RAMP_F
    return type("Off", (load(CONTENDER),), body)


def arm_b_class():
    """`lean_feed` held at six head until day 12. Never registered."""
    from strategies import load
    return type("Hold6", (load(CHAMPION),), {"HERD_RAMP_F": HOLD6_RAMP})


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


def run_census(seeds=SEEDS):  # pragma: no cover
    """Contender vs champion on the seeds, contender seat 0 on even list positions."""
    os.environ.setdefault("ROBRICULTURE_STRICT", "1")
    from kaggle_environments import make
    from kaggisim.strategy import make_agent
    from strategies import load
    games = []
    for i, seed in enumerate(seeds):
        seat = i % 2
        pair = [make_agent(load(CONTENDER)()), make_agent(load(CHAMPION)())]
        if seat == 1:
            pair.reverse()
        env = make("kaggriculture", configuration={"seed": seed, "episodeSteps": 720})
        env.run(pair)
        games.append({"seed": seed, "seat": seat,
                      "contender_lost": head_lost(head_by_day(env.steps, seat, CENSUS_DAYS)),
                      "champion_lost": head_lost(head_by_day(env.steps, 1 - seat, CENSUS_DAYS))})
    return games


def run_recorded(seeds=SEEDS):  # pragma: no cover
    os.environ.setdefault("ROBRICULTURE_STRICT", "1")
    from harness.triage import head_to_head_rate
    return run_census(seeds), [head_to_head_rate(ARM_B, CHAMPION, seeds, agents=_arm_b_agents(ARM_B))]


def main(argv=None):  # pragma: no cover
    os.environ.setdefault("ROBRICULTURE_STRICT", "1")
    ap = argparse.ArgumentParser(description="payday_herd: the herd waits for payday")
    ap.add_argument("--controls", action="store_true")
    ap.add_argument("--criterion", action="store_true")
    ap.add_argument("--recorded", action="store_true", help="escape census + arm B (recorded, not gated)")
    args = ap.parse_args(argv)

    if args.recorded:
        games, rows = run_recorded()
        print("escape census (seed, contender seat, contender lost, champion lost): "
              + str([(g["seed"], g["seat"], g["contender_lost"], g["champion_lost"]) for g in games]))
        print(f"census summary: {census_summary(games)}")
        print(format_rows(rows))
        print(f"recorded, not gated: arm B ({ARM_B}: lean_feed held at six head until day 12) vs {CHAMPION}")
        return 0

    do_controls = args.controls or not args.criterion
    do_criterion = args.criterion or not args.controls

    if do_controls:
        ctl = run_controls()
        print(f"control identity: {'OK' if ctl['identity']['ok'] else 'FAIL -- RUN VOID'}  {ctl['identity']}")
        c, b = ctl["mechanism"]["contender"], ctl["mechanism"]["champion"]
        print(f"control mechanism: {'OK' if ctl['mechanism']['ok'] else 'FAIL -- RUN VOID'}  "
              f"(declared: head lost days 0-16 <= {HEAD_LOST_BAR}, hands on day {CREW_DAY} >= {CREW_BAR}, "
              f"head at day {HEAD_DAY} >= lean_feed's)  contender lost {c['lost']} hands_10 {c['hands_10']} "
              f"head_16 {c['head_16']} heads {c['heads']}  lean_feed lost {b['lost']} hands_10 {b['hands_10']} "
              f"head_16 {b['head_16']} heads {b['heads']}  failed={ctl['mechanism']['failed'] or 'none'}")
        if not all(r["ok"] for r in ctl.values()):
            print("a control failed: the run is VOID and the recorded arms are NOT scored")
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

- [ ] **Step 5: Run the targeted tests and observe them pass**

Run: `.venv/bin/python -m pytest tests/test_payday_herd.py tests/test_payday_bench.py tests/test_fed_bench.py tests/test_lean_feed.py -q`
Expected: all PASS.

- [ ] **Step 6: Smoke the controls once (blocking, ~10 s), then commit**

Run: `.venv/bin/python -m harness.payday_bench --controls`; both control lines verbatim in the report. Identity FAIL → STOP, BLOCKED. Mechanism FAIL → commit anyway, DONE_WITH_CONCERNS with the reading; never tune.

```bash
git add strategies/payday_herd.py harness/payday_bench.py tests/test_payday_herd.py tests/test_payday_bench.py
git commit -m "feat(#274): payday_herd — the herd's 13-head step on day 12, and its declared bench

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```
