"""The wind_down experiment (#343): controls and criterion -- judged under
ADR-0007 as amended 2026-09-16, 2026-09-20 and 2026-09-21, corrected
2026-09-17.

Declared on #343 before any code. Controls first -- identity (every seam off,
twenty-one, is the frozen benchmark to the value) and mechanism (no BUY order
from WIND_DAY on while the champion issues some; no WHEAT in the shed at the
end of WIND_DAY while the champion holds some; the contender's first
divergence from the champion's own stream at or after WIND_STEP; fertilizer
in the shed printed, not gated); a failed control is a VOID run (exit 2).
Then rival_bench's criterion on the decided row: >= 60% of the decided games
vs town_melon (VOID if fewer than MIN_DECIDED are decided), >= 90% vs each
anchor, the paired external limb as a whole.

Readings come from `harness.episode_analysis._turns`, which dates each
action by the observation it answered.

    .venv/bin/python -m harness.winddown_bench --controls
    .venv/bin/python -m harness.winddown_bench --criterion
"""

from __future__ import annotations

import argparse
import os

from harness.cashflow import play  # noqa: F401  -- pinned by the tests
from harness.episode_analysis import _turns
from harness.evolve import DEFAULT_ANCHORS
from harness.external_pool import EXTERNAL_ANCHORS
from harness.reserve_bench import MADHUR, REFERENCE  # noqa: F401  -- pinned by the tests
from harness.rival_bench import (  # noqa: F401  -- pinned by the tests to rival_bench's own
    criterion,
    decided_row,
    format_external,
    format_rows,
    paired_external_rows,
)
from harness.sheep_bench import _seam_names
from harness.sixteend_bench import first_divergence
from strategies import field_pace as fp
from strategies import field_rival as fr

CONTENDER = "wind_down"
CHAMPION = "town_melon"
SEEDS = tuple(range(2586, 2602))
CONTROL_SEED = 2586
CHAMPION_BAR = 0.60
ANCHOR_BAR = 0.90
WIND_DAY = 28
#: The index of the first action that answers WIND_DAY: actions lag observations by one step.
WIND_STEP = WIND_DAY * fr.TURNS_PER_DAY + 1
LONESPEAR = EXTERNAL_ANCHORS[0]
assert LONESPEAR.startswith("lonespear"), LONESPEAR  # the pool order is the pin (review)


def load_reference():
    from strategies import load
    return load(REFERENCE)


def buys_from(steps, seat, day) -> int:
    """BUY orders (seed, product, animal, land) one seat issues on turns whose
    answered observation is on `day` or later."""
    total = 0
    for turn in _turns(steps, seat):
        if turn["day"] is None or turn["day"] < day:
            continue
        total += sum(1 for o in turn["orders"] if o and str(o[0]).startswith("BUY"))
    return total


def shed_on_day(steps, seat, day, item):
    """Units of `item` in the shed the last action of `day` answered, or
    ``None`` when no turn answered that day."""
    found = None
    for turn in _turns(steps, seat):
        if turn["day"] == day:
            found = int((turn["shed"] or {}).get(item, 0) or 0)
    return found


def reading(steps, seat) -> dict:
    """One side's BUY orders from WIND_DAY on, and its wheat and fertilizer
    in the shed at the end of WIND_DAY. No turn on WIND_DAY is an error."""
    wheat = shed_on_day(steps, seat, WIND_DAY, "WHEAT")
    if wheat is None:
        raise ValueError(f"no turn answered day {WIND_DAY}: the game ended early")
    return {"buys_28": buys_from(steps, seat, WIND_DAY), "wheat_28": wheat,
            "fertilizer_28": shed_on_day(steps, seat, WIND_DAY, "FERTILIZER")}


def mechanism_failures(contender, champion, *, first_diff) -> list:
    """Control 2's bars; the names of the ones that did not hold. Fertilizer
    is printed, never gated."""
    failed = []
    if contender["buys_28"] != 0 or not champion["buys_28"] > 0:
        failed.append("buys_28")
    if contender["wheat_28"] != 0 or not champion["wheat_28"] > 0:
        failed.append("wheat_28")
    if first_diff is None or first_diff < WIND_STEP:
        failed.append("first_divergence")
    return failed


def off_class():
    """Every seam off (twenty-one), the reference's caps, and the frozen herd ramp."""
    from strategies import load
    body = {n: (lambda self, *a, **k: None) for n in _seam_names()}
    body["CAPS"] = load_reference().CAPS
    body["HERD_RAMP_F"] = fp.HERD_RAMP_F
    return type("Off", (load(CONTENDER),), body)


# --- live games -------------------------------------------------------------

def _own_steps(seed):  # pragma: no cover
    from harness.rival_bench import _default_steps
    from harness.triage import _default_agents
    agents = _default_agents()
    return _default_steps()(agents(CHAMPION), agents(CHAMPION), seed)


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
    own = _own_steps(seed)
    contender, champion = reading(steps, 0), reading(steps, 1)
    first_diff = first_divergence(steps, own, 0)
    failed = mechanism_failures(contender, champion, first_diff=first_diff)
    out["mechanism"] = {"ok": not failed, "failed": failed, "first_diff": first_diff,
                        "contender": contender, "champion": champion}
    return out


def run_criterion(seeds=SEEDS):  # pragma: no cover
    os.environ.setdefault("ROBRICULTURE_STRICT", "1")
    from harness.triage import head_to_head_rate
    champion_row = decided_row(CONTENDER, CHAMPION, seeds)
    anchor_rows = [head_to_head_rate(CONTENDER, a, seeds) for a in DEFAULT_ANCHORS]
    pairs = paired_external_rows(CONTENDER, CHAMPION, seeds)
    return champion_row, anchor_rows, pairs


def main(argv=None):  # pragma: no cover
    os.environ.setdefault("ROBRICULTURE_STRICT", "1")
    ap = argparse.ArgumentParser(description="wind_down: from day 28 buy nothing, keep no feed, hold no fertilizer")
    ap.add_argument("--controls", action="store_true")
    ap.add_argument("--criterion", action="store_true")
    args = ap.parse_args(argv)

    do_controls = args.controls or not args.criterion
    do_criterion = args.criterion or not args.controls

    if do_controls:
        ctl = run_controls()
        print(f"control identity: {'OK' if ctl['identity']['ok'] else 'FAIL -- RUN VOID'}  {ctl['identity']}")
        m = ctl["mechanism"]
        print(f"control mechanism: {'OK' if m['ok'] else 'FAIL -- RUN VOID'}  "
              f"(declared: no BUY from day {WIND_DAY} and {CHAMPION} buys; no WHEAT in the shed at the end of day {WIND_DAY} and {CHAMPION} holds some; "
              f"first divergence >= step {WIND_STEP}; fertilizer recorded)  contender {m['contender']}  {CHAMPION} {m['champion']}  "
              f"first_diff={m['first_diff']}  failed={m['failed'] or 'none'}")
        if not all(r["ok"] for r in ctl.values()):
            print("a control failed: the run is VOID")
            return 2

    if do_criterion:
        champion_row, anchor_rows, pairs = run_criterion()
        print(format_rows([champion_row] + anchor_rows))
        print(format_external(pairs))
        v = criterion(champion_row, anchor_rows, CHAMPION_BAR, ANCHOR_BAR, external_pairs=pairs,
                      identical=champion_row["identical"])
        verdict = "VOID (under-powered)" if v["void"] else ("PROMOTE" if v["passed"] else "REJECTED")
        print(f"champion {champion_row['wins']}W {champion_row['ties']}T {champion_row['losses']}L over {v['decided']} decided "
              f"= {v['champion_rate']:.1%} (bar {CHAMPION_BAR:.0%}; {v['identical']} identical of {champion_row['games']}); "
              f"failing limbs: {v['failing'] or 'none'} -> {verdict}; external net {v['external_net']:+d}; "
              f"paired rows (contender, champion): madhur {v['external'].get(MADHUR)}, lonespear {v['external'].get(LONESPEAR)}")
        if v["void"]:
            return 2
        return 0 if v["passed"] else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
