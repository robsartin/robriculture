# herd_first — field_pace with the herd funded before land and seed (#254)

**Issue:** #254 (filed from #252's VOID; declaration on the issue before any code)
**Branch:** `254-herd-first`
**Decided with Rob, 2026-09-10:** the herd goes before land and seed in the buy order; arm B
is herd before seed only; the mechanism control is the bar #252 failed; the crop line is
paired against `field_pace`.

## Context

#252 put the field's schedule on the benchmark's buy order and VOIDed on the day-8 shape
control: 6 head placed against a bar of 8, with 15 in cash. `market_orders` funds land and the
whole strawberry seed bill before the herd. The field funds its herd first, and the sim says
why that is self-funding: every placed animal makes one fertilizer a day
(`fertilizer_available` set nightly per animal), fertilizer sells from 100 and falls 0.2 a
unit with no shop draining it, sheep add wool from day 6. Four head from day 0 earn ~380 a
day before any melon pays, thirteen ~1,200; lonespear takes 51% of revenue from livestock and
fertilizer (#234). The herd is the pre-payday cash engine, not a cost.

## The seam: `market_orders(..., order=None)`

The four buy blocks — hires, land, seed, herd — become named steps over the shared budget,
run in the order given; sells stay first and feed last, unchanged. The frozen order is
`BUY_ORDER = ("hires", "land", "seed", "herd")` and `order=None` selects it, so the benchmark
emits the same list it does today. `FieldRivalStrategy.buy_order()` returns `None`; `act`
passes `order=self.buy_order()`. An unknown block name raises (`KeyError`), pinned by a test.

The refactor is Mikado-shaped: the body is split into four inner steps that close over
`budget` and `buys`; a golden-pin test fixes the frozen list for one dawn state before the
split and holds through it; the identity control checks a whole game.

## The contender: `strategies/herd_first.py`

`HerdFirstStrategy(FieldPaceStrategy)`, `name = "herd_first"`, `benchmark = False`,
`ORDER_H = ("hires", "herd", "land", "seed")`, `buy_order()` returns it. Nothing else changes:
every `field_pace` knob (#252) and every `third_herder` rule beneath it is inherited.

## Arm B — `herd_mid`, recorded

Built in the bench, unregistered: `field_pace` with `buy_order()` = `("hires", "land", "herd", "seed")`.
Herd before seed, after land. If B matches A, land's priority is not what moved.

## The bench: `harness/order_bench.py`

Constants: `CONTENDER = "herd_first"`, `CHAMPION = "third_herder"`, `PACE = "field_pace"`,
`SEEDS = tuple(range(912, 928))`, `CONTROL_SEED = 912`, `CHAMPION_BAR = 0.60`, `ANCHOR_BAR = 0.90`,
`ARM_B = "herd_mid"`, `ORDER_B = ("hires", "land", "herd", "seed")`, `HEAD_DAY = 8`, `HEAD_BAR = 8`,
`CROP_DAY = 12`, `PLANTED_GAP_BAR = 12`. `REFERENCE`, `PILKWANG`, `PAYDAY_MONEY`, `shape_reading`
and `format_shape` are `pace_bench`'s, imported. Spent seeds: 100-115, 200-215, 300-331,
400-415, 500-515, 600-615, 700-703, 800-896.

Order fixed: controls, criterion, arm B; a failed control exits 2 VOID and arm B is not scored.

**Controls, seed 912.**
1. **Identity.** All eleven seams off (`pace_bench`'s ten plus `buy_order`) with dense_farm's
   caps is `dense_farm` to the value; precondition `base[0] > 0`.
2. **Mechanism, absolute.** `head_placed` at the close of day 8 **≥ 8** — the bar #252 failed
   at 6. Read off the contender's census in its game against the champion.
3. **Crop line, paired.** `|contender planted at day 12 − field_pace's planted at day 12| ≤ 12`,
   field_pace read off its own game against the champion on the same seed.
Recorded beside them, from `shape_reading`: quadrants, hands, planted and strawberry tiles at
day 8, money at day 8 and 12, payday, for the contender, field_pace and the champion.

**Criterion, seeds 912-927**, sides alternated by list position, ties are losses,
`kaggle-environments` 1.32.7, `ROBRICULTURE_STRICT=1`: ≥ 60% of 16 vs `third_herder`; ≥ 90% vs
each `DEFAULT_ANCHOR`; each `EXTERNAL_ANCHORS` member no fewer wins than the champion on the
same seeds in the same run. `rival_bench.criterion(..., external_pairs=pairs)` decides; exit
0/1/2; the pilkwang row is named in the verdict line.

**Recorded.** Arm B vs `third_herder` on 912-927.

## Risks named in advance

Seed starvation (the paired crop control bounds it at 12 tiles). Feed: thirteen head eat
thirteen wheat every other day from the same cash; eight `BUY_ANIMAL`s in one turn can push
the feed order off the ten-order cap (#252 review M7) — recorded through `head_placed`, since
an unfed animal escapes. The crop ceilings pinned on #252 (11/36/30/48 workable tiles by
window) still apply; no crop bar is set above them.

## Testing

Pure TDD. `tests/test_field_rival.py`: `buy_order()` is `None` on the benchmark; the golden
pin of the frozen dawn list (written before the split, red only against the new keyword);
`order=` reorders the same blocks; an unknown name raises; no existing assertion changes.
`tests/test_herd_first.py`: the declared order; the hook; registered, built on `field_pace`
with every knob inherited. `tests/test_order_bench.py`: constants and fresh seeds;
`mechanism_ok` and `crop_line_ok` at their bars on hand-built readings; arm B is unregistered,
carries `ORDER_B` and inherits `field_pace`'s knobs; the verdict machinery is `rival_bench`'s
and the readers `pace_bench`'s. Full gate and preflight before push.

## Outcomes

PROMOTE → PR closes #254; designation is a separate step on Rob's say-so. REJECTED → record
and root cause on #254, closed `not_planned`; the PR carries the seam and the bench as a record.
VOID → the control that failed and the census, on #254.

## Result and corrections, 2026-09-10 (whole-branch review, then the run)

**REJECTED on the external limb.** Controls all PASS (identity 35,608 both sides; head placed
8 at day 8; crop gap 1). The champion row **14/16** (87.5%, p = 0.002), every anchor ≥ 90%,
shashank 4/16 against the champion's 0, **madhur 5/16 against 11/16 — REGRESSED**. The first
contender since #239 to beat the champion, and it fails the field. Seeds 912-927 spent; arm
B not played (a REJECTED exit does not run `--recorded`).

**Root cause (the census on seed 912).** The sim clears `farm["hands"]` every night
(`kaggriculture.py:880`) and the crew is re-hired at dawn for the day's wage ladder. The hire
block runs first, but it spends what survived the previous day, and with `RESERVE_F = 0` the
herd block spends every coin on every hour: dawn finds 2-20 in hand and 2-5 hands, the crop
line stalls at 11 tiles for six days, and against madhur there is no feed wheat either —
head placed 9 → 3 between days 12 and 16, final 36K to 85K. Zero reserve is not "spend
everything on growth"; under daily re-hiring it is "fire the crew at dusk". The next single
decision is a reserve that covers tomorrow's wage bill and the herd's feed.

**From the review, before the run.** (I2) Day 0 is the same under both orders — both agents
buy 5 hires, 6 melon, 3 sheep and 1 cow and leave ~608 — so the arm's reach on the day-8 bar
was days 6-8; it reached it (8 placed). (I3) At day 8 dawn the herd block can push the feed
order and all the sells off the ten-order cap for one turn; self-limiting via `pending`.
(I1) The bench now records held head and free pasture beside placed head, so a head-placed
miss says whether the head were never bought or bought and stuck. (M4) `crop_line_ok` is
symmetric as declared; its upper limb can only VOID an outcome better than predicted and did
not fire.
