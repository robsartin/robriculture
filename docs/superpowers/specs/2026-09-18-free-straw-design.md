# free_straw — the strawberry cap removed (#312)

**Issue:** #312 (declaration posted before any code). **Branch:** `312-free-straw` from `main`.
**Decided with Rob, 2026-09-18 ("crop line first"):** the single lever is the strawberry cap, removed; no arm B. Judged under ADR-0007 as amended 2026-09-16 and corrected 2026-09-17.

## Context
#288: strawberry-shop count predicts our STRAWBERRY revenue at r = 0.72. A scratch probe (seeds 1287–1302, spent) of fixed caps against `town_split`'s 38: caps 20 and 28 lose 0/16 at every shop count; cap 48 (= 42 tiles, the land) wins 15/16 by 1.4–8K, losing only the one town with no strawberry shop. Strawberry revenue tracks tiles almost linearly; the cap binds from day 16, when the third quadrant opens, and sends four tiles to wheat worth a third as much.

## The change
`strategies/free_straw.py`: `FreeStrawStrategy(TownSplitStrategy)`, `name = "free_straw"`, `benchmark = False`, `CAPS = CAPS_S`.

```
CAPS_S = {"MELON": 10, "WHEAT": 24}      # town_split's caps without the STRAWBERRY key
```
`field_rival.crop_for_plot` and `market_orders` treat an absent key as no cap (`caps.get(crop, 10 ** 6)` / `caps.get(crop)` → all empty plots), so every empty crop tile after the melon window is strawberry while strawberry can still finish, then wheat as before. No method is overridden.

## The bench: `harness/straw_bench.py`
Constants: `CONTENDER = "free_straw"`, `CHAMPION = "town_split"`, `SEEDS = tuple(range(1303, 1319))`, `CONTROL_SEED = 1303`, `CHAMPION_BAR = 0.60`, `ANCHOR_BAR = 0.90`, `TILE_DAY = 16`, `LATE_DAY = 20`, `LONESPEAR = EXTERNAL_ANCHORS[1]`, and `PILKWANG`, `MADHUR`, `REFERENCE` re-exported from `reserve_bench`.

- Control 1, identity: `off_class()` (every seam off + the reference's caps + the frozen `HERD_RAMP_F`, derived from `_seam_names()`) vs the reference equals the reference vs itself on seed 1303; precondition reward > 0.
- Control 2, mechanism: one game `free_straw` (seat 0) vs `town_split` on seed 1303. `reading(steps, seat)` = `{"straw_16", "straw_20", "strawberry", "wheat"}` — standing strawberry tiles on the day-16 and day-20 boards (`feed_bench.board_on_day` + `field_rival.standing_crops`), revenue via `episode_analysis.decompose`. Bars: contender `straw_16 > champion's`; contender `strawberry > champion's`. Both readings and `four8_bench.escapes` printed.
- Criterion: `champion_row = rival_bench.decided_row(CONTENDER, CHAMPION, SEEDS)`; `rival_bench.criterion(champion_row, anchor_rows, external_pairs=paired_external_rows(...), identical=champion_row["identical"])`; `void` → exit 2, else 0 / 1. The verdict line prints decided/identical and the madhur, pilkwang and lonespear pairs.
- Recorded: none.
- Exits: 0 PROMOTE, 1 REJECTED, 2 VOID.

## Alternatives rejected
- A cap of 42 or 48: a number that only means "the land"; the absent key says what it means.
- A lower cap in poor strawberry towns: loses at every shop count probed.
- A town-conditioned cap: needs a per-turn caps seam on the frozen benchmark; deferred until the plain knob has a verdict.

## Tests (pure TDD)
`CAPS_S` has no STRAWBERRY key and keeps `town_split`'s MELON and WHEAT; `crop_for_plot` with `CAPS_S` still answers STRAWBERRY at 40 standing where `town_split`'s caps answer WHEAT; the class overrides no seam and no method; registered; `FOURTH_DAY == 8`. Bench: the declared constants; seed freshness (…, 960–1302); `reading` on stubbed boards/decompose and its early-end failure; `mechanism_failures` names the bars; `off_class()` every seam off + survives a turn; `decided_row` and `criterion` are `rival_bench`'s; `play` and the reference pinned.
