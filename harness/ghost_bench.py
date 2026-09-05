"""The ghost ladder (issue #204): bench the champion against 63 real rivals.

Every other bench in this repo scores our agents against agents we wrote. This
one replays the 63 downloaded ladder episodes (#157): the rival's recorded
actions are played back by `strategies.ghost.Ghost` while our champion plays
live, in the seat we actually sat in, under the seed the episode actually ran
under. That makes it the first bench here whose answer can be checked against
ground truth -- our real record over those 63 episodes is known.

**The positive control comes first.** A ghost that cannot reproduce its own
replay is not a ghost, so before any claim is made both seats are ghosted and
the re-drive is compared to the money the replay records. `episode_analysis`
reconstructs those replays by accounting to a median 7.3% residual, and #204
declares that same 7.3% as the control's tolerance, on at least 55 of 63.

**A ghost cannot react.** It plays its recorded sells whatever we do, so
anything that exploits passivity looks better here than it is. This is a
loss-mechanism bench and a calibration check, never a promotion gate.

Usage (replays are not in the repo -- they are downloaded, see #157):

    python -m harness.ghost_bench --replays <dir> --champion meta_rancher
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys

from strategies.field_rival import standing_crops
from strategies.ghost import Ghost, replay_actions

#: Our team name as the episode API records it, used to find which seat we sat in.
OUR_TEAM = "Rob Sartin"

# --- The criteria, declared in #204 before any code was written (ADR-0007) ---

#: `episode_analysis`'s median residual over these same replays; the control's
#: tolerance is deliberately the accuracy the existing reconstruction already has.
RESIDUAL_TOLERANCE = 0.073
#: Episodes of 63 that must land inside it for the control to pass.
CONTROL_MINIMUM = 55
#: Our real ladder win-rate as docs/findings.md records it, over 67 episodes.
LADDER_WIN_RATE = 0.403
WIN_RATE_TOLERANCE = 0.10
#: Criterion 1: share of ghost games in which the rival holds >= 10 melon tiles
#: at the day-8 probe.
TRIGGER_SHARE = 0.50
MELON_TRIGGER_TILES = 10

#: Day 8, mid-day. The replay medians in `strategies/field_rival.py` (11-12 melon
#: at day 8) are sampled mid-day, so the trigger is read at the same hour they
#: were measured at rather than at a boundary where a day's planting is half done.
#:
#: Validated as an instrument rather than assumed, twice. It reads 12 for
#: `field_rival` on seeds 0/1/2 -- that agent's own documented archetype -- and 0
#: for `starter`, so it both fires and can read zero. Run over the raw replays it
#: also reproduces the wins-vs-losses trigger split that docs/findings.md records
#: from #178, which is the measurement it has to be the same instrument as.
PROBE_STEP = 8 * 24 + 12

#: A full season, as the ladder runs it.
EPISODE_STEPS = 720


def episode_seed(replay):
    """The seed the episode actually ran under.

    A downloaded replay carries ``configuration.seed = null`` and the real seed
    in ``info.seed``. Without it the re-drive gets different weed spawns and the
    control is measuring the wrong thing, so a replay without one is reported
    rather than quietly benched.
    """
    seed = ((replay.get("info") or {}).get("seed"))
    return seed if isinstance(seed, int) else None


def seat_of(replay, team=OUR_TEAM):
    """Which player index `team` occupied. Raises if they did not play.

    We are player 0 in some of these episodes and player 1 in others. Defaulting
    to a seat would ghost our own agent and silently measure self-play.
    """
    names = list((replay.get("info") or {}).get("TeamNames") or [])
    if team not in names:
        raise ValueError(f"{team!r} did not play this episode; teams were {names}")
    return names.index(team)


def residual_fraction(reconstructed, recorded):
    """|reconstructed - recorded| / |recorded|, the scale the control judges on.

    A recorded zero cannot be divided into; an exact match there is 0.0 and
    anything else is reported as a whole-value miss rather than as a match.
    """
    recorded = float(recorded)
    gap = abs(float(reconstructed) - recorded)
    if recorded == 0:
        return 0.0 if gap == 0 else 1.0
    return gap / abs(recorded)


def standing_melon(steps, index, player):
    """Live melon tiles on `player`'s board at state `index`.

    Reads the shared observation, which both a downloaded replay and a live
    `kaggle_environments` env keep on player 0's slot. An episode shorter than
    the probe reports 0 rather than raising -- a crashed game grew no melon.
    """
    if index >= len(steps):
        return 0
    farms = ((steps[index][0].get("observation") or {}).get("farms")) or []
    if player >= len(farms):
        return 0
    return standing_crops(farms[player].get("tiles") or []).get("MELON", 0)


def win_rate(rows):
    """Wins over every episode benched.

    Wins only, and the denominator is every game played: that is how the
    ladder record this is compared against (20W-43L over these 63) was counted.
    """
    return sum(1 for row in rows if row["win"]) / len(rows) if rows else 0.0


def control_passed(residuals, tolerance=RESIDUAL_TOLERANCE, minimum=CONTROL_MINIMUM):
    """Did enough episodes reconstruct inside the declared residual?"""
    return sum(1 for r in residuals if r <= tolerance) >= minimum


def episode_digest(name, replay):
    """Everything the bench needs from a replay, with the observations dropped.

    A downloaded replay is ~21 MB on disk and far more once parsed; 63 of them
    resident at once made the run thrash before it finished a single season.
    What the bench actually needs is both players' action scripts, the seed, our
    seat and the recorded rewards -- a few hundred KB -- so the replay is
    digested at load and the parsed observations are released immediately.
    """
    return {
        "episode": name,
        "seed": episode_seed(replay),
        "seat": seat_of(replay),
        "rewards": [float(r or 0) for r in (replay.get("rewards") or [0.0, 0.0])],
        "scripts": [replay_actions(replay["steps"], 0),
                    replay_actions(replay["steps"], 1)],
    }


def ghost_players(digest):
    """Both seats of an episode as `kaggle_environments`-ready agent callables.

    A `Strategy` is not an agent -- it has to go through `make_agent`. Passing
    the Ghost objects straight to `env.run` ran a whole 63-episode control that
    came back "DONE" with both farms still holding their 3,000 starting money.
    """
    from kaggisim.strategy import make_agent
    return [make_agent(Ghost(script)) for script in digest["scripts"]]


# --- Full-game entrypoints: 63 seasons a run, integration by nature ---


def load_digests(directory):  # pragma: no cover
    """Digest every downloaded replay in `directory`, one resident at a time."""
    out = []
    for path in sorted(glob.glob(os.path.join(directory, "*.json"))):
        with open(path) as handle:
            replay = json.load(handle)
        out.append(episode_digest(os.path.basename(path), replay))
        del replay
    return out


def _make_env(seed):  # pragma: no cover
    from kaggle_environments import make
    config = {"episodeSteps": EPISODE_STEPS}
    if seed is not None:
        config["seed"] = seed
    # Only episodeSteps and seed are set: every other value in the replay's
    # recorded configuration is already the env default, and the recorded
    # actTimeout of 1s is a ladder limit that would make a local run flaky.
    return make("kaggriculture", configuration=config)


def control_row(digest):  # pragma: no cover
    """Ghost BOTH seats and re-drive the episode: the #204 positive control.

    Both sides must be ghosted. The two farms sell into one shared market, so a
    ghost whose opponent plays anything else is not reproducing its replay --
    it is playing a different game with the same opening moves.
    """
    env = _make_env(digest["seed"])
    env.run(ghost_players(digest))
    got = [s.reward or 0 for s in env.steps[-1]]
    us = digest["seat"]
    rival = 1 - us
    return {
        "episode": digest["episode"],
        "seed": digest["seed"],
        "rival_residual": residual_fraction(got[rival], digest["rewards"][rival]),
        "our_residual": residual_fraction(got[us], digest["rewards"][us]),
        "recorded": digest["rewards"],
        "replayed": got,
        "statuses": [s.status for s in env.steps[-1]],
    }


def bench_row(digest, strategy):  # pragma: no cover
    """One bench game: our champion live in our seat, the rival ghosted."""
    from kaggisim.strategy import make_agent

    us = digest["seat"]
    rival = 1 - us
    players = [None, None]
    players[us] = make_agent(strategy())
    players[rival] = ghost_players(digest)[rival]

    env = _make_env(digest["seed"])
    env.run(players)
    rewards = [s.reward or 0 for s in env.steps[-1]]
    return {
        "episode": digest["episode"],
        "win": rewards[us] > rewards[rival],
        "tie": rewards[us] == rewards[rival],
        "ours": rewards[us],
        "rival": rewards[rival],
        "rival_melon_day8": standing_melon(env.steps, PROBE_STEP, rival),
        "statuses": [s.status for s in env.steps[-1]],
    }


def main(argv=None):  # pragma: no cover
    ap = argparse.ArgumentParser(description="the ghost ladder bench (#204)")
    ap.add_argument("--replays", required=True, help="directory of downloaded replays")
    ap.add_argument("--champion", default=None,
                    help="strategy to bench (default: champion.json submit_default)")
    ap.add_argument("--control-only", action="store_true")
    ap.add_argument("--json", default=None, help="write per-episode rows here")
    args = ap.parse_args(argv)

    from strategies import load

    replays = load_digests(args.replays)
    print(f"{len(replays)} replays from {args.replays}\n")

    print("=== positive control: ghosts re-drive their own replays ===")
    control = []
    for i, digest in enumerate(replays, 1):
        row = control_row(digest)
        control.append(row)
        print(f"  [{i}/{len(replays)}] {row['episode']} "
              f"residual rival {row['rival_residual']:.3%} ours {row['our_residual']:.3%}")
    residuals = [row["rival_residual"] for row in control]
    inside = sum(1 for r in residuals if r <= RESIDUAL_TOLERANCE)
    for row in control:
        if row["rival_residual"] > RESIDUAL_TOLERANCE:
            print(f"  MISS {row['episode']}  residual {row['rival_residual']:.3%}")
    print(f"  {inside}/{len(control)} rival reconstructions within "
          f"{RESIDUAL_TOLERANCE:.1%}  (need {CONTROL_MINIMUM})")
    print(f"  CONTROL: {'PASS' if control_passed(residuals) else 'FAIL'}\n")

    if args.control_only or not control_passed(residuals):
        if not control_passed(residuals):
            print("Control failed -- the claim is not measured (#204 alternative 3).")
        return 0

    name = args.champion
    if name is None:
        with open(os.path.join(os.path.dirname(__file__), "champion.json")) as handle:
            name = json.load(handle)["submit_default"]
    print(f"=== bench: {name} vs 63 ghosts ===")
    strategy = load(name)
    rows = []
    for i, digest in enumerate(replays, 1):
        row = bench_row(digest, strategy)
        rows.append(row)
        print(f"  [{i}/{len(replays)}] {row['episode']} "
              f"{'WIN ' if row['win'] else 'loss'} {row['ours']:>9,.0f} vs "
              f"{row['rival']:>9,.0f}  melon@d8 {row['rival_melon_day8']}")

    triggered = sum(1 for row in rows if row["rival_melon_day8"] >= MELON_TRIGGER_TILES)
    share = triggered / len(rows) if rows else 0.0
    rate = win_rate(rows)
    wins = sum(1 for row in rows if row["win"])
    ties = sum(1 for row in rows if row["tie"])
    print(f"  criterion 1  rival melon >= {MELON_TRIGGER_TILES} at day 8: "
          f"{triggered}/{len(rows)} = {share:.1%}  (need >= {TRIGGER_SHARE:.0%})  "
          f"{'PASS' if share >= TRIGGER_SHARE else 'FAIL'}")
    print(f"  criterion 2  win-rate {rate:.3f} ({wins}W {len(rows) - wins - ties}L "
          f"{ties}T) vs ladder {LADDER_WIN_RATE:.3f}  "
          f"delta {abs(rate - LADDER_WIN_RATE):.3f}  "
          f"{'PASS' if abs(rate - LADDER_WIN_RATE) <= WIN_RATE_TOLERANCE else 'FAIL'}")

    if args.json:
        with open(args.json, "w") as handle:
            json.dump({"control": control, "bench": rows}, handle, indent=2)
        print(f"\n  rows written to {args.json}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
