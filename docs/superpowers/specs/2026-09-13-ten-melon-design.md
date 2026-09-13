# ten_melon — melon cap 10 (#279)

**Issue:** #279 (declaration posted before any code). **Branch:** `279-ten-melon` from `main`.
**Decided with Rob, 2026-09-13:** one number, melon cap 12 → 10 on `payday_herd`; cap 11 is arm B.

## Context
On days 0–5 the farm owns 11 crop tiles and two crop workers have land; the eleventh melon is the one nobody waters (36–40 units from 11 tiles). Probes vs `payday_herd` on spent seeds 1056/5001: cap 10 wins 2/2 with 45 melon sold, 29 planted at day 8 and the eleventh seed's 80 left in day 0's cash; cluster changes lose (they shrink the day-16 line); fewer early hands 1/2.

## The change — `strategies/ten_melon.py`
`CAPS_T = {"MELON": 10, "STRAWBERRY": 38, "WHEAT": 24}`; `TenMelonStrategy(PaydayHerdStrategy)`, `name = "ten_melon"`, `CAPS = CAPS_T`. No method overridden (`field_pace` sets `CAPS = CAPS_F` as a class attribute and `act` reads `self.CAPS`).

## The bench — `harness/melon_bench.py`, shape of `payday_bench`
Constants: `CONTENDER = "ten_melon"`, `CHAMPION = "payday_herd"`, `SEEDS = tuple(range(1072, 1088))`, `CONTROL_SEED = 1072`, `CHAMPION_BAR = 0.60`, `ANCHOR_BAR = 0.90`, `MELON_BAR = 44`, `PLANTED_DAY = 8`, `PLANTED_BAR = 28`, `ARM_B = "cap11"`, `CAPS_B = {"MELON": 11, "STRAWBERRY": 38, "WHEAT": 24}`.
- Reuses `fert_bench.units_sold`, `feed_bench.board_on_day`, `farm_census.planted_by_crop`, `sheep_bench._seam_names`.
- `reading(steps, seat)` → `{"melon": units, "planted_8": tiles}`; raises if day 8 unreached. `mechanism_failures(contender, champion)` → names among `["melon", "planted_8"]`: `melon < MELON_BAR or melon < champion["melon"]` → "melon"; `planted_8 < PLANTED_BAR or planted_8 < champion["planted_8"]` → "planted_8".
- `off_class()` as `payday_bench`'s (seams derived, `REFERENCE` caps, frozen ramp). `arm_b_class()` = `ten_melon` with `CAPS = CAPS_B`.
- Criterion via `rival_bench.criterion`; verdict line prints madhur, pilkwang and lonespear pairs. `--recorded` = arm B. Exits 0/1/2.

## Tests
The caps and that no seam is overridden; registered; declared constants; seed freshness (…, 1056–1071); `reading` on stubbed boards/orders; `mechanism_failures`; off-class survives a turn with 16 seams off and the reference caps; arm B's caps and no other change.
