# ADR-0007: Experiment-driven development process

- **Status:** Accepted
- **Date:** 2026-08-04
- **Deciders:** Rob

## Context

We evolve this agent under a competition, not ordinary product constraints. Two
kinds of change flow through the repo, and they are validated in fundamentally
different ways:

- **Engine / correctness changes** (economy constants, state parsing, action
  legality, the harness, packaging). "Does the code do what we said?" is a
  boolean a test can answer. Our existing red → green → refactor discipline fits
  perfectly here.
- **Strategy changes** (a new or tuned agent). "Is this agent actually *better*?"
  is **not** a boolean and no unit test can turn green to prove it. It is a
  statistical question answered by **win-rate in the tournament** against the
  current champion.

Three facts make the strategy case treacherous:

1. Ladder rating depends only on **win / loss / tie**, never coin margin
   ([ADR-0002](0002-heuristic-planner-before-rl.md)), and games carry real
   variance. A naive "ran 20 games, looks better, ship it" promotes noise.
2. Only the **latest 2 submissions** are live
   ([ADR-0003](0003-multi-strategy-portfolio.md)), so promotion to the ladder
   must be deliberate, not reflexive.
3. The prize requires a **reproducible writeup**
   ([ADR-0005](0005-cc-by-4.0-and-open-development.md)). Decisions we can't
   reproduce are decisions we can't defend.

We want a process that keeps our TDD discipline where it works, adds an honest
empirical gate where TDD can't reach, and leaves a reproducible trail as a
byproduct.

## Decision

**The unit of work is an experiment.** Each experiment is one GitHub issue
(label `experiment`) that states a hypothesis up front — and, for a strategy
experiment, a quantitative success criterion — before any code is written.

**Inner loop (all code, both tracks).** Follow strict TDD:

```
while (!done_with_experiment):
    write a test
    run it — it must fail (red)
    write code to make it pass (green)
    refactor, staying green
```

Work happens on a branch per experiment; nothing is committed directly to
`main`; PRs are reviewed, not auto-merged.

**Two validation tracks.**

- **Engine / correctness experiment.** Validated purely by tests going green plus
  the no-crash gate ([ADR-0006](0006-fail-safe-never-crash.md)). It merges via a
  normal green PR.
- **Strategy experiment.** Must *also* pass a **promotion test** before it can be
  promoted: a fixed set of **seeded** games (default **200**) against the current
  champion. Promote only if **both** hold:
  - win-rate ≥ the bar (default **55%**), and
  - a **binomial test** rejects the fair-coin null (50%) at **p < 0.05**.

  Seeds are fixed so the same experiment yields the same number on re-run. An
  experiment may override N / bar / α in its issue, but must state the values it
  used. The champion is the strategy currently designated as our best; the two
  live ladder slots are champion + challenger (ADR-0003).

**Outcomes.**

- **Hypothesis supported** → PR to `main`, review, merge; the strategy becomes a
  champion/challenger candidate. The issue records the result (N, win-rate,
  p-value) and is closed by the merge.
- **Hypothesis rejected** → **close the PR unmerged; keep the issue**, annotated
  with the recorded result and a link to the abandoned branch. `main` therefore
  only ever contains promoted/kept work. **Before closing, salvage any reusable
  engine / harness / infra changes into their own small green-test PR** — a
  losing strategy must not drag useful infrastructure down with it.

**The issue is the lab notebook.** Every experiment's hypothesis and result live
in its issue. This is the running record and the raw material for the ADR-0005
reproducible writeup — the writeup becomes a byproduct rather than a scramble.

## Consequences

- Decisions are reproducible: seeded games + a recorded (N, win-rate, p-value)
  mean anyone can re-run an experiment and get the same verdict.
- Discipline cost: a strategy experiment must state a hypothesis and run the full
  seeded protocol before promotion, and each run costs ~200 game-simulations of
  wall time. Accepted — it's the price of not promoting noise.
- `main` stays clean, but our chosen "close on reject" policy means a rejected
  experiment's infrastructure is lost unless deliberately split into an infra PR.
  The salvage step above is the mitigation and must not be skipped.
- The statistical gate will still occasionally err (a true improvement that
  narrowly misses p < 0.05, or a lucky pass). Accepted: over many experiments the
  bar keeps us honest better than judgment does.
- Engine experiments stay lightweight (green tests, no tournament), so
  correctness work isn't taxed by strategy-grade ceremony.
- **Ladder scores carry a ~98-point noise band, so a single ladder comparison is
  weak evidence (#74, measured 2026-08-16; widened by #80).** `ranch_hands` has
  been submitted five times and scored **536.8, 515.4, 509.5, 600.0, 501.6** — a
  98.4-point spread (501.6-600.0) on code that did not change. Verified by
  `git log`, not assumed: between the 509.5 and 600.0 submissions there is no
  commit touching `kaggisim/`, `build/`, `strategies/ranch_hands.py`, or its
  three strategy dependencies. The agent was byte-identical; only the opponent
  draw and rating settling differed.

  This decision already distrusts variance in *local* games — that is what the
  binomial gate is for. The same distrust must extend to the ladder. **Treat a
  ladder gap under ~98 points as no evidence at all**, and settle those
  comparisons with the seeded local gate instead, which is both cheaper and
  reproducible. Gaps well outside the band remain informative: the evolved
  neuropilot at 422.3 against `ranch_hands` at 600.0 is ~180 points, and the
  local benchmark had already predicted that ordering.

  This retroactively weakens any past reasoning that leaned on a sub-98-point
  ladder gap — see [ADR-0008](0008-neuroevolution-against-a-diverse-pool.md)'s
  ~522-vs-~482 comparison, which is inside the band.

  Corollary worth exploiting: **re-submitting a known agent measures the band for
  free.** These five data points cost nothing beyond submissions already spent.
- **The gate opponent changed mid-stream, so promotion results are not comparable
  across it (#76, 2026-08-16).** Until now the gate ran against `market_farmer`,
  designated on a 160/160 head-to-head record that turned out to be ~3% margins
  amplified by binary scoring — its pool share is 0.5082, within 0.0015 of two
  other agents, and it scored 476.7 on the ladder, our worst. Any challenger
  promoted before this date cleared a weaker and unrepresentative bar; do not
  compare those (N, win-rate, p) records with later ones. Designation is now by
  pool share, and the champion's two roles are recorded separately as
  `gate_opponent` and `submit_default`.
- **The promotion gate's 200 seeded games are not 200 independent trials — most
  pairings never flip outcome across seeds (#77, measured 2026-08-18).**
  `harness/flip_rate.py` played every pairing among the six `DEFAULT_ANCHORS`
  (`meta_bot`, `ranch_hands`, `market_farmer`, `ranch_adaptive`, `wheat_hands`,
  `spoiler` — the pool `designate()` already uses to rank candidates) over 10
  fixed seeds each, 15 pairings / 150 games total, and counted how many
  *distinct* outcomes (win/loss/tie) each pairing produced:

  ```
  market_farmer  vs ranch_adaptive  outcomes=(1,1,1,1,1,1,1,1,1,1)  distinct=1
  market_farmer  vs spoiler         outcomes=(1,1,1,1,1,1,1,1,1,1)  distinct=1
  market_farmer  vs wheat_hands     outcomes=(1,1,1,1,1,1,1,1,1,1)  distinct=1
  meta_bot       vs market_farmer   outcomes=(1,1,1,1,1,1,1,1,1,1)  distinct=1
  meta_bot       vs ranch_adaptive  outcomes=(1,1,1,1,1,1,1,1,1,1)  distinct=1
  meta_bot       vs ranch_hands     outcomes=(1,1,1,1,1,1,1,1,1,1)  distinct=1
  meta_bot       vs spoiler         outcomes=(1,1,1,1,1,1,1,1,1,1)  distinct=1
  meta_bot       vs wheat_hands     outcomes=(1,1,1,1,1,1,1,1,1,1)  distinct=1
  ranch_adaptive vs spoiler         outcomes=(1,1,1,1,1,1,1,1,1,1)  distinct=1
  ranch_adaptive vs wheat_hands     outcomes=(1,1,1,1,1,1,1,1,1,1)  distinct=1
  ranch_hands    vs market_farmer   outcomes=(-1,-1,-1,-1,-1,-1,-1,-1,-1,-1) distinct=1
  ranch_hands    vs ranch_adaptive  outcomes=(0,0,0,0,0,0,0,0,0,0)  distinct=1
  ranch_hands    vs spoiler         outcomes=(1,1,1,1,1,1,1,1,1,1)  distinct=1
  ranch_hands    vs wheat_hands     outcomes=(1,1,1,1,1,1,1,1,1,1)  distinct=1
  wheat_hands    vs spoiler         outcomes=(1,1,1,1,1,1,1,1,1,1)  distinct=1

  0/15 pairings flipped across 10 seeds (flip-rate = 0.0%)
  ```

  **Zero of 15 pairings produced more than one distinct outcome.** This was a
  bounded, labelled measurement, not a claim about every strategy: it covers
  the 6-agent anchor pool `designate()` already treats as representative, at
  10 seeds/pairing (150 games); it does not cover all 24 registered
  strategies pairwise (276 pairings), which would cost roughly two hours of
  wall time for a question this measurement already answers unambiguously.
  Reward magnitude does vary with the seed (ADR-0002's economy is
  stochastic); the win/loss/tie *outcome* derived from it does not, because
  the margin between two given agents consistently exceeds the per-seed
  variance in reward. An independent, larger-scale signal points the same
  way: a 12-generation neuroevolution run (#70 validation, 2026-08-18)
  improved its mean score share against these same six anchors from 0.3700 to
  0.4069 — a real, measured gain in strength — while its win-rate against them
  stayed pinned at exactly 0.1667 throughout; not one win changed hands. Two
  different measurements at two different scales agree: outcome is
  insensitive to real changes in relative strength here, until a challenger
  crosses whatever margin threshold flips a specific pairing.

  This means the promotion gate's `N=200` seeded games are, for a typical
  pairing, one repeated observation wearing 200 different seeds, not 200
  independent trials. The binomial test still computes a p-value, and that
  p-value is still arithmetically correct — but its premise (200 i.i.d.
  Bernoulli draws) is false for a pairing like these, so a passing p < 0.05
  does **not** carry the evidentiary weight 200 independent trials would.
  Effective sample size for a non-flipping pairing is close to 1, not 200.

  **What the gate is still good for:** it reliably answers "does this
  challenger beat that specific opponent, on these maps, at this strength
  gap" — the outcome is *reproducible* (ADR-0005) even where it isn't
  *independent* across seeds, and a challenger that cannot win a single
  seeded game against the champion is not being promoted on noise. What it
  does **not** establish is the statistical confidence the p-value implies:
  a PROMOTE verdict is closer to "won the one deterministic-ish matchup we
  checked" than to "beat a fair coin 200 times running." The gate is neither
  worthless (it still gates on real, reproducible outcomes) nor as rigorous
  as it presents (the significance test's independence assumption does not
  hold here). This is a documentation fix, not a gate change: the 55% bar,
  the binomial test, and N=200 are unchanged (#77) — issue #80 found the
  two candidate replacement statistics (score share vs ladder score) both sit
  at only n=6, Spearman ρ = 0.6377, short of the ≈0.886 significance
  threshold, so neither is validated evidence for changing what the gate
  measures.

## Alternatives considered

- **Judgment-based promotion** ("run enough games, eyeball it"). Rejected: not
  reproducible and easy to fool yourself near 50/50 — the exact regime where
  win/tie-only rating makes mistakes cheap to make and expensive to keep.
- **Fixed threshold without a significance test.** Rejected: near the bar, a raw
  win-rate is dominated by variance; the binomial test is cheap insurance.
- **Merge every experiment (record negative results in `main`).** A real option —
  it preserves all infra and builds the trail automatically — but rejected in
  favor of a clean `main`; the infra-salvage PR recovers its main benefit.
- **A continuous RL-style training loop instead of discrete experiments.**
  Out of scope; RL is deferred (ADR-0002). Discrete, hypothesis-driven
  experiments suit the heuristic-first phase and the reproducibility requirement.

## Follow-ups

- A mechanism for **testing ADRs** (keeping ADRs honest against the code they
  describe) is wanted but deferred to its own issue.

## Amendments

### 2026-09-05 — the frozen anchor `field_rival` was changed to fix a defect (#211)

**What this corrects.** The original decision above is unchanged: an experiment
is still measured against the designated gate opponent, and an anchor is still
not tuned in the middle of an experiment. What it did *not* say, and what this
amendment records, is what happens when a frozen anchor turns out to be
**incorrect** rather than merely weak. It says so now: a defect in an anchor is
fixed, dated, and recorded here — it is not preserved for the sake of exact
reproduction.

**The defect.** The simulator's `_spawn_weeds` converts *any* empty tile to
`{"kind": "WEED"}` at `weedSpawnChance` (0.005) per day. A pasture tile starts
empty, so a pasture tile could become a weed. A weed is a dict with no
`"animal"` key, so `field_rival._pasture_chore` fell past its `tile is None`
BUILD_PASTURE branch into the place/fetch branch and answered `["PLACE", "COW"]`
for the rest of the game. The sim's PLACE requires `tile["kind"] == "PASTURE"`,
so on a weed it is a **silent no-op**: the worker fetched an animal, walked out,
placed into nothing, and repeated — and first-match scanning over the pasture
list meant it never moved on to another tile either. The same shape existed in
`neuropilot._animal_chore` (`["PLACE", "COW", 1]`). Both modules already dug
weeds on the *crop* path; neither did on the pasture path.

**The change.** Both state machines now return DIG for a weed on a pasture /
animal tile, which clears the tile back to `None` and lets the existing
BUILD_PASTURE branch recover it. `balanced_farm` and `dense_farm` inherit
`field_rival`'s herd state machine and are fixed by the same edit.

**Why an anchor was allowed to move.** This is a correctness fix, not a
calibration change. Three reasons it is the conservative direction:

- The anchor gets **stronger**, so past PROMOTE verdicts measured against the
  pre-fix version become *harder* to reproduce, never easier.
- The defect was a **random** event (a per-tile, per-day dice roll), so it was
  an invisible source of seed-to-seed variance in exactly the measurement
  #181 exists to stabilise. A benchmark whose herd randomly strands is not a
  stable measuring stick.
- Option 2 — fixing only the contender line and leaving the anchor
  byte-frozen — was rejected: it would mean knowingly measuring every future
  experiment against an opponent we had already proven broken.

**What this costs.** `field_rival`'s behaviour changed on 2026-09-05. The
results recorded in **#181, #184, #193 and #202** were measured against the
**pre-fix** `field_rival` and are not exactly reproducible against `main` after
this date. Re-run them against the post-fix anchor before treating any of those
numbers as current. Their *direction* is expected to survive — the anchor got
stronger, not weaker — but the magnitudes are stale.

**Measured effect** (kaggle-environments 1.32.7, seeds 300-331 x both side
assignments = 64 games per condition, `dense_farm` vs `field_rival`; full
table in issue #211):

| | before | after |
|---|---|---|
| games where the dead-PLACE loop fired (`dense_farm` / `field_rival`) | 17% / 16% | **0% / 0%** |
| dead PLACE emissions across 64 games | 2,882 / 2,646 | **0 / 0** |
| turns holding a weed on a wanted pasture tile (mean per game) | 124 / 120 | **33 / 37** |
| final money (median) | 40,681 / 30,940 | 38,634 / 29,348 |

Weed *incidence* is unchanged, as it must be — the sim rolls the same dice
either way. What changes is duration: the weed is now cleared instead of held
for the rest of the game.

**The money effect is below the noise floor and is not claimed as a gain.**
Paired per-seed, per-side: 43 of 64 games are bit-identical, and the median
delta is +0 with a mean of +359 (`dense_farm`) and -268 (`field_rival`) against
a paired stdev of ~3,800 and the 6,000-11,200 seed-to-seed stdev of #181.
Restricted to the games where the loop actually fired, `dense_farm` gains a
median +2,798 (n=11, range -5,699 to +18,434) — real, but with a spread that
still swamps it. The justification for this change is correctness and reduced
variance, not score.

**Convention going forward.** An anchor may be changed to fix a defect. It may
not be changed to make it stronger, weaker, or differently calibrated. Every
such change is recorded here with its date and the issues whose numbers it
invalidates.

### 2026-09-07 — designation is by gate succession, not pool share (#241)

**What this corrects.** The #76 finding above ("Designation is now by pool
share") no longer decides the champion. The champion is now the **most recent
strategy to PROMOTE through this ADR's gate against the incumbent**, and
`harness/champion.json` records that succession — predecessor, issue, PR, date,
and the champion-row record with its one-sided binomial p — under
`"criterion": "gate_succession"`. `harness.promotion.succeed` builds the body
and refuses a record below the champion bar, so the artifact is the gate's own
verdict restated and can be rebuilt from its fields
(`tests/test_succession.py`). Pool share is still computed by
`python -m harness.promotion --designate` and `harness.rounds` as a *ranking*,
but `save_champion` refuses to overwrite a succession with a pool-share body.
The gate itself is unchanged.

**Why.** After #239 PROMOTED `third_herder` (16/16 against the incumbent
`rival_aware`, 16/16 against every anchor, seeds 816-831), the pool-share
designation on `main` at 52e582f read:

| rank | strategy | pool share | gate verdict |
|---|---|---|---|
| 1 | `cows_from_day_8` | 0.6907 | REJECTED (#225: 3/16, 12 ties vs `rival_aware`) |
| 2 | `third_herder` | 0.6635 | PROMOTE (#239: 16/16 vs `rival_aware`) |
| 3 | `rival_aware` | 0.6553 | incumbent |
| 4 | `pasture_ahead` | 0.6516 | lost to `third_herder` 16/16 (#239 A vs C) |
| 5 | `dense_farm` | 0.6391 | |

Every one of the top five beats every anchor 16/16, so share no longer
measures who wins: it measures how much money a contender banks against
opponents that never win — reward margin against a saturated pool, the
endpoint of the #77 caveat above. A designation that contradicts the gate it
exists to serve is worse than none, and hand-editing the file against its own
criterion would have been worse still.

**Alternatives rejected.**

- *Accept the pool-share pick* (`cows_from_day_8`): internally consistent, but
  it designates a strategy the gate rejected over one that beat the incumbent
  every game; the two have never played each other.
- *Leave `rival_aware` designated*: the gate said it lost 16/16. Keeping a
  beaten champion as the bar makes the next experiment easier, which is the
  wrong direction.
- *Fix the pool instead* (harder anchors: the vendored `lonespear`, #204's
  ghost bench): the right longer-term move and the subject of #152, but a pool
  decision in its own right, and the file had to say something true today. A
  pool that resolves wins again may earn pool share back; the ranking stays
  computable and is not deleted.

**What this costs.** Designations before this date (`dense_farm`, #215,
2026-09-05; `rival_aware`, #222, 2026-09-06) were by pool share; the artifact's
`criterion` field says which rule produced it. `--designate` and
`harness.rounds` are now read-only against a succession artifact.

**Convention going forward.** A PROMOTE designates through
`python -m harness.promotion --succeed <challenger> --issue N --pr N --wins W
--games G --ties T --seeds A-B --date YYYY-MM-DD`, in its own issue (as #241
was), so the decision is deliberate and not a side effect of the experiment's
PR. Both roles go to the challenger; a benchmark is refused.

### 2026-09-07 — the gate gains a paired external limb (#152)

**What this corrects.** The criterion above had two limbs: the champion bar and
the ≥ 90% floor against each `DEFAULT_ANCHOR`. Since #219 every contender has
cleared the floor 16/16, so it no longer separates contenders. A third limb is
added; the two existing ones are unchanged.

**The limb.** For each external anchor in `harness.external_pool.EXTERNAL_ANCHORS`
(cite the code, not a copy: the tuple is the authority and changing it is a
dated amendment here), the contender and the champion are both played on the
declared seeds in the same run, sides alternated by list position, and the
contender's win count must be **at least the champion's**. Ties are not wins on
either side. A pair not played on the same seeds is an error, not a verdict
(`harness.rival_bench.criterion`, `paired_external_rows`, passed to `criterion`
as the keyword-only `external_pairs=`). Paired non-regression was chosen over a
fixed bar because the champion loses to these anchors 0/2 today: a fixed 90%
could never be met, and "recorded, not gated" would keep the field out of the
verdict — which is what the limb exists to change.

**Reproducibility.** The anchors are not committed (ADR-0008 amendment of this
date); they are pinned by sha256 in `harness/external_agents.json`, and the gate
refuses to load an anchor that is missing, unpinned or mismatched.

**Cost.** Five anchors × 16 seeds × two strategies = 160 games per gate run, on
top of the 112 the first two limbs cost.

### 2026-09-15 — the paired external limb gains a floor (#291, PR #298)

**What this corrects.** The limb of 2026-09-07 reads "the contender's win count
must be at least the champion's" on the same seeds. On #291 that rejected a
contender that beat the champion 12/16, held every anchor, and was up or level
on four of the five externals — because against `lonespear` the champion won
one game of sixteen and the contender none. At a base rate of one in sixteen,
a pair of (0, 1) is a coin flip; the limb was written to catch a contender
buying its champion-row wins by giving up games against the strong externals,
and it cannot tell that from a coin.

**The rule.** A paired external limb regresses when the contender wins fewer
games than the champion on the same seeds, **unless the champion is at the
floor and the gap is one game**. The floor and the test are the code:
`harness.rival_bench.PAIRED_FLOOR_WINS` and `harness.rival_bench.regressed`
(cite them; do not copy the value here). Two games short of a champion at the
floor, or one game short of a champion above it, is still a regression — (15,
16) against an anchor the champion sweeps is exactly the case the limb exists
for.

**Alternatives rejected.**
- *Leave the limb as written.* It calls a coin a regression whenever a strong
  external is near zero for both sides, which is most of the strong externals
  most of the time; #291 was rejected on it with the rest of the gate clean.
- *One game of slack on every pair.* Would let a contender give up a game
  against `madhur` at 16/16 unnoticed — the case the limb was added for.
- *A significance test per pair.* Sixteen seeds cannot power one; it would
  pass everything or nothing.

**What it does not do.** It does not re-read #291: that run was declared and
rejected under the rule of the day and stays rejected. A contender wanting the
amended rule is declared again on fresh seeds.

### 2026-09-16 — identical play is not a measurement (#302, PR #304)

**What this corrects.** The champion limb reads "≥ 60% of the declared seeds,
ties are not wins". That was written for ties at nearly equal reward, where
the sign is noise. It also counts a game in which the contender made the
champion's every move — a contender whose one changed decision never fired on
that seed's draw. Such a game is the champion playing itself; it measures
nothing about the change, and a limb that counts it as a loss can never
promote a contender that acts on a minority of draws. #225 (`cows_from_day_8`,
3/16 with 12 ties) and #302 (`town_herd`, 6/16 with 7 ties) both ran into
it; on #302 the change fired on 4 of 16 seeds, and the other 12 were the
champion's own action stream to the step. Worse, five of those twelve were
scored as wins and losses of 2–119 reward: the two seats' farms are not
symmetric, so identical play does not even guarantee a tie. The row read
6/16; the measurement was 2 of 4.

**The rule.** For each seed on the champion row the champion is also played
against itself, and a game in which the contender's action stream in its
seat equals the champion's own in that seat is **identical play**: it leaves
the denominator. The 60% bar applies over the *decided* games, and fewer
than `MIN_DECIDED` decided games is **VOID** — an under-powered run, not a
verdict; the bench extends its seeds and runs again. The count, the floor and
the test are the code: `harness.rival_bench.identical_games`,
`harness.rival_bench.MIN_DECIDED` and `criterion(..., identical=)` (cite
them; do not copy the value here). The anchor rows and the paired external
limb are unchanged: there the contender plays whoever it plays, and a tie is
still not a win. A bench that does not pass `identical=` gets exactly the
verdict it got before this amendment.

**Alternatives rejected.**
- *Leave the limb as written.* Any contender whose change is conditioned on
  a draw the champion does not read — the town's shops, the rival's herd — is
  rejected by construction at ≤ 40%, and #302 shows the counted "wins" and
  "losses" on identical play are seat asymmetry, not evidence.
- *Count a tie as half a win.* Still counts the champion's own game as
  evidence about the contender, and says nothing about the near-ties.
- *Pick seeds whose draw makes the change fire.* The draw depends on both
  boards (the end-of-day RNG is consumed by the weed roll), so it is only
  known by playing the contender — running the experiment to choose its own
  sample.
- *Lower the bar.* A lower bar over a denominator padded with the champion's
  own games is a weaker test, not a fairer one.

**What it does not do.** It does not re-read #302: that run was declared and
rejected under the rule of its day and stays rejected; its reading on the
issue records what the amended count would have said. A contender wanting
the amended rule is declared again on fresh seeds, with enough of them that
the decided count can reach the floor.

### 2026-09-17 — correction to the amendment of 2026-09-16 (#305, PR #307)

**What this corrects.** The amendment says an identical-play game "leaves
the denominator". The code behind it did exactly that and no more: it
subtracted the identical count from the games but read the wins from
`head_to_head_rate`, which had already scored those games. The champion's
self-play scores its two seats differently, so an identical game in seat 0
is a "win" and in seat 1 a "loss"; on #305 the first verdict line read 18
wins over 16 decided games. The amendment's own text explains why those
wins are not wins; the code did not follow it.

**The rule, restated.** An identical-play game leaves **both** counts: it
is neither a win, a tie nor a loss, and it is not a game. The champion row
is read by `harness.rival_bench.decided_row`, which plays each seed once
against the champion and once as the champion against itself, and counts
wins, ties and losses on the decided games only; `identical_games` is its
identical count. `criterion(..., identical=)` is unchanged and now receives
a numerator that agrees with its denominator. A bench that reads the
champion row with `head_to_head_rate` and passes `identical=` separately is
wrong by construction and must use `decided_row`.

**What it does not do.** It does not change the rule of 2026-09-16, the
floor, the anchor rows or the external limb. #305's run stands: its games
are deterministic and its row is re-read with `decided_row` on the same
seeds; the anchor and external rows of that run are unaffected.

### 2026-09-19 — the external anchor set shrinks to three (#317)

**What this corrects.** The 2026-09-07 amendment declared
`harness.external_pool.EXTERNAL_ANCHORS` as a five-name tuple. Two of those
five, `pilkwang_structured_economic_policy` and `premaananda108_ecobot_v7`,
leave it: neither can be fetched from source any longer (ADR-0008's
2026-09-18 finding has the detail), and #152's own rule is that every pool
member is pinned in the manifest before the gate will load it — an anchor
that cannot be pinned cannot be an anchor. `EXTERNAL_ANCHORS` (cite the code,
not a copy) is now a three-name tuple.

**The cost, undiluted.** Of the five agents #152 recorded as beating
`third_herder` on seeds 700-701, this drops the strongest — our reward share
0.197 against `pilkwang` — and the third — 0.411 against `premaananda108` —
keeping only 0.362, 0.475 and 0.488. The limb is easier: two of the field's
harder opponents are gone from it, not because they were re-measured as
weak, but because they can no longer be run at all. Paired external rows
recorded before 2026-09-19 are not comparable with rows recorded after it —
they were measured against a five-anchor limb that no longer exists.

**The partial mitigation, as mitigation and not excuse.** `pilkwang` is a
ten-tape route-portfolio replayer (#316): part of that 0.197 "hardest
anchor" reading was the difficulty of a canned route, not of a policy. Its
departure removes a benchmark whose strength was partly an artifact of what
it was, not just how well it played.

**What it does not do.** It does not replace the dropped anchors. Choosing
new ones — from the widened #295 pool or elsewhere — is a measured decision
in its own right and gets its own dated amendment here, not a side effect of
this one.

### 2026-09-20 — the paired external limb is judged as a whole (#326, PR #328)

**What this corrects.** The limb of 2026-09-07, with its floor of
2026-09-15, rejects a contender that wins one game fewer than the champion
against any external above the floor, whatever it does against the others.
Three contenders this month were rejected on exactly one such game with the
rest of the gate clean: #291 (`lonespear` 0 vs 1, before the floor), #324
(`madhur` 15 vs 16, `lonespear` 8 vs 1) and #326 (`shashank` 14 vs 15,
`lonespear` 10 vs 4, `madhur` level). Over #324 and #326 together the same
contender was thirteen games up on `lonespear` and one down on each of the
other two. At sixteen games a change with no effect at all on a swept
external loses one game to it about half the time, and with three pairs a
neutral contender fails at least one pair by a coin more often than not.
The 2026-09-15 amendment kept the top-of-table case on purpose; the limb
cannot tell that case from a coin, and it has now cost the line with the
largest external gain of the season twice.

**The rule.** The pairs are judged together. A pair short by more than
`PAIRED_MAX_SHORTFALL` games still fails the limb on its own — a contender
that trades games away wholesale against one strong farm is still caught.
Otherwise the contender's wins over all the pairs must be at least the
champion's, a floor pair's single game (the 2026-09-15 coin) counting
nothing either way; a pooled shortfall fails as `external:net`. The
constant, the pooling and the record are the code:
`harness.rival_bench.PAIRED_MAX_SHORTFALL`, `external_failing`,
`external_net` (cite them; do not copy the value here); the verdict carries
`external_net` and the formatter prints each pair as ok, short or REGRESSED
and a last pooled line. `regressed` keeps its meaning (a pair is short) and
its floor.

**Alternatives rejected.**
- *Leave the limb as written.* It rejects half of all neutral contenders
  on a coin and has no way to credit a gain on one external against a loss
  on another; the guard it keeps at the top is one it cannot actually
  exercise at sixteen games.
- *One game of slack on every pair.* Lets a contender give up one game to
  each of three externals unnoticed; the pooled rule fails that (net −3).
- *A significance test per pair.* Sixteen seeds cannot power one.
- *More seeds per external.* Thirty-two per pair would halve the coin's
  odds, not remove them, at twice the run's cost.

**What it does not do.** It does not re-read #324 or #326: both were
declared and rejected under the rule of their day and stay rejected. A
contender wanting the amended rule is declared again on fresh seeds.

### 2026-09-21 — seeds may be screened by the champion's own play (#337)

**What this corrects.** The amendment of 2026-09-16 rejected *picking seeds
whose draw makes the change fire*, because the draw depends on both boards
and is only known by playing the contender — running the experiment to
choose its own sample. That holds for a change conditioned on state the
contender has already shaped. It does not hold for a change conditioned on
state fixed **before the contender's first divergence**: the town's shops at
day 9 are drawn at the end of day 8 from boards the contender has not
touched, so the champion playing itself reads them exactly. Without a
screen such a change — the strawberry-dead town of #337, one seed in eight
on the ladder — cannot reach `MIN_DECIDED` on sixteen seeds; the
2026-09-16 rule excludes the identical games and then voids the run for
having too few left. Extending the seeds until the floor is met costs about
a hundred and thirty seeds per run, most of them the champion playing
itself.

**The rule.** A bench may declare its seeds as *the first N seeds at or
above a declared start whose champion self-play satisfies a declared
condition*, when all of the following hold and are declared before code:

- the condition is read from the champion's own self-play, never from a
  contender game;
- the condition is fixed at a declared day, and the contender's first
  divergence from the champion's own action stream in its seat is at or
  after that day — a **mechanism control** on a screened seed proves it
  (`harness.sixteend_bench.first_divergence`), and a **live control** on a
  seed the screen rejects proves the change does not fire there
  (`harness.rival_bench.seat_actions` equal to the champion's own);
- the scan is in seed order from the declared start and recorded on the
  issue (the seeds read and the seeds kept) before the criterion runs;
- the condition's rate on the ladder is recorded with the verdict, so a
  win rate over screened seeds is read as a win rate in that share of
  games, never as a ladder rate.

The champion row, the anchor rows and the paired external limb all run on
the screened seeds; the identical-play rule of 2026-09-16 still applies to
the champion row. A bench that declares no screen is unchanged.

**Alternatives rejected.**
- *Extend the seeds until the floor is met.* The 2026-09-16 rule as
  written. A hundred-odd seeds a run, nearly all identical play, to measure
  the same sixteen games the screen finds directly; and the anchor and
  external limbs then run on the padding too.
- *Screen by contender play.* The rejection of 2026-09-16 stands: a screen
  that reads the contender's own game chooses the sample by the outcome.
- *Lower `MIN_DECIDED` for conditional contenders.* Fewer decided games is
  a weaker test; the screen gives the same sixteen decided games the rule
  already asks for.
- *Judge only the champion row on screened seeds and the other limbs on
  plain seeds.* Two seed sets in one run, with the external pairs no longer
  on the same seeds as the champion row; and a change that fires only in
  dead towns is only ever tested against the field in dead towns.

**What it does not do.** It does not admit a condition the contender can
influence — a seed screened on the day-12 town is admissible only if the
contender's first divergence is at or after day 12, which the mechanism
control checks. It does not read a screened win rate as a ladder rate. It
does not re-read #302: that run stays rejected.
