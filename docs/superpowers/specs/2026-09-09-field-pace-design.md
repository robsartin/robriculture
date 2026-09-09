# field_pace — the field's schedule on third_herder, as one package (#252)

**Issue:** #252 (filed from the #198 brainstorm; declaration on the issue before any code)
**Branch:** `252-field-pace`
**Decided with Rob, 2026-09-09:** hand-build the field's schedule from a census instead of
cloning it from replays; the contender carries all eight knobs at once as one declared
package, none tuned; a shape control gates the criterion.

## Context

A census of `third_herder` vs `pilkwang_structured_economic_policy` on spent seeds 864-867
(medians) reads the field's schedule directly: 5 hands, 4 head and no cash reserve from day
0; strawberry from day 5; NE on day 6 with 8 hands; 10 hands, 37 planted and 13 head by day
8; SW on day 11; 62 planted (38 strawberry, 24 wheat) by day 12; 14 pasture tiles inside NW;
12 hands by day 15. Closing money 129K to our 46K on seed 864. #244 and #246 showed that
moving one of these knobs alone is cash-limited; the field's edge is spending every coin on
growth from day 0, on every knob together.

## The contender: `strategies/field_pace.py`

`FieldPaceStrategy(ThirdHerderStrategy)`, `name = "field_pace"`, `benchmark = False`. The
change set, every value read off the medians above and declared on #252:

| knob | frozen | `field_pace` | seam |
|---|---|---|---|
| hands | `HAND_RAMP ((0,6),(8,7),(12,9),(16,10))` | `HAND_RAMP_F = ((0,5),(6,8),(8,10),(15,12))` | new `hire_target(day)` hook; `market_orders(..., hire=None)` |
| land | `LAND_RAMP ((0,1),(12,2),(16,3))` | `LAND_RAMP_F = ((0,1),(6,2),(11,3))` | `land_target` (#246) |
| crop pivot | `PIVOT_DAY 10` | `PIVOT_F = 5` | new `pivot_day()` hook; `crop_for_day(day, season_days, pivot=PIVOT_DAY)`, `crop_for_plot(..., pivot=None)`, `market_orders(..., pivot=None)` |
| crop caps | dense_farm `{MELON 18, STRAWBERRY 22, WHEAT 8}` | `CAPS_F = {"MELON": 12, "STRAWBERRY": 38, "WHEAT": 24}` | `CAPS` (#202) |
| tiles per hand | `CLUSTER 4` | `CLUSTER_F = 6` | new `cluster_size()` hook; `crop_cluster(..., cluster=CLUSTER)` |
| herd | `FRONT_RAMP`/`ANIMAL_RAMP` | `HERD_RAMP_F = ((0,4),(6,8),(8,13))` | `herd_target` (#237) |
| pasture block | 5 NW + 7 NE | `PASTURE_BLOCK_F = tuple(_quadrant_tiles("NW")[1:15])` (14) | `layout` (#246); crop tiles by the frozen rule with the block removed |
| cash reserve | `CAPITAL_RESERVE 1200` | `RESERVE_F = 0` | new `capital_reserve()` hook; `market_orders(..., reserve=None)` |

`pasture_count` is overridden to cap at `len(self.PASTURE_BLOCK_F)` (the #246 deferred minor:
`pasture_first` caps at the frozen twelve) and to read `HERD_RAMP_F` as its floor via the
inherited `herd_target`. Inherited unchanged: the third herder from day 8, the lead of 3,
#219's cow rule, the benchmark's sell and feed rules, `_crop_slot` (slot layout from
`LIVESTOCK_WORKERS`).

**Seam shape.** Each new hook on `FieldRivalStrategy` returns `None` for the frozen rule;
each helper gains a keyword parameter defaulting to the frozen constant; `act` threads them
in one place. `field_rival`'s own decisions stay byte-identical (identity control). `MAX_HANDS`
is not enforced by `market_orders` today and stays a documentation constant; the field runs
12 hands and the sim allows it (measured).

## Arm B — `crop_pace`, recorded

Built in the bench, unregistered: `field_pace` with the herd, pasture block and
`pasture_count` returned to `third_herder`'s (`herd_target`, `layout` and `pasture_count`
delegating to `ThirdHerderStrategy`'s). The crop-and-land schedule alone.

## The bench: `harness/pace_bench.py`

Constants: `CONTENDER = "field_pace"`, `CHAMPION = "third_herder"`, `SEEDS = tuple(range(896, 912))`,
`CONTROL_SEED = 896`, `CHAMPION_BAR = 0.60`, `ANCHOR_BAR = 0.90`, `ARM_B = "crop_pace"`,
`SHAPE_DAY = 8`, `CROP_DAY = 12`, `SHAPE_BARS = {"planted": 30, "quadrants": 2, "hands": 8, "head_placed": 8}`,
`PLANTED_AT_CROP_DAY_BAR = 45`, `PAYDAY_MONEY = 5000`. Spent seeds: 100-115, 200-215,
300-331, 400-415, 500-515, 600-615, 700-703, 800-895.

Order fixed: controls, criterion, arm B; a failed control exits 2 VOID and arm B is not scored.

**Controls, seed 896.**
1. **Identity.** All ten seams off (`herd_preference`, `pasture_count`, `herd_target`,
   `livestock_workers`, `layout`, `land_target`, `hire_target`, `pivot_day`, `cluster_size`,
   `capital_reserve`) is `dense_farm` to the value; precondition `base[0] > 0`.
2. **Shape, absolute.** The contender's own census (not paired): at the close of day 8,
   `planted_tiles >= 30`, `len(quadrants) >= 2`, `hands >= 8`, `head_placed >= 8`; at the
   close of day 12, `planted_tiles >= 45`. Every one must hold. Recorded beside them, not
   gated: money at day 8 and 12, the first day money reaches 5,000 (the melon payday; the
   field's is day 10), strawberry tiles at day 8, and the champion's same readings from the
   same game for contrast.

**Criterion, seeds 896-911**, sides alternated by list position, ties are losses,
`kaggle-environments` 1.32.7, `ROBRICULTURE_STRICT=1`: ≥ 60% of 16 vs `third_herder`; ≥ 90% vs
each `DEFAULT_ANCHOR`; each `EXTERNAL_ANCHORS` member no fewer wins than the champion on the
same seeds in the same run. `rival_bench.criterion(..., external_pairs=pairs)` decides; exit
0/1/2. The pilkwang paired row is printed and named in the verdict line as the hypothesis's
own reading.

**Recorded.** Arm B vs `third_herder` on 896-911.

## Risks named in advance

Cash (seed for 38 strawberry is 3,800; NE is 1,000 on day 6 against ~600 in hand): the package
buys in the benchmark's order — sells, hires, land, seed, herd — so one line may starve the
other; the day-8 shape control names which. Labour at 6 tiles per hand: the day-12 planted
bar catches a crew that cannot keep them watered. The melon race is not addressed (the sell
rule is unchanged); the payday reading records it.

## Testing

Pure TDD. `tests/test_field_rival.py`: each new hook returns `None` on the benchmark; each
helper's new parameter defaults to the frozen constant and honours a passed value; no existing
assertion changes. `tests/test_field_pace.py`: the declared constants; the block is fourteen
NW tiles keeping the frozen first five; crop tiles disjoint and complete; `pasture_count`
caps at 14 and floors at the herd ramp; every hook answers; registered, built on
`third_herder`. `tests/test_pace_bench.py`: constants and fresh seeds; the shape reading and
its bars on hand-built censuses (each bar can fail alone); the payday reading; arm B is
unregistered and delegates the herd hooks to `third_herder`; formatting. Full gate and
preflight before push.

## Outcomes

PROMOTE → PR closes #252; designation is a separate step on Rob's say-so. REJECTED → record
and root cause on #252, closed `not_planned`; the PR carries the seams and the bench as a
record (#245's precedent). VOID → the control that failed and the census, on #252.

## Note, 2026-09-09 (Task 3 review, before the bench ran)

The slot layout is derived from the frozen herder pair (`_crop_slot`, kept as #239 decided),
so worker 6 keeps its slot when it herds from day 8 and its six tiles idle, and the twelfth
hand (hired day 15) lands on slot 10, whose slice runs past the end of the 61-tile
`CROP_TILES_F`: it works one tile. In effect the package works about 55 crop tiles from day
15, not 60. Not changed here — a re-map is the second, unmeasured change #239 declined — and
not reached by the shape controls (day 8 and 12). Recorded so a REJECTED result is not
root-caused against "tiles per hand" without this in view.
