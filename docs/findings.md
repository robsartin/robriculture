# What we learned building robriculture

A record of what the experiments established, written so the reasoning survives the
repository. Every claim here cites the issue holding its numbers; nothing is restated
from memory. Where a claim was later withdrawn, the retraction is kept rather than the
original tidied away.

Status at time of writing: the submitted agent is `neuropilot` at commit `7766e9e`,
rated **489.1**, rank ~5,267 of 7,220, against a field median of ~764. Nineteen
strategy experiments were run against it; none met its promotion criterion.

---

## 1. The game

Two farms, one shared market, 720 turns (30 days x 24). The ladder scores a **skill
rating driven by wins and losses** — margin is discarded (#143, quoting the competition's
own Evaluation page). Only the latest two submissions play. A crash is an auto-loss
(ADR-0006).

### Melon is a trap, and it is the centre of everything

`SHOP_DEMAND` lists melon under **no shop**. Its only buyer is the town centre, giving it
roughly **140 units of demand a season**, against wheat's ~1,040 and strawberry's ~860
(#162). Both players together harvest ~171. Melon also carries the steepest glut curve in
`MARKET_PARAMS` (`sq`, 3.60).

So melon has the highest base price (250) and the smallest market. Its price collapses
from ~270 to ~40 by day 12 in a typical game, and never recovers, because nothing drains
it.

This single fact explains results that looked unrelated for weeks:

- **#136**'s ceiling LP put melon *last* by tile count. It was right, and the reason was
  the demand cap.
- **#155**'s "melon is best by revenue per tile-turn" used *base* prices, which the market
  invalidates by day 8.
- **#171** steered off the rival's crop, substituted **into** melon 338 times, and lost
  **0 of 200 games**.
- **#178**: our wins and losses differ in how far melon crashes, not in anything we do.

---

## 2. Why we lose

We downloaded our own rated matches (#157) — the competition publishes them (Rules §11),
and `competition_list_episodes` / `competition_episode_replay` return them.

**Real record: 27W-40L, win-rate 0.403** over 67 episodes.

**Our own output decides the result:**

| our reward | games | win-rate |
|---|---|---|
| 0-10K | 7 | **0.00** |
| 45-60K | 19 | 0.32 |
| 60-100K | 25 | **0.76** |

Then, across 63 replays (20W 43L), we diffed wins against losses (#176, #178):

- **Identical**: actions, units harvested (141.5 vs 141.0 by day 12), land timing (third
  quadrant at day 11.50 in both), crew size, farm size, first melon sale (day 11.04), and
  the price at that first sale (~235).
- **Different**: how far melon falls afterwards. Day 12 price **94 in wins, 40 in losses**
  — a **49% gap in realised price for identical goods**.

**Wins are games where the opponent was not also dumping melon.** Rival melon tiles >= 10
at day 8 appears in **63% of losses and 15% of wins**.

That is the loss mechanism, and it is substantially **opponent-determined**.

---

## 3. What we tried, and what each ruled out

Nineteen experiments. Grouped by what they eliminate.

### Crop policy — closed from four directions

| experiment | changed | result |
|---|---|---|
| #136 | diversify across tiles (LP allocation) | 0/10 |
| #160 | re-sort the ladder by current price | 0/10 |
| #161 | argmax by measured value per tile-turn | 1/10 |
| #162 | skip crops whose market is in glut | 5/10, +0.0014 |
| #175 | **cap tiles at measured market demand** | 1/10, −0.1009 |
| #179 | cut melon only when the rival is melon-heavy | 25% vs 100% in-regime |

Diversify and you lose crew locality; concentrate and you crash your own price (#161 drove
melon 270 -> 34 by itself). The static ladder sits accidentally between the two. And
**cutting melon is expensive in every configuration tried** — melon into a crashed market
still beats the alternatives.

### Livestock — measured, not assumed

#121 forced the livestock knobs on. The chain ran fully: 17 animals bought, 17 placed, 22
FEED, 31 CARE. **Reward collapsed 46,843 -> 2,674**, below the 3,000 starting cash, as the
crew abandoned the fields. The evolved `herd_target_scale ~= 0.09` is evolution's *correct*
answer. Four genuine defects in the livestock chain were repaired along the way and remain
unmerged on `121-empty-pasture-intent`, because the path they enable is one the agent is
right not to take.

#158: 53% of the strongest opponent's revenue is livestock we cannot touch; 100% of ours is
crops. Livestock is not unreachable — it is unaffordable.

### Labour — the constraint, not the slack

#156: we field **7.03 actors per turn to pilkwang's 11.29**, cap at 9 hands to their 13,
and spend **168 turns of 719 with zero hands** — because we are broke on 6 days of 30
(median money on those turns: 0). Labour is downstream of cash, and cash is downstream of
production. Several proposals assumed the reverse ("87/87 tiles at 54% worker capacity");
that premise is false on measurement.

### Evolution — not currently a working search

#148: **16 generations across two configurations produced a genome byte-identical to its
seed.** At 27 games/genome and again at 96. Any design requiring evolution to move is
blocked until the search mechanism changes (annealed sigma, crossover, or something
non-evolutionary).

### Market denial — arithmetically self-defeating

#158, #173: 100% of our revenue sits in the goods we would have to glut, against 47% of
theirs. The natural experiment (#161) crashed melon and moved our reward **46,843 ->
25,344** while the opponent's *rose* 4.4%. A guarded version fires in **1 of 20 games**.

---

## 4. Two methodological failures worth more than the experiments

### 4.1 A rollout metric nobody validated

#165, #167 and #174 were all built on scoring candidate policies with a forward rollout.
#174 finally checked the metric against reality:

```
Spearman rho(rollout score, real performance) = -0.05
```

The rollout's best pick was near the worst real performer. **#167's headline finding —
"a perturbed policy beats the champion in 10 of 11 states by 45-384%" — was an artifact and
is retracted.** Those were gains in the rollout's own metric.

#177 diagnosed it: **two independent defects, neither fixable alone.**

| configuration | rho |
|---|---|
| idle opponent + `standing_value` (what all three used) | −0.05 |
| mirror opponent + `standing_value` | −0.19 |
| idle opponent + final money | −0.10 |
| **mirror opponent + final money** | **+0.20 to +0.69** |

1. `standing_value` valued unsold stock at *current* price — a farm hoarding melon scored
   at 260 when selling it crashes the price to 34.
2. `ROLLOUT_PASS` (an idle opponent) removed the market dynamics: with no opponent supply
   the market never gluts, so aggressive selling scores brilliantly.

They masked each other. The check that catches this takes **four minutes** and is now the
entry condition for any rollout-scored work.

### 4.2 The benchmark cannot reproduce our loss mechanism

#179 measured melon planting across the seven vendored external opponents:

```
six of seven plant NO melon; pilkwang peaks at 9 tiles
opponents triggering "rival is melon-heavy": 0/7
```

**Our fitness pool cannot exercise the mechanism behind 63% of our real losses.** Every
paired test in this repository — including the rejections above — was measured in a regime
that excludes our main loss driver. #147 had already shown the pool was self-authored and
blind (the champion beats 23 of 23 agents we wrote, loses to 4 of 7 written by others);
this is the sharper version of the same problem.

---

## 5. What is worth keeping

- **`kaggisim/forward.py`** — rebuilds an exact steppable game from an observation.
  Validated to the value at 48 turns with the sim's randomness on and off (#164). Two traps
  are encoded in it: the interpreter reads its step from `len(env.steps)`, not
  `observation["step"]`, and both must be set.
- **`economy.market_price`** — the sim's price curve, reconciled at 90 points per item
  (#162/#163). The codebase previously documented the curve in a comment and never
  implemented it, which is why three experiments guessed at price impact.
- **The ladder-episode pipeline** (#157) — real matches, real opponents, and the only
  evidence in this project that was not generated by our own assumptions.
- **The positive-control habit.** Five dead instruments were caught by asserting something
  must be non-zero: a recorder returning the 3,000 starting cash, a license gate reporting
  every kernel unlicensed, a harvest probe reporting zero units, a "forfeited" column that
  was counting successful harvests, and a hands probe sampling at midnight when the crew is
  cleared.

## 6. What we would tell the next person

1. **Read the demand table before the price table.** Base price ranks melon first and
   demand ranks it last; demand wins.
2. **Validate a scoring function before optimising it.** Four minutes would have saved
   three experiments.
3. **Check your benchmark can produce the phenomenon you are chasing.** Ours could not.
4. **A single seed confirms a mechanism fires and says nothing about its size.** Five
   separate small-sample numbers pointed the wrong way here.
5. **Correlation in replay data is not a lever.** The strongest loss signature we found
   (#176) was tested (#175) and turned out to be a symptom.
