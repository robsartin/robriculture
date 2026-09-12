# sheep_first (#268) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The `sheep_first` contender and its declared bench, exactly as `docs/superpowers/specs/2026-09-12-sheep-first-design.md` and the declaration on #268.

**Architecture:** One strategy file on top of `lean_feed` overriding one seam; one bench in the shape of `harness/feed_bench.py` (controls → criterion → arm B).

**Tech Stack:** Python 3.12, `.venv/bin/python`, pytest.

## Global Constraints
- Pure TDD: failing test first, RUN it and observe the failure, then the code; the report quotes the red.
- Never edit `strategies/field_rival.py`, `strategies/lean_feed.py`, `harness/feed_bench.py`, `harness/rival_bench.py`, `harness/reserve_bench.py`.
- `.venv/bin/python` only; every command blocking; full suite (~5 min) green before each commit.
- Stage by explicit path; never `git add -A`; never stage `.venv`, `external_agents`, `replays/`.
- Declared values verbatim: `SHEEP_TARGET = 6`; bench `CONTENDER = "sheep_first"`, `CHAMPION = "lean_feed"`, `SEEDS = tuple(range(992, 1008))`, `CONTROL_SEED = 992`, `CHAMPION_BAR = 0.60`, `ANCHOR_BAR = 0.90`, `SHEEP_DAY = 8`, `SHEEP_BAR = 4`, `SHEEP_DAY_16 = 16`, `SHEEP_BAR_16 = 6`, `ARM_B = "drop_rule"`, `LONESPEAR = "lonespear_kaggriculture_v21"`.
- The tests never play a full game; the bench does.

---

### Task 1: The contender and the bench

**Files:**
- Create: `strategies/sheep_first.py`, `harness/sheep_bench.py`
- Test: `tests/test_sheep_first.py`, `tests/test_sheep_bench.py`

**Interfaces:**
- Consumes: `strategies.lean_feed.LeanFeedStrategy`; `strategies.field_rival.FieldRivalStrategy` (seam names: `herd_preference, pasture_count, herd_target, livestock_workers, layout, land_target, hire_target, capital_reserve, pivot_day, cluster_size, buy_order, spend_floor, feed_carry, feed_stock`); `harness.feed_bench.board_on_day(steps, player, day)`; `harness.farm_census.animals_placed(tiles)`; `harness.episode_analysis.decompose(steps, player)`; `harness.rival_bench.criterion / format_rows / format_external / paired_external_rows`; `harness.reserve_bench.MADHUR, PILKWANG, REFERENCE`; `harness.evolve.DEFAULT_ANCHORS`; `harness.cashflow.play(name, opponent, seed)` (returns steps; name seat 0); `harness.triage.head_to_head_rate(name, opponent, seeds, agents=None)` and `harness.triage._default_agents`.
- Produces: `sheep_first.our_sheep(tiles, shed) -> int`, `SheepFirstStrategy`, `STRATEGY`; `sheep_bench.sheep_reading(steps, seat) -> dict`, `mechanism_failures(contender, champion) -> list`, `off_class()`, `arm_b_class()`, `main(argv)`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_sheep_first.py
"""sheep_first (#268): the sheep count and the one seam it drives."""

from __future__ import annotations

from strategies import field_rival as fr
from strategies import sheep_first as sf
from strategies.lean_feed import LeanFeedStrategy


def _tiles(*animals):
    row = [{"animal": a} if a else None for a in animals]
    return [row + ["LOCKED", {"kind": "WEED"}]]


def test_our_sheep_counts_placed_and_pending_sheep_only():
    assert sf.our_sheep(_tiles("SHEEP", "SHEEP", "COW", None), {"SHEEP": 2, "COW": 5}) == 4
    assert sf.our_sheep(_tiles("COW"), {}) == 0
    assert sf.our_sheep([], None) == 0


def _obs(*animals, shed=None):
    return {"player": 1, "farms": [{"tiles": [[{"animal": "SHEEP"}] * 9]}, {"tiles": _tiles(*animals)}],
            "private": {"shed": shed or {}}}


def test_herd_preference_is_sheep_until_six_then_cow_and_never_reads_the_rival():
    p = sf.SheepFirstStrategy()
    assert p.name == "sheep_first" and sf.SHEEP_TARGET == 6 and isinstance(p, LeanFeedStrategy)
    assert p.herd_preference(_obs("SHEEP", "SHEEP", "SHEEP", "COW", shed={"SHEEP": 2})) == "SHEEP"   # 5
    assert p.herd_preference(_obs("SHEEP", "SHEEP", "SHEEP", "COW", shed={"SHEEP": 3})) == "COW"     # 6
    assert p.herd_preference(_obs("SHEEP", "SHEEP", "SHEEP", "SHEEP", "SHEEP", "SHEEP", "SHEEP")) == "COW"
    # the rival's nine sheep in farm 0 change nothing: the rule reads only our farm


def test_herd_preference_degrades_to_sheep_on_a_malformed_observation():
    p = sf.SheepFirstStrategy()
    assert p.herd_preference({}) == "SHEEP"
    assert p.herd_preference({"player": 3, "farms": [], "private": None}) == "SHEEP"


def test_every_other_seam_is_lean_feeds():
    p, q = sf.SheepFirstStrategy(), LeanFeedStrategy()
    for day in (0, 6, 8, 12, 16):
        assert p.herd_target(day) == q.herd_target(day) and p.hire_target(day) == q.hire_target(day)
    assert p.buy_order() == q.buy_order() and p.feed_carry(8, 3) == q.feed_carry(8, 3) and p.layout() == q.layout()
    assert fr.FieldRivalStrategy.herd_preference(p, {}) is None


def test_registered():
    from strategies import load
    assert load("sheep_first") is sf.SheepFirstStrategy
```

```python
# tests/test_sheep_bench.py
"""The sheep_first experiment's declared constants and pure parts (#268)."""

from __future__ import annotations

from harness import sheep_bench as sb
from strategies import field_rival as fr


def test_the_declared_constants():
    assert sb.CONTENDER == "sheep_first" and sb.CHAMPION == "lean_feed"
    assert sb.SEEDS == tuple(range(992, 1008)) and sb.CONTROL_SEED == 992
    assert sb.CHAMPION_BAR == 0.60 and sb.ANCHOR_BAR == 0.90 and sb.ARM_B == "drop_rule"
    assert (sb.SHEEP_DAY, sb.SHEEP_BAR, sb.SHEEP_DAY_16, sb.SHEEP_BAR_16) == (8, 4, 16, 6)
    assert sb.LONESPEAR == "lonespear_kaggriculture_v21" and sb.PILKWANG.startswith("pilkwang")


def test_the_seeds_are_fresh_against_every_range_already_spent():
    spent = set(range(100, 116)) | set(range(200, 216)) | set(range(300, 332)) \
        | set(range(400, 416)) | set(range(500, 516)) | set(range(600, 616)) \
        | set(range(700, 704)) | set(range(800, 960)) | set(range(960, 992))
    assert not spent & set(sb.SEEDS)


def _tile(animal=None):
    return {"animal": animal} if animal else {"kind": "WEED"}


def test_sheep_reading_reads_the_boards_and_the_revenue(monkeypatch):
    boards = {8: {"tiles": [[_tile("SHEEP"), _tile("SHEEP"), _tile("COW"), _tile()]]},
              16: {"tiles": [[_tile("SHEEP")] * 6 + [_tile("COW")] * 5]}}
    monkeypatch.setattr(sb, "board_on_day", lambda steps, seat, day: boards[day])
    monkeypatch.setattr(sb, "decompose", lambda steps, seat: {"revenue": {"WOOL": 21000, "MILK": 30000}, "spend": {}, "actions": {}, "final_money": 0, "residual": 0})
    assert sb.sheep_reading("steps", 0) == {"sheep_8": 2, "sheep_16": 6, "cows_16": 5, "wool": 21000, "milk": 30000}


def test_sheep_reading_raises_when_a_declared_day_was_never_reached(monkeypatch):
    monkeypatch.setattr(sb, "board_on_day", lambda steps, seat, day: None)
    import pytest
    with pytest.raises(ValueError):
        sb.sheep_reading("steps", 0)


def test_mechanism_failures_name_the_bars():
    good = {"sheep_8": 4, "sheep_16": 6, "cows_16": 5, "wool": 25000, "milk": 1}
    champ = {"sheep_8": 3, "sheep_16": 3, "cows_16": 8, "wool": 12000, "milk": 1}
    assert sb.mechanism_failures(good, champ) == []
    assert sb.mechanism_failures({**good, "sheep_8": 3}, champ) == ["sheep_8"]
    assert sb.mechanism_failures({**good, "sheep_16": 5, "wool": 12000}, champ) == ["sheep_16", "wool"]


def test_the_identity_stub_switches_every_seam_off_and_survives_a_turn():
    seams = [n for n in dir(fr.FieldRivalStrategy)
             if callable(getattr(fr.FieldRivalStrategy, n)) and not n.startswith("_") and n != "act"
             and getattr(fr.FieldRivalStrategy, n).__doc__ and "seam" in getattr(fr.FieldRivalStrategy, n).__doc__.lower()]
    cls = sb.off_class()
    off = cls()
    for n in seams:
        assert n in cls.__dict__, f"seam {n} not switched off"
    assert off.herd_preference({}) is None and off.feed_stock(4) is None and off.layout() is None
    assert off.CAPS == sb.load_reference().CAPS
    from kaggisim.state import parse
    from kaggle_environments import make
    env = make("kaggriculture", configuration={"seed": 992, "episodeSteps": 3})
    obs = env.reset()[0].observation
    out = off.act(parse(obs))
    assert set(out) >= {"farmer", "hands", "market"}


def test_arm_b_drops_the_rule_and_nothing_else():
    cls = sb.arm_b_class()
    b = cls()
    from strategies.lean_feed import LeanFeedStrategy
    assert isinstance(b, LeanFeedStrategy) and b.herd_preference({"player": 0, "farms": [{"tiles": [[{"animal": "SHEEP"}] * 5}]}) is None
```

- [ ] **Step 2: Run the tests and observe them fail**

Run: `.venv/bin/python -m pytest tests/test_sheep_first.py tests/test_sheep_bench.py -q`
Expected: two collection errors (`strategies.sheep_first`, `harness.sheep_bench` missing). Quote them.

- [ ] **Step 3: Write `strategies/sheep_first.py`**

```python
"""sheep_first: lean_feed with six sheep, bought first (#268).

#266 mined lean_feed's 47 rated games: opponents with four or more sheep placed
by day 8 beat it 11 of 12; against everyone else it wins 20 of 35. The winners
run 8 cows + 6 sheep at day 16 to our 8 + 3 and sell 138 wool units to our 77,
and wool is the one product with a double-consumption shop. lean_feed inherits
rival_aware's rule (#219: cows once the rival has two sheep), which answers a
sheep farm with cows -- into the milk market that farm is also flooding.

One decision changes: the herd's composition. `herd_preference` asks for SHEEP
until six sheep are placed or pending, then COW, and never reads the rival. The
ramp, the buy order, the feed sizing and everything else are lean_feed's.

Declared before measurement: `SHEEP_TARGET`, and the controls and criterion in
`harness/sheep_bench.py` (posted to #268 before any code).
"""

from __future__ import annotations

from strategies.lean_feed import LeanFeedStrategy

#: Sheep to own before the herd goes back to cows.
SHEEP_TARGET = 6


def our_sheep(tiles, shed) -> int:
    """Sheep on our tiles plus sheep waiting in the shed to be walked out.
    Counting the pending ones is what stops the ramp's per-turn loop from
    ordering the whole target again every turn (the benchmark's `pending`)."""
    placed = sum(1 for row in (tiles or []) for t in row
                 if isinstance(t, dict) and t.get("animal") == "SHEEP")
    return placed + int((shed or {}).get("SHEEP", 0) or 0)


class SheepFirstStrategy(LeanFeedStrategy):
    """`lean_feed` with sheep bought first, to six."""

    name = "sheep_first"
    benchmark = False

    def herd_preference(self, obs):
        """SHEEP until `SHEEP_TARGET` are ours, then COW. Reads only our own
        farm; a malformed observation degrades to SHEEP (ADR-0006)."""
        try:
            me = obs["farms"][obs["player"]]
            shed = (obs.get("private") or {}).get("shed") or {}
            have = our_sheep(me.get("tiles"), shed)
        except (LookupError, TypeError, AttributeError):
            return "SHEEP"
        return "SHEEP" if have < SHEEP_TARGET else "COW"


STRATEGY = SheepFirstStrategy
```

- [ ] **Step 4: Write `harness/sheep_bench.py`**

```python
"""The sheep_first experiment (#268): controls, criterion, arm B.

Declared on #268 before any code. Controls first -- identity (every seam off
is the frozen benchmark to the value) and mechanism (four sheep by day 8, six
by day 16, more wool than lean_feed in the same game); a failed control is a
VOID run (exit 2). Then rival_bench's criterion against lean_feed, the anchors
and the paired externals; the lonespear and pilkwang pairs -- the archetype
this contender exists for -- are printed whatever the verdict. Arm B
(`drop_rule`: lean_feed with the rival-sheep rule removed and no sheep target)
is recorded, never gated.

    .venv/bin/python -m harness.sheep_bench --controls
    .venv/bin/python -m harness.sheep_bench --criterion
    .venv/bin/python -m harness.sheep_bench --recorded
"""

from __future__ import annotations

import argparse
import os

from harness.cashflow import play  # noqa: F401  -- pinned by the tests
from harness.episode_analysis import decompose
from harness.evolve import DEFAULT_ANCHORS
from harness.farm_census import animals_placed
from harness.feed_bench import board_on_day
from harness.reserve_bench import MADHUR, PILKWANG, REFERENCE  # noqa: F401  -- pinned by the tests
from harness.rival_bench import (  # noqa: F401  -- pinned by the tests to rival_bench's own
    criterion,
    format_external,
    format_rows,
    paired_external_rows,
)
from strategies import field_rival as fr

CONTENDER = "sheep_first"
CHAMPION = "lean_feed"
SEEDS = tuple(range(992, 1008))
CONTROL_SEED = 992
CHAMPION_BAR = 0.60
ANCHOR_BAR = 0.90
ARM_B = "drop_rule"
SHEEP_DAY = 8
SHEEP_BAR = 4
SHEEP_DAY_16 = 16
SHEEP_BAR_16 = 6
LONESPEAR = "lonespear_kaggriculture_v21"


def load_reference():
    from strategies import load
    return load(REFERENCE)


def sheep_reading(steps, seat) -> dict:
    """One side's sheep at day 8 and 16, cows at 16, and its wool and milk revenue."""
    boards = {d: board_on_day(steps, seat, d) for d in (SHEEP_DAY, SHEEP_DAY_16)}
    missing = [d for d, b in boards.items() if b is None]
    if missing:
        raise ValueError(f"no board for day {missing[0]}: the game ended early")
    a8 = animals_placed(boards[SHEEP_DAY]["tiles"])
    a16 = animals_placed(boards[SHEEP_DAY_16]["tiles"])
    rev = decompose(steps, seat)["revenue"]
    return {"sheep_8": a8.get("SHEEP", 0), "sheep_16": a16.get("SHEEP", 0), "cows_16": a16.get("COW", 0),
            "wool": rev.get("WOOL", 0), "milk": rev.get("MILK", 0)}


def mechanism_failures(contender, champion) -> list:
    """Control 2's bars; the names of the ones that did not hold."""
    failed = []
    if contender["sheep_8"] < SHEEP_BAR:
        failed.append("sheep_8")
    if contender["sheep_16"] < SHEEP_BAR_16:
        failed.append("sheep_16")
    if not contender["wool"] > champion["wool"]:
        failed.append("wool")
    return failed


def _seam_names():
    """Every seam on the frozen benchmark: a public method whose docstring says so."""
    return [n for n in dir(fr.FieldRivalStrategy)
            if callable(getattr(fr.FieldRivalStrategy, n)) and not n.startswith("_") and n != "act"
            and getattr(fr.FieldRivalStrategy, n).__doc__
            and "seam" in getattr(fr.FieldRivalStrategy, n).__doc__.lower()]


def off_class():
    """The identity control's subject: the contender with every seam switched
    off and the reference's caps. Derived from the seam list so a seam added
    after this bench was written cannot be left on."""
    from strategies import load
    body = {n: (lambda self, *a, **k: None) for n in _seam_names()}
    body["CAPS"] = load_reference().CAPS
    return type("Off", (load(CONTENDER),), body)


def arm_b_class():
    """`lean_feed` with the rival-sheep rule removed: the frozen mix, no target. Never registered."""
    from strategies import load
    return type("DropRule", (load(CHAMPION),), {"herd_preference": lambda self, obs: None})


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
    contender, champion = sheep_reading(steps, 0), sheep_reading(steps, 1)
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
    ap = argparse.ArgumentParser(description="sheep_first: six sheep, bought first")
    ap.add_argument("--controls", action="store_true")
    ap.add_argument("--criterion", action="store_true")
    ap.add_argument("--recorded", action="store_true", help="arm B (recorded, not gated)")
    args = ap.parse_args(argv)

    if args.recorded:
        print(format_rows(run_recorded()))
        print(f"recorded, not gated: arm B ({ARM_B}: lean_feed without the rival-sheep rule) vs {CHAMPION}")
        return 0

    do_controls = args.controls or not args.criterion
    do_criterion = args.criterion or not args.controls

    if do_controls:
        ctl = run_controls()
        print(f"control identity: {'OK' if ctl['identity']['ok'] else 'FAIL -- RUN VOID'}  {ctl['identity']}")
        c, b = ctl["mechanism"]["contender"], ctl["mechanism"]["champion"]
        print(f"control mechanism: {'OK' if ctl['mechanism']['ok'] else 'FAIL -- RUN VOID'}  "
              f"(declared: sheep at day {SHEEP_DAY} >= {SHEEP_BAR}, at day {SHEEP_DAY_16} >= {SHEEP_BAR_16}, "
              f"wool > lean_feed's)  contender {c}  lean_feed {b}  failed={ctl['mechanism']['failed'] or 'none'}")
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

If `criterion`'s returned dict does not carry `external` as a `{name: (contender_wins, champion_wins)}` map, read `harness/rival_bench.py:59-120` and `feed_bench.main` and use the same access `feed_bench` does — never change `rival_bench`.

- [ ] **Step 5: Run the tests and observe them pass**

Run: `.venv/bin/python -m pytest tests/test_sheep_first.py tests/test_sheep_bench.py tests/test_feed_bench.py tests/test_lean_feed.py -q`
Expected: all PASS. If `test_the_identity_stub_switches_every_seam_off_and_survives_a_turn` reports a seam not switched off, the seam-name derivation and the test's derivation must agree — fix the bench's `_seam_names`, not the test.

- [ ] **Step 6: Smoke the controls once (blocking, ~10 s), then full suite, then commit**

Run: `.venv/bin/python -m harness.sheep_bench --controls` and put both control lines in the report verbatim. If identity FAILS, STOP and report BLOCKED. If mechanism FAILS, do not tune anything: commit as is and report DONE_WITH_CONCERNS quoting the reading (the controller decides).

Run: `.venv/bin/python -m pytest -q` (blocking, ~5 min).

```bash
git add strategies/sheep_first.py harness/sheep_bench.py tests/test_sheep_first.py tests/test_sheep_bench.py
git commit -m "feat(#268): sheep_first — six sheep bought first on lean_feed, and its declared bench

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```
