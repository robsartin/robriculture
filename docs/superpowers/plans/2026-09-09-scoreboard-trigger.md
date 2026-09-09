# Scoreboard trigger control (#197, Stage 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `harness/scoreboard_probe.py`, which plays the champion against itself and the five pinned externals on spent seeds, records both farms' census per game, and tabulates for every (day, margin) how often "behind by X% at day D" fires, its precision, its harm and its recall — plus the strawberry and herd asymmetry per opponent.

**Architecture:** Pure helpers (`behind`, `census_on_day`, `game_reading`, `tabulate`, `actionable`, the two formatters) unit-tested on hand-built censuses; one live runner (`run`) built on `harness.farm_census.census_series` and `harness.external_pool.external_anchor_agents`, and a `main` that writes the raw readings to a committed JSON record and can re-derive the tables from it without replaying. No strategy changes.

**Tech Stack:** Python 3.12 in `.venv` (`.venv/bin/python`, never a bare python3), pytest `-n auto`, `kaggle-environments` 1.32.7. Spec: `docs/superpowers/specs/2026-09-09-scoreboard-trigger-design.md`.

## Global Constraints

- Pure TDD: write the failing tests, **run them and quote the failure**, then the code, run green, commit.
- Full suite green before the commit: `.venv/bin/python -m pytest -q -n auto`.
- Declared values, verbatim from the spec, not to be tuned: `CHAMPION = "third_herder"`, `SEEDS = tuple(range(864, 880))`, `DAYS = (12, 15, 18, 21)`, `MARGINS = (10, 20, 30)`, `FIRE_BAR = 0.25`, `HARM_BAR = 0.20`, `OPPONENTS = (CHAMPION,) + tuple(EXTERNAL_ANCHORS)`; behind means `ours < theirs * (1 - margin/100)` (strict); loss means final `ours < theirs`, win `ours > theirs`, else tie.
- Definitions: fire_rate = fired / games; precision = fired losses / fired (`None` when nothing fired); harm = fired wins / wins (`0.0` when there are no wins — nothing to harm); recall = fired losses / losses (`None` when there are no losses). Actionable = fire_rate ≥ FIRE_BAR and harm ≤ HARM_BAR.
- Live-game code (`run`, `main`) carries `# pragma: no cover` at the `def`; every pure helper is covered. Do NOT run the live probe — the controller runs it after review.
- Test names read `test_<the fact>` with a docstring or comment saying why (house style, see `tests/test_front_bench.py`).
- Stage by explicit path; never `git add -A`; never stage `.venv` or `external_agents` (symlinks in this worktree).
- Commit messages end with a blank line and `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.

---

### Task 1: `harness/scoreboard_probe.py` and its tests

**Files:**
- Create: `harness/scoreboard_probe.py`
- Create: `tests/test_scoreboard_probe.py`
- Reference (read, do not modify): `harness/front_bench.py` (module shape, the missing-day raise), `harness/herder_bench.py` (`last_census_on_day(turns, day)` → the day's closing census or `None`), `harness/farm_census.py` (`census_series(agent_a, agent_b, seed)` → `(ours, theirs)` per-turn `[(day, census), ...]` for player 0 and player 1; a census has `money`, `planted` `{crop: tiles}`, `head_placed`), `harness/external_pool.py` (`EXTERNAL_ANCHORS`, `external_anchor_agents(names)` → `{name: FreshPerGame}` with `.fresh()`; the wrapper trims `(obs, config)` to the inner agent's arity).

**Interfaces:**
- Consumes: `harness.herder_bench.last_census_on_day`, `harness.external_pool.EXTERNAL_ANCHORS` / `external_anchor_agents`, `harness.farm_census.census_series`, `kaggisim.strategy.make_agent`, `strategies.load`.
- Produces: the declared constants; `behind(ours, theirs, margin_pct) -> bool`; `census_on_day(turns, day) -> dict` (raises `ValueError` naming the day when never reached); `game_reading(ours_turns, theirs_turns, opponent, seed, days=DAYS) -> dict` with keys `opponent, seed, at (str(day) -> {ours, theirs, strawberry_gap, head_gap}), final_ours, final_theirs, result`; `tabulate(readings, days=DAYS, margins=MARGINS) -> {(day, margin): {opponent_name: row, ..., "pooled": row}}` with row keys `games, fired, fire_rate, precision, harm, recall`; `actionable(row) -> bool`; `format_table(table) -> str`; `format_asymmetry(readings, days=DAYS) -> str`; `run(seeds=SEEDS, opponents=OPPONENTS) -> list[reading]`; `main(argv=None)`.

- [ ] **Step 1: Write the failing tests** — `tests/test_scoreboard_probe.py`:

```python
"""The scoreboard trigger control (#197, Stage 1): the declared constants and the
pure parts -- behind-by-X at the close of day D, the per-game reading off two
census series, and the fire / precision / harm / recall table those readings
tabulate to. The 96 live games are `run`'s and are not exercised here.
"""

from __future__ import annotations

import pytest

from harness import scoreboard_probe as sp
from harness.external_pool import EXTERNAL_ANCHORS


def test_the_declared_constants():
    assert sp.CHAMPION == "third_herder"
    assert sp.SEEDS == tuple(range(864, 880))
    assert sp.DAYS == (12, 15, 18, 21) and sp.MARGINS == (10, 20, 30)
    assert sp.FIRE_BAR == 0.25 and sp.HARM_BAR == 0.20
    assert sp.OPPONENTS == ("third_herder",) + tuple(EXTERNAL_ANCHORS)
    assert sp.RECORD.endswith("harness/scoreboard/trigger_readings.json")


def test_the_seeds_are_spent_not_fresh():
    # Stage 1 is a control on games already paid for: 864-879 are #244's seeds.
    assert set(sp.SEEDS) <= set(range(800, 896))


def test_behind_is_strict_at_the_margin():
    # ours < theirs * (1 - X/100): exactly at the line is NOT behind.
    assert sp.behind(699, 1000, 30) is True
    assert sp.behind(700, 1000, 30) is False
    assert sp.behind(799, 1000, 20) is True
    assert sp.behind(1000, 1000, 10) is False


def _census(money, strawberry=0, head=0):
    return {"money": float(money), "planted": {"STRAWBERRY": strawberry} if strawberry else {},
            "head_placed": head}


def _turns(moneys, strawberry=0, head=0):
    # Two turns a day; the second is the closing board, and it carries the day's money.
    turns = []
    for day, money in enumerate(moneys):
        turns.append((day, _census(money - 1, strawberry, head)))
        turns.append((day, _census(money, strawberry, head)))
    return turns


def test_census_on_day_takes_the_closing_board_and_raises_on_a_missing_day():
    turns = _turns([100, 200, 300])
    assert sp.census_on_day(turns, 1)["money"] == 200
    with pytest.raises(ValueError, match="day 7"):
        sp.census_on_day(turns, 7)


def test_game_reading_records_both_sides_at_each_day_and_the_final_result():
    ours = _turns([1000] * 22, strawberry=22, head=11)
    theirs = _turns([1500] * 21 + [900], strawberry=24, head=14)
    r = sp.game_reading(ours, theirs, "lonespear", 864, days=(12, 21))
    assert r["opponent"] == "lonespear" and r["seed"] == 864
    assert r["at"]["12"] == {"ours": 1000.0, "theirs": 1500.0, "strawberry_gap": 2, "head_gap": 3}
    assert r["final_ours"] == 1000.0 and r["final_theirs"] == 900.0
    assert r["result"] == "win"
    assert sp.game_reading(theirs, ours, "x", 1, days=(12,))["result"] == "loss"
    assert sp.game_reading(ours, ours, "x", 1, days=(12,))["result"] == "tie"


def _reading(opponent, ours_at_15, theirs_at_15, result):
    final = {"win": (2, 1), "loss": (1, 2), "tie": (1, 1)}[result]
    return {"opponent": opponent, "seed": 0,
            "at": {"15": {"ours": ours_at_15, "theirs": theirs_at_15, "strawberry_gap": 0, "head_gap": 0}},
            "final_ours": float(final[0]), "final_theirs": float(final[1]), "result": result}


def _four():
    # Behind by 30% and lost; behind by 30% and won; ahead and lost; ahead and won.
    return [_reading("x", 700, 1000, "loss"), _reading("x", 700, 1000, "win"),
            _reading("x", 1200, 1000, "loss"), _reading("x", 1200, 1000, "win")]


def test_tabulate_counts_fire_precision_harm_and_recall_per_opponent_and_pooled():
    table = sp.tabulate(_four(), days=(15,), margins=(20,))
    row = table[(15, 20)]["x"]
    assert row == {"games": 4, "fired": 2, "fire_rate": 0.5, "precision": 0.5, "harm": 0.5, "recall": 0.5}
    assert table[(15, 20)]["pooled"] == row


def test_tabulate_reports_none_where_a_rate_has_no_denominator_and_zero_harm_with_no_wins():
    # Nothing fired -> precision None. No losses -> recall None. No wins -> harm 0.0
    # (there is nothing for the trigger to harm), not None.
    table = sp.tabulate([_reading("x", 1200, 1000, "win")], days=(15,), margins=(20,))
    assert table[(15, 20)]["x"]["precision"] is None and table[(15, 20)]["x"]["recall"] is None
    table = sp.tabulate([_reading("x", 700, 1000, "loss")], days=(15,), margins=(20,))
    assert table[(15, 20)]["x"]["harm"] == 0.0 and table[(15, 20)]["x"]["precision"] == 1.0


def test_actionable_needs_the_fire_bar_and_the_harm_bar_together():
    ok = {"games": 16, "fired": 4, "fire_rate": 0.25, "precision": 1.0, "harm": 0.20, "recall": 1.0}
    assert sp.actionable(ok) is True
    assert sp.actionable(dict(ok, fire_rate=0.24)) is False
    assert sp.actionable(dict(ok, harm=0.21)) is False
    assert sp.actionable(dict(ok, harm=0.0)) is True


def test_format_table_prints_a_block_per_cell_with_the_pooled_line_and_the_marker():
    text = sp.format_table(sp.tabulate(_four(), days=(15,), margins=(20,)))
    assert "day 15" in text and "20%" in text
    lines = text.splitlines()
    assert any(l.startswith("x") for l in lines) and any(l.startswith("pooled") for l in lines)
    starred = sp.format_table(sp.tabulate([_reading("x", 700, 1000, "loss")] * 4, days=(15,), margins=(20,)))
    assert "*" in starred and "*" not in text        # fire 100% harm 0 is actionable; fire 50% harm 50% is not


def test_format_asymmetry_prints_the_median_gaps_per_opponent_and_day():
    readings = [dict(_reading("x", 1, 1, "win"), at={"15": {"ours": 1, "theirs": 1, "strawberry_gap": g, "head_gap": h}})
                for g, h in ((2, 3), (4, 1), (6, 5))]
    text = sp.format_asymmetry(readings, days=(15,))
    assert "x" in text and "4" in text and "3" in text   # medians: strawberry 4, head 3
```

- [ ] **Step 2: Run them and quote the failure**

Run: `.venv/bin/python -m pytest -q tests/test_scoreboard_probe.py`
Expected: collection error — `ImportError: cannot import name 'scoreboard_probe' from 'harness'` (or `ModuleNotFoundError`); quote whichever appears.

- [ ] **Step 3: Minimal implementation** — `harness/scoreboard_probe.py`:

```python
"""Scoreboard trigger control (#197, Stage 1): can "behind at day D" be read early enough to act on?

    python -m harness.scoreboard_probe                 # play the 96 games, write the record, print the tables
    python -m harness.scoreboard_probe --from-record   # re-derive the tables from the committed record

The issue asked whether a controller that knows it is behind and gambles wins
more rated games. Brainstormed 2026-09-09: rival money is in the live
observation (no estimator needed), the economy has no dice (a gamble can only
be a play whose payoff depends on the rival), and the champion's crop chooser
has one move after day 15, so no Stage 2 lever survives. What is worth knowing
-- for any future scoreboard contender -- is whether the trigger itself reads:
for "our money is behind the rival's by >= X% at the close of day D", how often
it fires, how often a fired game ends in a loss (precision), how often it fires
on a game we go on to win (harm), and how many losses it catches (recall).

Declared on #197 before any code: the champion vs itself and the five pinned
externals on SPENT seeds 864-879 (96 games), sides alternated by seed parity,
D in {12, 15, 18, 21}, X in {10, 20, 30}%. A cell is actionable at fire rate
>= 25% AND harm <= 20%; the whole table is reported and no cell clearing both
is a finding, not a failure. Beside it, per opponent and day: the rival's
strawberry tiles minus ours and head placed minus ours (medians) -- the
asymmetry any spoil lever would need.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics

from harness.external_pool import EXTERNAL_ANCHORS
from harness.herder_bench import last_census_on_day

CHAMPION = "third_herder"

#: Spent: #244's seeds. Stage 1 is a control on games already paid for.
SEEDS = tuple(range(864, 880))
DAYS = (12, 15, 18, 21)
MARGINS = (10, 20, 30)
FIRE_BAR = 0.25
HARM_BAR = 0.20
OPPONENTS = (CHAMPION,) + tuple(EXTERNAL_ANCHORS)

#: The raw per-game readings, committed so the tables re-derive without replaying.
RECORD = os.path.join(os.path.dirname(__file__), "scoreboard", "trigger_readings.json")


def behind(ours, theirs, margin_pct):
    """Strictly behind by `margin_pct` percent: exactly at the line is not behind."""
    return ours < theirs * (1 - margin_pct / 100)


def census_on_day(turns, day):
    """The day's closing census, raising when the game never reached it: "the
    run stopped early" and "nobody was behind" must not read the same."""
    census = last_census_on_day(turns, day)
    if census is None:
        raise ValueError(f"no census recorded on day {day}: the game covers days "
                         f"{turns[0][0]}-{turns[-1][0]}" if turns else
                         f"no census recorded on day {day}: no turns at all")
    return census


def game_reading(ours_turns, theirs_turns, opponent, seed, days=DAYS):
    """One game's numbers: both sides' money and the asymmetry at each declared
    day (JSON-friendly: day keys are strings), and the final result."""
    at = {}
    for day in days:
        ours, theirs = census_on_day(ours_turns, day), census_on_day(theirs_turns, day)
        at[str(day)] = {
            "ours": ours["money"], "theirs": theirs["money"],
            "strawberry_gap": theirs["planted"].get("STRAWBERRY", 0) - ours["planted"].get("STRAWBERRY", 0),
            "head_gap": theirs["head_placed"] - ours["head_placed"],
        }
    final_ours, final_theirs = ours_turns[-1][1]["money"], theirs_turns[-1][1]["money"]
    result = "loss" if final_ours < final_theirs else ("win" if final_ours > final_theirs else "tie")
    return {"opponent": opponent, "seed": seed, "at": at,
            "final_ours": final_ours, "final_theirs": final_theirs, "result": result}


def _row(readings, day, margin):
    fired = [r for r in readings if behind(r["at"][str(day)]["ours"], r["at"][str(day)]["theirs"], margin)]
    wins = [r for r in readings if r["result"] == "win"]
    losses = [r for r in readings if r["result"] == "loss"]
    fired_wins = [r for r in fired if r["result"] == "win"]
    fired_losses = [r for r in fired if r["result"] == "loss"]
    games = len(readings)
    return {
        "games": games,
        "fired": len(fired),
        "fire_rate": len(fired) / games if games else None,
        "precision": len(fired_losses) / len(fired) if fired else None,
        # No wins: there is nothing for the trigger to harm -- 0, not unknown.
        "harm": len(fired_wins) / len(wins) if wins else 0.0,
        "recall": len(fired_losses) / len(losses) if losses else None,
    }


def tabulate(readings, days=DAYS, margins=MARGINS):
    """``{(day, margin): {opponent: row, ..., "pooled": row}}``, champion first."""
    opponents = sorted({r["opponent"] for r in readings}, key=lambda n: (n != CHAMPION, n))
    table = {}
    for day in days:
        for margin in margins:
            cell = {opp: _row([r for r in readings if r["opponent"] == opp], day, margin)
                    for opp in opponents}
            cell["pooled"] = _row(readings, day, margin)
            table[(day, margin)] = cell
    return table


def actionable(row):
    """The declared bars: fires often enough, and rarely on a game we win."""
    return (row["fire_rate"] is not None and row["fire_rate"] >= FIRE_BAR
            and row["harm"] is not None and row["harm"] <= HARM_BAR)


def _pct(x):
    return "   -" if x is None else f"{x:4.0%}"


def format_table(table):
    """One block per (day, margin): a line per opponent, then pooled; `*` marks actionable."""
    lines = []
    for (day, margin), cell in table.items():
        lines.append(f"day {day}  behind by >= {margin}%")
        lines.append(f"{'opponent':<46} {'games':>5} {'fired':>5} {'fire':>5} {'prec':>5} {'harm':>5} {'recall':>6}")
        for name, r in cell.items():
            mark = " *" if actionable(r) else ""
            lines.append(f"{name:<46} {r['games']:>5} {r['fired']:>5} {_pct(r['fire_rate']):>5} "
                         f"{_pct(r['precision']):>5} {_pct(r['harm']):>5} {_pct(r['recall']):>6}{mark}")
        lines.append("")
    return "\n".join(lines).rstrip()


def format_asymmetry(readings, days=DAYS):
    """Per opponent and day, the median of (rival minus ours) for strawberry tiles and head placed."""
    opponents = sorted({r["opponent"] for r in readings}, key=lambda n: (n != CHAMPION, n))
    lines = [f"{'opponent':<46} " + " ".join(f"{'d' + str(d) + ' straw/head':>16}" for d in days)]
    for opp in opponents:
        mine = [r for r in readings if r["opponent"] == opp]
        cells = []
        for day in days:
            straw = statistics.median(r["at"][str(day)]["strawberry_gap"] for r in mine)
            head = statistics.median(r["at"][str(day)]["head_gap"] for r in mine)
            cells.append(f"{straw:+.0f}/{head:+.0f}".rjust(16))
        lines.append(f"{opp:<46} " + " ".join(cells))
    return "\n".join(lines)


# --- live games -------------------------------------------------------------

def run(seeds=SEEDS, opponents=OPPONENTS):  # pragma: no cover
    """Play every (opponent, seed) once, sides alternated by seed parity, and
    read both farms' census. Externals are pinned/verified and fresh per game
    (#247); `census_series` calls an agent with the observation alone, so each
    external is handed (obs, configuration) and the wrapper trims to its arity."""
    os.environ.setdefault("ROBRICULTURE_STRICT", "1")
    from kaggle_environments import make
    from harness.external_pool import external_anchor_agents
    from harness.farm_census import census_series
    from kaggisim.strategy import make_agent
    from strategies import load

    config = make("kaggriculture").configuration
    external_names = [n for n in opponents if n != CHAMPION]
    externals = external_anchor_agents(external_names) if external_names else {}
    readings = []
    for opponent in opponents:
        for seed in seeds:
            us = make_agent(load(CHAMPION)())
            if opponent == CHAMPION:
                them = make_agent(load(CHAMPION)())
            else:
                wrapper = externals[opponent].fresh()
                them = (lambda obs, w=wrapper: w(obs, config))
            if seed % 2 == 0:
                ours, theirs = census_series(us, them, seed)
            else:
                theirs, ours = census_series(them, us, seed)
            reading = game_reading(ours, theirs, opponent, seed)
            readings.append(reading)
            print(f"{opponent:<46} seed {seed} {reading['result']:<4} "
                  f"{reading['final_ours']:>8.0f} vs {reading['final_theirs']:>8.0f}", flush=True)
    return readings


def main(argv=None):  # pragma: no cover
    ap = argparse.ArgumentParser(description="scoreboard trigger control (#197, Stage 1)")
    ap.add_argument("--record", default=RECORD, help="where the raw readings are written / read")
    ap.add_argument("--from-record", action="store_true", help="re-derive the tables without replaying")
    args = ap.parse_args(argv)

    if args.from_record:
        with open(args.record) as f:
            readings = json.load(f)["readings"]
    else:
        readings = run()
        os.makedirs(os.path.dirname(args.record), exist_ok=True)
        with open(args.record, "w") as f:
            json.dump({"champion": CHAMPION, "seeds": list(SEEDS), "days": list(DAYS),
                       "margins": list(MARGINS), "fire_bar": FIRE_BAR, "harm_bar": HARM_BAR,
                       "readings": readings}, f, indent=1)
        print(f"record written: {args.record}")

    print(format_table(tabulate(readings)))
    print()
    print("asymmetry, median of rival minus ours (strawberry tiles / head placed):")
    print(format_asymmetry(readings))
    cells = [(d, m) for (d, m), cell in tabulate(readings).items() if actionable(cell["pooled"])]
    print(f"actionable pooled cells (fire >= {FIRE_BAR:.0%}, harm <= {HARM_BAR:.0%}): {cells or 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run green, with coverage**

Run: `.venv/bin/python -m pytest -q -n auto --cov --cov-branch --cov-report=term-missing 2>&1 | grep -E "scoreboard_probe|passed|failed"`
Expected: all pass; `harness/scoreboard_probe.py` fully covered outside the two `# pragma: no cover` functions.

- [ ] **Step 5: Commit**

```bash
git add harness/scoreboard_probe.py tests/test_scoreboard_probe.py
git commit -m "scoreboard_probe: the #197 trigger control -- fire, precision, harm, recall per (day, margin) on spent seeds

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

## Self-review

- **Spec coverage.** Constants, grid, definitions (strict behind, loss/win/tie), readings (fire/precision/harm/recall per opponent and pooled), asymmetry medians, bars and the `actionable` marker, the committed JSON record and `--from-record`, sides alternated by seed parity, externals fresh per game with the `(obs, config)` wrapper: all in Task 1. The live run, the issue comment and the close are the controller's.
- **Placeholders.** None.
- **Type consistency.** `game_reading` keys (`at[str(day)]` with `ours/theirs/strawberry_gap/head_gap`, `result`) are what `_row`, `tabulate` and `format_asymmetry` read and what the tests fabricate; `tabulate` keys are `(day, margin)` tuples with string opponent names plus `"pooled"`, as `format_table` and `main` consume.
