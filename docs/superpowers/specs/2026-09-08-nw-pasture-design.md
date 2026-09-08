# NW pasture block — open the pasture before the head (#246)

**Issue:** #246 — the layout change #244 pointed at
**Branch:** `246-nw-pasture`
**Decided with Rob, 2026-09-08:** the contender is #244's front ramp with the pasture block
moved into NW; the block stays twelve tiles; the pre-day-12 crop cost is left visible and
gated by the day-16 crop-line control; an earlier NE buy is a recorded arm B.

## Context

#244 fronted the herd ramp on `third_herder` (`FRONT_RAMP = ((0, 4), (2, 8), (6, 12))`) and
was REJECTED 3/16. Its census said why: the contender **owned** 10 head at day 9 against the
champion's 4 — the cash was there — but **placed** 5 against 4 and spent 561 of 719 turns
with head in the shed. `field_rival.PASTURE_TILES` is five NW tiles followed by seven NE
tiles, and `LAND_RAMP` buys NE on day 12, so pasture is land-capped at five until then
whatever the ramp asks.

Two facts make the layout the lever:

1. `BUILD_PASTURE` is free and instant — the sim op only sets the tile's kind. Pasture is
   bounded by owned tiles, not money.
2. #234 measured lonespear building six pasture tiles on day 0 and fourteen by day 7 **inside
   NW alone**, buying NE on day 9 for strawberry. NW has 25 tiles; the champion works 16 crop
   tiles there before day 12 — four crop hands × `CLUSTER` 4, on either side of the third
   herder joining on day 8 — and never needs the other four until NE opens.

A layout change on its own is inert: the frozen `ANIMAL_RAMP` asks for four head by day 8
and five tiles already hold that. The block matters only under a ramp that asks for more
head than five tiles hold — #244's ramp, whose cash #244 already proved. So the contender is
**one change on top of `pasture_first`**, two on top of the champion, and the honest framing
is "#244 re-run with the land cap removed".

## Hypothesis

The herd is layout-limited, not ramp-limited. With the twelve-tile block inside NW, the front
ramp converts head-owned into head-placed from day 2 instead of day 12, the shed-turns
collapse, and the extra head-days beat `third_herder`. The crop line gives up three worked NW
tiles before day 12 and is whole again when NE opens on day 12.

## The contender: `strategies/nw_pasture.py`

`NwPastureStrategy(PastureFirstStrategy)`, `name = "nw_pasture"`, `benchmark = False`.
Everything is inherited — `FRONT_RAMP`, the third herder from day 8, the lead of 3, #219's
cow rule, the crop caps, the frozen benchmark's crop/hire/land/feed/sell rules — except the
layout, which comes through one new seam.

**The block.** `PASTURE_BLOCK = tuple(fr._quadrant_tiles("NW")[1:13])` — the twelve NW tiles
nearest the shed after the shed-access tile `(4, 4)`, in the frozen nearest-to-shed order:

```
(3,4) (4,3) (2,4) (3,3) (4,2) (1,4) (2,3) (3,2) (4,1) (0,4) (1,3) (2,2)
```

The first five are the frozen block's own first five, so the shed-adjacent prefix the herders
walk is unchanged; tiles six to twelve are NW instead of NE. Twelve is `len(PASTURE_TILES)`,
so the ramp's ceiling and every inherited rule that reads the block length are unchanged.

**Crop tiles.** Derived by the frozen rule with the block removed:
`tuple(t for q in fr.OWNED_QUADRANTS for t in fr._quadrant_tiles(q) if t not in PASTURE_BLOCK)`.
NW keeps thirteen crop tiles, `(4, 4)` first. Crop slots 0-2 are all-NW; slot 3 is
`(0, 0)` plus three NE tiles, so its hand works one tile until day 12; slot 4 onward is NE
then SW as before. The class carries both tuples as attributes so tests read them off the
agent, in the shape `LEAD_TILES`, `HERDER_DAY` and `FRONT_RAMP` use.

**The seam.** `FieldRivalStrategy.layout(self)` returns `(pasture_tiles, crop_tiles)` or
`None` for the frozen `(PASTURE_TILES, CROP_TILES)`. On the benchmark it never fires (#181).
`act` reads it once per turn and threads the pair into the helpers, which gain keyword
parameters defaulting to the frozen constants so `field_rival`'s own decisions are
byte-identical:

- `active_pastures(day, animals, count=None, block=PASTURE_TILES)` → `block[:…]`
- `crop_cluster(worker, workers=LIVESTOCK_WORKERS, crops=CROP_TILES)` → `crops[slot*CLUSTER:…]`

`_crop_slot` is untouched: the slot layout is still derived from `LIVESTOCK_WORKERS`, so the
third herder still gives up only its own tiles. The `empty` count in `act` uses the same
`crops`. No other helper reads the layout.

## Arm B — the land seam

`FieldRivalStrategy.land_target(self, day)` returns quadrants to own or `None` for the frozen
`land_target` ramp; `market_orders` gains `land=None` and reads
`land_target(day) if land is None else land`. On the benchmark it never fires.

The bench builds arm B unregistered, as `front_bench.arm_b_class` does: `nw_pasture` with
`LAND_RAMP_B = ((0, 1), (6, 2), (16, 3))` — NE on day 6 instead of 12, SW unchanged. Day 6
is the day `FRONT_RAMP` steps to 12 head; NE costs 1,000 against `CAPITAL_RESERVE`
1,200 and competes with head, which is why B is recorded and not gated.

## The bench: `harness/layout_bench.py`

Constants, all declared here and on #246 before any code: `CONTENDER = "nw_pasture"`,
`CHAMPION = "third_herder"`, `SEEDS = range(880, 896)`, `CONTROL_SEED = 880`,
`CHAMPION_BAR = 0.60`, `ANCHOR_BAR = 0.90`, `PLACED_DAY = 9`, `CROP_DAY = 16`,
`PLACED_DELTA_BAR = 4`, `PLANTED_GAP_BAR = 5`, `ARM_B = "early_land"`. Spent seeds:
100-115, 200-215, 300-331, 400-415, 500-515, 600-615, 700-703, 800-879.

Order is fixed: controls, then the criterion, then arm B. A failed control exits 2 VOID and
nothing downstream is scored.

**Controls, on seed 880, contender vs champion, both seats.**

1. **Identity.** All six seams off (`herd_preference`, `pasture_count`, `herd_target`,
   `livestock_workers`, `layout`, `land_target`) is `dense_farm` to the value on a full
   seeded game, precondition `base[0] > 0`. Reuses `front_bench.run_controls`' identity
   shape, extended for the two new seams.
2. **Mechanism, paired.** Head **placed** at day 9, contender minus champion, **≥ 4**. The
   champion places 4 on 864 (#244); the contender under the front ramp owned 10 by day 9 with
   the cap on, so ≥ 8 placed is the expectation and 4 the bar. Recorded beside it, not gated:
   shed-turns (expected to fall from #244's 561), head owned at day 9, and the first day with
   ≥ 8 pasture tiles standing (the champion's is day 12; the contender's must be earlier or
   the block is not being built).
3. **Crop line, paired.** `|planted tiles at day 16 − the champion's| ≤ 5`. The champion
   plants 30; the contender's slot-3 hand has three NE tiles from day 12 and its NW tiles
   are the same count, so 30 is expected.

`mechanism_reading` is `front_bench.mechanism_reading` plus `first_day_pasture_at_least(turns, n)`;
`mechanism_ok` gates on the placed delta.

**Criterion, seeds 880-895, sides alternated by list position, ties are losses,
`kaggle-environments` 1.32.7, `ROBRICULTURE_STRICT=1`.** PROMOTE only if all three hold:

- ≥ 60% of 16 vs `third_herder`;
- ≥ 90% vs each `DEFAULT_ANCHOR`;
- for each `external_pool.EXTERNAL_ANCHORS` member, no fewer wins than the champion on the
  same seeds in the same run (#152's paired limb; the champion's 864-879 row from #244 was
  0, 0, 0, 0, 11 of 16).

`rival_bench.criterion(..., external_pairs=pairs)` decides; exit 0 PROMOTE / 1 REJECTED /
2 VOID. 288 gated games plus 16 for arm B, 304 in all.

**Recorded, not gated.** Arm B `early_land` vs `third_herder` on 880-895. If B beats A, the
crop cost before day 12 was the binding term, not the block.

## Risks named in advance

- **Labour.** Three herders from day 8 now have twelve tiles to build and up to twelve head to
  walk out and feed; #239 found two herders bind at eight. If placed head at day 9 lands at
  6-7, the herd is labour-limited next and the control still passes — the reading is recorded
  either way.
- **Cash.** The ramp buys head as fast as surplus allows; with the cap gone the day-2 want of
  8 spends the opening bankroll harder than #244 did. If the crop-line control fails, the herd
  is eating the seed budget and the arm is two changes.
- **Walk.** Tiles ten to twelve of the NW block are two and three steps further from the shed
  than NE's first tiles were; the herder feed round-trip is longer. Recorded by the shed-turn
  count, not gated.

## Testing

Pure TDD, red observed before green, one behaviour per loop; reports quote the red.

- `tests/test_field_rival.py`: `layout()` and `land_target()` return `None` on the benchmark;
  `active_pastures(..., block=)` and `crop_cluster(..., crops=)` default to the frozen
  constants and honour a passed pair; the existing frozen-layout assertions are unchanged.
- `tests/test_nw_pasture.py`: the block is twelve tiles, all NW, none `(4, 4)`, its first five
  equal the frozen block's first five; crop tiles are disjoint from the block and cover every
  owned tile; slot 3 is `((0, 0), (5, 4), (5, 3), (6, 4))`; the strategy is discovered by
  name, not a benchmark, and inherits `FRONT_RAMP`.
- `tests/test_layout_bench.py`: `first_day_pasture_at_least` on a hand-built census;
  `mechanism_ok` at delta 3 and 4; `arm_b_class` is unregistered and returns
  `LAND_RAMP_B`; the verdict path with fabricated rows as `test_front_bench` does.
- Full gate `pytest -q -n auto --cov --cov-branch` and `python -m scripts.preflight` before
  push.

## Outcomes

PROMOTE → PR closes #246, then designation is a separate step on Rob's say-so
(`python -m harness.promotion --succeed nw_pasture --issue 246 --pr N …`).
REJECTED → record and root cause on #246, closed `not_planned`; the PR carries the seams and
the bench as a rejection record, as #245 did. VOID → the control that failed, on #246; the
criterion is not read.

## Correction, 2026-09-08 (final whole-branch review, before the bench ran)

The Context and Hypothesis sections understate the pre-day-12 crop cost. Measured off the
code (`HAND_RAMP (0, 6)`, the farmer works too, `_crop_slot`, `land_target`):

- Days 0-7: six hands plus the farmer, herders (1, 2), **five** crop slots — the champion works
  all **20** NW crop tiles, not 16. Under the block NW holds 13: slots 0-2 all NW, slot 3
  `(0, 0)` plus three locked NE tiles, slot 4 wholly NE and locked. The gap is **7 tiles**, and
  crop hand 6 idles for eight days.
- Days 8-11: the third herder takes worker 6 on both sides; slot 5 is NE for both layouts.
  Champion 16, contender 13. Gap **3**.
- "Slot 4 onward is NE then SW as before" is wrong: under the frozen layout slot 4 is four NW
  tiles.

The day-16 crop-line control is structurally blind to this deficit: by day 16 both layouts
expose the same workable tiles. It stays as declared. The bench additionally **records**
planted tiles at day 8 (`EARLY_CROP_DAY`) per side, not gated, so a REJECTED result can be
root-caused against the crop line through the melon-funding window rather than against
labour, walk or cash by default. No declared constant, bar or gate changes.
