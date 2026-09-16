# town_herd — the animal kind from the town's shops (#302)

**Issue:** #302 (declaration posted before any code). **Branch:** `302-town-herd` from `main`.
**Decided with Rob, 2026-09-16:** the single lever is the kind of the next animal, read from the town's unlocked shops; the headroom subtraction is the design, and "shop capacity alone" is arm B, recorded.

## Context
#288 decomposed `four_at_eight`'s 30 rated ladder games. The losses are not escapes (0–1 head lost) and the herd ramp is identical in every game; revenue from the same board runs 24K–110K because the market price is set by inventory against the 10,000 anchor (`kaggisim/economy.py: MARKET_PARAMS`, T ≈ 122 units for MILK, 105 for WOOL) and only the town's shops drain it. Shops unlock every 3 days, eight instances, drawn with replacement by the episode RNG; each instance takes one unit of every product it lists every `townShopSellInterval` (4) turns, two for a single-product shop. MILK is drained by PIZZA_SHOP, ICE_CREAM_SHOP, SMOOTHIE_SHOP; WOOL by YARN_STORE alone. Over the 30 games the milk-shop count predicts our MILK revenue at r = 0.78 and the yarn-store count our WOOL revenue at r = 0.77. The herd is bought blind: the frozen rule buys COW unless the budget covers three sheep; `rival_aware` switches to COW when the rival has two sheep.

## The change
`strategies/town_herd.py`: `TownHerdStrategy(FourAtEightStrategy)`, `name = "town_herd"`, `benchmark = False`.

```
SHOP_TICKS_PER_DAY       = CONFIG_DEFAULTS["turnsPerDay"] // CONFIG_DEFAULTS["townShopSellInterval"]   # 6, from the sim's tables
shop_drain(shops, p)     = Σ over unlocked instances listing p of SHOP_TICKS_PER_DAY × (2 if the shop lists one product else 1)
head_supported(shops, k) = shop_drain(shops, ANIMALS[k]["product"]) × ANIMALS[k]["interval"]        # a pizza shop: 12 cows; a yarn store: 36 sheep
our_head(tiles, shed, k) = placed head of k + shed.get(k, 0)                                          # pending counts (the sheep_first lesson)
town_kind(shops, c, s)   = None if the town supports neither kind
                           else "SHEEP" if (supported SHEEP − s) > (supported COW − c) else "COW"     # COW on a tie: cheaper
owned(obs)               = (our cows, our sheep)                                                      # a method, so arm B can override it
herd_preference(obs)     = town_kind(obs["town"]["unlocked_shops"], *owned(obs)); when None, super().herd_preference(obs)
```
`obs` is the parsed state the benchmark's `act` receives (`kaggisim/state.py`): `obs["town"]["unlocked_shops"]`, `obs["farms"][obs["player"]]["tiles"]`, `obs["private"]["shed"]`. A malformed observation falls through to the inherited rule (`rival_aware`'s), never raises (ADR-0006). Tables come from `kaggisim.economy` and are never restated. Nothing else changes: `FOURTH_DAY = 8`, the ramp, caps and crop line are four_at_eight's.

## The bench: `harness/town_bench.py`
Constants: `CONTENDER = "town_herd"`, `CHAMPION = "four_at_eight"`, `SEEDS = tuple(range(1171, 1187))`, `CONTROL_SEED = 1174`, `CHAMPION_BAR = 0.60`, `ANCHOR_BAR = 0.90`, `KIND_DAY = 12`, `HEAD_DAY = 14`, `ARM_B = "shop_count"`, `LONESPEAR = EXTERNAL_ANCHORS[1]`, and `PILKWANG`, `MADHUR`, `REFERENCE` re-exported from `reserve_bench`.

- Control 1, identity: `off_class()` (every seam off + the reference's caps + the frozen `HERD_RAMP_F`, the `four8_bench` pattern, derived from `_seam_names()`) vs `field_rival` equals `field_rival` vs `field_rival` on seed 1174; precondition reward > 0.
- Control 2, mechanism: one game `town_herd` (seat 0) vs `four_at_eight` on seed 1174. `reading(steps, seat)` = `{"favoured", "shops_12", "cows_14", "sheep_14", "milk", "wool"}` — `favoured = town_kind(shops on day 12, 0, 0)` (the kind the town favours, ownership aside), head on the day-14 board via `feed_bench.board_on_day` + `farm_census.animals_placed`, revenue via `episode_analysis.decompose`. Bars: `favoured` is not `None` (else the control fails as `favoured`); contender's head of the favoured kind at day 14 > champion's; contender's revenue in that kind's product > champion's in the same game. Both readings and `four8_bench.escapes` printed.
- Precondition established before the declaration (not the experiment): the draw is keyed off the seed and the day; seeds 1171–1190 were read by playing `four_at_eight` against itself once each, no contender played. Seed 1174 draws PET_CAFE, YARN_STORE by day 6, a second YARN_STORE by day 9.
- Criterion: `rival_bench.criterion` with `external_pairs=paired_external_rows(...)` under the 2026-09-15 amended limb. Verdict line prints the madhur, pilkwang and lonespear pairs.
- Recorded: arm B `shop_count` = `town_herd` with `owned` returning `(0, 0)` (the kind with the larger shop capacity, COW on a tie) vs `four_at_eight` on the same seeds; `--recorded`, never gated.
- Exits: 0 PROMOTE, 1 REJECTED, 2 VOID. A VOID run scores nothing else.

## Alternatives rejected
- Reading the rival's placed head as supply: the opponent also adapts; one more moving part before the first reading.
- Reading market inventory instead of the shops: inventory has not moved by the day-6 buys; the shops are the leading signal.
- A fixed sheep target (`sheep_first`, #268, rejected): sheep without demand.

## Tests (pure TDD)
`SHOP_TICKS_PER_DAY` is derived from the sim's tables (6); `shop_drain` counts instances, doubles single-product shops, ignores unknown names; `head_supported` gives 12 cows per pizza shop and 36 sheep per yarn store; `our_head` counts placed and pending of one kind only; `town_kind` is None for a bakery-only town, SHEEP for a yarn store alone, COW for a pizza shop alone, subtracts owned head and ties to COW; `herd_preference` reads the town and our farm, falls through to `rival_aware`'s rule when the town is silent (rival sheep → COW, none → None) and on a malformed observation; exactly one seam defined; registered; `FOURTH_DAY == 8` inherited. Bench: the declared constants; seed freshness (…, 960–1170); `town_on_day` reads the last observation of the day; `reading` on stubbed board/town/decompose and its early-end failure; `mechanism_failures` names the bars and fails `favoured` on None; `off_class()` switches every seam off and survives a turn; `arm_b_class().owned(obs) == (0, 0)`; the verdict is `rival_bench.criterion`.
