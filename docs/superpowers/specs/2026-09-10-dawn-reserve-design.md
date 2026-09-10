# dawn_reserve — herd_first with the cash floor set to tomorrow's wages plus the herd's feed (#256)

**Issue:** #256 (filed from #254's rejection on Rob's instruction; declaration on the issue before any code)
**Branch:** `256-dawn-reserve`

## Context

#254's `herd_first` beat `third_herder` 14/16 and lost the field (madhur 5/16 against the
champion's 11/16). The census said why: the sim clears `farm["hands"]` every night
(`kaggriculture.py:880`) and re-hires at dawn on the wage ladder (1, 1, 2, 3, 5, 8, 13, 21,
34, 55 — 143 for ten hands), and with `RESERVE_F = 0` the herd block, which runs on every hour,
spends every coin before dawn: 2-20 in hand, 2-5 hands, the crop line stalled at 11 tiles for
six days, no feed wheat against a strong opponent and head placed 9 → 3. The buy order was the
right knob; a zero reserve is wrong under daily re-hiring.

## The change: one decision on top of `herd_first`

`dawn_reserve` = `herd_first` with

```
capital_reserve(day, animals) = wage_bill(hire_target(day + 1)) + feed_cost(animals)
```

- `wage_bill(n)` = Σ `hired_hands.hand_wage(k)` for k = 1..n — the benchmark's own ladder:
  12 for five hands, 54 for eight, 143 for ten, 376 for twelve.
- `feed_cost(animals)` = `field_rival.feed_buffer(animals)` × `CROPS["WHEAT"]["seed"]` — the
  units the feed block keeps in the shed at the price it already budgets with: 80 for four
  head, 160 for eight, 260 for thirteen.

The reserve is what the herd block leaves behind at dusk; nothing else changes.

**The seam.** `FieldRivalStrategy.capital_reserve(self, day=None, animals=None)` — the same
hook with two optional arguments, `None` on the benchmark; `act` passes `(day, animals)`;
`field_pace` keeps returning `RESERVE_F` and ignores them. Every existing call without
arguments still works.

## Arm B — `wage_reserve`, recorded

Built in the bench, unregistered: `herd_first` with `capital_reserve` = `wage_bill(hire_target(day + 1))`
alone. If B matches A, feed was not the starving line.

## The bench: `harness/reserve_bench.py`

Constants: `CONTENDER = "dawn_reserve"`, `CHAMPION = "third_herder"`, `BASELINE = "herd_first"`,
`SEEDS = tuple(range(928, 944))`, `CONTROL_SEED = 928`, `CHAMPION_BAR = 0.60`, `ANCHOR_BAR = 0.90`,
`ARM_B = "wage_reserve"`, `HEAD_DAY = 8`, `HEAD_BAR = 8`, `HANDS_BAR = 8`, `CROP_DAY = 12`,
`PLANTED_GAP_BAR = 12`. `order_reading`, `format_order_shape`, `crop_line_ok`, `REFERENCE` and
`PILKWANG` are `order_bench`'s / `pace_bench`'s, imported. Spent seeds: 100-115, 200-215,
300-331, 400-415, 500-515, 600-615, 700-703, 800-927.

Order fixed: controls, criterion, arm B; a failed control exits 2 VOID and arm B is not scored.

**Controls, seed 928.**
1. **Identity.** All eleven seams off (`capital_reserve` now switched off as
   `lambda self, day=None, animals=None: None`) with dense_farm's caps is `dense_farm` to the
   value; precondition `base[0] > 0`.
2. **Mechanism, absolute, two bars.** At the close of day 8, `hands ≥ 8` (herd_first had 2)
   **and** `head_placed ≥ 8` (herd_first's gain). Both must hold; a miss names which.
3. **Crop line, paired.** `|planted at day 12 − herd_first's on the same seed| ≤ 12`
   (herd_first measured 48 on seed 912), herd_first read off its own game vs the champion.
Recorded beside them: head held, free pasture, planted and strawberry tiles at day 8, money at
day 8 and 12, payday — for the contender, herd_first and the champion.

**Criterion, seeds 928-943**, sides alternated by list position, ties are losses,
`kaggle-environments` 1.32.7, `ROBRICULTURE_STRICT=1`: ≥ 60% of 16 vs `third_herder`; ≥ 90% vs
each `DEFAULT_ANCHOR`; each `EXTERNAL_ANCHORS` member no fewer wins than the champion on the
same seeds in the same run. The madhur row is named in the verdict line beside pilkwang's.
Exit 0/1/2.

**Recorded.** Arm B vs `third_herder` on 928-943.

## Risks named in advance

The reserve slows the herd (each animal waits behind 12-376 of wages and 80-260 of feed); the
head bar catches it. Twelve hands cost 376 a day from day 15. The crop ceilings pinned on #252
still apply.

## Testing

Pure TDD. `tests/test_field_rival.py`: the hook accepts `(day, animals)` and still returns
`None`; `act` passes the day and the placed head to it (a recording subclass on a real reset
observation). `tests/test_field_pace.py`: `capital_reserve(8, 4) == 0`. `tests/test_dawn_reserve.py`:
`wage_bill` and `feed_cost` at the declared values; the reserve at named days; registered,
built on `herd_first` with the order and every knob inherited. `tests/test_reserve_bench.py`:
constants and fresh seeds; `crew_ok` and `mechanism_ok` at their bars; arm B unregistered,
wages-only; readers and verdict imported. Full gate and preflight before push.

## Outcomes

PROMOTE → PR closes #256; designation is a separate step on Rob's say-so
(`python -m harness.promotion --succeed dawn_reserve --issue 256 --pr N …`). REJECTED → record
and root cause on #256, closed `not_planned`; the PR carries the seam change and the bench as a
record. VOID → the control that failed and the census, on #256.

## Result and corrections, 2026-09-10 (the run, then the whole-branch review)

**VOID on the crew bar.** Controls: identity PASS (41,064 both sides); mechanism FAIL — hands
**2** at day 8 (bar 8), head placed 8 (bar 8); crop gap 0 against herd_first. Criterion and arm
B not scored; only seed 928 played. Record: #256's result comment.

**The premise at "The change" above is false for this base.** `capital_reserve` is applied as
`cash_floor` inside the herd block only. Under the frozen `BUY_ORDER` the herd is the last
spender, so a herd floor is a day floor; under `herd_first`'s order the land and seed blocks
run after the herd and spend the reserved cash, so dusk still ends near zero and dawn hires
two hands. The two contenders played the same board (23 planted, 8 head, 48 at day 12); the
reserve only moved where the money sat at day 12 (3,220 against 876). Predictable from one
grep before the run — a lesson for the next declaration: trace the seam to every use site.

**Two more corrections from the review, for the next contender:**
1. `feed_cost` prices wheat at the seed price (10); the feed block emits `BUY_PRODUCT` at the
   market price, which starts at 25 and climbs as the farm's own buying drains it. The feed leg
   under-reserves by roughly 2.5-3×.
2. The feed leg is reserved in full, ignoring wheat already in the shed; the sell sweep already
   keeps `feed_buffer(animals)`, so the honest quantity is the shortfall, which needs the seam
   to see the shed.

**The next single decision.** A turn-wide floor under a new seam — applied by land, seed and
herd alike, hires exempt, 0 on the benchmark (`reserve=` must stay herd-only or the frozen
1,200 leaks into land and seed and breaks identity) — carrying dawn's wage bill plus the feed
shortfall at the market price. Once the floor is real, the crop-gap bar becomes the binding
control.
