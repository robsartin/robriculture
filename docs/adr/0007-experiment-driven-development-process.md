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
