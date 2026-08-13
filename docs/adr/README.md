# Architecture Decision Records

This directory holds ADRs — short, immutable records of significant architecture
decisions, capturing the context and the *why* at the time the decision was made.

We use the lightweight [Michael Nygard format](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions).

## Conventions

- One file per decision: `NNNN-short-title.md`, numbered sequentially.
- Status is one of: `Proposed`, `Accepted`, `Deprecated`, `Superseded by ADR-XXXX`.
- ADRs are **append-only**: don't rewrite an old decision. If it changes, write a
  new ADR that supersedes it and update the old one's status line.
- Copy `0000-template.md` to start a new one.

## Index

| # | Title | Status |
|---|-------|--------|
| [0001](0001-record-architecture-decisions.md) | Record architecture decisions | Accepted |
| [0002](0002-heuristic-planner-before-rl.md) | Heuristic + planner before RL | Accepted |
| [0003](0003-multi-strategy-portfolio.md) | Multi-strategy portfolio with a build step | Accepted |
| [0004](0004-python-only-agent.md) | Python-only agent | Accepted |
| [0005](0005-cc-by-4.0-and-open-development.md) | CC-BY 4.0 and open development | Accepted |
| [0006](0006-fail-safe-never-crash.md) | Fail safe, never crash | Accepted |
| [0007](0007-experiment-driven-development-process.md) | Experiment-driven development process | Accepted |
| [0008](0008-neuroevolution-against-a-diverse-pool.md) | Neuroevolution of an NN-guided controller vs a diverse pool | Accepted |
