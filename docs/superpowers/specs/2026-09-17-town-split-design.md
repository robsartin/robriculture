# town_split — the herd in proportion to the town's drain (#305)

**Issue:** #305 (declaration posted before any code). **Branch:** `305-town-split` from `main`.
**Decided with Rob, 2026-09-16:** the single lever is the sheep share of the herd, set from the town's wool drain against its milk drain; the proportion is the design and "even split whenever both" is arm B, recorded. Judged under ADR-0007 as amended 2026-09-16 (PR #304).

## Context
#302's switch (`town_herd`) fired on 4 of 16 seeds and went to 11 sheep / 1 cow in every yarn-store town: won by 26–33K where no milk shop competed, lost by 7–11K where one did (the milk line abandoned; eleven sheep halved their own price per head). The other 12 seeds were the champion's own action stream, which the amendment now leaves out of the denominator. The frozen rule buys 3 sheep and 1 cow on day 0, before the first shop; the town can shape only the head bought from day 6.

## The change
`strategies/town_split.py`: `TownSplitStrategy(FourAtEightStrategy)`, `name = "town_split"`, `benchmark = False`.

```
sheep_share(shops)            = wool / (wool + milk) with wool = shop_drain(shops, "WOOL"), milk = shop_drain(shops, "MILK")
                                (town_herd.shop_drain; None when wool + milk == 0)
split_kind(share, cows, sheep) = "SHEEP" if sheep < share * (cows + sheep + 1) else "COW"
owned(obs)                     = (our_head(tiles, shed, "COW"), our_head(tiles, shed, "SHEEP"))   # town_herd.our_head: placed + pending
herd_preference(obs)           = split_kind(sheep_share(shops), *owned(obs)); super().herd_preference(obs) when the share is None
```
Share 1 → every head a sheep; share 0 → every head a cow; 2/3 → 8 sheep / 4 cows at twelve head; 0.4 → 5 / 7. Malformed input falls through to the inherited rule (ADR-0006), never raises. Everything else is four_at_eight's.

## The bench: `harness/split_bench.py`
Constants: `CONTENDER = "town_split"`, `CHAMPION = "four_at_eight"`, `SEEDS = tuple(range(1191, 1223))`, `IDENTITY_SEED = 1191`, `CHAMPION_BAR = 0.60`, `ANCHOR_BAR = 0.90`, `KIND_DAY = 12`, `HEAD_DAY = 14`, `COWS_BAR = 3`, `ARM_B = "even_split"`, `LONESPEAR = EXTERNAL_ANCHORS[1]`, and `PILKWANG`, `MADHUR`, `REFERENCE` re-exported from `reserve_bench`.

- Control 1, identity: `off_class()` (every seam off + the reference's caps + the frozen `HERD_RAMP_F`, derived from `_seam_names()`) vs the reference equals the reference vs itself on seed 1191; precondition reward > 0.
- Control 2, mechanism, by procedure: for each seed in `SEEDS` in order, play `town_split` (seat 0) vs `four_at_eight`; the first game whose day-12 town has `sheep_share` strictly between 0 and 1 is the control game (`control_game(seeds)` → `(seed, steps)` or `None` → VOID as `no_split_town`). `reading(steps, seat)` = `{"share_12", "shops_12", "cows_14", "sheep_14", "milk", "wool"}` (town via `town_bench.town_on_day`, board via `feed_bench.board_on_day` + `farm_census.animals_placed`, revenue via `episode_analysis.decompose`). Bars: contender `sheep_14 > champion's`, `cows_14 >= COWS_BAR`, `wool > champion's`. The seed, both readings and `four8_bench.escapes` printed.
- Criterion: `identical = rival_bench.identical_games(CONTENDER, CHAMPION, SEEDS)`; `rival_bench.criterion(champion_row, anchor_rows, external_pairs=paired_external_rows(...), identical=identical)`; `void` → exit 2 (under-powered), else 0 / 1. The verdict line prints decided/identical and the madhur, pilkwang and lonespear pairs.
- Recorded: arm B `even_split` = `town_split` with `sheep_share` returning 0.5 when both drains are positive (else 1 / 0 / None) vs `four_at_eight` on the same seeds, with its own identical count; `--recorded`, never gated.
- Exits: 0 PROMOTE, 1 REJECTED, 2 VOID.

## Alternatives rejected
- Per-head capacity as the weight (36 sheep per yarn store vs 12 cows per milk shop): #302's switch; over-commits to sheep.
- A sheep cap: a fixed dose; the two big wins came at 11 sheep.
- Reading the rival's herd as supply: one more moving part before the first reading.

## Tests (pure TDD)
`sheep_share` (None for a bakery town; 1 for a yarn store alone; 0 for a pizza shop alone; 2/3 for yarn + pizza; 0.4 for yarn + three milk shops); `split_kind` at shares 0, 1, 2/3 and 0.4 from the day-0 herd (3 sheep, 1 cow) through twelve head; `herd_preference` reads the town and our farm, falls through to `rival_aware`'s rule when the share is None and on a malformed observation; exactly one seam defined; registered; `FOURTH_DAY == 8`. Bench: the declared constants; seed freshness (…, 960–1190); `reading` on stubbed town/board/decompose; `mechanism_failures` names the bars; `control_game` picks the first split town and returns None when none (stubbed play); `off_class()` every seam off + survives a turn; `arm_b_class().sheep_share(...)` is 0.5 / 1 / 0 / None; the verdict is `rival_bench.criterion` and `identical_games` is `rival_bench.identical_games`.
