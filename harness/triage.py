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
        lines.append(f"{i} {r['name']:<18} {r['score']:>10.1f}  {seeds}  ({r['seconds']:.1f})")
    return "\n".join(lines)
