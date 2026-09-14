# fert_eight — fertilize from day 8 (#284)

**Issue:** #284 (declaration posted before any code). **Branch:** `284-fert-eight` from `main`.
**Decided with Rob, 2026-09-14:** #282's arm B declared as the contender; from day 10 is arm B.

## The change — `strategies/fert_eight.py`
`FERT_FROM_EIGHT = 8`; `FertEightStrategy(FertSixStrategy)`, `name = "fert_eight"`, `FERT_FROM = FERT_FROM_EIGHT`. Nothing else overridden (`fert_six`'s two seam overrides read `self.FERT_FROM`).

## The bench — `harness/eight_bench.py`, shape of `six_bench`, reusing its helpers
Constants: `CONTENDER = "fert_eight"`, `CHAMPION = "ten_melon"`, `SEEDS = tuple(range(1104, 1120))`, `CONTROL_SEED = 1104`, `CHAMPION_BAR = 0.60`, `ANCHOR_BAR = 0.90`, `FERTILIZE_BAR = 100`, `STRAWBERRY_FACTOR = 1.5`, `EARLY_DAYS = range(1, 8)`, `PLANTED_DAY = 8`, `ARM_B = "from_ten"`, `ARM_B_FROM = 10`.
- `reading(steps, seat)` → `{"fertilize", "strawberry", "melon", "planted_8", "dawn_1_7"}` via `six_bench.dawn_cash`, `fert_bench.action_counts`/`units_sold`, `feed_bench.board_on_day`, `farm_census.planted_by_crop`; raises if day 8 unreached.
- `mechanism_failures(contender, champion)` → names among `["fertilize", "strawberry", "dawn_1_7", "planted_8"]`: `fertilize < FERTILIZE_BAR`; `strawberry < STRAWBERRY_FACTOR * champion["strawberry"]`; `dawn_1_7 != champion["dawn_1_7"]`; `planted_8 < champion["planted_8"]`.
- `off_class()` and `arm_b_class()` as `six_bench`'s on this bench's names (`arm_b_class` sets `FERT_FROM = ARM_B_FROM`).
- Criterion via `rival_bench.criterion`; verdict line prints madhur, pilkwang, lonespear. `--recorded` = arm B. Exits 0/1/2.

## Tests
The contender's `FERT_FROM` and that nothing beyond `name`/`benchmark`/`FERT_FROM` is in its `__dict__`; seams off on day 7, on from day 8; registered; declared constants; seed freshness (…, 1088–1103); `reading` on stubbed helpers incl. the day-8 failure; `mechanism_failures` for all four bars; off-class with 16 seams; arm B from day 10.
