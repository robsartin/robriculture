"""The town_split experiment (#305): controls, criterion, arm B -- judged under
ADR-0007's amendment of 2026-09-16 (identical play leaves the denominator).

Declared on #305 before any code. Controls first -- identity (every seam off
is the frozen benchmark to the value) and mechanism, by procedure: the draw
depends on both boards, so the control game is the first seed in SEEDS whose
contender-vs-champion game has a split town on day 12 (both a wool and a milk
drain); on it the contender holds more sheep than the champion at day 14,
keeps at least COWS_BAR cows, and earns more wool. No split town, or a bar
missed, is a VOID run (exit 2). Then rival_bench's criterion on the
decided row (`rival_bench.decided_row`, wins on decided games only): >= 60% of the *decided* games vs four_at_eight (VOID if
fewer than MIN_DECIDED are decided), >= 90% vs each anchor, paired external
non-regression. Arm B (`even_split`) is recorded, never gated.

    .venv/bin/python -m harness.split_bench --controls
    .venv/bin/python -m harness.split_bench --criterion
    .venv/bin/python -m harness.split_bench --recorded
"""

from __future__ import annotations

import argparse
import os

from harness.cashflow import play  # noqa: F401  -- pinned by the tests
from harness.episode_analysis import decompose
from harness.evolve import DEFAULT_ANCHORS
from harness.external_pool import ANCHORS_2026_09_07
from harness.farm_census import animals_placed
from harness.feed_bench import board_on_day
from harness.four8_bench import escapes
from harness.reserve_bench import MADHUR, PILKWANG, REFERENCE  # noqa: F401  -- pinned by the tests
from harness.rival_bench import (  # noqa: F401  -- pinned by the tests to rival_bench's own
    criterion,
    decided_row,
    format_external,
    format_rows,
    paired_external_rows,
)
from harness.sheep_bench import _seam_names
from harness.town_bench import town_on_day
from strategies import field_pace as fp
from strategies import town_split as ts
from strategies.town_herd import shop_drain

CONTENDER = "town_split"
CHAMPION = "four_at_eight"
SEEDS = tuple(range(1191, 1223))
IDENTITY_SEED = 1191
CHAMPION_BAR = 0.60
ANCHOR_BAR = 0.90
KIND_DAY = 12
HEAD_DAY = 14
COWS_BAR = 3
ARM_B = "even_split"
LONESPEAR = ANCHORS_2026_09_07[1]
assert LONESPEAR.startswith("lonespear"), LONESPEAR  # the pool order is the pin (review)


def load_reference():
    from strategies import load
    return load(REFERENCE)


def even_share(shops):
    """Arm B's share: a half whenever the town takes both wool and milk, one
    or zero when it takes only one, ``None`` when neither."""
    wool, milk = shop_drain(shops, "WOOL"), shop_drain(shops, "MILK")
    if wool + milk == 0:
        return None
    if milk == 0:
        return 1.0
    if wool == 0:
        return 0.0
    return 0.5


def is_split_town(share) -> bool:
    """Both a wool and a milk drain: the share is strictly between 0 and 1."""
    return share is not None and 0 < share < 1


def reading(steps, seat) -> dict:
    """One side's day-12 share and shops, its herd at day 14, and its milk and
    wool revenue."""
    shops = town_on_day(steps, seat, KIND_DAY)
    if shops is None:
        raise ValueError(f"no observation for day {KIND_DAY}: the game ended early")
    board = board_on_day(steps, seat, HEAD_DAY)
    if board is None:
        raise ValueError(f"no board for day {HEAD_DAY}: the game ended early")
    placed = animals_placed(board["tiles"])
    rev = decompose(steps, seat)["revenue"]
    return {"share_12": ts.sheep_share(shops), "shops_12": tuple(shops),
            "cows_14": placed.get("COW", 0), "sheep_14": placed.get("SHEEP", 0),
            "milk": rev.get("MILK", 0), "wool": rev.get("WOOL", 0)}


def control_game(seeds=SEEDS, play=None):
    """The mechanism control's game, by procedure: `(seed, steps)` for the
    first seed whose contender (seat 0) vs champion game has a split town on
    day 12; ``None`` when no seed does."""
    play = play or _default_play()
    for seed in seeds:
        steps = play(CONTENDER, CHAMPION, seed)
        if is_split_town(reading(steps, 0)["share_12"]):
            return seed, steps
    return None


def _default_play():  # pragma: no cover
    from harness.cashflow import play as live_play
    return live_play


def mechanism_failures(contender, champion) -> list:
    """Control 2's bars; the names of the ones that did not hold."""
    failed = []
    if not contender["sheep_14"] > champion["sheep_14"]:
        failed.append("sheep_14")
    if contender["cows_14"] < COWS_BAR:
        failed.append("cows_14")
    if not contender["wool"] > champion["wool"]:
        failed.append("wool")
    return failed


def off_class():
    """Every seam off (sixteen), the reference's caps, and the frozen herd ramp."""
    from strategies import load
    body = {n: (lambda self, *a, **k: None) for n in _seam_names()}
    body["CAPS"] = load_reference().CAPS
    body["HERD_RAMP_F"] = fp.HERD_RAMP_F
    return type("Off", (load(CONTENDER),), body)


def arm_b_class():
    """`town_split` at an even share whenever the town takes both. Never registered."""
    from strategies import load
    return type("EvenSplit", (load(CONTENDER),), {"sheep_share": lambda self, shops: even_share(shops)})


# --- live games -------------------------------------------------------------

def _arm_b_agents(name):  # pragma: no cover
    from harness.triage import _default_agents
    from kaggisim.strategy import make_agent
    arm_b = arm_b_class()
    default_agents = _default_agents()

    def agents(who):
        return make_agent(arm_b()) if who == name else default_agents(who)
    return agents


def run_controls(seed=IDENTITY_SEED):  # pragma: no cover
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
    found = control_game()
    if found is None:
        out["mechanism"] = {"ok": False, "failed": ["no_split_town"], "seed": None,
                            "contender": None, "champion": None}
        return out
    control_seed, steps = found
    contender, champion = reading(steps, 0), reading(steps, 1)
    contender["escapes"], champion["escapes"] = escapes(steps, 0), escapes(steps, 1)
    failed = mechanism_failures(contender, champion)
    out["mechanism"] = {"ok": not failed, "failed": failed, "seed": control_seed,
                        "contender": contender, "champion": champion}
    return out


def run_criterion(seeds=SEEDS):  # pragma: no cover
    os.environ.setdefault("ROBRICULTURE_STRICT", "1")
    from harness.triage import head_to_head_rate
    champion_row = decided_row(CONTENDER, CHAMPION, seeds)   # wins on decided games only (2026-09-17 correction)
    identical = champion_row["identical"]
    anchor_rows = [head_to_head_rate(CONTENDER, a, seeds) for a in DEFAULT_ANCHORS]
    pairs = paired_external_rows(CONTENDER, CHAMPION, seeds)
    return champion_row, identical, anchor_rows, pairs


def run_recorded(seeds=SEEDS):  # pragma: no cover
    os.environ.setdefault("ROBRICULTURE_STRICT", "1")
    agents = _arm_b_agents(ARM_B)
    row = decided_row(ARM_B, CHAMPION, seeds, agents=agents)
    return row, row["identical"]


def main(argv=None):  # pragma: no cover
    os.environ.setdefault("ROBRICULTURE_STRICT", "1")
    ap = argparse.ArgumentParser(description="town_split: the herd in proportion to the town's drain")
    ap.add_argument("--controls", action="store_true")
    ap.add_argument("--criterion", action="store_true")
    ap.add_argument("--recorded", action="store_true", help="arm B (recorded, not gated)")
    args = ap.parse_args(argv)

    if args.recorded:
        row, identical = run_recorded()
        print(format_rows([row]))
        decided = row["games"] - identical
        print(f"recorded, not gated: arm B ({ARM_B}: an even share whenever the town takes both) vs {CHAMPION}: "
              f"{row['wins']}/{decided} decided ({identical} identical)")
        return 0

    do_controls = args.controls or not args.criterion
    do_criterion = args.criterion or not args.controls

    if do_controls:
        ctl = run_controls()
        print(f"control identity: {'OK' if ctl['identity']['ok'] else 'FAIL -- RUN VOID'}  {ctl['identity']}")
        m = ctl["mechanism"]
        print(f"control mechanism: {'OK' if m['ok'] else 'FAIL -- RUN VOID'}  seed {m['seed']}  "
              f"(declared: the first seed with a split town on day {KIND_DAY}; sheep at day {HEAD_DAY} > {CHAMPION}'s, "
              f"cows >= {COWS_BAR}, wool > {CHAMPION}'s)  contender {m['contender']}  {CHAMPION} {m['champion']}  "
              f"failed={m['failed'] or 'none'}")
        if not all(r["ok"] for r in ctl.values()):
            print("a control failed: the run is VOID and arm B is NOT scored")
            return 2

    if do_criterion:
        champion_row, identical, anchor_rows, pairs = run_criterion()
        print(format_rows([champion_row] + anchor_rows))
        print(format_external(pairs))
        v = criterion(champion_row, anchor_rows, CHAMPION_BAR, ANCHOR_BAR, external_pairs=pairs, identical=identical)
        verdict = "VOID (under-powered)" if v["void"] else ("PROMOTE" if v["passed"] else "REJECTED")
        print(f"champion {champion_row['wins']}/{v['decided']} decided = {v['champion_rate']:.1%} (bar {CHAMPION_BAR:.0%}; "
              f"{v['identical']} identical of {champion_row['games']}); failing limbs: {v['failing'] or 'none'} -> {verdict}; "
              f"paired rows (contender, champion): madhur {v['external'].get(MADHUR)}, "
              f"pilkwang {v['external'].get(PILKWANG)}, lonespear {v['external'].get(LONESPEAR)}")
        if v["void"]:
            return 2
        return 0 if v["passed"] else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
