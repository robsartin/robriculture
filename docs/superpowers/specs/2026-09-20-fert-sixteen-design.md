# fert_sixteen — the fertilizer line from day 16 (#324)

**Issue:** #324 (declaration posted before any code). **Branch:** `324-fert-sixteen` from `main`.
**Decided with Rob, 2026-09-20 ("both in order, declare fertilizer"):** the single lever is the day the fertilizer line starts, sixteen; day twelve is arm B, recorded. Judged under ADR-0007 as amended 2026-09-16 and corrected 2026-09-17.

## Context
Fertilizer doubles a strawberry tile's yield on its production day (#277's seam). Started on day 8 (#286) it beat the champion 13/16 and lost on the anchors: the walk for fertilizer delayed the second quadrant's planting two days and the withheld sales starved days 1–7. From day 16 the field is planted and cash is not scarce. Two scratch seed sets (1479–1510, spent) read day 16 at 15/16 and 15/16, +11.2K and +9.8K; day 12 at 14/16 and 12/16.

## The change
`strategies/fert_sixteen.py`: `FertSixteenStrategy(TwelveHeadStrategy)`, `name = "fert_sixteen"`, `benchmark = False`, `FERT_FROM = 16`.

```
fertilizer_stock(day) = fert_six.FERT_STOCK if (day or 0) >= FERT_FROM else None
fertilize_crops(day)  = fert_six.FERT_CROPS if (day or 0) >= FERT_FROM else None
```
The two seams as `fert_six` defines them, its constants imported and never restated. Melon is harvested before day 16, so the crop the line reaches is strawberry. Everything else is twelve_head's.

## The bench: `harness/sixteen_bench.py`
Constants: `CONTENDER = "fert_sixteen"`, `CHAMPION = "twelve_head"`, `SEEDS = tuple(range(1511, 1527))`, `CONTROL_SEED = 1511`, `CHAMPION_BAR = 0.60`, `ANCHOR_BAR = 0.90`, `FERTILIZE_BAR = 100`, `STRAWBERRY_FACTOR = 1.5`, `EARLY_DAYS = range(1, 17)`, `ARM_B = "from_twelve"`, `ARM_B_FROM = 12`, `LONESPEAR = EXTERNAL_ANCHORS[0]` (the pool's first entry after #317; the assertion pins the name), and `MADHUR`, `REFERENCE` re-exported from `reserve_bench`.

- Control 1, identity: `off_class()` (every seam off + the reference's caps + the frozen `HERD_RAMP_F`, derived from `_seam_names()`) vs the reference equals the reference vs itself on seed 1511; precondition reward > 0.
- Control 2, mechanism: one game `fert_sixteen` (seat 0) vs `twelve_head` on seed 1511. `reading(steps, seat)` = `{"fertilize", "strawberry", "fertilizer_sold", "dawn_1_16"}` — FERTILIZE actions (`fert_bench.action_counts`), strawberry and fertilizer units sold (`fert_bench.units_sold`), money at dawn on days 1–16 (`six_bench.dawn_cash`). Bars: contender `fertilize >= FERTILIZE_BAR`; contender `strawberry >= STRAWBERRY_FACTOR × champion's`; contender `dawn_1_16 == champion's`. Both readings and `four8_bench.escapes` printed.
- Criterion: `champion_row = rival_bench.decided_row(CONTENDER, CHAMPION, SEEDS)`; `rival_bench.criterion(champion_row, anchor_rows, external_pairs=paired_external_rows(...), identical=champion_row["identical"])`; `void` → exit 2, else 0 / 1. The verdict line prints decided/identical and the madhur and lonespear pairs (the two externals that remain in `EXTERNAL_ANCHORS` besides shashank).
- Recorded: arm B `from_twelve` = `fert_sixteen` with `FERT_FROM = 12` vs `twelve_head` by `decided_row`; `--recorded`, never gated.
- Exits: 0 PROMOTE, 1 REJECTED, 2 VOID.

## Alternatives rejected
- Day 8: #286, rejected on the anchors.
- Day 12: arm B, weaker on both seed sets.
- A larger stock: eight sufficed for 120 FERTILIZE actions.
- Fertilizing only where the town takes strawberry: a second knob without a reading.

## Tests (pure TDD)
`FERT_FROM == 16`; `fertilizer_stock` and `fertilize_crops` are `None` through day 15 and `fert_six`'s constants from day 16 (and `None` for `day=None`); the class defines exactly those two seams and nothing else callable; the ramp is `twelve_head`'s and the caps `free_straw`'s; registered. Bench: the declared constants (and `MADHUR` from `reserve_bench`); seed freshness (…, 960–1510); `reading` on stubbed counts/units/dawn cash; `mechanism_failures` names the bars; `off_class()` every seam off (both fertilizer seams return None) + survives a turn; `arm_b_class().FERT_FROM == 12` and its seams fire from day 12; `decided_row` and `criterion` are `rival_bench`'s; `play` and the reference pinned.
