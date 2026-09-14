# fert_six — fertilize from day 6 with a stock of 8 (#282)

**Issue:** #282 (declaration posted before any code). **Branch:** `282-fert-six` from `main`.
**Decided with Rob, 2026-09-14:** the lever is the fertilizer seams of #277, timed to day 6 with a small stock; from day 8 is arm B.

## Context
#277 showed a fertilizer hold-back from day 0 kills the farm and a day-10 start is a wash. The probe (seeds 1088/5001 vs ten_melon): from day 6 with stock 8, +13K and +7K, strawberry 149 → 260, the early economy's dawn cash unchanged.

## Task 1 — the seams take the day (`strategies/field_rival.py`, byte-identical when off)
`fertilizer_stock(self, day=None)` and `fertilize_crops(self, day=None)` gain a `day` argument; both still return `None` on the benchmark; `act` calls `self.fertilize_crops(day)` and `self.fertilizer_stock(day)`. `strategies/fertilized.py`'s two overrides and `harness/feed_bench.py`'s identity stub gain `day=None` (feed_bench's test checks the stub at the seam's arity). `tests/test_field_rival.py` untouched and green.

## Task 2 — the contender and the bench
`strategies/fert_six.py`: `FERT_FROM = 6`, `FERT_STOCK = 8`, `FERT_CROPS = ("MELON", "STRAWBERRY")`; `FertSixStrategy(TenMelonStrategy)`, `name = "fert_six"`; `fertilizer_stock(day=None)` → `FERT_STOCK` if `(day or 0) >= FERT_FROM` else `None`; `fertilize_crops(day=None)` → `FERT_CROPS` on the same condition else `None`.

`harness/six_bench.py` (shape of `melon_bench`): `CONTENDER = "fert_six"`, `CHAMPION = "ten_melon"`, `SEEDS = tuple(range(1088, 1104))`, `CONTROL_SEED = 1088`, `CHAMPION_BAR = 0.60`, `ANCHOR_BAR = 0.90`, `FERTILIZE_BAR = 100`, `STRAWBERRY_FACTOR = 1.5`, `EARLY_DAYS = range(1, 6)`, `ARM_B = "from_eight"`, `ARM_B_FROM = 8`.
- `dawn_cash(steps, seat, days)` → list of money at hour 0 of each day (None if unreached); `reading(steps, seat)` → `{"fertilize", "strawberry", "melon", "planted_8", "dawn_1_5"}` using `fert_bench.action_counts`/`units_sold`, `feed_bench.board_on_day`, `farm_census.planted_by_crop`.
- `mechanism_failures(contender, champion)` → names among `["fertilize", "strawberry", "dawn_1_5"]`: `fertilize < FERTILIZE_BAR`; `strawberry < STRAWBERRY_FACTOR * champion["strawberry"]`; `dawn_1_5 != champion["dawn_1_5"]`.
- `off_class()` as `melon_bench`'s; `arm_b_class()` = `fert_six` with `FERT_FROM = ARM_B_FROM` (a class attribute the two overrides read via `self.FERT_FROM`).
- Criterion via `rival_bench.criterion`; verdict line prints madhur, pilkwang, lonespear. `--recorded` = arm B. Exits 0/1/2.

## Tests
Task 1: the seams accept and ignore `day` on the benchmark; `act` passes the day (a subclass recording the `day` it receives sees the observation's day); `fertilized` still answers with `day` given; feed_bench's stub test green. Task 2: the contender's two seams switch on at day 6 and not before, nothing else overridden; registered; declared constants; seed freshness (…, 1072–1087); `dawn_cash`/`reading` on synthetic steps; `mechanism_failures`; off-class with 16 seams; arm B's `FERT_FROM`.
