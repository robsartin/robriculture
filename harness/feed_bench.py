"""lean_feed: does feed sized to the herd free the cash the schedule needs, and beat the champion?

    python -m harness.feed_bench --controls     # identity, the three feed/head bars, the paired crop line
    python -m harness.feed_bench --criterion    # 16 seeds: champion, anchors, the external limb
    python -m harness.feed_bench --recorded     # arm B (recorded, not gated)
    python -m harness.feed_bench                # controls then criterion

Declared on #262 before any code: seeds 960-975 -- fresh; 100-115, 200-215,
300-331, 400-415, 500-515, 600-615, 700-703, 800-928 and 944 are spent,
929-943 and 945-959 were declared and never played -- sides alternated by
list position (`harness.triage.head_to_head_rate`); PROMOTE only at >= 60% of
16 vs the champion `third_herder` AND >= 90% vs each DEFAULT_ANCHOR AND, for
each `external_pool.EXTERNAL_ANCHORS` member, no fewer wins than the champion
on the same seeds in the same run (#152's paired limb); a tie is not a win.
Controls run first and a failed control voids the run -- arm B is then not
scored either. Exit codes: 0 PROMOTE, 1 REJECTED, 2 VOID. Runs under
ROBRICULTURE_STRICT=1.

**The controls read the contender's own game.** #260's cash-flow tool
(`harness.cashflow`) prices every order against the state it was chosen
from, per day; the mechanism is the `product` column -- feed -- on day 0
(herd_first spent 664) and over days 1-5 (2,467), with head placed at day 8
retained as the third bar. Boards are read by the day-boundary rule
cashflow established: the state a day's last turn produced is stamped with
the next day. The crop line is PAIRED against herd_first on the same seed.

The verdict is `harness.rival_bench`'s; the readings are `harness.cashflow`'s.
"""

from __future__ import annotations

import argparse
import os

from harness.cashflow import daily_cashflow, format_cashflow, play  # noqa: F401  -- pinned by the tests
from harness.episode_analysis import _slot, decompose
from harness.evolve import DEFAULT_ANCHORS
from harness.farm_census import animals_placed, planted_by_crop
from harness.reserve_bench import MADHUR, PILKWANG, REFERENCE  # noqa: F401  -- pinned by the tests
from harness.rival_bench import (  # noqa: F401  -- pinned by the tests to rival_bench's own
    criterion,
    format_external,
    format_rows,
    paired_external_rows,
)

CONTENDER = "lean_feed"
CHAMPION = "third_herder"
BASELINE = "herd_first"

#: Fresh. Everything through 928 and 944 are spent; 929-943 and 945-959 were
#: declared and never played, and are not reused.
SEEDS = tuple(range(960, 976))
CHAMPION_BAR = 0.60
ANCHOR_BAR = 0.90
CONTROL_SEED = 960

#: Arm B: the shed stock sized, the carry left at 8. If B matches A, the
#: pockets were not the leak. Never registered.
ARM_B = "lean_buffer"

#: The mechanism: feed spend (cashflow's `product` column) on day 0 and over
#: days 1-5, and head placed at day 8 retained.
FEED_DAY0_BAR = 250
FEED_DAYS = range(1, 6)
FEED_DAYS_BAR = 1200
HEAD_DAY = 8
HEAD_BAR = 8

#: The cost the arm may pay: planted at day 12 within this many of herd_first's.
CROP_DAY = 12
PLANTED_GAP_BAR = 12


def board_on_day(steps, player, day):
    """The player's farm in the state the day's last turn produced -- the
    observation whose PRIOR observation is `day`, last wins -- or ``None``."""
    board = None
    for t in range(1, len(steps)):
        prior = (_slot(steps, t - 1, player) or {}).get("observation") or {}
        obs = (_slot(steps, t, player) or {}).get("observation") or {}
        farms = obs.get("farms")
        if prior.get("day") == day and farms:
            board = farms[obs.get("player", player)] if len(farms) > 1 else farms[0]
    return board


def hands_on_day(steps, player, day):
    """The size of the player's crew on `day` -- the `len(hands)` of the LAST
    observation whose own `day` is `day`, or ``None`` if the day is never
    reached.

    The sim clears the crew at the nightly rollover, so the boundary board
    `board_on_day` returns (the state a day's last turn produced, stamped with
    the NEXT day) always shows `hands == 0` -- it is the day after's opening
    board. The crew that actually worked `day` is on the observation labelled
    `day` itself, last one wins (the crew can grow mid-day on a HIRE)."""
    hands = None
    for t in range(len(steps)):
        obs = (_slot(steps, t, player) or {}).get("observation") or {}
        if obs.get("day") != day:
            continue
        farms = obs.get("farms")
        if not farms:
            continue
        farm = farms[obs.get("player", player)] if len(farms) > 1 else farms[0]
        hands = len(farm.get("hands") or [])
    return hands


def feed_reading_from(table, boards, hands_8):
    """The reading off a cash-flow table, the day-8 / day-12 boards, and the
    crew size on day 8 (read separately -- see `hands_on_day`)."""
    b8, b12 = boards[HEAD_DAY], boards[CROP_DAY]
    return {
        "feed_day0": table.get(0, {"spend": {"product": 0}})["spend"]["product"],
        "feed_days_1_5": sum(table.get(d, {"spend": {"product": 0}})["spend"]["product"] for d in FEED_DAYS),
        "head_placed_8": sum(animals_placed(b8["tiles"]).values()),
        "hands_8": hands_8,
        "planted_12": sum(planted_by_crop(b12["tiles"]).values()),
    }


def feed_reading(steps, player):
    """One side's reading off one game's steps; raises if a declared day was never reached."""
    boards = {d: board_on_day(steps, player, d) for d in (HEAD_DAY, CROP_DAY)}
    missing = [d for d, b in boards.items() if b is None]
    if missing:
        raise ValueError(f"no board for day {missing[0]}: the game ended early")
    hands_8 = hands_on_day(steps, player, HEAD_DAY)
    return feed_reading_from(daily_cashflow(steps, player), boards, hands_8)


def mechanism_failures(reading):
    """Control (ii): the three bars; the names of the ones that did not hold."""
    failed = []
    if reading["feed_day0"] > FEED_DAY0_BAR:
        failed.append("feed_day0")
    if reading["feed_days_1_5"] > FEED_DAYS_BAR:
        failed.append("feed_days_1_5")
    if reading["head_placed_8"] < HEAD_BAR:
        failed.append("head_placed_8")
    return failed


def crop_line_ok(contender, baseline):
    """Control (iii): the crop line paid no more than the declared gap."""
    return abs(contender["planted_12"] - baseline["planted_12"]) <= PLANTED_GAP_BAR


def off_class():
    """The identity control's subject: the contender with every seam switched
    off and dense_farm's caps. Built here so a test proves it survives a turn."""
    from strategies import load
    return type("Off", (load(CONTENDER),), {
        "herd_preference": lambda self, obs: None,
        "pasture_count": lambda self, day, animals: None,
        "herd_target": lambda self, day: None,
        "livestock_workers": lambda self, day: None,
        "layout": lambda self: None,
        "land_target": lambda self, day: None,
        "hire_target": lambda self, day: None,
        "pivot_day": lambda self: None,
        "cluster_size": lambda self: None,
        "capital_reserve": lambda self, day=None, animals=None: None,
        "buy_order": lambda self: None,
        "spend_floor": lambda self, day=None, animals=None, shed=None, prices=None: None,
        "feed_carry": lambda self, animals=None, herders=None: None,
        "feed_stock": lambda self, animals=None: None,
        "CAPS": load(REFERENCE).CAPS,
    })


def arm_b_class():
    """`herd_first` with the shed stock sized and the carry left at 8. Never registered."""
    from strategies import load
    from strategies.lean_feed import stock_for

    return type("LeanBuffer", (load(BASELINE),), {"feed_stock": lambda self, animals=None: stock_for(animals or 0)})


# --- live games -------------------------------------------------------------

def _arm_b_agents(name):  # pragma: no cover
    """`head_to_head_rate`'s `agents` hook, resolving arm B by name."""
    from harness.triage import _default_agents
    from kaggisim.strategy import make_agent
    arm_b = arm_b_class()
    default_agents = _default_agents()

    def agents(who):
        return make_agent(arm_b()) if who == name else default_agents(who)
    return agents


def run_controls(seed=CONTROL_SEED):  # pragma: no cover
    """Identity, then the three bars, then the paired crop line -- off full games."""
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

    ours = play(CONTENDER, CHAMPION, seed)
    theirs = play(BASELINE, CHAMPION, seed)
    contender, baseline = feed_reading(ours, 0), feed_reading(theirs, 0)
    failed = mechanism_failures(contender)
    out["mechanism"] = {"ok": not failed, "failed": failed, "contender": contender, "baseline": baseline,
                        "tables": {CONTENDER: daily_cashflow(ours, 0), BASELINE: daily_cashflow(theirs, 0)},
                        "residuals": {CONTENDER: decompose(ours, 0)["residual"], BASELINE: decompose(theirs, 0)["residual"]}}
    out["crop_line"] = {"ok": crop_line_ok(contender, baseline),
                        "gap": abs(contender["planted_12"] - baseline["planted_12"])}
    return out


def run_criterion(seeds=SEEDS):  # pragma: no cover
    """The declared criterion: the champion row, the anchors, and the paired
    external limb -- the champion played on the same seeds in this run."""
    os.environ.setdefault("ROBRICULTURE_STRICT", "1")
    from harness.triage import head_to_head_rate
    champion_row = head_to_head_rate(CONTENDER, CHAMPION, seeds)
    anchor_rows = [head_to_head_rate(CONTENDER, a, seeds) for a in DEFAULT_ANCHORS]
    pairs = paired_external_rows(CONTENDER, CHAMPION, seeds)
    return champion_row, anchor_rows, pairs


def run_recorded(seeds=SEEDS):  # pragma: no cover
    """Recorded, never gated: arm B against the champion."""
    os.environ.setdefault("ROBRICULTURE_STRICT", "1")
    from harness.triage import head_to_head_rate
    return [head_to_head_rate(ARM_B, CHAMPION, seeds, agents=_arm_b_agents(ARM_B))]


def main(argv=None):  # pragma: no cover
    os.environ.setdefault("ROBRICULTURE_STRICT", "1")
    ap = argparse.ArgumentParser(description="lean_feed: feed sized to the herd")
    ap.add_argument("--controls", action="store_true")
    ap.add_argument("--criterion", action="store_true")
    ap.add_argument("--recorded", action="store_true", help="arm B (recorded, not gated)")
    args = ap.parse_args(argv)

    if args.recorded:
        print(format_rows(run_recorded()))
        print(f"recorded, not gated: arm B ({ARM_B}: the shed stock sized, the carry left at 8) vs {CHAMPION}")
        return 0

    do_controls = args.controls or not args.criterion
    do_criterion = args.criterion or not args.controls

    if do_controls:
        ctl = run_controls()
        print(f"control identity: {'OK' if ctl['identity']['ok'] else 'FAIL -- RUN VOID'}"
              f"  {ctl['identity']}")
        c, b = ctl["mechanism"]["contender"], ctl["mechanism"]["baseline"]
        print(f"control mechanism: {'OK' if ctl['mechanism']['ok'] else 'FAIL -- RUN VOID'}  "
              f"(declared: feed day 0 <= {FEED_DAY0_BAR}, feed days 1-5 <= {FEED_DAYS_BAR}, "
              f"head placed at day {HEAD_DAY} >= {HEAD_BAR})  got {c['feed_day0']} / {c['feed_days_1_5']} / "
              f"{c['head_placed_8']}  (herd_first {b['feed_day0']} / {b['feed_days_1_5']} / {b['head_placed_8']})  "
              f"failed={ctl['mechanism']['failed'] or 'none'}")
        print(f"control crop line: {'OK' if ctl['crop_line']['ok'] else 'FAIL -- RUN VOID'}  "
              f"(declared: |planted at day {CROP_DAY} - herd_first's| <= {PLANTED_GAP_BAR})  "
              f"gap={ctl['crop_line']['gap']}  (planted {c['planted_12']} vs {b['planted_12']}; hands at day 8: "
              f"{c['hands_8']} vs {b['hands_8']})")
        for name in (CONTENDER, BASELINE):
            print(f"-- {name} vs {CHAMPION}, seed {CONTROL_SEED}; decompose residual "
                  f"{ctl['mechanism']['residuals'][name]:+.0f}")
            print(format_cashflow(ctl["mechanism"]["tables"][name], days=range(0, 13)))
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
              f"madhur paired row (contender, champion): {v['external'].get(MADHUR)}; "
              f"pilkwang: {v['external'].get(PILKWANG)}")
        return 0 if v["passed"] else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
