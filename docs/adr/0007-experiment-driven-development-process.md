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
