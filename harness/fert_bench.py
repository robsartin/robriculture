"""The fertilized experiment (#277): controls, criterion, arm B.

Declared on #277 before any code. Controls first -- identity (every seam off,
sixteen of them now, is the frozen benchmark to the value) and mechanism (at
least FERTILIZE_BAR FERTILIZE actions, strawberry units at least
STRAWBERRY_FACTOR times the champion's, melon units at least the champion's,
both sides of one game); a failed control is a VOID run (exit 2). Then
rival_bench's criterion; the lonespear and pilkwang pairs print on the verdict
line whatever the result. Arm B (`melon_only`) is recorded, never gated.

    .venv/bin/python -m harness.fert_bench --controls
    .venv/bin/python -m harness.fert_bench --criterion
    .venv/bin/python -m harness.fert_bench --recorded
"""

from __future__ import annotations

import argparse
import os

from harness.cashflow import play  # noqa: F401  -- pinned by the tests
from harness.episode_analysis import _slot
from harness.evolve import DEFAULT_ANCHORS
from harness.external_pool import EXTERNAL_ANCHORS
from harness.reserve_bench import MADHUR, PILKWANG, REFERENCE  # noqa: F401  -- pinned by the tests
from harness.rival_bench import (  # noqa: F401  -- pinned by the tests to rival_bench's own
    criterion,
    format_external,
    format_rows,
    paired_external_rows,
)
from harness.sheep_bench import _seam_names
from strategies import field_pace as fp

CONTENDER = "fertilized"
CHAMPION = "payday_herd"
SEEDS = tuple(range(1056, 1072))
CONTROL_SEED = 1056
CHAMPION_BAR = 0.60
ANCHOR_BAR = 0.90
FERTILIZE_BAR = 30
STRAWBERRY_FACTOR = 1.5
ARM_B = "melon_only"
LONESPEAR = EXTERNAL_ANCHORS[1]
assert LONESPEAR.startswith("lonespear"), LONESPEAR


def load_reference():
    from strategies import load
    return load(REFERENCE)


def action_counts(steps, seat) -> dict:
    """Every farmer and hand action of one seat over the game, tallied by op."""
    counts: dict = {}
    for t in range(len(steps)):
        act = (_slot(steps, t, seat) or {}).get("action") or {}
        for a in [act.get("farmer")] + list(act.get("hands") or []):
            if isinstance(a, list) and a:
                counts[a[0]] = counts.get(a[0], 0) + 1
    return counts


def units_sold(steps, seat) -> dict:
    """Units in one seat's SELL orders over the game, by item."""
    units: dict = {}
    for t in range(len(steps)):
        act = (_slot(steps, t, seat) or {}).get("action") or {}
        for o in act.get("market") or []:
            if isinstance(o, list) and len(o) >= 3 and o[0] == "SELL":
                units[o[1]] = units.get(o[1], 0) + int(o[2])
    return units


def reading(steps, seat) -> dict:
    a, u = action_counts(steps, seat), units_sold(steps, seat)
    return {"fertilize": a.get("FERTILIZE", 0), "water": a.get("WATER", 0),
            "strawberry": u.get("STRAWBERRY", 0), "melon": u.get("MELON", 0),
            "fertilizer_sold": u.get("FERTILIZER", 0)}


def mechanism_failures(contender, champion) -> list:
    failed = []
    if contender["fertilize"] < FERTILIZE_BAR:
        failed.append("fertilize")
    if contender["strawberry"] < STRAWBERRY_FACTOR * champion["strawberry"]:
        failed.append("strawberry")
    if contender["melon"] < champion["melon"]:
        failed.append("melon")
    return failed


def off_class():
    """Every seam off (sixteen), the reference's caps, and the frozen herd ramp."""
    from strategies import load
    body = {n: (lambda self, *a, **k: None) for n in _seam_names()}
    body["CAPS"] = load_reference().CAPS
    body["HERD_RAMP_F"] = fp.HERD_RAMP_F
    return type("Off", (load(CONTENDER),), body)


def arm_b_class():
    """`fertilized` on melon only. Never registered."""
    from strategies import load
    return type("MelonOnly", (load(CONTENDER),), {"fertilize_crops": lambda self: ("MELON",)})


# --- live games -------------------------------------------------------------

def _arm_b_agents(name):  # pragma: no cover
    from harness.triage import _default_agents
    from kaggisim.strategy import make_agent
    arm_b = arm_b_class()
    default_agents = _default_agents()

    def agents(who):
        return make_agent(arm_b()) if who == name else default_agents(who)
    return agents


def run_controls(seed=CONTROL_SEED):  # pragma: no cover
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
    steps = play(CONTENDER, CHAMPION, seed)
    contender, champion = reading(steps, 0), reading(steps, 1)
    failed = mechanism_failures(contender, champion)
    out["mechanism"] = {"ok": not failed, "failed": failed, "contender": contender, "champion": champion}
    return out


def run_criterion(seeds=SEEDS):  # pragma: no cover
    os.environ.setdefault("ROBRICULTURE_STRICT", "1")
    from harness.triage import head_to_head_rate
    champion_row = head_to_head_rate(CONTENDER, CHAMPION, seeds)
    anchor_rows = [head_to_head_rate(CONTENDER, a, seeds) for a in DEFAULT_ANCHORS]
    pairs = paired_external_rows(CONTENDER, CHAMPION, seeds)
    return champion_row, anchor_rows, pairs


def run_recorded(seeds=SEEDS):  # pragma: no cover
    os.environ.setdefault("ROBRICULTURE_STRICT", "1")
    from harness.triage import head_to_head_rate
    return [head_to_head_rate(ARM_B, CHAMPION, seeds, agents=_arm_b_agents(ARM_B))]


def main(argv=None):  # pragma: no cover
    os.environ.setdefault("ROBRICULTURE_STRICT", "1")
    ap = argparse.ArgumentParser(description="fertilized: apply the fertilizer we collect")
    ap.add_argument("--controls", action="store_true")
    ap.add_argument("--criterion", action="store_true")
    ap.add_argument("--recorded", action="store_true", help="arm B (recorded, not gated)")
    args = ap.parse_args(argv)

    if args.recorded:
        print(format_rows(run_recorded()))
        print(f"recorded, not gated: arm B ({ARM_B}: fertilized on melon only) vs {CHAMPION}")
        return 0

    do_controls = args.controls or not args.criterion
    do_criterion = args.criterion or not args.controls

    if do_controls:
        ctl = run_controls()
        print(f"control identity: {'OK' if ctl['identity']['ok'] else 'FAIL -- RUN VOID'}  {ctl['identity']}")
        c, b = ctl["mechanism"]["contender"], ctl["mechanism"]["champion"]
        print(f"control mechanism: {'OK' if ctl['mechanism']['ok'] else 'FAIL -- RUN VOID'}  "
              f"(declared: FERTILIZE >= {FERTILIZE_BAR}, strawberry >= {STRAWBERRY_FACTOR} x champion's, "
              f"melon >= champion's)  contender {c}  {CHAMPION} {b}  failed={ctl['mechanism']['failed'] or 'none'}")
        if not all(r["ok"] for r in ctl.values()):
            print("a control failed: the run is VOID and arm B is NOT scored")
            return 2

    if do_criterion:
        champion_row, anchor_rows, pairs = run_criterion()
        print(format_rows([champion_row] + anchor_rows))
        print(format_external(pairs))
        v = criterion(champion_row, anchor_rows, CHAMPION_BAR, ANCHOR_BAR, external_pairs=pairs)
        print(f"champion {v['champion_rate']:.1%} (bar {CHAMPION_BAR:.0%}); failing limbs: "
              f"{v['failing'] or 'none'} -> {'PROMOTE' if v['passed'] else 'REJECTED'}; "
              f"archetype pairs (contender, champion): lonespear {v['external'].get(LONESPEAR)}, "
              f"pilkwang {v['external'].get(PILKWANG)}; madhur {v['external'].get(MADHUR)}")
        return 0 if v["passed"] else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
