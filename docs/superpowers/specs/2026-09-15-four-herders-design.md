# four_herders — a fourth herder from day 12 (#289)

**Issue:** #289 (declaration posted before any code). **Branch:** `289-four-herders` from `main`.
**Decided with Rob, 2026-09-15:** the fourth herder alone; the herder scan order is a later lever.

## Context
#288: our herd ends every game at 11 placed with four animals in the shed from day 12; three herders are saturated at eleven head. Probe vs ten_melon: a fourth herder from day 12 wins 8/8, places a twelfth head by day 14, milk 171–177 → 204–210.

## The change — `strategies/four_herders.py`
`FOURTH_HERDER = 7`, `FOURTH_DAY = 12`; `FourHerdersStrategy(TenMelonStrategy)`, `name = "four_herders"`, class attributes `FOURTH_HERDER`, `FOURTH_DAY`; `livestock_workers(day)`: `base = super().livestock_workers(day)`; if `day < self.FOURTH_DAY` return `base` unchanged (`None` before day 8, the trio from 8); else `tuple(base or fr.LIVESTOCK_WORKERS) + (self.FOURTH_HERDER,)`.

## The bench — `harness/fourth_bench.py`, shape of `melon_bench`
Constants: `CONTENDER = "four_herders"`, `CHAMPION = "ten_melon"`, `SEEDS = tuple(range(1122, 1138))`, `CONTROL_SEED = 1122`, `CHAMPION_BAR = 0.60`, `ANCHOR_BAR = 0.90`, `PLACED_DAY = 14`, `PLACED_BAR = 12`, `PENDING_DAYS = (14, 20)`, `PLANTED_DAY = 16`, `ARM_B = "from_eight"`, `ARM_B_FROM = 8`.
- `pending_at(steps, seat, day)` → COW + SHEEP in the shed on the last observation of `day` (None if unreached).
- `reading(steps, seat)` → `{"placed_14", "milk", "pending": {14: n, 20: n}, "planted_16"}` via `feed_bench.board_on_day`, `farm_census.animals_placed`/`planted_by_crop`, `fert_bench.units_sold`; raises if day 14 unreached.
- `mechanism_failures(contender, champion)` → names among `["placed_14", "milk"]`: `placed_14 < PLACED_BAR or placed_14 < champion["placed_14"]`; `milk <= champion["milk"]`.
- `off_class()` as `melon_bench`'s; `arm_b_class()` = `four_herders` with `FOURTH_DAY = ARM_B_FROM`.
- Criterion via `rival_bench.criterion`; verdict prints madhur, pilkwang, lonespear. `--recorded` = arm B. Exits 0/1/2.

## Tests
Seam values by day (None before 8, trio 8–11, quartet from 12), nothing else overridden; registered; declared constants; seed freshness (…, 1105–1121); `pending_at`/`reading` on synthetic steps and stubs; `mechanism_failures`; off-class with 16 seams; arm B from day 8.
