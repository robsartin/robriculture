# ADR-0006: Fail safe, never crash — defensive wrapper and a no-crash gate

- **Status:** Accepted
- **Date:** 2026-08-04
- **Deciders:** Rob

## Context

On the ladder, an agent that raises an unhandled exception during an episode
**forfeits that episode** — a crash is an automatic loss, and a submission whose
validation episode errors never joins the matchmaking pool at all. Because rating
depends only on win/loss/tie (see [ADR-0002](0002-heuristic-planner-before-rl.md)),
a single crash is as costly as a decisive strategic defeat and far cheaper to
avoid. We run five genuinely different strategies
([ADR-0003](0003-multi-strategy-portfolio.md)) over a 720-turn game with no
network and no chance to intervene mid-episode, so robustness has to be
structural rather than hoped-for.

## Decision

Treat "never crash the episode" as a first-class architectural constraint:

- **Defensive wrapper.** Every strategy runs behind a `try/except` that degrades
  any unexpected error to a safe no-op turn (`{"farmer": ["PASS"], ...}`) instead
  of propagating. This lives in both `kaggisim.strategy.make_agent` (harness path)
  and the generated `main.py` shim (`build/package.py`, submission path), so the
  guarantee holds identically locally and at evaluation.
- **A visible-bugs escape hatch.** During development, `ROBRICULTURE_STRICT=1`
  lets exceptions propagate so defects surface loudly rather than hiding behind a
  silent PASS. The safety net is for the ladder, not for masking bugs in dev.
- **A no-crash gate.** `tests/test_no_crash.py` is a required, always-green
  regression guard, and `build/package.py` re-runs the packaged agent in a
  subprocess for one short game as a post-build smoke test. A green gate is a
  precondition for any submission.

## Consequences

- A logic bug costs at most one wasted *turn* (a PASS), never a whole episode;
  the worst realistic outcome of an unforeseen edge case is a slightly weaker
  game, not a forfeit.
- The PASS fallback can mask a strategy that is quietly failing every turn — it
  would lose on merit while looking "healthy". Mitigations: the strict-mode
  toggle in development, and the local tournament as a truth signal (a strategy
  PASSing its way to consistent losses shows up immediately in win rate).
- Every strategy inherits the same safety contract for free, and the shared shim
  keeps the local and submission execution paths identical — no "works in the
  harness, errors on submit" surprises.
- Small ongoing cost: the no-crash test and the build smoke test must stay green
  and be kept fast enough not to slow iteration.

## Alternatives considered

- **Let exceptions propagate (fail loud everywhere).** Correct for a service you
  can redeploy; wrong here, where a crash is an unrecoverable in-game forfeit and
  there is no operator in the loop.
- **Per-strategy error handling.** Rejected: easy to forget in one of five
  strategies, and the one that's forgotten is the one that crashes on the ladder.
  A single choke point in the wrapper is both simpler and safer.
- **A validating router that pre-checks each action before returning it.** More
  defensive still, but it adds code — and therefore crash surface — on the hottest
  path; deferred unless we observe actions being rejected by the simulator.
