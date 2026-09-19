# twelve_head — the herd target's last step is twelve (#320)

**Issue:** #320 (declaration posted before any code). **Branch:** `320-twelve-head` from `main`.
**Decided with Rob, 2026-09-19:** the single lever is the herd ramp's last step, twelve instead of thirteen; no arm B. Judged under ADR-0007 as amended 2026-09-16 and corrected 2026-09-17.

## Context
With four herders the herd is labour-bound at twelve head (#288, 2026-09-16); the frozen path buys a thirteenth that stays pending in the shed. Scratch probe (seeds 1447–1462, spent): herd target 12 against `free_straw` 16/16, mean +446, animal spend 6,300 vs 6,700, placed head 12/12 on both sides.

## The change
`strategies/twelve_head.py`: `TwelveHeadStrategy(FreeStrawStrategy)`, `name = "twelve_head"`, `benchmark = False`, `HERD_RAMP_F = HERD_RAMP_T`.

```
HERD_RAMP_T = ((0, 4), (6, 8), (12, 12))      # payday_herd's HERD_RAMP_P with its last step at twelve
```
`field_pace.herd_target(day)` = `max(_ramp(HERD_RAMP_F, day), field_rival.animal_target(day))`, so the target is 4 → 8 → 12 and never below the frozen ramp. No method is overridden.

## The bench: `harness/twelve_bench.py`
Constants: `CONTENDER = "twelve_head"`, `CHAMPION = "free_straw"`, `SEEDS = tuple(range(1463, 1479))`, `CONTROL_SEED = 1463`, `CHAMPION_BAR = 0.60`, `ANCHOR_BAR = 0.90`, `HEAD_DAY = 20`, `LONESPEAR = EXTERNAL_ANCHORS[1]`, and `PILKWANG`, `MADHUR`, `REFERENCE` re-exported from `reserve_bench`.

- Control 1, identity: `off_class()` (every seam off + the reference's caps + the frozen `HERD_RAMP_F`, derived from `_seam_names()`) vs the reference equals the reference vs itself on seed 1463; precondition reward > 0.
- Control 2, mechanism: one game `twelve_head` (seat 0) vs `free_straw` on seed 1463. `reading(steps, seat)` = `{"head_20", "pending_20", "animal_spend", "milk_wool"}` — placed head on the day-20 board (`feed_bench.board_on_day` + `farm_census.animals_placed`), pending COW + SHEEP in the shed on day 20 (`fourth_bench.pending_at`), animal spend and MILK + WOOL revenue via `episode_analysis.decompose`. Bars: contender `pending_20 < champion's`; contender `animal_spend < champion's`. Both readings and `four8_bench.escapes` printed.
- Criterion: `champion_row = rival_bench.decided_row(CONTENDER, CHAMPION, SEEDS)`; `rival_bench.criterion(champion_row, anchor_rows, external_pairs=paired_external_rows(...), identical=champion_row["identical"])`; `void` → exit 2, else 0 / 1.
- Recorded: none.
- Exits: 0 PROMOTE, 1 REJECTED, 2 VOID.

## Alternatives rejected
- Eleven: the herders work twelve.
- A twelve-tile pasture block: 8/16; it changes the crop order too.
- Selling the pending head: no market for a live animal.

## Tests (pure TDD)
`HERD_RAMP_T` is `payday_herd.HERD_RAMP_P` with the last step at twelve; `herd_target` reads 4 / 8 / 12 at days 0, 6, 12, 20 and equals `free_straw`'s before day 12; no seam and no method overridden; registered; `FOURTH_DAY == 8`; `CAPS is free_straw.CAPS_S`. Bench: the declared constants; seed freshness (…, 960–1462); `reading` on stubbed board/pending/decompose and its early-end failure; `mechanism_failures` names the bars; `off_class()` every seam off + survives a turn (and its `HERD_RAMP_F` is the frozen one, not `HERD_RAMP_T`); `decided_row` and `criterion` are `rival_bench`'s; `play` and the reference pinned.
