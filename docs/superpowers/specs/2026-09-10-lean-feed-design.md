# lean_feed — herd_first with feed sized to the herd (#262)

**Issue:** #262 (filed from #260's cash-flow tables; declaration on the issue before any code)
**Branch:** `262-lean-feed`, stacked on `260-cashflow` (PR #261) because the bench reads the
contender's own game through `harness/cashflow.py`.
**Decided with Rob, 2026-09-10:** the feed economy is the lever; the contender sits on
`herd_first`; the crew is recorded, not gated.

## Context

#260 measured the cash flow of the three schedule contenders on seed 944. Every one ends day
0 at 15 after 1,900 on animals and 395-664 on feed — the herders filling their pockets
(`FEED_CARRY` 8 each, three herders) plus the shed buffer (`feed_buffer` = max(8, 2 × head)).
Days 1-5 the herd's fertilizer and wheat sales roughly cover its own feed churn — wheat bought
at 30-33 to refill pockets and buffer, harvested wheat sold at 25-30 the same day; herd_first
spent 1,004 / 439 / 508 / 516 gross on days 2-5 for four head that eat four a day. The
champion banks 9,808 of melon on day 10 from eighteen tiles; the contenders 2,505-4,589 from
twelve. The pre-payday economy is break-even and the feed churn is the largest controllable
outflow in it.

## The change: one decision on top of `herd_first` — feed sized to the herd

**Two seams on the frozen benchmark**, both defaulting to the frozen numbers:
- `feed_carry(self, animals=None, herders=None)` on the class, `None` on the benchmark →
  `act` passes `carry` to `herd_worker_action(..., carry=FEED_CARRY)` → `_pasture_chore(...,
  carry=FEED_CARRY)`, whose shed pickup becomes `min(shed["WHEAT"], carry)`.
- `feed_stock(self, animals=None)` on the class, `None` on the benchmark → `market_orders(...,
  feed=None)`: `buffer = feed_buffer(animals) if feed is None else feed`, used by both the sell
  sweep's hold-back (`reserved`) and the feed block's top-up (`want_feed`).

**The contender.** `LeanFeedStrategy(HerdFirstStrategy)`, `name = "lean_feed"`:

```
carry_for(animals, herders) = max(1, ceil(animals / herders))    # one day's feed for the herder's own tiles
stock_for(animals)          = max(1, animals)                    # one feeding in the shed
feed_carry(animals, herders) = carry_for(animals or 0, herders or len(LIVESTOCK_WORKERS))
feed_stock(animals)          = stock_for(animals or 0)
```

Everything else inherited: the buy order, `field_pace`'s eight knobs, `third_herder`'s rules,
`capital_reserve` 0, no spend floor.

## Arm B — `lean_buffer`, recorded

Built in the bench, unregistered: `herd_first` with `feed_stock` = `stock_for(animals)` and the
carry left at 8. If B matches A, the pockets were not the leak.

## The bench: `harness/feed_bench.py`

Constants: `CONTENDER = "lean_feed"`, `CHAMPION = "third_herder"`, `BASELINE = "herd_first"`,
`SEEDS = tuple(range(960, 976))`, `CONTROL_SEED = 960`, `CHAMPION_BAR = 0.60`, `ANCHOR_BAR = 0.90`,
`ARM_B = "lean_buffer"`, `FEED_DAY0_BAR = 250`, `FEED_DAYS = range(1, 6)`, `FEED_DAYS_BAR = 1200`,
`HEAD_DAY = 8`, `HEAD_BAR = 8`, `CROP_DAY = 12`, `PLANTED_GAP_BAR = 12`. `REFERENCE`, `PILKWANG`,
`MADHUR` from `reserve_bench`; `daily_cashflow`, `format_cashflow`, `play` from `cashflow`.
Spent seeds: 100-115, 200-215, 300-331, 400-415, 500-515, 600-615, 700-703, 800-928, 944;
929-943 and 945-959 declared and never played, not reused.

**Readers, pure.** `board_on_day(steps, player, day)` — the observation produced by the day's
last turn (the one whose prior observation is that day, last wins — `cashflow`'s rule), as the
player's farm dict; `feed_reading(steps, player)` → `{"feed_day0", "feed_days_1_5",
"head_placed_8", "hands_8", "planted_12"}` using `daily_cashflow` (the `product` column) and
`farm_census.animals_placed` / `planted_by_crop` on the boards; `mechanism_failures(reading)`
→ the names among `feed_day0`, `feed_days_1_5`, `head_placed_8` that missed their bars;
`crop_line_ok(contender, baseline)` on `planted_12` within `PLANTED_GAP_BAR`.

**Controls, seed 960.** The control games are full games (`cashflow.play`), one per farm.
1. **Identity.** All thirteen seams off (`floor_bench`'s twelve plus `feed_carry` and
   `feed_stock`) with dense_farm's caps is `dense_farm` to the value; precondition `base[0] > 0`.
2. **Mechanism, three bars.** `feed_day0 ≤ 250`, `feed_days_1_5 ≤ 1,200`, `head_placed_8 ≥ 8`.
3. **Crop line, paired.** `|planted_12 − herd_first's| ≤ 12`.
Recorded: `hands_8`, the daily table for days 0-12 for both farms, `decompose`'s residual.

**Criterion, seeds 960-975**, sides alternated by list position, ties are losses,
`kaggle-environments` 1.32.7, `ROBRICULTURE_STRICT=1`: ≥ 60% of 16 vs `third_herder`; ≥ 90% vs
each `DEFAULT_ANCHOR`; each `EXTERNAL_ANCHORS` member no fewer wins than the champion on the
same seeds in the same run; madhur and pilkwang named in the verdict line. Exit 0/1/2.

**Recorded.** Arm B vs `third_herder` on 960-975.

## Risks named in advance

A one-day carry means a shed trip every day per herder; if the walk starves placement, the
head bar names it. A one-feeding buffer has no slack for a turn the feed block is truncated
off the ten-order cap; one unfed day is survivable, two are an escape. The crew (herd_first's
2 hands at day 8) is not addressed and is recorded.

## Testing

Pure TDD. `tests/test_field_rival.py`: both hooks `None` on the benchmark; a herder with
`carry=3` picks up 3 and with the default picks up `FEED_CARRY`; `market_orders(feed=4)`
holds back 4 in the sweep and tops the shed up to 4, and the default is the frozen buffer;
`act` passes the carry (with the herder count) and the stock to the hooks (recording subclass
on a reset observation); no existing assertion changes. `tests/test_lean_feed.py`: `carry_for`
and `stock_for` at the edges; the hooks; registered, built on `herd_first`, everything else
inherited. `tests/test_feed_bench.py`: constants and fresh seeds; `board_on_day` on the
`cashflow` fixture shape (the day boundary rule); `feed_reading` and `mechanism_failures` on
fabricated readings, each bar failing alone; the thirteen-hook identity stub survives a turn;
arm B buffer-only and unregistered; imports pinned.

## Outcomes

PROMOTE → PR closes #262 (base `main` once #261 has merged); designation is a separate step
on Rob's say-so. REJECTED → record and root cause on #262, closed `not_planned`; the PR carries
the seams and the bench as a record. VOID → the control that failed and the tables, on #262.
