"""#172 Stage 1: does a mirror-opponent, final-money rollout rank sell policies
the way a real-opponent rollout does?

    python -m harness.objective_check                      # dense_farm vs the gate opponent
    python -m harness.objective_check --champion meta_rancher --seeds 0 1 --days 3 5 7 10 15

Declared before code (docs/superpowers/specs/2026-09-05-mpc-sell-hold-objective-design.md):
candidates are the champion behind `strategies.sell_discipline` at each
`min_frac` in GRID; states are hour 0 of each day in --days from a real game of
the bare champion vs the gate opponent on each --seed; prediction = the
candidate mirrored on the other farm, truth = the real opponent there, with
its private state restored from the real game, both rolled to step 720 from
the same state under the same seed; the statistic is
Spearman rho over the grid, one per state; PASS iff the median over DEFINED
states is >= BAR. Controls run first, per state: the truth rollout at min_frac
0.0 must reproduce the real game's final money to the value before the other
21 rollouts for that state run, or the run is void from there on.
`main` runs under `ROBRICULTURE_STRICT=1` (see below), so a crashing candidate
raises instead of being measured as a silent PASS (ADR-0006).

Exit codes: 0 PASS / 1 FAIL / 2 VOID (a control mismatch).

rho ranks; it does not choose (#177). `predicted_best`/`true_best` are recorded
for that reason and are not part of the verdict.
"""

from __future__ import annotations

import argparse
import os
import statistics

from harness.ladder_correlation import spearman


class ControlFailed(Exception):
    """The truth rollout at min_frac 0.0 did not reproduce the real game's
    final money for (seed, day); the run is void from this state on."""

    def __init__(self, seed, day, got, real):
        self.seed, self.day, self.got, self.real = seed, day, got, real
        super().__init__(
            f"seed {seed} day {day}: control truth@0.0={got:.0f} real={real:.0f} "
            "MISMATCH -- RUN VOID")


#: The declared grid; 0.0 is the champion unchanged — the positive control.
GRID = (0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0)
#: The declared bar on the median rho over defined states.
BAR = 0.40
DEFAULT_DAYS = (3, 5, 7, 10, 15)
DEFAULT_SEEDS = (0, 1)
EPISODE_STEPS = 720


def score_state(predicted, truth):
    """Spearman rho of predicted vs true final money over the candidates
    (keys of both dicts, same set), plus which candidate each side ranks
    first. `rho` is None when undefined (no rank variance on a side)."""
    keys = sorted(predicted)
    xs = [predicted[k] for k in keys]
    ys = [truth[k] for k in keys]
    return {
        "rho": spearman(xs, ys),
        "predicted_best": max(keys, key=lambda k: predicted[k]),
        "true_best": max(keys, key=lambda k: truth[k]),
        "n": len(keys),
        "distinct_truth": len(set(truth.values())),
    }


def verdict(rhos, bar=BAR):
    """PASS iff the median of the DEFINED rhos is >= `bar`. Undefined states
    (None) are counted and excluded, never scored as zero: an all-tied state
    is 'no evidence', not 'no relationship'."""
    defined = [r for r in rhos if r is not None]
    median = statistics.median(defined) if defined else None
    return {
        "passed": median is not None and median >= bar,
        "median": median,
        "defined": len(defined),
        "undefined": len(rhos) - len(defined),
    }


def format_table(rows):
    """One line per state: seed, day, n, distinct (truth values), rho,
    predicted best, true best, cost."""
    head = (f"{'seed':>4} {'day':>3} {'n':>3} {'distinct':>8} {'rho':>9} "
           f"{'pred.best':>9} {'true.best':>9} {'s/rollout':>9}")
    lines = [head]
    for r in rows:
        rho = "undefined" if r["rho"] is None else f"{r['rho']:.2f}"
        lines.append(f"{r['seed']:>4} {r['day']:>3} {r['n']:>3} {r['distinct_truth']:>8} {rho:>9} "
                     f"{r['predicted_best']:>9.1f} {r['true_best']:>9.1f} "
                     f"{r['seconds_per_rollout']:>9.2f}")
    return "\n".join(lines)


def _candidate(champion_cls, min_frac):  # pragma: no cover
    from kaggisim.strategy import make_agent
    from strategies.sell_discipline import SellDiscipline
    return make_agent(SellDiscipline(champion_cls(), min_frac))


def run_state(state, champion_name, opponent_name, real_final, grid=GRID):  # pragma: no cover
    """Score one state: every candidate rolled with a mirror and with the
    real opponent. The positive control -- the truth rollout at min_frac 0.0
    -- runs FIRST and is checked against `real_final` before any of the other
    21 rollouts run; on a mismatch, `ControlFailed` is raised and nothing
    else in this state is rolled. The control rollout is reused as the
    grid's 0.0 truth value rather than rolled a second time. Returns the
    table row plus the raw per-candidate money."""
    from harness.rollout_objective import timed_final_money
    from kaggisim.strategy import make_agent
    from strategies import load

    champion_cls, opponent_cls = load(champion_name), load(opponent_name)

    control_truth, control_seconds = timed_final_money(
        state["obs"], _candidate(champion_cls, 0.0), make_agent(opponent_cls()),
        state["seed"], EPISODE_STEPS, opponent_private=state["opponent_private"])
    if control_truth != real_final:
        raise ControlFailed(state["seed"], state["day"], control_truth, real_final)

    predicted, truth, seconds = {}, {0.0: control_truth}, [control_seconds]
    for f in grid:
        p, tp = timed_final_money(state["obs"], _candidate(champion_cls, f),
                                  _candidate(champion_cls, f), state["seed"], EPISODE_STEPS)
        predicted[f] = p
        seconds.append(tp)
        if f == 0.0:
            continue
        t, tt = timed_final_money(state["obs"], _candidate(champion_cls, f),
                                  make_agent(opponent_cls()), state["seed"], EPISODE_STEPS,
                                  opponent_private=state["opponent_private"])
        truth[f] = t
        seconds.append(tt)
    row = score_state(predicted, truth)
    row.update(seed=state["seed"], day=state["day"],
               seconds_per_rollout=sum(seconds) / len(seconds),
               predicted=predicted, truth=truth)
    return row


def main(argv=None):  # pragma: no cover
    # An instrument inverts ADR-0006's default: a crash must surface, not
    # become PASS.
    os.environ.setdefault("ROBRICULTURE_STRICT", "1")

    from harness.promotion import gate_opponent
    from harness.state_set import capture_states
    from kaggisim.strategy import make_agent
    from strategies import load

    ap = argparse.ArgumentParser(description="#172 Stage 1 objective check")
    ap.add_argument("--champion", default="dense_farm")
    ap.add_argument("--opponent", default=None, help="default: champion.json gate_opponent")
    ap.add_argument("--seeds", type=int, nargs="+", default=list(DEFAULT_SEEDS))
    ap.add_argument("--days", type=int, nargs="+", default=list(DEFAULT_DAYS))
    args = ap.parse_args(argv)
    opponent = args.opponent or gate_opponent()
    print(f"champion={args.champion} opponent={opponent} seeds={args.seeds} days={args.days} "
          f"grid={GRID} bar={BAR}")

    rows = []
    for seed in args.seeds:
        states, real_final = capture_states(make_agent(load(args.champion)()),
                                            make_agent(load(opponent)()), seed,
                                            args.days, hour=0, episode_steps=EPISODE_STEPS)
        for state in states:
            try:
                row = run_state(state, args.champion, opponent, real_final)
            except ControlFailed as e:
                print(f"seed {e.seed} day {e.day:>2}: control truth@0.0={e.got:.0f} "
                      f"real={e.real:.0f} MISMATCH -- RUN VOID")
                print()
                print(format_table(rows))
                return 2
            print(f"seed {seed} day {state['day']:>2}: control truth@0.0={row['truth'][0.0]:.0f} "
                  f"real={real_final:.0f} OK")
            rows.append(row)
            print(format_table([row]).splitlines()[1])

    print()
    print(format_table(rows))
    v = verdict([r["rho"] for r in rows])
    med = "undefined" if v["median"] is None else f"{v['median']:.2f}"
    print(f"\nmedian rho over {v['defined']} defined states ({v['undefined']} undefined): {med}  "
          f"bar {BAR:.2f}  ->  {'PASS' if v['passed'] else 'FAIL'}")
    print("per-candidate money (predicted | truth):")
    for r in rows:
        print(f"  seed {r['seed']} day {r['day']:>2}: " + "  ".join(
            f"{f:.1f}:{r['predicted'][f]:.0f}|{r['truth'][f]:.0f}" for f in GRID))
    return 0 if v["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
