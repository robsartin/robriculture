# ladder_episodes (#266) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A committed tool that turns a submission's rated Kaggle episodes into the #157 readings — record, opponents, reward-band win-rate, and a both-sides decomposition of losses and matched wins from downloaded replays.

**Architecture:** `harness/ladder_episodes.py`: pure functions over the episode listing (dicts as `ApiEpisode.to_json()` gives them) and over replay `steps` (the same shape as `env.steps`, which `harness.episode_analysis.decompose` and `harness.feed_bench.board_on_day` already read); one thin `# pragma: no cover` layer talks to `KaggleApi`. Tables are printed for pasting onto the issue.

**Tech Stack:** Python 3.12, `.venv/bin/python`, pytest, `kaggle` 2.2.4 (`KaggleApi.competition_list_episodes(submission_id=...)`, `competition_episode_replay(episode_id, path=...)`).

## Global Constraints

- Pure TDD: failing test first, RUN it and observe the failure, then the code; the report quotes the red.
- `.venv/bin/python` only; every command blocking; the full suite (`.venv/bin/python -m pytest -q`, ~5 min) green before the commit.
- Stage by explicit path; never `git add -A`; never stage `replays/`, `.venv`, `external_agents`.
- Do not edit `harness/episode_analysis.py`, `harness/feed_bench.py`, `harness/farm_census.py`.
- Facts of the API, verbatim: an episode dict has `id`, `createTime`, `endTime`, `state` (`"COMPLETED"`), `type` (`"EPISODE_TYPE_PUBLIC"` or `"EPISODE_TYPE_VALIDATION"`), `agents` (list, in seat order, each `{"submissionId", "reward", "teamName", "teamId"}`; JSON drops zero/absent fields, so read with `.get`). A validation episode pairs the submission with itself: both agents carry our `submissionId`; skip those. Replay JSON has `steps`: a list of 720 lists of slot dicts `{"action", "info", "observation", "reward", "status"}`; the observation has `day`, `farms`, `player`, `market`, ....
- Reward bands for reading 3: 10,000 wide from 0 (`0-10K`, `10-20K`, ...), as #157's table.
- Replays go to `replays/` (gitignored) as `episode-<id>-replay.json`; never re-download an existing file.

---

### Task 1: The tool

**Files:**
- Create: `harness/ladder_episodes.py`
- Test: `tests/test_ladder_episodes.py`

**Interfaces:**
- Consumes: `harness.episode_analysis.decompose(steps, player) -> {"revenue", "spend", "actions", "final_money", "residual"}`; `harness.feed_bench.board_on_day(steps, player, day)` (a farm dict with `tiles`, or None) and `hands_on_day(steps, player, day)`; `harness.farm_census.planted_by_crop(tiles)`, `animals_placed(tiles)` (dicts by crop / animal kind).
- Produces: `episode_rows(episodes, submission_id) -> list[dict]`, `record(rows) -> dict`, `by_opponent(rows) -> list[dict]`, `by_reward_band(rows, width=10_000) -> list[dict]`, `losses(rows)`, `matched_wins(rows, n)`, `replay_path(directory, episode_id)`, `side_reading(steps, seat) -> dict`, `episode_reading(steps, row) -> dict` with `"ours"` and `"theirs"`, `summarise(readings) -> dict`, `format_record`, `format_opponents`, `format_bands`, `format_readings`, `main(argv)`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_ladder_episodes.py
"""The ladder-episode readings (#266): the record, opponents and reward bands
off the episode listing, and the both-sides reading off a replay's steps.
Fixtures are the API's own shapes; no network, no replay files."""

from __future__ import annotations

from harness import ladder_episodes as le

ME = 56153224


def _ep(eid, agents, etype="EPISODE_TYPE_PUBLIC", state="COMPLETED"):
    return {"id": eid, "createTime": "2026-09-12T13:50:35.378Z", "endTime": "2026-09-12T13:56:43.026Z",
            "state": state, "type": etype, "agents": agents}


def _ag(sub, reward, team, team_id=1):
    return {"submissionId": sub, "reward": reward, "teamName": team, "teamId": team_id}


EPISODES = [
    _ep(1, [_ag(ME, 96400, "Rob Sartin", 9), _ag(777, 56060, "Women or something", 1)]),
    _ep(2, [_ag(778, 154838, "Sergey Kutepov", 2), _ag(ME, 71174, "Rob Sartin", 9)]),
    _ep(3, [_ag(ME, 5000, "Rob Sartin", 9), _ag(777, 5000, "Women or something", 1)]),
    _ep(4, [_ag(ME, 96400, "Rob Sartin", 9), _ag(ME, 96400, "Rob Sartin", 9)], etype="EPISODE_TYPE_VALIDATION"),
    _ep(5, [_ag(779, None, "Pending", 3), _ag(ME, None, "Rob Sartin", 9)], state="RUNNING"),
    _ep(6, [_ag(778, 20000, "Sergey Kutepov", 2), _ag(ME, 38797, "Rob Sartin", 9)]),
]


def test_episode_rows_skip_self_matches_and_unfinished_games_and_keep_the_seat():
    rows = le.episode_rows(EPISODES, ME)
    assert [r["episode"] for r in rows] == [1, 2, 3, 6]
    assert rows[0] == {"episode": 1, "seat": 0, "ours": 96400, "theirs": 56060, "margin": 40340,
                       "opponent": "Women or something", "team_id": 1, "outcome": "W"}
    assert rows[1]["seat"] == 1 and rows[1]["outcome"] == "L" and rows[1]["margin"] == -83664
    assert rows[2]["outcome"] == "T"


def test_record_counts_wins_losses_ties_and_reward_stats():
    rows = le.episode_rows(EPISODES, ME)
    rec = le.record(rows)
    assert (rec["wins"], rec["losses"], rec["ties"], rec["games"]) == (2, 1, 1, 4)
    assert rec["win_rate"] == 0.5
    assert (rec["reward_min"], rec["reward_median"], rec["reward_max"]) == (5000, 55000.5, 96400)
    assert rec["median_margin"] == 9585.0  # margins 40340, -83664, 0, 18797 -> median of the middle two


def test_by_opponent_groups_and_orders_by_games_then_name():
    rows = le.episode_rows(EPISODES, ME)
    groups = le.by_opponent(rows)
    assert groups[0] == {"opponent": "Sergey Kutepov", "team_id": 2, "games": 2, "wins": 1, "losses": 1, "ties": 0}
    assert groups[1] == {"opponent": "Women or something", "team_id": 1, "games": 2, "wins": 1, "losses": 0, "ties": 1}


def test_by_reward_band_is_10k_wide_from_zero_with_win_rate():
    rows = le.episode_rows(EPISODES, ME)
    bands = le.by_reward_band(rows)
    assert bands[0] == {"band": "0-10K", "games": 1, "wins": 0, "win_rate": 0.0}
    assert bands[1] == {"band": "30-40K", "games": 1, "wins": 1, "win_rate": 1.0}
    assert bands[2] == {"band": "70-80K", "games": 1, "wins": 0, "win_rate": 0.0}
    assert bands[3] == {"band": "90-100K", "games": 1, "wins": 1, "win_rate": 1.0}


def test_losses_and_matched_wins():
    rows = le.episode_rows(EPISODES, ME)
    assert [r["episode"] for r in le.losses(rows)] == [2]
    # matched wins: the n wins closest to the losses' median own-reward (71174) -> episode 6 (38797) before 1 (96400)? no: |96400-71174|=25226 < |38797-71174|=32377
    assert [r["episode"] for r in le.matched_wins(rows, 1)] == [1]
    assert [r["episode"] for r in le.matched_wins(rows, 5)] == [1, 6]


def test_replay_path():
    assert le.replay_path("replays", 108090526) == "replays/episode-108090526-replay.json"


def _tile(kind=None, crop=None, animal=None):
    t = {}
    if kind: t["kind"] = kind
    if crop: t["crop"] = crop
    if animal: t["animal"] = animal
    return t


def test_side_reading_reads_day_boards_and_the_decomposition(monkeypatch):
    boards = {8: {"tiles": [[_tile("PLANT", "MELON"), _tile(animal="COW")]]},
              16: {"tiles": [[_tile("PLANT", "MELON"), _tile("PLANT", "STRAWBERRY"), _tile(animal="COW"), _tile(animal="SHEEP")]]}}
    monkeypatch.setattr(le, "board_on_day", lambda steps, seat, day: boards.get(day))
    monkeypatch.setattr(le, "hands_on_day", lambda steps, seat, day: {8: 6, 16: 9}[day])
    monkeypatch.setattr(le, "decompose", lambda steps, seat: {
        "revenue": {"MELON": 30000, "MILK": 5000}, "spend": {"seed": 800, "hire": 4000, "land": 1000, "animal": 1900, "product": 600},
        "actions": {"WATER": 100}, "final_money": 40000.0, "residual": -12.0})
    r = le.side_reading("steps", 1)
    assert r["day8"] == {"planted": 1, "animals": 1, "hands": 6}
    assert r["day16"] == {"planted": 2, "animals": 2, "hands": 9}
    assert r["revenue"] == {"MELON": 30000, "MILK": 5000} and r["revenue_total"] == 35000
    assert r["spend"]["hire"] == 4000 and r["spend_total"] == 8300
    assert r["final_money"] == 40000.0 and r["residual"] == -12.0


def test_episode_reading_puts_us_in_ours_by_seat(monkeypatch):
    monkeypatch.setattr(le, "side_reading", lambda steps, seat: {"seat": seat})
    row = {"episode": 2, "seat": 1, "ours": 71174, "theirs": 154838, "margin": -83664,
           "opponent": "Sergey Kutepov", "team_id": 2, "outcome": "L"}
    r = le.episode_reading("steps", row)
    assert r["ours"] == {"seat": 1} and r["theirs"] == {"seat": 0} and r["row"] is row


def test_summarise_takes_medians_over_readings():
    readings = [
        {"row": {"outcome": "L"}, "ours": {"day8": {"planted": 20, "animals": 4, "hands": 6}, "day16": {"planted": 30, "animals": 8, "hands": 9},
                                          "revenue": {"MELON": 10000}, "revenue_total": 10000, "spend": {"hire": 3000}, "spend_total": 3000, "final_money": 30000, "residual": 0},
         "theirs": {"day8": {"planted": 10, "animals": 8, "hands": 5}, "day16": {"planted": 12, "animals": 12, "hands": 8},
                    "revenue": {"MILK": 40000}, "revenue_total": 40000, "spend": {"animal": 9000}, "spend_total": 9000, "final_money": 90000, "residual": 500}},
        {"row": {"outcome": "L"}, "ours": {"day8": {"planted": 22, "animals": 4, "hands": 6}, "day16": {"planted": 34, "animals": 10, "hands": 10},
                                          "revenue": {"MELON": 14000}, "revenue_total": 14000, "spend": {"hire": 3200}, "spend_total": 3200, "final_money": 34000, "residual": 0},
         "theirs": {"day8": {"planted": 12, "animals": 10, "hands": 5}, "day16": {"planted": 14, "animals": 14, "hands": 8},
                    "revenue": {"MILK": 50000}, "revenue_total": 50000, "spend": {"animal": 11000}, "spend_total": 11000, "final_money": 100000, "residual": 700}},
    ]
    s = le.summarise(readings)
    assert s["games"] == 2
    assert s["ours"]["day8"] == {"planted": 21, "animals": 4, "hands": 6}
    assert s["theirs"]["day16"] == {"planted": 13, "animals": 13, "hands": 8}
    assert s["ours"]["revenue_total"] == 12000 and s["theirs"]["revenue_total"] == 45000
    assert s["theirs"]["revenue"] == {"MILK": 45000} and s["ours"]["spend"] == {"hire": 3100}
    assert s["theirs"]["residual"] == 600


def test_formatters_render_tables():
    rows = le.episode_rows(EPISODES, ME)
    out = le.format_record(le.record(rows))
    assert "21W" not in out and "2W 1L 1T" in out and "0.500" in out
    assert "Sergey Kutepov" in le.format_opponents(le.by_opponent(rows))
    assert "90-100K" in le.format_bands(le.by_reward_band(rows))
```

- [ ] **Step 2: Run the tests and observe them fail**

Run: `.venv/bin/python -m pytest tests/test_ladder_episodes.py -q`
Expected: collection error, `ImportError`/`ModuleNotFoundError` for `harness.ladder_episodes`. Quote it.

- [ ] **Step 3: Write `harness/ladder_episodes.py`**

```python
"""Mine a submission's rated ladder episodes (#266; the #157 method, committed).

The episode listing alone gives the record: every rated game's rewards, seats
and the opponent's team. Replays give the mechanism: `episode_analysis.decompose`
on both sides plus the day-8 / day-16 boards. Validation episodes (the
submission against itself) and unfinished games are skipped.

    .venv/bin/python -m harness.ladder_episodes --submission 56153224            # record + opponents + bands
    .venv/bin/python -m harness.ladder_episodes --submission 56153224 --decompose  # + losses and matched wins off replays
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys

from harness.episode_analysis import decompose
from harness.farm_census import animals_placed, planted_by_crop
from harness.feed_bench import board_on_day, hands_on_day

DAYS = (8, 16)
REPLAY_DIR = "replays"


def episode_rows(episodes, submission_id) -> list:
    """One row per rated, finished game against someone else, in listing order."""
    rows = []
    for e in episodes:
        agents = e.get("agents") or []
        if e.get("state") != "COMPLETED" or len({a.get("submissionId") for a in agents}) < 2:
            continue
        seat = next(i for i, a in enumerate(agents) if a.get("submissionId") == submission_id)
        me, them = agents[seat], agents[1 - seat]
        ours, theirs = me.get("reward"), them.get("reward")
        if ours is None or theirs is None:
            continue
        outcome = "W" if ours > theirs else "L" if ours < theirs else "T"
        rows.append({"episode": e["id"], "seat": seat, "ours": ours, "theirs": theirs,
                     "margin": ours - theirs, "opponent": them.get("teamName"),
                     "team_id": them.get("teamId"), "outcome": outcome})
    return rows


def record(rows) -> dict:
    ours = [r["ours"] for r in rows]
    wins = sum(r["outcome"] == "W" for r in rows)
    losses = sum(r["outcome"] == "L" for r in rows)
    ties = len(rows) - wins - losses
    return {"wins": wins, "losses": losses, "ties": ties, "games": len(rows),
            "win_rate": wins / len(rows) if rows else 0.0,
            "reward_min": min(ours) if ours else None,
            "reward_median": statistics.median(ours) if ours else None,
            "reward_max": max(ours) if ours else None,
            "median_margin": statistics.median(r["margin"] for r in rows) if rows else None}


def by_opponent(rows) -> list:
    groups: dict = {}
    for r in rows:
        g = groups.setdefault((r["opponent"], r["team_id"]),
                              {"opponent": r["opponent"], "team_id": r["team_id"],
                               "games": 0, "wins": 0, "losses": 0, "ties": 0})
        g["games"] += 1
        g[{"W": "wins", "L": "losses", "T": "ties"}[r["outcome"]]] += 1
    return sorted(groups.values(), key=lambda g: (-g["games"], g["opponent"] or ""))


def by_reward_band(rows, width=10_000) -> list:
    bands: dict = {}
    for r in rows:
        lo = (r["ours"] // width) * width
        b = bands.setdefault(lo, {"band": f"{lo // 1000}-{(lo + width) // 1000}K", "games": 0, "wins": 0})
        b["games"] += 1
        b["wins"] += r["outcome"] == "W"
    out = []
    for lo in sorted(bands):
        b = bands[lo]
        out.append({**b, "win_rate": b["wins"] / b["games"]})
    return out


def losses(rows) -> list:
    return [r for r in rows if r["outcome"] == "L"]


def matched_wins(rows, n) -> list:
    """The `n` wins whose own reward is closest to the losses' median own reward."""
    lost = losses(rows)
    wins = [r for r in rows if r["outcome"] == "W"]
    if not lost or not wins:
        return wins[:n]
    centre = statistics.median(r["ours"] for r in lost)
    return sorted(wins, key=lambda r: (abs(r["ours"] - centre), r["episode"]))[:n]


def replay_path(directory, episode_id) -> str:
    return os.path.join(directory, f"episode-{episode_id}-replay.json")


def _board(steps, seat, day) -> dict:
    board = board_on_day(steps, seat, day)
    if board is None:
        return {"planted": None, "animals": None, "hands": hands_on_day(steps, seat, day)}
    return {"planted": sum(planted_by_crop(board["tiles"]).values()),
            "animals": sum(animals_placed(board["tiles"]).values()),
            "hands": hands_on_day(steps, seat, day)}


def side_reading(steps, seat) -> dict:
    d = decompose(steps, seat)
    return {"day8": _board(steps, seat, 8), "day16": _board(steps, seat, 16),
            "revenue": d["revenue"], "revenue_total": sum(d["revenue"].values()),
            "spend": d["spend"], "spend_total": sum(d["spend"].values()),
            "final_money": d["final_money"], "residual": d["residual"]}


def episode_reading(steps, row) -> dict:
    return {"row": row, "ours": side_reading(steps, row["seat"]),
            "theirs": side_reading(steps, 1 - row["seat"])}


def _median_dict(dicts) -> dict:
    keys = sorted({k for d in dicts for k in d})
    return {k: statistics.median(d.get(k, 0) for d in dicts) for k in keys}


def _median_side(sides) -> dict:
    return {"day8": _median_dict([s["day8"] for s in sides]),
            "day16": _median_dict([s["day16"] for s in sides]),
            "revenue": _median_dict([s["revenue"] for s in sides]),
            "revenue_total": statistics.median(s["revenue_total"] for s in sides),
            "spend": _median_dict([s["spend"] for s in sides]),
            "spend_total": statistics.median(s["spend_total"] for s in sides),
            "final_money": statistics.median(s["final_money"] for s in sides),
            "residual": statistics.median(s["residual"] for s in sides)}


def summarise(readings) -> dict:
    return {"games": len(readings),
            "ours": _median_side([r["ours"] for r in readings]),
            "theirs": _median_side([r["theirs"] for r in readings])}


def format_record(rec) -> str:
    return (f"{rec['wins']}W {rec['losses']}L {rec['ties']}T over {rec['games']} rated games, "
            f"win-rate {rec['win_rate']:.3f}; our reward min/median/max "
            f"{rec['reward_min']} / {rec['reward_median']} / {rec['reward_max']}; "
            f"median margin {rec['median_margin']}")


def format_opponents(groups) -> str:
    lines = ["| opponent | games | W | L | T |", "|---|---|---|---|---|"]
    lines += [f"| {g['opponent']} | {g['games']} | {g['wins']} | {g['losses']} | {g['ties']} |" for g in groups]
    return "\n".join(lines)


def format_bands(bands) -> str:
    lines = ["| our reward | games | won | win-rate |", "|---|---|---|---|"]
    lines += [f"| {b['band']} | {b['games']} | {b['wins']} | {b['win_rate']:.2f} |" for b in bands]
    return "\n".join(lines)


def _fmt_side(s) -> str:
    d8, d16 = s["day8"], s["day16"]
    top = sorted(s["revenue"].items(), key=lambda kv: -kv[1])[:4]
    return (f"day8 {d8['planted']}/{d8['animals']}/{d8['hands']}  day16 {d16['planted']}/{d16['animals']}/{d16['hands']}  "
            f"revenue {s['revenue_total']:.0f} ({', '.join(f'{k} {v:.0f}' for k, v in top)})  "
            f"spend {s['spend_total']:.0f} ({', '.join(f'{k} {v:.0f}' for k, v in s['spend'].items() if v)})  "
            f"final {s['final_money']:.0f}  residual {s['residual']:.0f}")


def format_readings(label, summary) -> str:
    return (f"{label} (n={summary['games']}; planted/animals/hands)\n"
            f"  ours:   {_fmt_side(summary['ours'])}\n"
            f"  theirs: {_fmt_side(summary['theirs'])}")


# ---- the API layer (never run by the tests) --------------------------------------

def list_episodes(api, submission_id):  # pragma: no cover
    return [json.loads(e.to_json()) for e in api.competition_list_episodes(submission_id=submission_id)]


def fetch_replay(api, episode_id, directory=REPLAY_DIR):  # pragma: no cover
    """Download a replay once; return its steps."""
    path = replay_path(directory, episode_id)
    if not os.path.exists(path):
        os.makedirs(directory, exist_ok=True)
        api.competition_episode_replay(episode_id, path=directory)
    with open(path) as fh:
        return json.load(fh)["steps"]


def main(argv=None):  # pragma: no cover
    ap = argparse.ArgumentParser(description="mine a submission's rated ladder episodes (#266)")
    ap.add_argument("--submission", type=int, required=True)
    ap.add_argument("--decompose", action="store_true", help="download replays for the losses and matched wins and decompose both sides")
    ap.add_argument("--replays", default=REPLAY_DIR)
    ap.add_argument("--json", default=None, help="write rows + readings here")
    args = ap.parse_args(argv)
    from kaggle.api.kaggle_api_extended import KaggleApi
    api = KaggleApi()
    api.authenticate()
    rows = episode_rows(list_episodes(api, args.submission), args.submission)
    print(format_record(record(rows)))
    print(format_opponents(by_opponent(rows)))
    print(format_bands(by_reward_band(rows)))
    out = {"rows": rows}
    if args.decompose:
        lost = losses(rows)
        won = matched_wins(rows, len(lost))
        readings = {}
        for label, group in (("losses", lost), ("matched wins", won)):
            group_readings = []
            for r in group:
                print(f"  {label}: episode {r['episode']} vs {r['opponent']} ({r['ours']} vs {r['theirs']})", file=sys.stderr)
                group_readings.append(episode_reading(fetch_replay(api, r["episode"], args.replays), r))
            readings[label] = group_readings
            print(format_readings(label, summarise(group_readings)))
        out["readings"] = readings
    if args.json:
        with open(args.json, "w") as fh:
            json.dump(out, fh, indent=1, default=str)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
```

- [ ] **Step 4: Run the tests and observe them pass**

Run: `.venv/bin/python -m pytest tests/test_ladder_episodes.py -q`
Expected: all PASS. If `test_record_counts_wins_losses_ties_and_reward_stats`'s medians disagree with the code by a rounding artefact, re-derive by hand from the fixture (rewards 96400, 71174, 5000, 38797; margins 40340, -83664, 0, 18797) and fix whichever is wrong, saying which.

- [ ] **Step 5: Full suite, commit**

Run: `.venv/bin/python -m pytest -q` (blocking, ~5 min).

```bash
git add harness/ladder_episodes.py tests/test_ladder_episodes.py
git commit -m "feat(#266): ladder_episodes — record, opponents, reward bands and both-sides decomposition of a submission's rated episodes

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```
