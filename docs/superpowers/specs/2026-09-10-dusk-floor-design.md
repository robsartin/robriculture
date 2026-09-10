# dusk_floor — herd_first with a turn-wide spend floor on land, seed and herd (#258)

**Issue:** #258 (filed from #256's VOID on Rob's instruction; declaration on the issue before any code)
**Branch:** `258-dusk-floor`

## Context

#254's `herd_first` beat `third_herder` 14/16 and lost the field because a zero reserve fires
the crew at dusk (the sim clears the hands nightly and re-hires at dawn). #256 put dawn's
wages and feed behind `capital_reserve` and VOIDed on the same crew bar: that reserve is a
floor inside the herd block only, and under `herd_first`'s order the land and seed blocks run
after the herd and spend it. The review added two corrections: the feed leg must be priced
at the market price the feed block pays (wheat starts at 25 and climbs), and only the
shortfall against the shed should be reserved.

## The change: one decision on top of `herd_first`

**The seam.** `market_orders(..., floor=None)` — a turn-wide floor that every spending block
after hires respects; `None` means 0, so the frozen benchmark keeps every decision it makes
today. With a floor `keep`:
- land buys only if `budget − cost ≥ keep`;
- seed buys `min(want, (budget − keep) // seed_cost)` (never negative);
- herd stops when `budget − cost < keep`, as well as at `cash_floor`;
- hires and the feed block are exempt — hires run at dawn before anything else, and the feed
  block is what the feed part of the floor is for.
`FieldRivalStrategy.spend_floor(self, day=None, animals=None, shed=None, prices=None)`
returns `None`; `act` passes the day, the placed head, the shed and `obs["market"]["prices"]`.
`capital_reserve` stays as it is (herd-only, frozen 1,200 on the benchmark) — the two floors
are independent, so the frozen 1,200 never leaks into land and seed.

**The contender.** `DuskFloorStrategy(HerdFirstStrategy)`, `name = "dusk_floor"`:

```
spend_floor(day, animals, shed, prices)
    = wage_bill(hire_target(day + 1)) + feed_shortfall_cost(animals, shed, prices)
feed_shortfall_cost(animals, shed, prices)
    = max(0, feed_buffer(animals) − shed.get("WHEAT", 0)) × prices.get("WHEAT", 25)
```

`wage_bill` is #256's (`strategies.dawn_reserve.wage_bill`, a pure helper: 12 for five hands,
54 for eight, 143 for ten, 376 for twelve); 25 is wheat's base price (`MARKET_PARAMS`). The
bare call answers for the opening crew, no head, an empty shed and base prices. `capital_reserve`
stays `field_pace`'s 0; the buy order stays `herd_first`'s. #256's `dawn_reserve` is not
inherited from.

## Arm B — `wage_floor`, recorded

Built in the bench, unregistered: `herd_first` with `spend_floor` = `wage_bill(hire_target(day + 1))`
alone. If B matches A, feed was not the starving line.

## The bench: `harness/floor_bench.py`

Constants: `CONTENDER = "dusk_floor"`, `CHAMPION = "third_herder"`, `BASELINE = "herd_first"`,
`SEEDS = tuple(range(944, 960))`, `CONTROL_SEED = 944`, `CHAMPION_BAR = 0.60`, `ANCHOR_BAR = 0.90`,
`ARM_B = "wage_floor"`; `HEAD_DAY`, `HEAD_BAR`, `HANDS_BAR`, `CROP_DAY`, `PLANTED_GAP_BAR`,
`crew_ok`, `mechanism_failures`, `order_reading`, `format_order_shape`, `crop_line_ok`,
`REFERENCE`, `PILKWANG`, `MADHUR` are `reserve_bench`'s / `order_bench`'s / `pace_bench`'s,
imported. Spent seeds: 100-115, 200-215, 300-331, 400-415, 500-515, 600-615, 700-703, 800-928;
929-943 declared for #256 and never played, not reused.

Order fixed: controls, criterion, arm B; a failed control exits 2 VOID and arm B is not scored.

**Controls, seed 944.**
1. **Identity.** All twelve seams off (`reserve_bench`'s eleven plus `spend_floor`) with
   dense_farm's caps is `dense_farm` to the value; precondition `base[0] > 0`. A pure positive
   control lives in the suite: on a fixed dawn state the floor leaves at least `floor` unspent
   across land, seed and herd.
2. **Mechanism, absolute, two bars.** At the close of day 8, `hands ≥ 8` **and** `head_placed ≥ 8`
   (#256's bars unchanged; #256 measured 2 and 8, #254 2 and 8, field_pace 9 and 6).
3. **Crop line, paired.** `|planted at day 12 − herd_first's on the same seed| ≤ 12` — with a
   real floor this is the binding cost (herd_first measured 48 on seeds 912 and 928).
Recorded beside them: head held, free pasture, planted and strawberry tiles at day 8, money
at day 8 and 12, payday — for the contender, herd_first and the champion.

**Criterion, seeds 944-959**, sides alternated by list position, ties are losses,
`kaggle-environments` 1.32.7, `ROBRICULTURE_STRICT=1`: ≥ 60% of 16 vs `third_herder`; ≥ 90% vs
each `DEFAULT_ANCHOR`; each `EXTERNAL_ANCHORS` member no fewer wins than the champion on the
same seeds in the same run. The madhur row is named in the verdict line beside pilkwang's.
Exit 0/1/2.

**Recorded.** Arm B vs `third_herder` on 944-959.

## Risks named in advance

The floor throttles seed: strawberry is bought from what is left above 12-376 of wages and
the feed shortfall, so the crop line may fall below herd_first's 48; the paired bar bounds
it at 12 tiles. Twelve hands cost 376 a day from day 15. The crop ceilings pinned on #252
still apply.

## Testing

Pure TDD. `tests/test_field_rival.py`: `spend_floor()` is `None` on the benchmark; `act`
passes the day, the placed head, the shed and the prices (recording subclass on a reset
observation); the positive control — a floor leaves at least the floor unspent, on the
frozen order and on herd_first's; the default (`None`) and `floor=0` emit the frozen list;
no existing assertion changes. `tests/test_dusk_floor.py`: `feed_shortfall_cost` at the shed
and price edges; the floor at named states; the bare call; registered, built on `herd_first`
with the order and every knob inherited, `capital_reserve` still 0. `tests/test_floor_bench.py`:
constants and fresh seeds; the identity stub survives a turn; arm B wages-only and
unregistered; readers, bars and verdict imported.

## Outcomes

PROMOTE → PR closes #258; designation is a separate step on Rob's say-so
(`python -m harness.promotion --succeed dusk_floor --issue 258 --pr N …`). REJECTED → record
and root cause on #258, closed `not_planned`; the PR carries the seam and the bench as a
record. VOID → the control that failed and the census, on #258.
