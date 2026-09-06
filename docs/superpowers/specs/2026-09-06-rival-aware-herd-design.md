# #219: read the rival's herd off the board, and keep our herd out of their market

- **Issue:** #219 (Rob's wild idea, 2026-09-06; cross-checked and narrowed in the issue)
- **Date:** 2026-09-06
- **Depends on:** #146 (wool is the knife-edge shared market), #202 (`dense_farm` is the champion; the
  `caps` precedent for a behaviour-preserving parameter on the frozen benchmark), #181 (`field_rival`
  frozen), ADR-0007
- **Decides:** whether one rival-aware decision beats the champion on the declared bar

## Context

Most of the rival is public: `obs["farms"][1 - player]` carries their tiles, including every
placed animal. No strategy in the repo reads it. The one shared-market effect measured to swing
a season is wool: #146 found the same ~160 wool earning 25,827 alone and 6,765 when the other
farm sold wool too, because wool has one shop and floors past roughly 300 units between the two
farms. Milk has three shops, 570 season demand, and never floored in those runs. The champion's
herd rule is budget-driven, not market-driven: a sheep whenever the budget covers three, else a cow.

Adapting by *denying* the rival's market was tried and is arithmetically self-defeating (#173).
Adapting by *avoiding* it has not been tried. This experiment adapts exactly one decision.

## Hypothesis

If the rival is running sheep, buying cows instead of sheep — everything else byte-identical to
`dense_farm` — wins more games, because our wool would otherwise land in the market they are
flooding and milk is the deeper market.

## Design

**Signal.** `rival_sheep(obs)`: the number of tiles on the other farm whose `animal` is `SHEEP`.
Public state only; no market-delta reading in this version.

**Decision.** In the herd buy loop, if `rival_sheep >= SHEEP_THRESHOLD` (declared: **2** — one can
be a stray placement, two is a herd), buy `COW` regardless of budget; otherwise the existing rule.
Nothing else changes: crop caps, ramps, sells, land, feed are `dense_farm`'s.

**Where it lives.** `strategies/rival_aware.py`, `RivalAwareStrategy(DenseFarmStrategy)`,
registered as `rival_aware`, a contender (not a benchmark). The frozen benchmark gains one
behaviour-preserving seam in the #202 shape: `market_orders(..., prefer=None)` and a
`FieldRivalStrategy.herd_preference(obs)` hook returning `None`; with the defaults its decisions are
byte-identical, pinned by the existing frozen-pin tests plus one new equality test.

## Controls (run first; a failed control voids the run)

1. **Identity.** `SHEEP_THRESHOLD` set to infinity reproduces `dense_farm` to the value on a full
   seeded game (both seats' rewards equal).
2. **Mechanism fires.** Against `dense_farm` as rival (it runs sheep when rich), the contender's
   emitted `BUY_ANIMAL COW` count over a seeded game exceeds the baseline's, and its `BUY_ANIMAL
   SHEEP` count is lower. Precondition asserted: the rival actually placed >= 2 sheep in that game.
3. **Quiet when the rival has no sheep.** Against a rival that places no sheep (`wheat_hands`), the
   contender's action stream is identical to `dense_farm`'s, turn for turn.

## Pass criterion (declared before code, ADR-0007; the bars #202 and #206 used)

kaggle-environments 1.32.7. **16 fresh seeds, 400-415, sides alternated by list position**
(`harness.triage.head_to_head_rate`). Promote only if the contender:

- beats `dense_farm` (the champion, `champion.json`) in **>= 60% of 16**, and
- wins **>= 90%** against each of `harness.evolve.DEFAULT_ANCHORS` (six, including `field_rival`
  and `meta_bot`; `meta_bot` runs 4 sheep and 9 cows, so the rule fires against it and shares its
  milk market — a real test of whether milk is deep enough).

A tie is not a win. Anything less is REJECTED; the issue keeps the record and the PR carries the
seam and the harness as salvage (ADR-0007), with no promotion.

**Recorded, not gated:** per-opponent medians of final money; cows/sheep bought per game;
realised wool and milk prices from `harness.episode_analysis.price_realisation` on two seeds
(the mechanism's direct signature).

## Risks, recorded up front

- **Timing.** The rival's sheep show up from about day 4-8; our herd ramps 1 -> 3 by day 4 and
  8 by day 12, so early buys are sheep either way and only the later head switch.
- **Cost when it fires needlessly.** A cow's first product is at day 8 (sheep: day 6) at base
  160 (sheep: 200). Against a rival who never floods wool the rule gives revenue away.
- **Milk can be shared too.** 570 demand and three shops make it deeper, not bottomless; the
  `meta_bot` anchor is where that shows.

## Out of scope

Melon, freed-tile crop routing, reading market inventory deltas, any second decision, any change
to `field_rival`'s own decisions, any change to `champion.json`.

## Alternatives rejected

- **Read wool sells off market-inventory deltas.** Later and noisier than the tiles, which show
  the herd the day it is placed; kept for a follow-up if the tile signal proves too slow.
- **Melon tiles by the rival's melon count.** Bigger money, but #162 found "skip the glutted
  market" a wash and #178 says losses track the rival's volume, not ours.
- **Freed-tile crop choice by the rival's planted counts.** Strawberry does not floor at 750
  demand, so the strongest crop signal has no market to route away from.
- **Subclass `act` wholesale.** Duplicates 40 lines of the benchmark; the `prefer` seam is the
  #202 shape and keeps the frozen pin meaningful.
