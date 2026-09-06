# #172 Stage 2: Offline Triage Tool — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A harness command that ranks whole strategies by seeded self-play final money, calibrated against the win-rates already recorded on issues, and a recorded PASS/FAIL/VOID against the declared bar.

**Architecture:** One module `harness/triage.py` whose scoring, ranking, calibration and formatting are pure functions with an injected `play` callable (so they test in milliseconds with a fake), a `main()` that wires the real `harness.tournament.play_rewards`, and one committed data file `harness/calibration_verdicts.json` holding the recorded verdicts as wins/games with their issue numbers. Nothing touches any strategy or `champion.json`.

**Tech Stack:** Python 3.12 (`.venv/bin/python`, symlinked into the worktree), `kaggle_environments` 1.32.7 (pinned, #195), stdlib only. Tests: `pytest`. Spec: `docs/superpowers/specs/2026-09-06-triage-tool-design.md`.

## Global Constraints

- Work in `~/code/rb-172` on branch `172-triage`. Run everything from there with `.venv/bin/python -m pytest ...` (never bare `python3`, which is 3.9). Commands run BLOCKING.
- Pure TDD: failing test written and RUN and seen failing for the right reason, then minimum code, then green, then commit by explicit path (`git add <files>`, never `git add -A`). Commit messages end with `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.
- Fixed by the spec and never moved after numbers exist: `SEEDS = (0, 1, 2, 3)`, `BAR = 0.40`, `FLOOR = "lean"`, minimum calibration set size 5, prediction = mean over seeds of `(reward_a + reward_b) / 2` in self-play from turn 0.
- Truth = recorded 16-seed win-rates vs `meta_bot` from issues, stored as `wins`/`games` (never a percentage) with the issue number. No fresh head-to-heads to grow the set.
- Exit codes: 0 PASS (or a plain ranking), 1 FAIL, 2 VOID (a failed control or fewer than five members). `main()` sets `ROBRICULTURE_STRICT=1` first (an instrument must surface a crash).
- `main()` is `# pragma: no cover`; everything else is tested. CI gate: line >= 85%, branch >= 65%.
- The tool never promotes, never writes `champion.json`, registers no strategy.

## File Structure

| File | Responsibility |
|---|---|
| `harness/triage.py` (create) | scoring/ranking/calibration/formatting (pure, injected `play`) + CLI `main()` |
| `harness/calibration_verdicts.json` (create) | the recorded verdicts: `{"protocol": ..., "members": [{"name","wins","games","seeds","issue"}, ...]}` |
| `tests/test_triage.py` (create) | unit tests with a fake `play`; one short-game integration test |
| `tests/test_calibration_verdicts.py` (create) | the data file's invariants |

Existing APIs (do not modify): `harness.tournament.play_rewards(agent_a, agent_b, seed=None) -> (reward_a, reward_b)` (plays one 720-step game, `# pragma: no cover`); `harness.tournament.build_agents(names) -> {name: agent}`; `kaggisim.strategy.make_agent(strategy)`; `strategies.load(name)` / `strategies.REGISTRY` (registered names include `lean`, `dense_farm`, `dung_farm`, `balanced_farm`, `neuropilot`, `meta_bot`, `splitbrain`, `field_rival`, `meta_rancher`, `ranch_hands`, `market_farmer`, `ranch_adaptive`, `wheat_hands`); `harness.ladder_correlation.spearman(xs, ys) -> float | None` (None when undefined); `harness.objective_check` for the strict-mode / exit-code pattern.

---

### Task 1: Scoring, ranking and the table (pure core)

**Files:**
- Create: `harness/triage.py`
- Test: `tests/test_triage.py`

**Interfaces:**
- Consumes: nothing from earlier tasks. `play` is any callable `(agent_a, agent_b, seed) -> (ra, rb)`; `agents` is any callable `(name) -> agent` (defaults are wired in Task 3).
- Produces: `SEEDS`, `BAR`, `FLOOR`, `MIN_MEMBERS = 5`; `self_play_score(name, seeds=SEEDS, play=None, agents=None) -> dict` with keys `name`, `score` (float), `per_seed` (list[float]), `seconds` (float); `rank(names, seeds=SEEDS, play=None, agents=None) -> list[dict]` sorted by `score` descending, ties keep input order; `format_ranking(rows) -> str`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_triage.py
"""The offline triage tool (#172 Stage 2): rank whole strategies by seeded
self-play final money. Everything here runs against a fake `play` so the
arithmetic is pinned without a simulator; the one real game is at the end."""

from __future__ import annotations

from harness import triage


def _fake_play(table):
    """A `play` whose rewards are looked up by (agent name, seed)."""
    def play(agent_a, agent_b, seed):
        return table[(agent_a, seed)]
    return play


def _names(name):
    return name          # the fake agent IS its name


def test_the_declared_constants():
    assert triage.SEEDS == (0, 1, 2, 3)
    assert triage.BAR == 0.40
    assert triage.FLOOR == "lean"
    assert triage.MIN_MEMBERS == 5


def test_self_play_score_averages_both_seats_and_all_seeds():
    table = {("a", 0): (100.0, 300.0), ("a", 1): (50.0, 50.0)}
    got = triage.self_play_score("a", seeds=(0, 1), play=_fake_play(table), agents=_names)
    assert got["name"] == "a"
    assert got["per_seed"] == [200.0, 50.0]
    assert got["score"] == 125.0
    assert got["seconds"] >= 0.0


def test_self_play_hands_the_same_strategy_to_both_seats_with_the_seed():
    seen = []

    def play(agent_a, agent_b, seed):
        seen.append((agent_a, agent_b, seed))
        return (1.0, 1.0)

    triage.self_play_score("z", seeds=(7,), play=play, agents=lambda n: f"agent:{n}")
    assert seen == [("agent:z", "agent:z", 7)]


def test_rank_sorts_best_first_and_keeps_input_order_on_ties():
    table = {("low", 0): (1.0, 1.0), ("high", 0): (9.0, 9.0),
             ("tie1", 0): (5.0, 5.0), ("tie2", 0): (5.0, 5.0)}
    rows = triage.rank(["low", "tie1", "high", "tie2"], seeds=(0,),
                       play=_fake_play(table), agents=_names)
    assert [r["name"] for r in rows] == ["high", "tie1", "tie2", "low"]


def test_format_ranking_has_a_header_and_one_line_per_strategy_with_seeds():
    rows = [{"name": "high", "score": 9.0, "per_seed": [9.0, 9.0], "seconds": 0.5},
            {"name": "low", "score": 1.0, "per_seed": [1.5, 0.5], "seconds": 0.4}]
    text = triage.format_ranking(rows)
    lines = [ln for ln in text.splitlines() if ln.strip()]
    assert len(lines) == 3
    assert lines[1].startswith("1") and "high" in lines[1] and "9.0" in lines[1]
    assert "1.5" in lines[2] and "0.5" in lines[2]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest -q tests/test_triage.py`
Expected: `ModuleNotFoundError: No module named 'harness.triage'` at collection.

- [ ] **Step 3: Write the minimal implementation**

```python
# harness/triage.py
"""Offline triage: rank whole strategies by seeded self-play final money
(#172 Stage 2), so a contender set can be ordered in seconds before anyone
pays for the 200-game ADR-0007 gate.

    python -m harness.triage NAME [NAME ...] [--top K] [--seeds 0 1 2 3]
    python -m harness.triage --calibrate

Prediction = mean over SEEDS of (reward_a + reward_b) / 2 with the SAME
strategy on both farms -- the mirror opponent Stage 1 (#214) found to be the
only rollout configuration that ranks. Both seats are averaged because they
run one policy, which halves seed noise for free.

The tool RANKS; it never chooses (#177: rho ~0.4 ranks, it does not choose)
and never promotes -- it does not write `harness/champion.json` and registers
nothing. Calibration compares its ranking to the 16-seed win-rates against
`meta_bot` already recorded on issues (`harness/calibration_verdicts.json`,
the source of truth; this docstring cites it and does not repeat it).

Exit codes: 0 PASS (or a plain ranking), 1 FAIL, 2 VOID (a control failed,
or fewer than MIN_MEMBERS in the calibration set). `main` runs under
ROBRICULTURE_STRICT=1: an instrument must surface a crash, not score a PASS bot.
"""

from __future__ import annotations

import time

#: Declared in the spec before any number existed; not moved afterwards.
SEEDS = (0, 1, 2, 3)
BAR = 0.40
FLOOR = "lean"
MIN_MEMBERS = 5


def _default_play():
    from harness.tournament import play_rewards
    return play_rewards


def _default_agents():
    from kaggisim.strategy import make_agent
    from strategies import load

    def agents(name):
        return make_agent(load(name)())
    return agents


def self_play_score(name, seeds=SEEDS, play=None, agents=None):
    """One number for `name`: mean over `seeds` of the two seats' mean final
    reward when the strategy plays itself. Fresh agent per seat and per game."""
    play = play or _default_play()
    agents = agents or _default_agents()
    t0 = time.perf_counter()
    per_seed = []
    for seed in seeds:
        ra, rb = play(agents(name), agents(name), seed)
        per_seed.append((float(ra) + float(rb)) / 2.0)
    score = sum(per_seed) / len(per_seed)
    return {"name": name, "score": score, "per_seed": per_seed,
            "seconds": time.perf_counter() - t0}


def rank(names, seeds=SEEDS, play=None, agents=None):
    """Rows from `self_play_score`, best first; ties keep input order."""
    rows = [self_play_score(n, seeds, play, agents) for n in names]
    return sorted(rows, key=lambda r: -r["score"])


def format_ranking(rows):
    """One header line, then rank, name, score, per-seed values, seconds."""
    lines = [f"{'#':>2} {'strategy':<18} {'score':>10}  per-seed  (s)"]
    for i, r in enumerate(rows, 1):
        seeds = " ".join(f"{v:.1f}" for v in r["per_seed"])
        lines.append(f"{i:>2} {r['name']:<18} {r['score']:>10.1f}  {seeds}  ({r['seconds']:.1f})")
    return "\n".join(lines)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest -q tests/test_triage.py`
Expected: `5 passed`.

- [ ] **Step 5: Commit**

```bash
git add harness/triage.py tests/test_triage.py
git commit -m "triage: self-play score, ranking and table with an injected play (#172 Stage 2)

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 2: Calibration verdicts file, `calibrate`, `floor_holds`

**Files:**
- Create: `harness/calibration_verdicts.json`
- Modify: `harness/triage.py` (append functions)
- Test: `tests/test_calibration_verdicts.py`, `tests/test_triage.py` (append)

**Interfaces:**
- Consumes: `harness.ladder_correlation.spearman`, `strategies.REGISTRY`, Task 1's `MIN_MEMBERS`, `BAR`.
- Produces: `VERDICTS_PATH` (module constant, absolute path of the JSON next to the module); `load_verdicts(path=VERDICTS_PATH) -> dict[str, float]` (name -> wins/games); `calibrate(scores: dict[str, float], verdicts: dict[str, float], bar=BAR, minimum=MIN_MEMBERS) -> dict` with keys `n`, `rho` (float|None), `passed` (bool), `void` (bool), `top_predicted` (str|None), `top_recorded` (str|None); `floor_holds(scores: dict[str, float], floor_score: float) -> bool`.

- [ ] **Step 1: Research and write the verdicts file (this step is data, not code — do it before the tests so the invariants test has a real file)**

For each candidate below, open the issue (`gh issue view N --json body,comments -q '[.body]+[.comments[].body]|.[]'`) and find the strategy's OWN win-rate against `meta_bot` on the 16-seed alternated protocol. Record only a row you can point to; write the issue number and the seed range as the issue states them. Do not compute a rate from anything but wins/16.

- `neuropilot` — #193/#202 body table: 16/16 vs meta_bot (confirm the seeds it states, or write `"seeds": "unstated"`).
- `dense_farm` — #202 / `strategies/dense_farm.py` docstring: 88% on 100-115 = 14/16 (confirm 14; 88% of 16 is 14.08).
- `dung_farm` — #206 verdict: 12/16 on 300-315.
- `balanced_farm` — #193 verdict: 9/16.
- Check and add if recorded: `splitbrain` (#196), `field_rival` (#181), `meta_rancher` (#204 or earlier), `ranch_hands`, `market_farmer`, `ranch_adaptive`, `wheat_hands`. A row where the issue records `balanced_farm`'s (or another agent's) rate AGAINST that strategy does not count — it must be the strategy's rate against `meta_bot`.

File shape (exact keys):

```json
{
  "protocol": "16 seeds vs meta_bot, sides alternated (ADR-0007 / #181)",
  "members": [
    {"name": "neuropilot", "wins": 16, "games": 16, "seeds": "unstated", "issue": 193},
    {"name": "dense_farm", "wins": 14, "games": 16, "seeds": "100-115", "issue": 202},
    {"name": "dung_farm", "wins": 12, "games": 16, "seeds": "300-315", "issue": 206},
    {"name": "balanced_farm", "wins": 9, "games": 16, "seeds": "100-115", "issue": 193}
  ]
}
```

(Correct any of the four from what the issues actually say, and append the extra members you confirmed.) In your report, list each row with the exact sentence or table cell it came from. If fewer than five rows can be confirmed, still commit the file — `calibrate` reports VOID for `n < 5` and that outcome is recorded in Task 4, not papered over.

- [ ] **Step 2: Write the failing tests**

```python
# tests/test_calibration_verdicts.py
"""The calibration data must be citable and shaped so the sample size is
visible: wins/games with the issue each number came from (#172 Stage 2)."""

from __future__ import annotations

import json

from harness import triage
from strategies import REGISTRY


def _members():
    return json.load(open(triage.VERDICTS_PATH))["members"]


def test_every_member_is_a_registered_strategy_with_a_cited_issue():
    members = _members()
    assert members, "POSITIVE CONTROL: no members, nothing to check"
    for m in members:
        assert m["name"] in REGISTRY, m
        assert isinstance(m["issue"], int) and m["issue"] > 0, m
        assert isinstance(m["wins"], int) and isinstance(m["games"], int), m
        assert 0 <= m["wins"] <= m["games"] and m["games"] > 0, m


def test_load_verdicts_returns_rates_by_name():
    rates = triage.load_verdicts()
    members = _members()
    assert set(rates) == {m["name"] for m in members}
    for m in members:
        assert rates[m["name"]] == m["wins"] / m["games"]


def test_no_member_is_duplicated():
    names = [m["name"] for m in _members()]
    assert len(names) == len(set(names))
```

Append to `tests/test_triage.py`:

```python
def test_calibrate_reports_rho_and_the_two_tops():
    scores = {"a": 300.0, "b": 200.0, "c": 100.0, "d": 50.0, "e": 10.0}
    verdicts = {"a": 1.0, "b": 0.9, "c": 0.7, "d": 0.5, "e": 0.1}
    got = triage.calibrate(scores, verdicts)
    assert got["n"] == 5 and got["rho"] == 1.0
    assert got["passed"] is True and got["void"] is False
    assert got["top_predicted"] == "a" and got["top_recorded"] == "a"


def test_calibrate_passes_at_the_bar_and_not_just_under_it():
    # Five points whose rank correlation is exactly 0.4 (ranks 1,2,3,4,5 vs 2,4,1,3,5? no --
    # build it from the definition instead: use a stub spearman to pin the comparison).
    scores = {n: float(i) for i, n in enumerate("abcde")}
    verdicts = {n: float(i) for i, n in enumerate("abcde")}
    assert triage.calibrate(scores, verdicts, bar=1.0)["passed"] is True      # rho 1.0 >= 1.0
    assert triage.calibrate(scores, verdicts, bar=1.01)["passed"] is False    # rho 1.0 < 1.01


def test_calibrate_is_void_below_the_minimum_and_never_passes_void():
    scores = {"a": 3.0, "b": 2.0, "c": 1.0, "d": 0.5}
    verdicts = {"a": 1.0, "b": 0.9, "c": 0.7, "d": 0.5}
    got = triage.calibrate(scores, verdicts)
    assert got["void"] is True and got["passed"] is False and got["n"] == 4


def test_calibrate_uses_only_the_names_present_in_both():
    scores = {"a": 3.0, "b": 2.0, "c": 1.0, "d": 0.5, "e": 0.1, "unrecorded": 9.0}
    verdicts = {"a": 1.0, "b": 0.9, "c": 0.7, "d": 0.5, "e": 0.1, "unscored": 0.3}
    got = triage.calibrate(scores, verdicts)
    assert got["n"] == 5 and got["top_predicted"] == "a"


def test_calibrate_with_all_tied_verdicts_is_void_not_zero():
    scores = {"a": 3.0, "b": 2.0, "c": 1.0, "d": 0.5, "e": 0.1}
    verdicts = {n: 0.5 for n in scores}
    got = triage.calibrate(scores, verdicts)
    assert got["rho"] is None and got["void"] is True and got["passed"] is False


def test_floor_holds_only_when_every_member_beats_the_floor():
    assert triage.floor_holds({"a": 10.0, "b": 5.0}, 4.0) is True
    assert triage.floor_holds({"a": 10.0, "b": 4.0}, 4.0) is False     # a tie fails
    assert triage.floor_holds({"a": 10.0, "b": 3.0}, 4.0) is False
```

Then replace the confused second test above with this exact one (the plan keeps the intent explicit; the committed test must be this):

```python
def test_calibrate_passes_at_the_bar_and_not_just_under_it():
    scores = {n: float(i) for i, n in enumerate("abcde")}
    verdicts = {n: float(i) for i, n in enumerate("abcde")}          # rho exactly 1.0
    assert triage.calibrate(scores, verdicts, bar=1.0)["passed"] is True
    assert triage.calibrate(scores, verdicts, bar=1.01)["passed"] is False
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest -q tests/test_calibration_verdicts.py tests/test_triage.py`
Expected: `AttributeError: module 'harness.triage' has no attribute 'VERDICTS_PATH'` / `'calibrate'` / `'floor_holds'`; the Task 1 tests still pass.

- [ ] **Step 4: Write the implementation** (append to `harness/triage.py`)

```python
import json
import os

from harness.ladder_correlation import spearman

#: The recorded verdicts the tool is calibrated against (wins/games + issue).
VERDICTS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "calibration_verdicts.json")


def load_verdicts(path=VERDICTS_PATH):
    """name -> recorded win-rate (wins / games) against meta_bot."""
    with open(path) as f:
        members = json.load(f)["members"]
    return {m["name"]: m["wins"] / m["games"] for m in members}


def calibrate(scores, verdicts, bar=BAR, minimum=MIN_MEMBERS):
    """Spearman rho between self-play scores and recorded rates over the names
    present in both. `void` when fewer than `minimum` names or rho is undefined
    (all-tied), and a void never passes: no evidence is not no relationship."""
    names = sorted(set(scores) & set(verdicts))
    n = len(names)
    rho = spearman([scores[k] for k in names], [verdicts[k] for k in names]) if n else None
    void = n < minimum or rho is None
    return {
        "n": n,
        "rho": rho,
        "void": void,
        "passed": (not void) and rho >= bar,
        "top_predicted": max(names, key=lambda k: scores[k]) if names else None,
        "top_recorded": max(names, key=lambda k: verdicts[k]) if names else None,
    }


def floor_holds(scores, floor_score):
    """Every member strictly beats the floor strategy's score; a tie fails."""
    return all(v > floor_score for v in scores.values())
```

Put the two new imports (`json`, `os`, and the `spearman` import) at the top of the module with the existing `import time`, not mid-file.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest -q tests/test_calibration_verdicts.py tests/test_triage.py`
Expected: all pass (`3 + 11`).

- [ ] **Step 6: Commit**

```bash
git add harness/calibration_verdicts.json harness/triage.py tests/test_calibration_verdicts.py tests/test_triage.py
git commit -m "triage: calibration verdicts (cited wins/games), calibrate and floor_holds (#172 Stage 2)

<one line per verdict row: name wins/games <- issue #N, quoting the cell>

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 3: CLI `main()` with controls, exit codes, and one real short game

**Files:**
- Modify: `harness/triage.py` (append `main`)
- Test: `tests/test_triage.py` (append one integration test)

**Interfaces:**
- Consumes: Task 1 and Task 2 functions; `harness.tournament.play_rewards`; the strict-mode pattern from `harness/objective_check.py`.
- Produces: `main(argv=None) -> int` (`# pragma: no cover`); `run_calibration(seeds=SEEDS, play=None, agents=None, verdicts=None) -> dict` (tested with the fake) returning `{"rows", "scores", "floor_score", "floor_ok", "determinism_ok", "result"}` where `result` is `calibrate(...)`'s dict.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_triage.py`)

```python
def test_run_calibration_runs_both_controls_and_calibrates():
    table = {}
    for seed in (0, 1):
        for name, val in (("a", 5.0), ("b", 4.0), ("c", 3.0), ("d", 2.0), ("e", 1.0), ("lean", 0.0)):
            table[(name, seed)] = (val, val)
    verdicts = {"a": 1.0, "b": 0.8, "c": 0.6, "d": 0.4, "e": 0.2}
    got = triage.run_calibration(seeds=(0, 1), play=_fake_play(table), agents=_names,
                                 verdicts=verdicts)
    assert got["floor_score"] == 0.0 and got["floor_ok"] is True
    assert got["determinism_ok"] is True
    assert got["result"]["passed"] is True and got["result"]["n"] == 5
    assert [r["name"] for r in got["rows"]] == ["a", "b", "c", "d", "e"]


def test_run_calibration_reports_a_failed_floor():
    table = {}
    for name, val in (("a", 5.0), ("b", 4.0), ("c", 3.0), ("d", 2.0), ("e", 1.0), ("lean", 1.0)):
        table[(name, 0)] = (val, val)                 # e ties the floor
    verdicts = {"a": 1.0, "b": 0.8, "c": 0.6, "d": 0.4, "e": 0.2}
    got = triage.run_calibration(seeds=(0,), play=_fake_play(table), agents=_names, verdicts=verdicts)
    assert got["floor_ok"] is False


def test_run_calibration_detects_a_nondeterministic_play():
    calls = {"n": 0}

    def drifting(agent_a, agent_b, seed):
        calls["n"] += 1
        return (float(calls["n"]), float(calls["n"]))   # never the same twice

    verdicts = {n: 0.5 for n in "abcde"}
    got = triage.run_calibration(seeds=(0,), play=drifting, agents=_names, verdicts=verdicts)
    assert got["determinism_ok"] is False


def test_a_real_short_self_play_game_ranks_dense_farm_above_lean():
    # The floor control in miniature, through the real simulator: ~10 s.
    from kaggle_environments import make
    from kaggisim.strategy import make_agent
    from strategies import load

    def short_play(agent_a, agent_b, seed):
        env = make("kaggriculture", configuration={"episodeSteps": 240, "seed": seed})
        env.run([agent_a, agent_b])
        ra, rb = (s.reward or 0 for s in env.steps[-1])
        return ra, rb

    agents = lambda n: make_agent(load(n)())
    rows = triage.rank(["lean", "dense_farm"], seeds=(0,), play=short_play, agents=agents)
    assert all(r["score"] > 0 for r in rows), "POSITIVE CONTROL: no money moved, test proves nothing"
    assert [r["name"] for r in rows] == ["dense_farm", "lean"]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest -q tests/test_triage.py`
Expected: three `AttributeError: ... no attribute 'run_calibration'`; the short-game test PASSES already (it uses `rank` from Task 1) — record that it passed and that it is a real-simulator positive control, not a red for new code.

- [ ] **Step 3: Write the implementation** (append to `harness/triage.py`)

```python
def run_calibration(seeds=SEEDS, play=None, agents=None, verdicts=None):
    """Controls first, then the calibration. The floor strategy is scored
    once; determinism re-scores the first member and demands equality to the
    value; then `calibrate` over the members."""
    verdicts = verdicts if verdicts is not None else load_verdicts()
    names = sorted(verdicts)
    rows = rank(names, seeds, play, agents)
    scores = {r["name"]: r["score"] for r in rows}
    floor_score = self_play_score(FLOOR, seeds, play, agents)["score"]
    again = self_play_score(names[0], seeds, play, agents)["score"]
    return {
        "rows": rows,
        "scores": scores,
        "floor_score": floor_score,
        "floor_ok": floor_holds(scores, floor_score),
        "determinism_ok": again == scores[names[0]],
        "result": calibrate(scores, verdicts),
    }


def main(argv=None):  # pragma: no cover
    import argparse
    import os as _os
    # An instrument inverts ADR-0006's default: a crash must surface, not
    # become a PASS bot whose score gets ranked.
    _os.environ.setdefault("ROBRICULTURE_STRICT", "1")

    ap = argparse.ArgumentParser(description="offline triage: rank strategies by self-play (#172)")
    ap.add_argument("names", nargs="*", help="registered strategy names to rank")
    ap.add_argument("--top", type=int, default=None, help="print the top K as the gate candidates")
    ap.add_argument("--seeds", type=int, nargs="+", default=list(SEEDS))
    ap.add_argument("--calibrate", action="store_true",
                    help="run the controls and the calibration against calibration_verdicts.json")
    args = ap.parse_args(argv)
    seeds = tuple(args.seeds)

    if args.calibrate:
        cal = run_calibration(seeds=seeds)
        print(f"seeds={seeds} bar={BAR} floor={FLOOR} members={cal['result']['n']}")
        print(f"floor control: {FLOOR} scored {cal['floor_score']:.1f} -> "
              f"{'OK' if cal['floor_ok'] else 'FAIL -- RUN VOID'}")
        print(f"determinism control: {'OK' if cal['determinism_ok'] else 'FAIL -- RUN VOID'}")
        print(format_ranking(cal["rows"]))
        r = cal["result"]
        rho = "undefined" if r["rho"] is None else f"{r['rho']:.2f}"
        print(f"top predicted: {r['top_predicted']}  top recorded: {r['top_recorded']}")
        if not (cal["floor_ok"] and cal["determinism_ok"]) or r["void"]:
            print(f"rho={rho} n={r['n']} -> VOID")
            return 2
        print(f"rho={rho} n={r['n']} bar={BAR:.2f} -> {'PASS' if r['passed'] else 'FAIL'}")
        return 0 if r["passed"] else 1

    if not args.names:
        ap.error("give strategy names to rank, or --calibrate")
    rows = rank(args.names, seeds)
    print(format_ranking(rows))
    if args.top:
        print("proceed to the gate: " + ", ".join(r["name"] for r in rows[:args.top]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest -q tests/test_triage.py tests/test_calibration_verdicts.py`
Expected: all pass.

- [ ] **Step 5: Smoke the CLI (blocking, ~30 s)**

Run: `.venv/bin/python -m harness.triage lean dense_farm --seeds 0 --top 1`
Expected: a two-row table with `dense_farm` first and `proceed to the gate: dense_farm`.

- [ ] **Step 6: Full suite as CI runs it, plus the gate numbers**

Run: `.venv/bin/python -m pytest -q -n auto --cov --cov-branch --cov-report=term-missing --cov-report=json 2>&1 | tail -3`, then
```bash
.venv/bin/python - <<'PY'
import json
t = json.load(open("coverage.json"))["totals"]
print("line", round(100*t["covered_lines"]/t["num_statements"],1), "branch", round(100*t["covered_branches"]/t["num_branches"],1))
PY
```
Expected: all pass; line >= 85, branch >= 65.

- [ ] **Step 7: Commit**

```bash
git add harness/triage.py tests/test_triage.py
git commit -m "triage: run_calibration with floor and determinism controls, CLI with exit codes (#172 Stage 2)

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 4: Run the declared calibration and draft the record

**Files:** none in the repo. Output goes to the scratchpad for the controller to review and post.

- [ ] **Step 1: Run the calibration, blocking, timed**

```bash
time .venv/bin/python -m harness.triage --calibrate 2>&1 | tee /private/tmp/claude-501/-Users-sartin/2195f188-57a5-4834-a6b9-acc4ec519961/scratchpad/172-triage-calibration.txt; echo "exit ${pipestatus[1]}"
```

Expected: both control lines `OK`, the ranking, the `top predicted / top recorded` line, and `rho=... -> PASS|FAIL` (exit 0/1) or `VOID` (exit 2). Do not re-run with different seeds or members.

- [ ] **Step 2: Draft the issue comment** to `/private/tmp/claude-501/-Users-sartin/2195f188-57a5-4834-a6b9-acc4ec519961/scratchpad/172-stage2-comment.md`, lab-notebook style (numbers first; the bar never moves): heading `## Stage 2 calibration, 2026-09-06: PASS|FAIL|VOID`; the setup line (sim 1.32.7, seeds, members with their recorded wins/games and issue numbers, bar); both controls with their numbers; the ranking table verbatim; rho and n; top predicted vs top recorded (ranking, not choosing); wall-clock per strategy; a "What this licenses" paragraph (PASS: the tool may stand in front of the ADR-0007 gate as a rank-only pre-filter, and the issue's runtime-planner framing is closed by Stage 1's table; FAIL/VOID: not shipped as a pre-filter, issue keeps the record); last line naming the branch `172-triage` and that the PR carries harness code and one data file, no strategy change.

- [ ] **Step 3: Draft the PR body** to `/private/tmp/claude-501/-Users-sartin/2195f188-57a5-4834-a6b9-acc4ec519961/scratchpad/172-stage2-pr-body.md`: the spec path and its declared criterion; what the PR carries (`harness/triage.py`, `harness/calibration_verdicts.json`, tests); the usage lines; the calibration result block; `Closes #172` ONLY if the verdict is PASS (a PASS closes the issue: Stage 1 answered the planner question and Stage 2 delivered the tool); otherwise no `Closes`; final line `🤖 Generated with [Claude Code](https://claude.com/claude-code)`.

Do not post either file; do not commit anything (`git status` must show no tracked changes).

---

---

### Task 5: Fresh head-to-heads for the short calibration set (added after Task 2; run BEFORE Task 3)

**Why:** Task 2 could cite only four recorded rates; the spec's amendment of 2026-09-06 widens the
truth source to fresh 16-seed alternated head-to-heads against `meta_bot` for five more strategies.

**Files:**
- Modify: `harness/triage.py` (append `head_to_head_rate`, `measure_verdicts`, `append_verdicts`)
- Modify: `harness/calibration_verdicts.json` (add `"source"` to every row; append the five fresh rows produced by the run)
- Test: `tests/test_triage.py` (append), `tests/test_calibration_verdicts.py` (append)

**Interfaces:**
- Consumes: Task 1's injected `play`/`agents`; Task 2's `VERDICTS_PATH`, `load_verdicts`.
- Produces: `FRESH_SEEDS = tuple(range(100, 116))`, `GATE = "meta_bot"`; `head_to_head_rate(name, opponent=GATE, seeds=FRESH_SEEDS, play=None, agents=None) -> {"name","opponent","wins","games","seeds"}` with sides alternated (name in seat 0 on even seeds, seat 1 on odd; a win is strictly more reward than the opponent; a tie is not a win); `measure_verdicts(names, ...) -> list[dict]` of rows shaped for the file with `"issue": 172, "source": "fresh"`; `append_verdicts(rows, path=VERDICTS_PATH) -> None` which refuses (raises `ValueError`) to add a name already present.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_triage.py`)

```python
def test_head_to_head_alternates_seats_and_counts_strict_wins():
    seen = []

    def play(agent_a, agent_b, seed):
        seen.append((agent_a, agent_b, seed))
        # seat 0 gets 10, seat 1 gets 5, except seed 3 is a tie
        return (7.0, 7.0) if seed == 3 else (10.0, 5.0)

    got = triage.head_to_head_rate("me", opponent="them", seeds=(0, 1, 2, 3), play=play, agents=_names)
    assert seen == [("me", "them", 0), ("them", "me", 1), ("me", "them", 2), ("them", "me", 3)]
    # seed 0: me in seat 0 wins; seed 1: me in seat 1 loses; seed 2: wins; seed 3: tie -> not a win
    assert got == {"name": "me", "opponent": "them", "wins": 2, "games": 4, "seeds": "0-3"}


def test_measure_verdicts_shapes_rows_for_the_file():
    play = lambda a, b, seed: (10.0, 5.0)
    rows = triage.measure_verdicts(["x", "y"], opponent="them", seeds=(0, 1), play=play, agents=_names)
    assert [r["name"] for r in rows] == ["x", "y"]
    for r in rows:
        assert r["games"] == 2 and r["issue"] == 172 and r["source"] == "fresh"
        assert r["seeds"] == "0-1" and "opponent" in r


def test_append_verdicts_adds_rows_and_refuses_duplicates(tmp_path):
    import json
    path = tmp_path / "v.json"
    path.write_text(json.dumps({"protocol": "p", "members": [
        {"name": "a", "wins": 1, "games": 2, "seeds": "0-1", "issue": 1, "source": "recorded"}]}))
    triage.append_verdicts([{"name": "b", "wins": 2, "games": 2, "seeds": "0-1", "issue": 172,
                             "source": "fresh", "opponent": "meta_bot"}], path=str(path))
    assert [m["name"] for m in json.load(open(path))["members"]] == ["a", "b"]
    import pytest
    with pytest.raises(ValueError):
        triage.append_verdicts([{"name": "a", "wins": 0, "games": 2, "seeds": "0-1", "issue": 172,
                                 "source": "fresh", "opponent": "meta_bot"}], path=str(path))
```

Append to `tests/test_calibration_verdicts.py`:

```python
def test_every_member_names_its_source():
    for m in _members():
        assert m["source"] in ("recorded", "fresh"), m
        if m["source"] == "fresh":
            assert m["issue"] == 172 and m["opponent"] == "meta_bot" and m["games"] == 16, m
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest -q tests/test_triage.py tests/test_calibration_verdicts.py`
Expected: three `AttributeError` (no `head_to_head_rate` / `measure_verdicts` / `append_verdicts`) and `KeyError: 'source'` from the verdicts test.

- [ ] **Step 3: Implement** (append to `harness/triage.py`; `json`/`os` are already imported at the top)

```python
#: The seed set dense_farm's recorded row used (#202), so fresh rows sit on it.
FRESH_SEEDS = tuple(range(100, 116))
GATE = "meta_bot"


def _seed_range(seeds):
    return f"{min(seeds)}-{max(seeds)}" if len(seeds) > 1 else str(seeds[0])


def head_to_head_rate(name, opponent=GATE, seeds=FRESH_SEEDS, play=None, agents=None):
    """`name` vs `opponent` over `seeds`, sides alternated (seat 0 on even
    seeds, seat 1 on odd -- the repo's convention, see opening_bench.our_seat).
    A win is strictly more reward; a tie is not a win."""
    play = play or _default_play()
    agents = agents or _default_agents()
    wins = 0
    for seed in seeds:
        if seed % 2 == 0:
            ours, theirs = play(agents(name), agents(opponent), seed)
        else:
            theirs, ours = play(agents(opponent), agents(name), seed)
        wins += int(ours > theirs)
    return {"name": name, "opponent": opponent, "wins": wins, "games": len(seeds),
            "seeds": _seed_range(seeds)}


def measure_verdicts(names, opponent=GATE, seeds=FRESH_SEEDS, play=None, agents=None):
    """Rows shaped for calibration_verdicts.json, marked fresh and cited to #172."""
    rows = []
    for name in names:
        row = head_to_head_rate(name, opponent, seeds, play, agents)
        row.update(issue=172, source="fresh")
        rows.append(row)
    return rows


def append_verdicts(rows, path=VERDICTS_PATH):
    """Append fresh rows to the verdicts file; a name already present is an
    error, never a silent overwrite of a recorded verdict."""
    with open(path) as f:
        data = json.load(f)
    present = {m["name"] for m in data["members"]}
    clash = [r["name"] for r in rows if r["name"] in present]
    if clash:
        raise ValueError(f"already in the verdicts file: {clash}")
    data["members"].extend(rows)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
```

Then edit `harness/calibration_verdicts.json` by hand: add `"source": "recorded"` to each of the four existing rows.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest -q tests/test_triage.py tests/test_calibration_verdicts.py`
Expected: all pass.

- [ ] **Step 5: Commit the code (before the run)**

```bash
git add harness/triage.py harness/calibration_verdicts.json tests/test_triage.py tests/test_calibration_verdicts.py
git commit -m "triage: fresh head-to-head verdicts, sides alternated, appended never overwritten (#172 Stage 2)

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

- [ ] **Step 6: Run the declared measurement, blocking (~5 x 16 games x ~2 s, under 4 minutes), and append**

```bash
.venv/bin/python - <<'PY'
import os
os.environ.setdefault("ROBRICULTURE_STRICT", "1")
from harness import triage
rows = triage.measure_verdicts(["splitbrain", "field_rival", "meta_rancher", "ranch_hands", "wheat_hands"])
for r in rows:
    print(r)
triage.append_verdicts(rows)
PY
.venv/bin/python -m pytest -q tests/test_calibration_verdicts.py
```

Expected: five rows printed with `games: 16`, the file now has nine members, the invariants test passes.

- [ ] **Step 7: Commit the data**

```bash
git add harness/calibration_verdicts.json
git commit -m "calibration_verdicts: five fresh 16-seed rates vs meta_bot on seeds 100-115 (#172)

<one line per row: name wins/16>

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

## Self-review

- **Amendment 2026-09-06:** Task 5 (fresh head-to-heads) was added after Task 2 found only four recorded rates; it runs before Task 3 so the CLI's calibration sees nine members.

- **Spec coverage:** prediction definition and constants (Task 1); verdicts file with wins/games + issue, `load_verdicts`, `calibrate` with `n < 5` void and undefined-rho void, `floor_holds` with tie failing (Task 2); controls first, determinism, exit codes 0/1/2, strict mode, `--top K`, never writes champion.json (Task 3); the declared run and the record (Task 4); the slow real-game floor test (Task 3 Step 1). Out-of-scope items untouched.
- **Placeholders:** none — the one ambiguous test draft in Task 2 Step 2 is immediately replaced by its exact committed form.
- **Type consistency:** `self_play_score` returns `name/score/per_seed/seconds` and `rank`/`format_ranking`/`run_calibration` consume exactly those; `calibrate` returns `n/rho/void/passed/top_predicted/top_recorded` and `main` reads exactly those; `run_calibration` returns `rows/scores/floor_score/floor_ok/determinism_ok/result` and the tests and `main` read exactly those.
