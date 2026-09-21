# second_melon — a second melon wave through a `melon_windows` seam (#334)

**Issue:** #334 (declaration posted before any code). **Branch:** `334-second-melon` from `main`.
**Decided with Rob, 2026-09-21 ("declare it"):** the single lever is a second melon wave on days 12–13; it needs one new seam on the frozen benchmark, off by default. No arm B. Judged under ADR-0007 as amended 2026-09-16 and 2026-09-20, corrected 2026-09-17.

## Context
In 27 of `fert_sixteen`'s 29 decomposable ladder games the opponent earned 15–22K from melon to our 8–11K. We plant melon only before the day-5 pivot. Two scratch seed sets (1639–1670, spent) read a day 12–13 window at cap 10 as 12/16 and 12/16, +1.3K and +1.9K; a day 12–15 window at cap 12 lost on both.

## The seam (commit 1)
`strategies/field_rival.py`:
- `crop_for_day(day, season_days=SEASON_DAYS, pivot=PIVOT_DAY, windows=None)`: when `windows` holds an inclusive `(first, last)` pair containing `day` and `hh.plantable("MELON", day, season_days)`, the answer is `"MELON"`; otherwise exactly the frozen answer. `windows=None` is the frozen benchmark.
- `crop_for_plot(day, standing, season_days=SEASON_DAYS, caps=None, pivot=None, windows=None)` passes `windows` to `crop_for_day`; the MELON cap still binds.
- `market_orders(..., fert=None, windows=None)` passes `windows` to `crop_for_plot` in its `seed()` block, so seed-buying agrees with planting.
- `FieldRivalStrategy.melon_windows(self)` returns `None`; its docstring says it is a seam (#334) so `sheep_bench._seam_names()` lists it. `act` reads `windows = self.melon_windows()` once per turn and passes it to `crop_for_plot` and `market_orders`.
- `harness/feed_bench.off_class`'s hand-written stub gains `"melon_windows": lambda self: None`.
- Every `assert len(names) == 16` seam-count pin becomes 17 (twelve test files; the pin exists so a new seam cannot be left on).

## The contender (commit 2)
`strategies/second_melon.py`: `SecondMelonStrategy(FertSixteenStrategy)`, `name = "second_melon"`, `benchmark = False`, `MELON_WINDOWS = ((12, 13),)`, `melon_windows()` returns `MELON_WINDOWS`. Caps stay `free_straw.CAPS_S` (melon ten), so the wave takes at most the tiles the first wave freed.

## The bench: `harness/melon2_bench.py`
Constants: `CONTENDER = "second_melon"`, `CHAMPION = "fert_sixteen"`, `SEEDS = tuple(range(1671, 1687))`, `CONTROL_SEED = 1671`, `CHAMPION_BAR = 0.60`, `ANCHOR_BAR = 0.90`, `MELON_DAY = 14`, `LATE_DAY = 20`, `MELON_BAR = 5`, `LONESPEAR = EXTERNAL_ANCHORS[0]`, and `MADHUR`, `REFERENCE` from `reserve_bench`.

- Control 1, identity: `off_class()` (every seam off — seventeen — + the reference's caps + the frozen `HERD_RAMP_F`, derived from `_seam_names()`) vs the reference equals the reference vs itself on seed 1671; precondition reward > 0.
- Control 2, mechanism: one game `second_melon` (seat 0) vs `fert_sixteen` on seed 1671. `reading(steps, seat)` = `{"melon_14", "melon_20", "melon_units", "strawberry_units"}` — standing melon on the day-14 and day-20 boards (`feed_bench.board_on_day` + `field_rival.standing_crops`), units sold via `fert_bench.units_sold`. Bars: contender `melon_14 >= MELON_BAR` and `> champion's`; contender `melon_units > champion's`. Both readings and `four8_bench.escapes` printed.
- Criterion: `champion_row = rival_bench.decided_row(...)`; `rival_bench.criterion(champion_row, anchor_rows, external_pairs=..., identical=champion_row["identical"])`; `void` → exit 2, else 0 / 1.
- Recorded: none.

## Alternatives rejected
- A pivot move: the day-5 pivot is measured (#288 2026-09-18).
- A wave only in strawberry-dead towns: the town inside the crop rule is the next contender.
- A larger cap for the wave: 12–15 lost twice.

## Tests (pure TDD)
Seam: `crop_for_day` answers MELON inside a window and the frozen answer outside, before the pivot, with `windows=None`, and past melon's horizon; `crop_for_plot` still caps MELON; `market_orders` buys MELON seed inside a window and STRAWBERRY seed without one; the hook returns None on the benchmark and is listed by `_seam_names()` (seventeen); a stub with the seam on survives a turn; `feed_bench.off_class` switches it off. Contender: `MELON_WINDOWS == ((12, 13),)`, the hook returns it, the class defines nothing else, caps and ramp inherited, registered. Bench: the declared constants; seed freshness (…, 960–1670); `reading` on stubbed boards/units and its early-end failure; `mechanism_failures` names the bars; `off_class()` seventeen seams off + survives a turn; pins.
