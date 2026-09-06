# #172 Stage 1: does a mirror-opponent, final-money rollout rank sell/hold policies?

- **Issue:** #172 (re-specified 2026-09-05)
- **Date:** 2026-09-05
- **Depends on:** #177 (the only rollout configuration that ever correlated with reality),
  #159/#164 (`kaggisim.forward.rebuild` is exact), #195 (pinned to 1.32.7)
- **Decides:** whether Stage 2 (wiring a sell/hold planner into `act()`) is worth building

## Context

#172 as first written could not fire: its objective (idle opponent, fixed horizon,
`standing_value`) is the rho = -0.05 metric #174 measured and #177 diagnosed. #177 found
exactly one configuration with signal — **mirror opponent, rolled to the end of the game,
scored on final money** — at rho = +0.20 to +0.69 depending on state, n = 8-12, and set a
four-minute rho check as the entry condition for any further rollout-scored work.

Nothing from #174 or #177 is on `main`. The candidate set, the state set and the
mirror-rollout code lived on branches that are gone. This stage rebuilds the check on
`main`, for the decision #172 actually cares about — **how hard to sell into a market** —
and gates on it before any controller is written.

## Question and pass criterion (declared before code, ADR-0007)

**Question.** From a mid-game state, does the rollout-predicted final money of a sell-policy
variant rank the variants the same way their true final money does?

**Candidates.** The champion with one sell-discipline knob, `min_frac`: every SELL order is
capped by `kaggisim.pricing.sell_quantity(item, inventory, have, min_price=min_frac * base)`,
so no unit is sold below `min_frac` of its base price and the rest is held in the shed.
`min_frac = 0.0` is the champion unchanged (liquidate everything — the positive control:
the wrapper at 0.0 must produce byte-identical orders). Grid, fixed:

    min_frac in {0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0}    (11 candidates)

**State set.** Ten states: a real game of the champion against the gate opponent
(`meta_bot`, `harness/champion.json`) on seeds 0 and 1, snapshotting our observation at
hour 0 of days 3, 5, 7, 10 and 15. Days 3/5/7 are #177's; 10 and 15 add the phase where
sheds are full and markets glutted, which is where a sell decision matters.

**Prediction.** From a state, roll every candidate to step 720 with the **mirror opponent**
— the same candidate playing the other farm — and read our final money.

**Truth.** From the same state, roll every candidate to step 720 with the **real gate
opponent** (`meta_bot`) on the other farm, and read our final money. Both rollouts use
`kaggisim.forward.rebuild` under the same seed, so weeds are identical between them; the
differences are who plays the other farm and, for the truth only, that the other farm starts
with its real private stock; the mirror starts with an empty shed (Decision 5).

> **Amendment 2026-09-05, after the first run.** The truth rollout also restores the
> opponent's **private state** (shed, seeds, inventories) captured from the real game.
> The harness drives that game, so it knows the state even though the live planner never
> will. Without it the positive control failed at seed 0, day 15 — truth 68,715 against a
> real 68,451, with the opponent holding WHEAT 7 / FERTILIZER 11 at the snapshot — and
> passed only on the days whose opponent shed happened to be empty. Restoring the private
> state makes all five day-15-inclusive controls exact (measured before the fix was
> written). The **prediction** is unchanged: the mirror still starts the other farm with an
> empty shed, per Decision 5, because that is the planner's real information set.
> Interpretation: a low rho can therefore come from the private-state gap as well as from
> the mirror being a poor opponent model; the write-up must say which it looks like.

**Statistic.** Spearman rho between predicted and true final money over the 11 candidates,
one rho per state, using `harness.ladder_correlation.spearman` (stdlib, tie-averaged).

**Pass:** median rho over the ten states **>= 0.40**, with the positive control holding.
**Fail:** anything else. On fail, Stage 2 is not started and the issue records the table.
The criterion is not moved after the numbers exist; #204 records what happens when it is
set without checking the population first, which is why the control comes first here too.

**Recorded, not gated (constraints the issue names):** the cost of one rollout-to-end from
each day, and whether the best-predicted candidate is the true best (rho ranks; it does not
choose — #177).

## Decisions made without Rob (each is a one-line change if he disagrees)

1. **Champion = `dense_farm`**, not `champion.json`'s `submit_default` (`meta_rancher`,
   last changed 2026-08-18). `dense_farm` is the agent live on the ladder (#146, #206) and the
   one #146 measured crashing wool to the $1 floor — the market this stage is about. The
   champion is a CLI argument (`--champion`), so re-running on `meta_rancher` is one flag.
2. **The knob is a wrapper, not an edit.** `field_rival` is frozen (#181, pinned by
   `tests/test_dense_farm.py`); `dense_farm` inherits its sell sweep. A post-processing
   wrapper leaves both untouched and works on any strategy.
3. **Truth is a rollout with the real opponent, not a fresh ladder game.** A game re-run
   from turn 0 cannot be started from a mid-game state; a `rebuild` rollout can, and it is
   validated exact (#164). This is the same design as #177's measurement.
4. **Aggregate = median over states.** The issue says "rho >= 0.40 on the state set" without
   saying how ten rhos become one. Median is robust to one degenerate state (e.g. a day-3
   state where no candidate has anything to sell yet, so all predictions tie).
5. **Opponent's private shed is unknown to the mirror.** `rebuild` reconstructs the other
   farm from public state only, so the mirror starts with an empty shed. This is the
   planner's real information set at runtime, so it belongs in the prediction, not
   patched out.

## Design

Four units, each testable alone; nothing touches `strategies/field_rival.py` or the
champion's decisions.

### 1. `strategies/sell_discipline.py` — the knob

```
def cap_sells(orders, market, min_frac) -> list
    # each ["SELL", item, n] -> ["SELL", item, sell_quantity(item, inv, n, min_frac*base)]
    # drops an order whose cap is 0; leaves non-SELL orders and order positions alone
class SellDiscipline(Strategy)   # wraps any Strategy; act() = inner.act() with market capped
```

`market[:10]` is preserved: capping never adds orders, so the ten-slot cap and the
sells-first ordering (#117) are the inner strategy's and stay as they were. Dropping a
zero-cap SELL frees the slot rather than burning it on a dead order (#146's lesson on
dead orders).

### 2. `harness/state_set.py` — capture states from a real game

```
def capture_states(agent, opponent, seed, days, hour=0) -> list[dict]
    # drives a real env step by step (as tests/test_forward.py does) and deep-copies
    # our seat's observation at (day, hour); returns [{"day","seed","obs"}]
```

Pure and small; the state set is regenerated by the run, not committed (observations are
large and the run takes seconds to reach day 15).

### 3. `harness/rollout_objective.py` — roll to the end, read final money

```
def final_money(obs, our_strategy, opponent_agent, seed, episode_steps=720) -> float
    # forward.rebuild(obs, seed) then step both seats to episode_steps; our farm's money
def mirror(strategy_factory) -> agent      # the candidate on the other farm
```

The opponent is an argument, so prediction (mirror) and truth (`meta_bot`) are the same
function called twice. `ROLLOUT_PASS` is not used anywhere in this stage: #174 showed an
idle opponent is a dynamics change, not a bias.

### 4. `harness/objective_check.py` — the CLI and the table

```
python -m harness.objective_check --champion dense_farm --seeds 0 1 --days 3 5 7 10 15
```

Builds the grid, runs the control, computes per-state rho, prints the table below and the
verdict against the declared criterion, plus wall-clock per rollout per day. Reads
`gate_opponent` from `harness/champion.json` (one source, cited).

    state (seed, day) | n | rho | predicted best | true best | cost/rollout

`main()` is `# pragma: no cover` like every other harness entrypoint; the table assembly,
rho aggregation and verdict are pure functions with tests.

## Positive controls (run first; a failed control voids the run)

- `SellDiscipline(min_frac=0.0)` emits byte-identical actions to the bare champion on a
  full seeded game (both seats' rewards equal to the value).
- `final_money` with the bare champion and the real opponent from a state at day *d*
  equals the money the real game reached at step 720 — the #164 exactness, re-asserted on
  this code path.
- At least one state must have rank variance among the 11 candidates on the truth side;
  otherwise rho is undefined and the state is reported as such, not scored.

## Cost (estimate; measured and recorded by the run)

One rollout-to-end from day 3 is ~650 two-sided steps. At ~1 ms per two-sided step that
is ~0.7 s; 11 candidates x 10 states x 2 opponents = 220 rollouts, ~3 minutes, plus two
real games for the states. Matches #177's "four-minute check". If a step turns out to be
several ms, the run is still under half an hour — no budget question arises at this stage.

## Testing (pure TDD, red observed before green)

- `test_sell_discipline.py`: cap at 0.0 is identity; cap at 1.0 sells nothing into a market
  above its anchor; a SELL capped to 0 is dropped; non-SELL orders and order positions
  untouched; wrapper preserves `farmer`/`hands` verbatim.
- `test_state_set.py`: captures the requested (day, hour) observations with our seat's
  `private`; asks for a day past the game and gets a clear error.
- `test_rollout_objective.py`: the exactness control above, on a short game (`episode_steps`
  small so it runs in seconds); mirror agent is the candidate, not the champion.
- `test_objective_check.py`: verdict is PASS at median 0.40 and FAIL at 0.39; a state with
  no rank variance is reported undefined and excluded from the median; table columns.

## Out of scope (Stage 2 and beyond, only if Stage 1 passes)

Wiring anything into `act()`; per-turn wall-clock budgeting; the 200-game promotion test;
any knob other than `min_frac`; an opponent model better than the mirror.

## Alternatives rejected

- **Reuse `standing_value` with a mirror opponent.** rho = -0.19 (#177). Rejected.
- **Truth from fresh ladder games with each variant.** Cannot start mid-game, and each
  variant's game diverges from the state being scored; the correlation would mix the
  candidate's effect with a different game. Rejected in favour of the rebuild rollout.
- **Edit the sell sweep in `field_rival`/`dense_farm` directly.** Moves the measuring stick
  (#181) and breaks the frozen-benchmark pin. Rejected for the wrapper.
- **A hold-N-days knob instead of a price floor.** Needs per-item timers and state across
  turns; `min_frac` is stateless, uses the sim's own price curve via `pricing`, and is the
  knob #146's wool result points at. A second knob can be a follow-up if this one passes.
