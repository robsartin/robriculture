# ADR-0003: Multi-strategy portfolio with a build step

- **Status:** Accepted
- **Date:** 2026-08-04
- **Deciders:** Rob

## Context

Iterating on a single agent risks hill-climbing into a local optimum. We want to
explore genuinely different strategic philosophies (greedy ROI, rollout planner,
capital rush, market timing, plus a lean robust baseline) and select empirically.
Two facts shape how: (1) local games are cheap (~2s), so an internal tournament
can be our fitness signal; (2) on the real ladder **only the latest 2 submissions
are active**, so we cannot run many philosophies live at once.

## Decision

- A shared library (`kaggisim/`) plus swappable strategy modules (`strategies/`)
  behind one interface: `Strategy.act(state) -> action_dict`. Same signature makes
  strategies both submittable and able to fight each other in the harness.
- A local round-robin harness (`harness/tournament.py`) is the primary selection
  mechanism; the 2 ladder slots are reserved for validating top contenders.
- A build step (`build/package.py`) packages any one strategy into a
  self-contained `submission.tar.gz` (main.py shim + `kaggisim` + `strategies`),
  with a post-build smoke test.
- Ladder discipline: treat the 2 live slots as **champion + challenger**; promote
  only when local *and* ladder evidence agree. Remember "latest 2" is by
  recency, so a third submission drops the oldest live agent.

## Consequences

- Diverge in development, converge to 2 at submission — exploration is unbounded
  and cheap; ladder time is spent deliberately.
- Some overhead maintaining several strategies and the registry, and the shared
  lib must stay dependency-light so it bundles cleanly under the 100 MiB / no-
  network constraints.
- A single submission *could* later become a router that selects a strategy from
  early-game signals; deferred because it adds crash surface (a crash is an auto-
  loss).

## Alternatives considered

- **One agent, iterated.** Simpler, but prone to local optima and gives no
  portfolio for the champion/challenger scheme.
- **Many agents live simultaneously.** Impossible: only the latest 2 count.
