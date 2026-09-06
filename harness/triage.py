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

import json
import os
import time

from harness.ladder_correlation import spearman

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
        lines.append(f"{i} {r['name']:<18} {r['score']:>10.1f}  {seeds}  ({r['seconds']:.1f})")
    return "\n".join(lines)


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
