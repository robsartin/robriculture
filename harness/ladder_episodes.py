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
        seats = [i for i, a in enumerate(agents) if a.get("submissionId") == submission_id]
        if not seats or len(agents) < 2:
            continue
        seat = seats[0]
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
        return {"planted": None, "animals": None, "cows": None, "sheep": None,
                "hands": hands_on_day(steps, seat, day)}
    animals = animals_placed(board["tiles"])
    return {"planted": sum(planted_by_crop(board["tiles"]).values()),
            "animals": sum(animals.values()),
            "cows": animals.get("COW", 0), "sheep": animals.get("SHEEP", 0),
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
    """Median per key over the dicts; a key absent from a dict counts as 0
    (a game that sold no MILK sold 0 MILK)."""
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
    if not readings:
        return {"games": 0, "ours": None, "theirs": None}
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
    return (f"day8 {d8['planted']}/{d8['animals']}/{d8['hands']} ({d8.get('cows')}c+{d8.get('sheep')}s)  "
            f"day16 {d16['planted']}/{d16['animals']}/{d16['hands']} ({d16.get('cows')}c+{d16.get('sheep')}s)  "
            f"revenue {s['revenue_total']:.0f} ({', '.join(f'{k} {v:.0f}' for k, v in top)})  "
            f"spend {s['spend_total']:.0f} ({', '.join(f'{k} {v:.0f}' for k, v in s['spend'].items() if v)})  "
            f"final {s['final_money']:.0f}  residual {s['residual']:.0f}")


def format_readings(label, summary) -> str:
    if not summary["games"]:
        return f"{label} (n=0)"
    return (f"{label} (n={summary['games']}; planted/animals/hands, cows+sheep)\n"
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
