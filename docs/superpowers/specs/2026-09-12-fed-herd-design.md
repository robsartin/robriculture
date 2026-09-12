# fed_herd — two feedings in the shed (#270)

**Issue:** #270 (declaration posted before any code). **Branch:** `270-fed-herd` from `main`.
**Decided with Rob, 2026-09-12:** the lever is the shed's feed stock (two feedings, lean carry kept); the feed-only floor is arm B, recorded.

## Context
Re-reading #266's 47 ladder replays for head placed by day: lean_feed's animals escape in 24 of 47 games (first escape day 9 in 15), and we are 0/11 when three or more head go. Locally on seeds 992/993 `third_herder` loses 0/0 head, `herd_first` 1/0, `lean_feed` 3/7. #262 cut the shed's stock to one feeding; on days 7–11 dawn cash is ~30, so one failed top-up starves the herd and the sim's `consecutive_unfed >= 2` rule takes it.

## The change
`strategies/fed_herd.py`: `FEEDINGS = 2`; `stock_for_fed(animals) = max(1, FEEDINGS * animals)`; `FedHerdStrategy(LeanFeedStrategy)`, `name = "fed_herd"`, overriding only `feed_stock(animals=None) -> stock_for_fed(animals or 0)`. Carry and every other seam are lean_feed's.

## The bench: `harness/fed_bench.py` (shape of `sheep_bench`)
Constants: `CONTENDER = "fed_herd"`, `CHAMPION = "lean_feed"`, `SEEDS = tuple(range(1008, 1024))`, `CONTROL_SEED = 1008`, `CHAMPION_BAR = 0.60`, `ANCHOR_BAR = 0.90`, `CENSUS_DAYS = range(0, 17)`, `HEAD_LOST_BAR = 0`, `HEAD_DAY = 12`, `ARM_B = "feed_floor"`; `PILKWANG`, `MADHUR`, `REFERENCE` re-exported from `reserve_bench`.

- `head_by_day(steps, seat, days)` → list of placed head (`farm_census.animals_placed` on `feed_bench.board_on_day`; `None` for a day never reached). `head_lost(heads)` → the sum of day-over-day decreases, skipping `None`. `head_reading(steps, seat)` → `{"lost": head_lost over CENSUS_DAYS, "head_12": head at HEAD_DAY, "heads": the list}`; raises `ValueError` if day 12 was never reached.
- `mechanism_failures(contender, champion)` → names among `["lost", "head_12"]`: `lost > HEAD_LOST_BAR`, `head_12 < champion["head_12"]`.
- Control 1 identity as `sheep_bench.off_class()` (seams derived from the benchmark's docstrings + `REFERENCE` caps); control 2 mechanism on `play(CONTENDER, CHAMPION, CONTROL_SEED)`, seats 0/1.
- Criterion via `rival_bench.criterion` with `paired_external_rows`; verdict line prints madhur and pilkwang pairs.
- `--recorded`: (a) `run_census(seeds)`: contender vs champion, sides alternated by list position (contender seat 0 on even positions), each game's `head_lost` per side; printed per game and as medians; (b) arm B `feed_floor` vs champion via `head_to_head_rate(..., agents=)`. `arm_b_class()` = `lean_feed` with `spend_floor(day, animals, shed, prices)` = `max(0, 2*animals - shed.get("WHEAT", 0)) * int(prices.get("WHEAT", 25))`, with `feed_stock` left at lean_feed's; bare call → 0.
- Exits 0 PROMOTE / 1 REJECTED / 2 VOID.

## Tests
`stock_for_fed`; the one overridden seam (`set(FedHerdStrategy.__dict__) & seams == {"feed_stock"}`); registered; declared constants; seed freshness (…, 976–991, 992–1007); `head_by_day`/`head_lost`/`head_reading` on stubbed boards; `mechanism_failures`; `off_class` survives a turn; `arm_b_class` floor arithmetic and its `feed_stock` unchanged; `census_summary` medians.
