"""Scoreboard trigger control (#197, Stage 1): can "behind at day D" be read early enough to act on?

    python -m harness.scoreboard_probe                 # play the 96 games, write the record, print the tables
    python -m harness.scoreboard_probe --from-record   # re-derive the tables from the committed record

The issue asked whether a controller that knows it is behind and gambles wins
more rated games. Brainstormed 2026-09-09: rival money is in the live
observation (no estimator needed), the economy has no dice (a gamble can only
be a play whose payoff depends on the rival), and the champion's crop chooser
has one move after day 15, so no Stage 2 lever survives. What is worth knowing
-- for any future scoreboard contender -- is whether the trigger itself reads:
for "our money is behind the rival's by >= X% at the close of day D", how often
it fires, how often a fired game ends in a loss (precision), how often it fires
on a game we go on to win (harm), and how many losses it catches (recall).

Declared on #197 before any code: the champion vs itself and the five pinned
externals on SPENT seeds 864-879 (96 games), sides alternated by seed parity,
D in {12, 15, 18, 21}, X in {10, 20, 30}%. A cell is actionable at fire rate
>= 25% AND harm <= 20%; the whole table is reported and no cell clearing both
is a finding, not a failure. Beside it, per opponent and day: the rival's
strawberry tiles minus ours and head placed minus ours (medians) -- the
asymmetry any spoil lever would need.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics

from harness.external_pool import EXTERNAL_ANCHORS
from harness.herder_bench import last_census_on_day

CHAMPION = "third_herder"

#: Spent: #244's seeds. Stage 1 is a control on games already paid for.
SEEDS = tuple(range(864, 880))
DAYS = (12, 15, 18, 21)
MARGINS = (10, 20, 30)
FIRE_BAR = 0.25
HARM_BAR = 0.20
OPPONENTS = (CHAMPION,) + tuple(EXTERNAL_ANCHORS)

#: The raw per-game readings, committed so the tables re-derive without replaying.
RECORD = os.path.join(os.path.dirname(__file__), "scoreboard", "trigger_readings.json")


def behind(ours, theirs, margin_pct):
    """Strictly behind by `margin_pct` percent: exactly at the line is not behind."""
    return ours < theirs * (1 - margin_pct / 100)


def census_on_day(turns, day):
    """The day's closing census, raising when the game never reached it: "the
    run stopped early" and "nobody was behind" must not read the same."""
    census = last_census_on_day(turns, day)
    if census is None:
        span = f"the game covers days {turns[0][0]}-{turns[-1][0]}" if turns else "no turns at all"
        raise ValueError(f"no census recorded on day {day}: {span}")
    return census


def champion_seat(seed):
    """Sides alternate by seed parity: even seeds seat the champion at 0."""
    return seed % 2


def seat_series(seed, seat0_series, seat1_series):
    """``(ours, theirs)`` with ours always the champion, whichever seat it sat in."""
    return (seat0_series, seat1_series) if champion_seat(seed) == 0 else (seat1_series, seat0_series)


def seats_alternated(readings):
    """The seating's positive control: both seats appear in the record."""
    return {r["seat"] for r in readings} == {0, 1}


def game_reading(ours_turns, theirs_turns, opponent, seed, days=DAYS):
    """One game's numbers: both sides' money and the asymmetry at each declared
    day (JSON-friendly: day keys are strings), and the final result."""
    at = {}
    for day in days:
        ours, theirs = census_on_day(ours_turns, day), census_on_day(theirs_turns, day)
        at[str(day)] = {
            "ours": ours["money"], "theirs": theirs["money"],
            "strawberry_gap": theirs["planted"].get("STRAWBERRY", 0) - ours["planted"].get("STRAWBERRY", 0),
            "head_gap": theirs["head_placed"] - ours["head_placed"],
        }
    final_ours, final_theirs = ours_turns[-1][1]["money"], theirs_turns[-1][1]["money"]
    result = "loss" if final_ours < final_theirs else ("win" if final_ours > final_theirs else "tie")
    return {"opponent": opponent, "seed": seed, "seat": champion_seat(seed), "at": at,
            "final_ours": final_ours, "final_theirs": final_theirs, "result": result}


def _row(readings, day, margin):
    fired = [r for r in readings if behind(r["at"][str(day)]["ours"], r["at"][str(day)]["theirs"], margin)]
    wins = [r for r in readings if r["result"] == "win"]
    losses = [r for r in readings if r["result"] == "loss"]
    fired_wins = [r for r in fired if r["result"] == "win"]
    fired_losses = [r for r in fired if r["result"] == "loss"]
    games = len(readings)
    return {
        "games": games,
        "fired": len(fired),
        "wins": len(wins),
        "losses": len(losses),
        "fire_rate": len(fired) / games if games else None,
        "precision": len(fired_losses) / len(fired) if fired else None,
        # No wins: there is nothing for the trigger to harm -- 0, not unknown.
        "harm": len(fired_wins) / len(wins) if wins else 0.0,
        "recall": len(fired_losses) / len(losses) if losses else None,
    }


def tabulate(readings, days=DAYS, margins=MARGINS):
    """``{(day, margin): {opponent: row, ..., "pooled": row}}``, champion first."""
    opponents = sorted({r["opponent"] for r in readings}, key=lambda n: (n != CHAMPION, n))
    table = {}
    for day in days:
        for margin in margins:
            cell = {opp: _row([r for r in readings if r["opponent"] == opp], day, margin)
                    for opp in opponents}
            cell["pooled"] = _row(readings, day, margin)
            table[(day, margin)] = cell
    return table


def actionable(row):
    """The declared bars: fires often enough, and rarely on a game we win."""
    return (row["fire_rate"] is not None and row["fire_rate"] >= FIRE_BAR
            and row["harm"] is not None and row["harm"] <= HARM_BAR)


def informative(row):
    """A row where the trigger could have been wrong: at least one win to harm
    and one loss to catch. Against an opponent we never beat, harm is 0 by
    construction and a star would say nothing."""
    return row["wins"] >= 1 and row["losses"] >= 1


def _pct(x):
    return "   -" if x is None else f"{x:4.0%}"


def format_table(table):
    """One block per (day, margin): a line per opponent, then pooled; `*` marks
    a row that is both actionable and informative (has both outcomes to prove it)."""
    lines = []
    for (day, margin), cell in table.items():
        lines.append(f"day {day}  behind by >= {margin}%")
        lines.append(f"{'opponent':<46} {'games':>5} {'fired':>5} {'fire':>5} {'prec':>5} {'harm':>5} "
                     f"{'recall':>6} {'W':>3} {'L':>3}")
        for name, r in cell.items():
            mark = " *" if actionable(r) and informative(r) else ""
            lines.append(f"{name:<46} {r['games']:>5} {r['fired']:>5} {_pct(r['fire_rate']):>5} "
                         f"{_pct(r['precision']):>5} {_pct(r['harm']):>5} {_pct(r['recall']):>6} "
                         f"{r['wins']:>3} {r['losses']:>3}{mark}")
        lines.append("")
    return "\n".join(lines).rstrip()


def format_asymmetry(readings, days=DAYS):
    """Per opponent and day, the median of (rival minus ours) for strawberry tiles and head placed."""
    opponents = sorted({r["opponent"] for r in readings}, key=lambda n: (n != CHAMPION, n))
    lines = [f"{'opponent':<46} " + " ".join(f"{'d' + str(d) + ' straw/head':>16}" for d in days)]
    for opp in opponents:
        mine = [r for r in readings if r["opponent"] == opp]
        cells = []
        for day in days:
            straw = statistics.median(r["at"][str(day)]["strawberry_gap"] for r in mine)
            head = statistics.median(r["at"][str(day)]["head_gap"] for r in mine)
            cells.append(f"{straw:+.0f}/{head:+.0f}".rjust(16))
        lines.append(f"{opp:<46} " + " ".join(cells))
    return "\n".join(lines)


# --- live games -------------------------------------------------------------

def run(seeds=SEEDS, opponents=OPPONENTS):  # pragma: no cover
    """Play every (opponent, seed) once, sides alternated by seed parity, and
    read both farms' census. Externals are pinned/verified and fresh per game
    (#247); `census_series` calls an agent with the observation alone, so each
    external is handed (obs, configuration) and the wrapper trims to its arity."""
    os.environ.setdefault("ROBRICULTURE_STRICT", "1")
    from kaggle_environments import make
    from harness.external_pool import external_anchor_agents
    from harness.farm_census import census_series
    from kaggisim.strategy import make_agent
    from strategies import load

    config = make("kaggriculture").configuration
    external_names = [n for n in opponents if n != CHAMPION]
    externals = external_anchor_agents(external_names) if external_names else {}
    readings = []
    for opponent in opponents:
        for seed in seeds:
            us = make_agent(load(CHAMPION)())
            if opponent == CHAMPION:
                them = make_agent(load(CHAMPION)())
            else:
                wrapper = externals[opponent].fresh()
                them = (lambda obs, w=wrapper: w(obs, config))
            if champion_seat(seed) == 0:
                seat0, seat1 = census_series(us, them, seed, closing=True)
            else:
                seat0, seat1 = census_series(them, us, seed, closing=True)
            ours, theirs = seat_series(seed, seat0, seat1)
            reading = game_reading(ours, theirs, opponent, seed)
            readings.append(reading)
            print(f"{opponent:<46} seed {seed} {reading['result']:<4} "
                  f"{reading['final_ours']:>8.0f} vs {reading['final_theirs']:>8.0f}", flush=True)
    return readings


def main(argv=None):  # pragma: no cover
    ap = argparse.ArgumentParser(description="scoreboard trigger control (#197, Stage 1)")
    ap.add_argument("--record", default=RECORD, help="where the raw readings are written / read")
    ap.add_argument("--from-record", action="store_true", help="re-derive the tables without replaying")
    args = ap.parse_args(argv)

    if args.from_record:
        with open(args.record) as f:
            readings = json.load(f)["readings"]
    else:
        readings = run()
        os.makedirs(os.path.dirname(args.record), exist_ok=True)
        with open(args.record, "w") as f:
            json.dump({"champion": CHAMPION, "seeds": list(SEEDS), "days": list(DAYS),
                       "margins": list(MARGINS), "fire_bar": FIRE_BAR, "harm_bar": HARM_BAR,
                       "readings": readings}, f, indent=1)
        print(f"record written: {args.record}")

    print(format_table(tabulate(readings)))
    print()
    print("asymmetry, median of rival minus ours (strawberry tiles / head placed):")
    print(format_asymmetry(readings))
    cells = [(d, m) for (d, m), cell in tabulate(readings).items()
             if actionable(cell["pooled"]) and informative(cell["pooled"])]
    print(f"actionable pooled cells (fire >= {FIRE_BAR:.0%}, harm <= {HARM_BAR:.0%}): {cells or 'none'}")
    print(f"seating control: {'OK' if seats_alternated(readings) else 'FAIL -- one seat only'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
