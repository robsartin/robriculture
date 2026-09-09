# Scoreboard trigger: can "behind at day D" be read early enough to act on? (#197, Stage 1 only)

**Issue:** #197 — wild: play the scoreboard, not the balance sheet
**Branch:** `197-scoreboard`
**Decided with Rob, 2026-09-09:** the issue's Stage 1 estimator is dropped (rival money is
observable); it is replaced by a trigger control on spent seeds; the lever analysis below
finds no viable Stage 2 inside the champion's action space, so the issue runs Stage 1 only
and closes with the table and the analysis as its finding.

## What the exploration settled

1. **Rival money is in the live observation.** Both seats' `obs["farms"][rival]` carry
   `money`, `tiles`, `hands`, `unlocked_quadrants` (checked in a live game on both seats);
   only the rival's shed, seeds and inventories are hidden. The issue's Spearman-0.7
   estimator would infer a number the sim hands us.
2. **The economy has no dice beyond weeds and shop draws.** Prices start at each product's
   anchor and move only with sales and town-shop consumption. Melon is demanded by no shop:
   both farms floor it by day 12 and it never recovers (34-76 for the rest of a champion
   game on seed 816). Strawberry, milk and wool stay above base all season because shops
   drain them. "Variance" can only mean a payoff that depends on the rival.
3. **The champion already dumps its whole shed every turn** (`market_orders` sells first,
   everything tradable). It is a continuous spoiler of its own products; spoiling harder
   needs more units of the rival's product.
4. **The crop chooser has one move after day 15.** `crop_for_plot` plants the day's headline
   crop (strawberry after the pivot, plantable until ~day 19) and otherwise wheat. Wheat's
   price barely moves under flooding (log, 0.20). Strawberry planted after the trigger
   first yields on day 25. So the issue's lever collapses to "uncap strawberry", lands for
   four days, and kills both farms' strawberry income equally against every opponent whose
   mix we know (the champion 22 tiles, lonespear 24). This is the issue's declared
   alternative 2 — "the gambles available in this sim are all bad" — reached by reading the
   code. Rob chose not to spend a bench on it.
5. **The trigger is not obviously right.** On seed 816 the champion was behind 21% at day
   15 (13,824 vs 17,557) and won 64,765 to 59,875. A day-15 trigger fires on games we go on
   to win.

## Stage 1 — the trigger control (the whole deliverable)

**Question.** For a trigger "our money is behind the rival's by ≥ X% at the close of day D",
how often does it fire, how often does a fired game end in a loss (precision), how often does
it fire on a game we go on to win (harm), and how many losses does it catch (recall)?

**Data.** `third_herder` (the champion) against six opponents — itself and the five
`external_pool.EXTERNAL_ANCHORS` — on **spent** seeds 864-879 (16 each, 96 games), sides
alternated by seed parity (even: champion is player 0). Each game records both farms' census
per turn via `harness.farm_census.census_series`, so money, standing crops by kind and head
placed are available for both sides at every day. Externals are loaded through
`external_anchor_agents` (pinned, verified) and refreshed per game with `fresh()` (#247);
`census_series` calls an agent with the observation only, so each external is wrapped to
receive `(obs, configuration)` and the wrapper trims to the agent's own arity.

**Grid.** D ∈ {12, 15, 18, 21}; X ∈ {10, 20, 30}%. "Behind by X% at D" means
`ours < theirs * (1 - X/100)` on the last census of day D. The result is the final reward
comparison (loss = `ours < theirs`; a tie is not a loss and not a win).

**Readings, per (D, X), per opponent and pooled:** games, fire rate, precision, harm, recall.
Beside them, per opponent at each D (not gated): the rival's strawberry tiles minus ours and
the rival's head placed minus ours, medians over the 16 games — the asymmetry any future
spoil lever would need.

**Bars, declared before the run.** A cell is *actionable* when fire rate ≥ 25% AND harm ≤ 20%.
The table is reported whole; the bars only name which cells, if any, a future contender could
declare a trigger from. No cell clearing both bars is a finding, not a failure.

**Output.** `python -m harness.scoreboard_probe` prints the table (rows D×X, columns per
opponent + pooled) and the asymmetry table, and writes the raw per-game readings to
`harness/scoreboard/trigger_readings.json` — committed as the record, about 100 rows — so the
table re-derives without replaying.

## Components

- `harness/scoreboard_probe.py`
  - constants: `CHAMPION = "third_herder"`, `SEEDS = tuple(range(864, 880))`, `DAYS = (12, 15, 18, 21)`,
    `MARGINS = (10, 20, 30)`, `FIRE_BAR = 0.25`, `HARM_BAR = 0.20`, `OPPONENTS = (CHAMPION,) + EXTERNAL_ANCHORS`.
  - pure: `behind(ours, theirs, margin_pct) -> bool`; `money_on_day(turns, day) -> float`
    (last census of the day, raises when the day was never reached, as `front_bench` does);
    `game_reading(ours_turns, theirs_turns, final) -> dict` (money per side at each D,
    strawberry tiles and head placed per side at each D, final result);
    `tabulate(readings, days, margins) -> {(day, margin): {opponent: row, "pooled": row}}` with
    row = `games, fired, fire_rate, precision, harm, recall`; `actionable(row)`; `format_table`,
    `format_asymmetry`.
  - live (`# pragma: no cover`): `run(seeds, opponents)` → readings; `main`.
- `tests/test_scoreboard_probe.py`: the pure parts on hand-built censuses — `behind` at the
  boundary, `money_on_day` closing-board and missing-day raise, `game_reading` on a two-turn
  fixture, `tabulate` on four fabricated readings whose precision/harm/recall are known,
  `actionable` at each bar, formatting prints a row per cell.

## Outcome

The table and the lever analysis are posted on #197 as its result; the issue closes
`not_planned` (no contender was built; nothing promotes). The probe and its record merge as a
harness PR — the trigger table is the input any future scoreboard contender declares from,
and the visible-rival-money and one-move-chooser findings correct the issue's premises.

## Not in scope

No Stage 2, no strategy change, no fresh seeds, no ADR change. If a future contender finds a
lever with a real asymmetry (a rival whose income mix differs from ours), it declares its
trigger from this table and runs the issue's original criterion against the current gate.
