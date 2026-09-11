"""The #199 stage-1 gate: did the search breed a predator, and is it a farmer?

Declared on #199 before any code. Controls first (a failed control is VOID,
exit 2): the frozen predator is `field_rival` to the value, and the search
moved. Then the criterion -- the checkpoint's best genome vs the champion on
sixteen fresh seeds, sides alternated by list position, wins >= WIN_BAR, a tie
never a win -- and two non-degeneracy limbs: strict parity (the same games
with the predator built under ROBRICULTURE_STRICT=1 and unset complete with
identical rewards) and the day-16 farm profile inside the field's envelope.

    .venv/bin/python -m harness.predator_bench --controls
    .venv/bin/python -m harness.predator_bench --criterion
    .venv/bin/python -m harness.predator_bench            # both, controls first
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import statistics
import sys

from harness.farm_census import animals_placed, planted_by_crop
from harness.feed_bench import board_on_day, hands_on_day
from strategies import predator as pr

CHAMPION = "lean_feed"
REFERENCE = "field_rival"
GENOME = os.path.join(os.path.dirname(os.path.abspath(__file__)), "genomes", "199-predator.json")
SEEDS = tuple(range(976, 992))
CONTROL_SEED = 976
WIN_BAR = 8
PROFILE_DAY = 16
RECORD_DAY = 8
PROFILE_BOUNDS = {"planted": (14, 40), "animals": (5, 15), "hands": (5, 10)}


def load_checkpoint(path=GENOME) -> dict:
    with open(path) as fh:
        data = json.load(fh)
    if not isinstance(data.get("genome"), list) or "meta" not in data:
        raise ValueError(f"{path!r} is not a predator checkpoint")
    return data


def search_moved(checkpoint) -> dict:
    """Control 2: the final generation's best beat the reference on the same
    seeds, and its schedule is not the frozen one."""
    best = checkpoint["meta"]["fitness"]
    reference = checkpoint["meta"]["reference"]["fitness"]
    schedule, frozen = pr.decode(checkpoint["genome"]), pr.Schedule.frozen()
    changed = [f.name for f in dataclasses.fields(pr.Schedule)
               if getattr(schedule, f.name) != getattr(frozen, f.name)]
    return {"ok": best > reference and bool(changed), "best": best, "reference": reference,
            "changed": changed}


def record(games) -> dict:
    wins = sum(1 for g in games if g["rewards"][0] > g["rewards"][1])
    ties = sum(1 for g in games if g["rewards"][0] == g["rewards"][1])
    return {"wins": wins, "ties": ties, "games": len(games)}


def strict_parity(strict_games, loose_games) -> dict:
    """Limb A: every game done on both runs, rewards identical seed by seed."""
    for s, l in zip(strict_games, loose_games):
        if not (s["done"] and l["done"]):
            return {"ok": False, "reason": f"seed {s['seed']}: a game did not complete"}
        if s["rewards"] != l["rewards"]:
            return {"ok": False, "reason": f"seed {s['seed']}: rewards {s['rewards']} strict vs {l['rewards']} loose"}
    return {"ok": True, "reason": None}


def profile(games, seat_key, day=PROFILE_DAY) -> dict:
    """Median planted tiles, animals placed and crew on `day` over the games,
    for the predator's seat (`"predator"`) or the champion's (`"champion"`)."""
    planted, animals, hands = [], [], []
    for g in games:
        seat = g["seat"] if seat_key == "predator" else 1 - g["seat"]
        board = board_on_day(g["steps"], seat, day)
        if board is None:
            raise ValueError(f"seed {g['seed']}: no board for day {day}")
        planted.append(sum(planted_by_crop(board["tiles"]).values()))
        animals.append(sum(animals_placed(board["tiles"]).values()))
        hands.append(hands_on_day(g["steps"], seat, day))
    return {"planted": statistics.median(planted), "animals": statistics.median(animals),
            "hands": statistics.median(hands)}


def profile_failures(reading) -> list:
    return [k for k, (lo, hi) in PROFILE_BOUNDS.items() if not lo <= reading[k] <= hi]


def verdict(wins, strict_ok, failures) -> tuple:
    if wins < WIN_BAR:
        return "REJECT", 1
    if not strict_ok:
        return "DEGENERATE: strict parity", 1
    if failures:
        return "DEGENERATE: profile " + " ".join(failures), 1
    return "PASS", 0


# ---- the games (never run by the tests) ---------------------------------------

def _agents(genome, strict):  # pragma: no cover
    """Fresh agents built under the given strict setting (read at wrap time)."""
    from kaggisim.strategy import make_agent
    from strategies import load
    if strict:
        os.environ["ROBRICULTURE_STRICT"] = "1"
    else:
        os.environ.pop("ROBRICULTURE_STRICT", None)
    return (lambda: make_agent(pr.PredatorStrategy(genome)),
            lambda: make_agent(load(CHAMPION)()))


def play_games(genome, seeds, strict=True):  # pragma: no cover
    """The predator vs the champion on `seeds`, predator seat 0 on even list
    positions; each game's rewards (predator, champion), completion and steps."""
    from kaggle_environments import make
    predator_fn, champion_fn = _agents(genome, strict)
    games = []
    for i, seed in enumerate(seeds):
        seat = i % 2
        pair = [predator_fn(), champion_fn()] if seat == 0 else [champion_fn(), predator_fn()]
        env = make("kaggriculture", configuration={"seed": seed, "episodeSteps": 720})
        env.run(pair)
        last = env.steps[-1]
        rewards = tuple((s.reward or 0) for s in last)
        games.append({"seed": seed, "seat": seat,
                      "rewards": (rewards[seat], rewards[1 - seat]),
                      "done": all(s.status == "DONE" for s in last), "steps": env.steps})
    return games


def run_controls(seed=CONTROL_SEED):  # pragma: no cover
    os.environ["ROBRICULTURE_STRICT"] = "1"
    from harness.tournament import play_rewards
    from kaggisim.strategy import make_agent
    from strategies import load
    champ = lambda: make_agent(load(CHAMPION)())  # noqa: E731
    ref = lambda: make_agent(load(REFERENCE)())  # noqa: E731
    pred = lambda: make_agent(pr.PredatorStrategy())  # noqa: E731
    base = (play_rewards(ref(), champ(), seed), play_rewards(champ(), ref(), seed))
    got = (play_rewards(pred(), champ(), seed), play_rewards(champ(), pred(), seed))
    precondition_ok = base[0][0] > 0 and base[1][1] > 0
    identity = {"ok": got == base and precondition_ok, "base": base, "got": got,
                "precondition_ok": precondition_ok}
    moved = search_moved(load_checkpoint())
    return {"identity": identity, "moved": moved}


def run_criterion(seeds=SEEDS):  # pragma: no cover
    genome = load_checkpoint()["genome"]
    strict_games = play_games(genome, seeds, strict=True)
    loose_games = play_games(genome, seeds, strict=False)
    os.environ["ROBRICULTURE_STRICT"] = "1"
    rec = record(strict_games)
    parity = strict_parity(strict_games, loose_games)
    pred16 = profile(strict_games, "predator", PROFILE_DAY)
    out = {"record": rec, "parity": parity, "profile": pred16, "failures": profile_failures(pred16),
           "recorded": {"predator_day8": profile(strict_games, "predator", RECORD_DAY),
                        "champion_day16": profile(strict_games, "champion", PROFILE_DAY),
                        "champion_day8": profile(strict_games, "champion", RECORD_DAY)},
           "games": [(g["seed"], g["seat"], g["rewards"]) for g in strict_games]}
    return out


def main(argv=None):  # pragma: no cover
    ap = argparse.ArgumentParser(description="#199 stage 1: did the search breed a predator?")
    ap.add_argument("--controls", action="store_true")
    ap.add_argument("--criterion", action="store_true")
    args = ap.parse_args(argv)
    do_controls = args.controls or not args.criterion
    do_criterion = args.criterion or not args.controls

    if do_controls:
        ctl = run_controls()
        print(f"control identity: {'OK' if ctl['identity']['ok'] else 'FAIL -- RUN VOID'}  {ctl['identity']}")
        m = ctl["moved"]
        print(f"control search moved: {'OK' if m['ok'] else 'FAIL -- RUN VOID'}  best {m['best']:.3f} "
              f"vs reference {m['reference']:.3f}; changed: {m['changed']}")
        if not (ctl["identity"]["ok"] and m["ok"]):
            print("VOID")
            return 2

    if do_criterion:
        ck = load_checkpoint()
        print(f"schedule: {ck['meta']['schedule']}")
        res = run_criterion()
        rec = res["record"]
        print(f"predator vs {CHAMPION}: {rec['wins']}/{rec['games']} wins, {rec['ties']} ties (bar {WIN_BAR})")
        print(f"games (seed, predator seat, (predator, champion)): {res['games']}")
        print(f"limb A strict parity: {'OK' if res['parity']['ok'] else 'FAIL'}  {res['parity']['reason'] or ''}")
        print(f"limb B profile day {PROFILE_DAY}: {res['profile']}  bounds {PROFILE_BOUNDS}  "
              f"{'OK' if not res['failures'] else 'FAIL ' + str(res['failures'])}")
        print(f"recorded, not gated: {res['recorded']}")
        name, code = verdict(rec["wins"], res["parity"]["ok"], res["failures"])
        print(f"-> {name}")
        return code
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
