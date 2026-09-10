"""Per-day cash flow of one side of one game (#260).

    python -m harness.cashflow --seed 944 --agents pilkwang_structured_economic_policy field_pace herd_first dusk_floor

Three contenders on the field's schedule starved three different lines --
field_pace (#252) the herd, herd_first (#254) the crew, dusk_floor (#258)
land and seed -- each for a reason a one-turn trace would have shown. Before
a fourth guess: the same accounting `harness.episode_analysis.decompose`
already does on a replay, per day, on our own games. A local game's
`env.steps` has the shape a replay has, so the helpers are reused unchanged
and the positive control is that the days sum to the season.
"""

from __future__ import annotations

import argparse
import os

from harness.episode_analysis import (
    _slot,
    _turns,
    decompose,
    sell_revenue,
    spend_by_category,
)

#: `decompose`'s spend buckets, in the order the table prints them.
CATEGORIES = ("hire", "land", "seed", "animal", "product")

#: Revenue columns, in the order the table prints them; anything else follows.
ITEMS = ("WHEAT", "MELON", "STRAWBERRY", "MILK", "WOOL", "FERTILIZER")


def daily_cashflow(steps, player):
    """``{day: {"spend": {category: amount}, "revenue": {item: amount}, "close": money}}``.

    Built on `_turns` (each action paired with the state it was chosen from),
    `sell_revenue` and `spend_by_category`, with the hire ladder reset at each
    new day exactly as `decompose` resets it. `close` is the money in the last
    observation recorded for the day. Days with no turns are absent. The
    reset slot (no prior observation) is skipped.
    """
    table: dict = {}
    hires_today, last_day = 0, None
    for turn in _turns(steps, player):
        day = turn["day"]
        if day is None:
            continue          # the reset slot: no prior state, nothing was chosen from it
        if day != last_day:
            hires_today, last_day = 0, day
        row = table.setdefault(day, {"spend": {c: 0 for c in CATEGORIES}, "revenue": {}, "close": None})
        for item, amount in sell_revenue(turn["orders"], turn["prices"], turn["shed"],
                                         turn["banked"], turn["inv_levels"]).items():
            row["revenue"][item] = row["revenue"].get(item, 0) + amount
        for bucket, amount in spend_by_category(turn["orders"], hires_today, turn["quadrants"],
                                                turn["prices"], turn["inv_levels"]).items():
            row["spend"][bucket] += amount
        hires_today += sum(1 for o in turn["orders"] if isinstance(o, list) and o and o[0] == "HIRE")

    for t in range(len(steps)):
        slot = _slot(steps, t, player)
        obs = (slot or {}).get("observation") or {}
        farms = obs.get("farms")
        if not farms or obs.get("day") is None:
            continue
        me = farms[obs.get("player", player)] if len(farms) > 1 else farms[0]
        row = table.setdefault(obs["day"], {"spend": {c: 0 for c in CATEGORIES}, "revenue": {}, "close": None})
        row["close"] = float(me.get("money", 0))
    return table


def season_totals(table):
    """Spend and revenue summed over every day -- what `decompose` reports."""
    spend = {c: 0 for c in CATEGORIES}
    revenue: dict = {}
    for row in table.values():
        for c in CATEGORIES:
            spend[c] += row["spend"][c]
        for item, amount in row["revenue"].items():
            revenue[item] = revenue.get(item, 0) + amount
    return {"spend": spend, "revenue": revenue}


def _items(table):
    extra = sorted({i for row in table.values() for i in row["revenue"]} - set(ITEMS))
    return list(ITEMS) + extra


def _line(label, close, spend, revenue, items):
    cells = [f"{label:<10}", f"{close:>7}"] + [f"{spend[c]:>7.0f}" for c in CATEGORIES]
    cells += [f"{revenue.get(i, 0):>7.0f}" for i in items]
    return " ".join(cells)


def format_cashflow(table, days=range(0, 13)):
    """One line per day in `days` (an absent day prints `-`), then `cumulative`
    over those days and `season` over every day in the table."""
    items = _items(table)
    header = " ".join([f"{'day':<10}", f"{'close':>7}"] + [f"{c:>7}" for c in CATEGORIES]
                      + [f"{i[:7]:>7}" for i in items])
    lines = [header]
    cum = {"spend": {c: 0 for c in CATEGORIES}, "revenue": {}}
    for day in days:
        row = table.get(day)
        if row is None:
            lines.append(f"{day:>3}        {'-':>7}")
            continue
        close = f"{row['close']:.0f}" if row["close"] is not None else "-"
        lines.append(_line(f"{day:>3}", close, row["spend"], row["revenue"], items))
        for c in CATEGORIES:
            cum["spend"][c] += row["spend"][c]
        for item, amount in row["revenue"].items():
            cum["revenue"][item] = cum["revenue"].get(item, 0) + amount
    lines.append(_line("cumulative", "", cum["spend"], cum["revenue"], items))
    season = season_totals(table)
    lines.append(_line("season", "", season["spend"], season["revenue"], items))
    return "\n".join(lines)


# --- live games -------------------------------------------------------------

def play(name, opponent, seed):  # pragma: no cover
    """`name` (a registry strategy or a pinned external, fresh per game) in
    seat 0 against `opponent` (registry) in seat 1; returns the env's steps."""
    os.environ.setdefault("ROBRICULTURE_STRICT", "1")
    from kaggle_environments import make
    from harness.external_pool import EXTERNAL_ANCHORS, external_anchor_agents
    from kaggisim.strategy import make_agent
    from strategies import REGISTRY, load
    if name in REGISTRY:
        agent = make_agent(load(name)())
    elif name in EXTERNAL_ANCHORS:
        agent = external_anchor_agents([name])[name].fresh()
    else:
        raise KeyError(f"{name!r} is neither a registered strategy nor a pinned external anchor")
    env = make("kaggriculture", configuration={"seed": seed})
    env.run([agent, make_agent(load(opponent)())])
    return env.steps


def main(argv=None):  # pragma: no cover
    ap = argparse.ArgumentParser(description="per-day cash flow of one side of one game (#260)")
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--agents", nargs="+", required=True)
    ap.add_argument("--opponent", default="third_herder")
    ap.add_argument("--days", type=int, default=13, help="print days 0..days-1")
    args = ap.parse_args(argv)
    for name in args.agents:
        steps = play(name, args.opponent, args.seed)
        table = daily_cashflow(steps, 0)
        season = decompose(steps, 0)
        print(f"== {name} vs {args.opponent}, seed {args.seed} ==")
        print(format_cashflow(table, days=range(0, args.days)))
        print(f"final money {season['final_money']:.0f}; decompose residual {season['residual']:+.0f}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
