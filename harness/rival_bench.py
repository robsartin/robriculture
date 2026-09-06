"""#219: does buying cows when the rival runs sheep beat the champion?

    python -m harness.rival_bench --controls      # the three spec controls, ~2 min
    python -m harness.rival_bench --criterion     # 16 seeds x 7 opponents, ~8 min
    python -m harness.rival_bench                 # both, controls first

Declared before code (docs/superpowers/specs/2026-09-06-rival-aware-herd-design.md):
seeds 400-415, sides alternated by list position (`harness.triage.head_to_head_rate`),
PROMOTE only at >= 60% of 16 vs the champion AND >= 90% vs each DEFAULT_ANCHOR;
a tie is not a win. Controls run first and a failed control voids the run.
Exit codes: 0 PROMOTE, 1 REJECTED, 2 VOID. Runs under ROBRICULTURE_STRICT=1.
"""

from __future__ import annotations

import argparse
import os

from harness.evolve import DEFAULT_ANCHORS

CHAMPION = "dense_farm"
CONTENDER = "rival_aware"
SEEDS = tuple(range(400, 416))
CHAMPION_BAR = 0.60
ANCHOR_BAR = 0.90
CONTROL_SEED = 400
QUIET_RIVAL = "wheat_hands"        # places no SHEEP (it does buy cows)


def animal_buys(actions):
    """{kind: count} of BUY_ANIMAL orders across a list of action dicts."""
    counts = {}
    for action in actions:
        for order in action.get("market", []):
            if order and order[0] == "BUY_ANIMAL" and len(order) >= 2:
                counts[order[1]] = counts.get(order[1], 0) + 1
    return counts


def mechanism_fired(contender_counts, baseline_counts):
    """More cows AND fewer sheep than the baseline, strictly."""
    return (contender_counts.get("COW", 0) > baseline_counts.get("COW", 0)
            and contender_counts.get("SHEEP", 0) < baseline_counts.get("SHEEP", 0))


def _rate(row):
    games = row["games"]
    return row["wins"] / games if games else 0.0


def criterion(champion_row, anchor_rows, champion_bar=CHAMPION_BAR, anchor_bar=ANCHOR_BAR):
    """The declared verdict: both bars, ties never wins."""
    champion_rate = _rate(champion_row)
    anchor_rates = {r["opponent"]: _rate(r) for r in anchor_rows}
    failing = ([champion_row["opponent"]] if champion_rate < champion_bar else []) + \
              [n for n, rate in anchor_rates.items() if rate < anchor_bar]
    return {"passed": not failing, "champion_rate": champion_rate,
            "anchor_rates": anchor_rates, "failing": failing}


def format_rows(rows):
    lines = [f"{'opponent':<16} {'wins':>7} {'ties':>4} {'rate':>6}"]
    for r in rows:
        lines.append(f"{r['opponent']:<16} {r['wins']:>3}/{r['games']:<3} {r.get('ties', 0):>4} "
                     f"{_rate(r):>6.1%}")
    return "\n".join(lines)


# --- live games -------------------------------------------------------------

def action_stream(strategy_name, opponent_name, seed, episode_steps=720):  # pragma: no cover
    """Our per-turn actions in seat 0 against `opponent_name`, plus the rival's
    placed-animal counts at the end (the precondition for control 2)."""
    from kaggle_environments import make
    from kaggisim.strategy import make_agent
    from strategies import load
    env = make("kaggriculture", configuration={"episodeSteps": episode_steps, "seed": seed})
    env.reset(2)
    ours = make_agent(load(strategy_name)())
    theirs = make_agent(load(opponent_name)())
    actions = []
    for _ in range(episode_steps - 1):
        act0 = ours(env.state[0].observation)
        actions.append(act0)
        env.step([act0, theirs(env.state[1].observation)])
    rival = env.state[1].observation["farms"][1]["tiles"]
    placed = {}
    for row in rival:
        for t in row:
            if isinstance(t, dict) and t.get("animal"):
                placed[t["animal"]] = placed.get(t["animal"], 0) + 1
    return actions, placed


def run_controls(seed=CONTROL_SEED):  # pragma: no cover
    os.environ.setdefault("ROBRICULTURE_STRICT", "1")   # an instrument surfaces crashes
    from harness.tournament import play_rewards
    from kaggisim.strategy import make_agent
    from strategies import load
    out = {}
    # 1. identity with the threshold off
    off = type("Off", (load(CONTENDER),), {"THRESHOLD": 10 ** 9})
    base = play_rewards(make_agent(load(CHAMPION)()), make_agent(load(CHAMPION)()), seed)
    got = play_rewards(make_agent(off()), make_agent(load(CHAMPION)()), seed)
    # Positive control: base[0] > 0 is the identity control's own precondition
    # -- if no money moved, "got == base" is a vacuous match, not evidence.
    precondition_ok = base[0] > 0
    out["identity"] = {"ok": got == base and precondition_ok, "base": base, "got": got,
                       "precondition_ok": precondition_ok}
    # 2. mechanism fires against the champion (which runs sheep when rich)
    c_actions, rival_placed = action_stream(CONTENDER, CHAMPION, seed)
    b_actions, _ = action_stream(CHAMPION, CHAMPION, seed)
    c_counts, b_counts = animal_buys(c_actions), animal_buys(b_actions)
    out["mechanism"] = {"ok": rival_placed.get("SHEEP", 0) >= 2 and mechanism_fired(c_counts, b_counts),
                        "rival_sheep_placed": rival_placed.get("SHEEP", 0),
                        "contender": c_counts, "baseline": b_counts}
    # 3. quiet against a rival with no sheep: identical action stream
    q_actions, q_placed = action_stream(CONTENDER, QUIET_RIVAL, seed)
    qb_actions, _ = action_stream(CHAMPION, QUIET_RIVAL, seed)
    out["quiet"] = {"ok": q_placed.get("SHEEP", 0) == 0 and q_actions == qb_actions,
                    "rival_sheep_placed": q_placed.get("SHEEP", 0)}
    return out


def run_criterion(seeds=SEEDS):  # pragma: no cover
    os.environ.setdefault("ROBRICULTURE_STRICT", "1")   # an instrument surfaces crashes
    from harness.triage import head_to_head_rate
    champion_row = head_to_head_rate(CONTENDER, CHAMPION, seeds)
    anchor_rows = [head_to_head_rate(CONTENDER, a, seeds) for a in DEFAULT_ANCHORS]
    return champion_row, anchor_rows


def main(argv=None):  # pragma: no cover
    os.environ.setdefault("ROBRICULTURE_STRICT", "1")   # an instrument surfaces crashes
    ap = argparse.ArgumentParser(description="#219 rival-aware herd: controls and criterion")
    ap.add_argument("--controls", action="store_true")
    ap.add_argument("--criterion", action="store_true")
    args = ap.parse_args(argv)
    do_controls = args.controls or not args.criterion
    do_criterion = args.criterion or not args.controls

    if do_controls:
        ctl = run_controls()
        for name, r in ctl.items():
            print(f"control {name}: {'OK' if r['ok'] else 'FAIL -- RUN VOID'}  {r}")
        if not all(r["ok"] for r in ctl.values()):
            return 2
    if do_criterion:
        champion_row, anchor_rows = run_criterion()
        print(format_rows([champion_row] + anchor_rows))
        v = criterion(champion_row, anchor_rows)
        print(f"champion {v['champion_rate']:.1%} (bar {CHAMPION_BAR:.0%}); anchors below {ANCHOR_BAR:.0%}: "
              f"{v['failing'] or 'none'} -> {'PROMOTE' if v['passed'] else 'REJECTED'}")
        return 0 if v["passed"] else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
