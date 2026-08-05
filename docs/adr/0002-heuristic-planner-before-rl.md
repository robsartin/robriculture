# ADR-0002: Heuristic + planner before reinforcement learning

- **Status:** Accepted
- **Date:** 2026-08-04
- **Deciders:** Rob

## Context

Kaggriculture is a 1v1 turn-based farming-economy simulation. Winning is decided
by most coins after 720 turns, and — critically — the ladder rating depends only
on win/loss/tie, **not** the coin margin. Underneath, the game is largely an
operations-research problem: schedule labor, route the farmer and hired hands,
time sales against a demand-driven price curve, and make long-horizon capital
bets (land, animals). The dynamics are mostly deterministic; the main randomness
is weed spawning and the order of town-shop unlocks. A full game simulates in
~2s locally, and there is no network access during evaluation (any learned
artifact must be bundled into a ≤100 MiB submission).

## Decision

Build in this order:

1. **Heuristic economic engine** — ROI-per-tile-per-day model, survival-first
   (water/feed before anything), demand-aware selling.
2. **Short-horizon planner** on top — forward-simulate a few days; solve the
   daily labor/route assignment and the market-timing sub-problem by rollout.
3. **Reinforcement learning (self-play)** — held in reserve, pursued only if we
   plateau outside the top 10.

## Consequences

- Fast path to a real ladder score (week 1) and a reproducible baseline the
  prize writeup requires.
- Because margin is irrelevant, we optimize for *robust, consistent* wins rather
  than maximum expected coins — favoring lower-variance policies.
- RL infrastructure (self-play loop, training compute) is deferred, so if we do
  need it later there's ramp-up cost. Accepted given the 8-week window.
- Economic constants in `kaggisim/economy.py` are transcribed from the spec and
  must be validated against the installed sim source before heavy tuning.

## Alternatives considered

- **RL from the start.** Higher potential ceiling, but slow to first score,
  expensive, and risky in 8 weeks for a long-horizon (720-step) structured
  action space.
- **Pure greedy, no planning.** Simple, but leaves the main edge (multi-day
  scheduling and market timing) on the table.
