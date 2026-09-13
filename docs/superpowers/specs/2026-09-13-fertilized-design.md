# fertilized — apply the fertilizer we collect (#277)

**Issue:** #277 (declaration posted before any code). **Branch:** `277-fertilized` from `main`.
**Decided with Rob, 2026-09-13:** the lever is fertilizer on the crop line, through two new seams on the frozen benchmark; melon-only is arm B.

## Context
pilkwang (0/16 against every contender of this line) opens like us and wins the payday: 72 melon from 12 tiles and 269 strawberry from 38 to our 45 and 150. The sim doubles a watered day's yield growth and each strawberry production while a tile is fertilized (`FERTILIZE` takes one unit from the worker's inventory, lasts three days). Our line collects fertilizer from the pastures and sells every unit; the benchmark never emits `FERTILIZE`.

## The seams (Task 1) — `strategies/field_rival.py`, byte-identical when off
- `FERT_CARRY = 3` (module constant): fertilizer a crop worker picks up per shed visit.
- `crop_worker_action(cluster, tiles, pos, inv, crop, day, hour, shed=None, fertilize=None, fert_carry=FERT_CARRY)`:
  - `carrying` excludes FERTILIZER when `fertilize` is set (fertilizer in hand is a tool, not a load);
  - when `fertilize` is set, the worker is at the shed, has no fertilizer in hand and the shed has some: `["PICKUP", "FERTILIZER", min(shed, fert_carry)]` — pickups happen only on a shed visit the worker was making anyway (after a DROP), never a dedicated trip;
  - in the tile loop, a tile whose `plot_action` is WATER, whose crop is in `fertilize`, whose `fertilized_until_day < day`, while the worker has fertilizer in hand → `["FERTILIZE"]` (on site) or the walk toward it; the next turn's WATER then earns the bonus. HARVEST, DIG and PLANT are never displaced.
- `market_orders(..., fert=None)`: the sell sweep keeps `fert` units of FERTILIZER (`keep`), as it keeps the feed wheat.
- Seams on `FieldRivalStrategy`, both returning `None`: `fertilizer_stock(self)` and `fertilize_crops(self)`; docstrings say "seam" so `sheep_bench._seam_names()` picks them up. `act` threads `shed=shed, fertilize=self.fertilize_crops()` into `crop_worker_action` and `fert=self.fertilizer_stock()` into `market_orders`.

## The contender (Task 2) — `strategies/fertilized.py`
`FERT_CROPS = ("STRAWBERRY", "MELON")`, `FERT_STOCK = 24`; `FertilizedStrategy(PaydayHerdStrategy)`, `name = "fertilized"`, `fertilizer_stock() -> FERT_STOCK`, `fertilize_crops() -> FERT_CROPS`. Nothing else.

## The bench (Task 2) — `harness/fert_bench.py`, shape of `payday_bench`
Constants: `CONTENDER = "fertilized"`, `CHAMPION = "payday_herd"`, `SEEDS = tuple(range(1056, 1072))`, `CONTROL_SEED = 1056`, `CHAMPION_BAR = 0.60`, `ANCHOR_BAR = 0.90`, `FERTILIZE_BAR = 30`, `STRAWBERRY_FACTOR = 1.5`, `ARM_B = "melon_only"`, `LONESPEAR` from the pool.
- `action_counts(steps, seat)` → `{op: n}` over farmer + hands for the game; `units_sold(steps, seat)` → `{item: units}` from SELL orders; `reading(steps, seat)` → `{"fertilize", "water", "strawberry", "melon", "fertilizer_sold"}`.
- `mechanism_failures(contender, champion)` → names among `["fertilize", "strawberry", "melon"]`.
- Identity control as `payday_bench.off_class()` (seams derived, caps, frozen ramp); mechanism on `play(CONTENDER, CHAMPION, CONTROL_SEED)`, both seats read.
- Criterion via `rival_bench.criterion`; verdict line prints lonespear, pilkwang and madhur pairs. `--recorded`: arm B `melon_only` (`fertilize_crops` → `("MELON",)`) vs the champion.
- Exits 0/1/2.

## Tests
Task 1: the frozen path never picks up or fertilizes and sells all fertilizer (`shed` and `fert` absent); pickup at the shed only when active, empty-handed and stocked, capped by `fert_carry`; the WATER→FERTILIZE intercept and each condition that blocks it (crop not in set, still fertilized, no fertilizer in hand); HARVEST never displaced; carry limit excludes fertilizer only when active; the sweep's `fert` keep; both seams on the class return `None` and `_seam_names()` counts 16; the existing `tests/test_field_rival.py` untouched and green.
Task 2: the contender's two seams and nothing else overridden; registered; declared constants; seed freshness (…, 1040–1055); `action_counts`/`units_sold`/`reading` on synthetic steps; `mechanism_failures`; off-class survives a turn with 16 seams off; arm B's set.
