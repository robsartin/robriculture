# payday_herd — the herd waits for payday (#274)

**Issue:** #274 (declaration posted before any code). **Branch:** `274-payday-herd` from `main`.
**Decided with Rob, 2026-09-12:** the lever is the herd's pace — 8 head until day 12, then 13; hold-at-6 is arm B.

## Context
#270's VOID named the mechanism behind lean_feed's escapes (24 of 47 ladder games): on days 7–11 dawn cash is 0–30, the crew is 5–6 hands, feed cannot be topped up, and the herd bought on days 6–10 (6,400) starves. Probes on spent seeds showed a cash floor and a delayed tenth hand are byte-identical to lean_feed, while moving the 13-head step from day 8 to day 12 gave zero escapes, ten hands by day 9–10 and 2/2 wins.

## The change
`strategies/payday_herd.py`: `HERD_RAMP_P = ((0, 4), (6, 8), (12, 13))`; `PaydayHerdStrategy(LeanFeedStrategy)`, `name = "payday_herd"`, `HERD_RAMP_F = HERD_RAMP_P`. No method overridden: `field_pace.herd_target` (`max(_ramp(self.HERD_RAMP_F, day), fr.animal_target(day))`) and `pasture_count` read the attribute.

## The bench: `harness/payday_bench.py` (shape of `fed_bench`)
Constants: `CONTENDER = "payday_herd"`, `CHAMPION = "lean_feed"`, `SEEDS = tuple(range(1040, 1056))`, `CONTROL_SEED = 1040`, `CHAMPION_BAR = 0.60`, `ANCHOR_BAR = 0.90`, `CENSUS_DAYS = range(0, 17)`, `HEAD_LOST_BAR = 0`, `CREW_DAY = 10`, `CREW_BAR = 10`, `HEAD_DAY = 16`, `ARM_B = "hold6"`, `HOLD6_RAMP = ((0, 4), (6, 6), (12, 13))`.
- Reuses `fed_bench.head_by_day`, `head_lost`, `census_summary`; `feed_bench.hands_on_day`; `sheep_bench._seam_names`.
- `reading(steps, seat)` → `{"lost", "hands_10", "head_16", "heads"}`; raises if day 16 unreached. `mechanism_failures(contender, champion)` → names among `["lost", "hands_10", "head_16"]`.
- `off_class()`: every seam off, `REFERENCE` caps, and `HERD_RAMP_F` reset to `field_pace.HERD_RAMP_F` (the declaration's parenthetical; the seams being off is what makes it frozen, the reset is belt and braces).
- `arm_b_class()`: lean_feed with `HERD_RAMP_F = HOLD6_RAMP`; never registered.
- `run_census(seeds)` as `fed_bench`'s, on this bench's names. Criterion via `rival_bench.criterion`; `--recorded` = census + arm B. Exits 0/1/2.

## Tests
The ramp value and that no seam is overridden (`set(cls.__dict__) & seams == set()`); `herd_target(8) == 8`, `herd_target(12) == 13`, `pasture_count(8, 8) == min(14, 8 + LEAD_TILES)`; registered; declared constants; seed freshness (…, 1024–1039); `reading` on stubbed boards/hands; `mechanism_failures`; off-class survives a turn and has the frozen ramp; arm B's ramp and no other change.
