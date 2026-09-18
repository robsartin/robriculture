# even_split — an even herd whenever the town takes both (#310)

**Issue:** #310 (declaration posted before any code). **Branch:** `310-even-split` from `main`.
**Decided with Rob, 2026-09-18:** the single lever is the share rule — a half whenever the town drains both wool and milk — and "a half whenever any yarn store" is arm B, recorded. Judged under ADR-0007 as amended 2026-09-16 and corrected 2026-09-17.

## Context
#305's arm B, exactly this rule, went 16/16 decided against `four_at_eight` where the proportional split went 13/16; the proportional split's three losses were the three towns where a yarn store sat among two or three milk shops and its weight still tipped the herd to nine sheep. The two rules agree wherever the town takes one product or neither and wherever the proportional share is exactly a half.

## The change
`strategies/even_split.py`: `EvenSplitStrategy(TownSplitStrategy)`, `name = "even_split"`, `benchmark = False`.

```
even_share(shops)      = None if wool + milk == 0; 1.0 if milk == 0; 0.0 if wool == 0; else 0.5
                         (wool = shop_drain(shops, "WOOL"), milk = shop_drain(shops, "MILK"); town_herd.shop_drain)
sheep_share(self, shops) = even_share(shops)          # the one override; split_kind, owned, herd_preference are town_split's
```
From the frozen day-0 herd (three sheep, one cow) a half share buys cows until the herd is even and alternates from there: 6 / 6 at twelve head. Malformed input falls through as `town_split` does (ADR-0006).

## The bench: `harness/even_bench.py`
Constants: `CONTENDER = "even_split"`, `CHAMPION = "town_split"`, `SEEDS = tuple(range(1223, 1271))`, `IDENTITY_SEED = 1223`, `CHAMPION_BAR = 0.60`, `ANCHOR_BAR = 0.90`, `KIND_DAY = 12`, `HEAD_DAY = 14`, `BALANCE_BAR = 2`, `ARM_B = "half_always"`, `LONESPEAR = EXTERNAL_ANCHORS[1]`, and `PILKWANG`, `MADHUR`, `REFERENCE` re-exported from `reserve_bench`.

- Control 1, identity: `off_class()` (every seam off + the reference's caps + the frozen `HERD_RAMP_F`, derived from `_seam_names()`) vs the reference equals the reference vs itself on seed 1223; precondition reward > 0.
- Control 2, mechanism, by procedure: for each seed in `SEEDS` in order, play `even_split` (seat 0) vs `town_split`; the first game whose day-12 town is **uneven** — `town_split.sheep_share(shops)` strictly between 0 and 1 and not a half (`is_uneven_town`) — is the control game (`control_game(seeds)` → `(seed, steps)` or `None` → VOID `no_uneven_town`). `reading(steps, seat)` = `{"share_12", "even_12", "shops_12", "cows_14", "sheep_14", "balance_14", "milk", "wool"}` (town via `town_bench.town_on_day`, board via `feed_bench.board_on_day` + `farm_census.animals_placed`, revenue via `episode_analysis.decompose`; `balance_14 = |cows_14 − sheep_14|`). Bars: contender `balance_14 <= BALANCE_BAR` (`balance`); contender `balance_14 < champion's balance_14` (`balance_vs_champion`). The seed, both readings and `four8_bench.escapes` printed.
- Criterion: `champion_row = rival_bench.decided_row(CONTENDER, CHAMPION, SEEDS)`; `rival_bench.criterion(champion_row, anchor_rows, external_pairs=paired_external_rows(...), identical=champion_row["identical"])`; `void` → exit 2, else 0 / 1. The verdict line prints decided/identical and the madhur, pilkwang and lonespear pairs.
- Recorded: arm B `half_always` = `even_split` with `sheep_share` returning `half_share(shops)` — `None` when the town takes neither, `0.0` when it takes no wool, `0.5` otherwise (so a wool-only town gets an even herd, not all sheep) — vs `town_split` by `decided_row`; `--recorded`, never gated.
- Exits: 0 PROMOTE, 1 REJECTED, 2 VOID.

## Alternatives rejected
- A damped proportion (square root of the drains): a second knob with no reading behind it.
- A per-town lookup: overfits sixteen games.
- Reading the rival's herd: declared alternative for a later contender.

## Tests (pure TDD)
`even_share` at neither / wool only / milk only / both (any counts); `sheep_share` on the class; `herd_preference` walks (1 cow, 3 sheep) to 6 / 6 at a half share and to all sheep at 1.0, falls through to the inherited rule when the town is silent and on a malformed observation; the class defines no seam of its own (`herd_preference` is inherited); registered; `FOURTH_DAY == 8`. Bench: the declared constants; seed freshness (…, 960–1222); `half_share`; `is_uneven_town` (None, 0, 1, 0.5 → False; 2/3, 0.4 → True); `reading` on stubbed town/board/decompose and its early-end failures; `control_game` picks the first uneven town and returns None when none (stubbed play); `mechanism_failures` names the bars; `off_class()` every seam off + survives a turn; `arm_b_class().sheep_share` is `half_share`; `decided_row` is `rival_bench.decided_row` and `criterion` is `rival_bench.criterion`.
