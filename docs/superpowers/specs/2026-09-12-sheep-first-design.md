# sheep_first — six sheep, bought first (#268)

**Issue:** #268 (declaration posted before any code). **Branch:** `268-sheep-first` from `main`.
**Decided with Rob, 2026-09-12:** the single lever is the herd's composition — sheep first to six — and the inherited rival-sheep rule goes; "just drop the rule" is arm B, recorded.

## Context
#266 mined `lean_feed`'s 47 rated games: opponents with ≥ 4 sheep placed by day 8 beat it 11 of 12; against everyone else it wins 20 of 35. The winners run 8 cows + 6 sheep at day 16 to our 8 + 3 and sell 138 wool units to our 77; wool has the only double-consumption shop. `lean_feed` inherits `rival_aware`'s rule (COW once the rival has 2 sheep), which answers a sheep farm with cows. Two external anchors are the archetype: lonespear (5 sheep at day 8) and pilkwang (4), both 0/16 against us.

## The change
`strategies/sheep_first.py`: `SheepFirstStrategy(LeanFeedStrategy)`, `name = "sheep_first"`, `SHEEP_TARGET = 6`.

```
our_sheep(tiles, shed) = sheep placed on our tiles + shed.get("SHEEP", 0)   # pending counts, so the ramp's per-turn loop cannot over-order
herd_preference(obs)   = "SHEEP" if our_sheep(...) < SHEEP_TARGET else "COW"
```
`obs` is the parsed state the benchmark's `act` receives: `obs["farms"][obs["player"]]["tiles"]` and `obs["private"]["shed"]`. Malformed input degrades to `"SHEEP"` (ADR-0006), never raises. Everything else is inherited unchanged.

## The bench: `harness/sheep_bench.py`
Constants: `CONTENDER = "sheep_first"`, `CHAMPION = "lean_feed"`, `SEEDS = tuple(range(992, 1008))`, `CONTROL_SEED = 992`, `CHAMPION_BAR = 0.60`, `ANCHOR_BAR = 0.90`, `SHEEP_DAY = 8`, `SHEEP_BAR = 4`, `SHEEP_DAY_16 = 16`, `SHEEP_BAR_16 = 6`, `ARM_B = "drop_rule"`, `LONESPEAR = "lonespear_kaggriculture_v21"`, and `PILKWANG`, `MADHUR`, `REFERENCE` re-exported from `reserve_bench`.

- Control 1, identity: `off_class()` (every seam off + `dense_farm`'s caps, the `feed_bench` pattern, derived from the seam names on `FieldRivalStrategy` so a new seam cannot be missed) vs `field_rival` equals `field_rival` vs `field_rival` on seed 992; precondition reward > 0.
- Control 2, mechanism: one game `sheep_first` (seat 0) vs `lean_feed` on seed 992; `sheep_reading(steps, seat)` = `{"sheep_8", "sheep_16", "cows_16", "wool", "milk"}` (boards via `feed_bench.board_on_day` + `farm_census.animals_placed`; revenue via `episode_analysis.decompose`). Bars: contender `sheep_8 >= 4`, `sheep_16 >= 6`, `wool > lean_feed's wool` in the same game. lean_feed's reading printed beside.
- Criterion: `rival_bench.criterion` with `external_pairs=paired_external_rows(...)`, exactly as `feed_bench`. Verdict line prints the lonespear and pilkwang pairs (contender, champion) and madhur's.
- Recorded: arm B `drop_rule` = `lean_feed` with `herd_preference` returning `None` (frozen mix, no rival read) vs `lean_feed` on the same seeds; `--recorded`, never gated.
- Exits: 0 PROMOTE, 1 REJECTED, 2 VOID. A VOID run scores nothing else.

## Tests (pure TDD)
`our_sheep` counts placed sheep and shed sheep and ignores cows/weeds/locked tiles; `herd_preference` flips from SHEEP to COW at six; degrades to SHEEP on malformed obs; the declared constants; seed freshness against every spent range (…, 960–975, 976–991); `sheep_reading` on stubbed boards/decompose; `mechanism_failures` names the bars; `off_class()` switches every seam off and survives a turn; `arm_b_class()` returns None from `herd_preference`.
