# ADR-0008: Neuroevolution of an NN-guided controller against a diverse opponent pool

- **Status:** Accepted
- **Date:** 2026-08-12
- **Deciders:** Rob

## Context

[[ADR-0002]] built heuristics first and held reinforcement learning "in reserve,
pursued only if we plateau outside the top 10." That condition has been reached:
after a heuristic portfolio and an overnight promotion loop, our best public score
sits around 520–535 against a field top of ~3190, at rank ~2874 / 4134.

Two findings this session forced the pivot:

1. **Self-play against our own bots is a broken fitness signal.** `market_farmer`
   wins 100% of local self-play yet is our *worst* live bot (public ~482), while
   `ranch_hands` — our best *ladder* bot (~522) — loses to `market_farmer` 2.5% in
   self-play. Optimizing against one self-play champion (the ADR-0007 promotion
   gate) rewards the wrong thing; it cannot predict the ladder.
2. **Hand-tuning is fragile.** Manually tuning the meta-composition contender
   (`meta_rancher`, #61) made it measurably *weaker* — each local "improvement"
   traded away the bank that wins.

The ladder is the only ground truth, but it costs submissions. We need a *local*
fitness signal that actually correlates with the ladder, and a search that finds
good policies without brittle hand-tuning.

## Decision

Pursue **neuroevolution of an NN-guided controller, with fitness measured by
competition against a deliberately diverse opponent pool.**

- **Agent:** a small **pure-Python** MLP (stdlib only, per [[ADR-0004]]; its flat
  weight vector is the genome) reads a fixed feature vector and emits continuous
  policy knobs; a **fresh, self-contained controller** turns knobs + game rules
  into legal actions (under the [[ADR-0006]] fail-safe). The controller is
  independent of our existing heuristic strategies — it uses only low-level sim
  primitives — so evolution has genuine control over the policy.
- **Optimizer:** a population of weight-variants, evaluated by round-robin
  tournament win-rate against the pool; select survivors; mutate/recombine; repeat.
- **The diverse pool** — our own bots + prior survivors + **real external
  competitor agents** vendored as readonly benchmark opponents (the #59
  `benchmark=True` mechanism; license-gated, attributed). Robustness against a
  varied field is a far better ladder proxy than beating one self-play champion.

Built in four phases: (1) the NN-guided agent architecture; (2) the neuroevolution
harness; (3) the diverse external-opponent pool; (4) submission integration.

## Consequences

- Directly attacks the broken-signal problem: fitness = robustness vs a diverse
  field, not vs one self-play specialist.
- Replaces fragile hand-tuning with automated search; removes the human from the
  inner tuning loop.
- Compute cost rises sharply (population × pairings × games/generation). Games are
  ~2s, so this is feasible but must be scoped (population/generation caps, seeds).
- New infrastructure (genome encoding, evolution loop, opponent-vendoring) that
  must stay reproducible ([[ADR-0005]]) and stdlib-only in the submitted artifact
  ([[ADR-0004]] — hence a pure-Python MLP, not numpy).
- The existing heuristic portfolio is **not** discarded: those bots remain
  submission candidates and become opponents/seeds in the evolution pool.
- Vendoring external agents carries licensing obligations — only agents whose
  license clearly permits reuse, each attributed (consistent with [[ADR-0005]]'s
  open-development stance).

## Alternatives considered

- **Keep hand-tuning heuristics.** Rejected: demonstrably fragile this session, and
  bounded by the human's inner-loop bandwidth.
- **End-to-end neural policy** (network emits every worker + market action).
  Rejected for now: the structured, legality-constrained, variable-cardinality
  action space makes it very hard to evolve; the NN-guided controller guarantees
  legal play and is tractable.
- **Gradient-based RL (PPO/self-play).** Deferred: heavier framework, and the
  "random variants competing, survivors advance" formulation maps cleanly onto
  neuroevolution without a training stack.
- **Fix the self-play gate only** (gate vs `meta_bot`/`ranch_hands` instead of the
  champion). A cheaper patch, but it still optimizes against a handful of *our*
  bots; the diverse external pool is the more durable fix.
