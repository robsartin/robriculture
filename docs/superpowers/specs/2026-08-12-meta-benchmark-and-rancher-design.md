# Design: benchmark realism + a meta-matching rancher

**Date:** 2026-08-12
**Issues:** #59 (Piece 1, infra) — Piece 2 issue opened when Piece 1 merges.
**Status:** approved (brainstorming), pending implementation plan.

## Motivation

The 2026-08-12 ladder check and Kaggle recon exposed two linked problems.

1. **Our fitness signal doesn't predict the ladder.** The promotion gate plays only
   our own strategies against each other. `market_farmer` wins 100% of self-play yet
   is our worst live bot (public **474.0**, vs `ranch_hands` **530.7** and
   `ranch_adaptive` 520.6). A pool made only of our bots rewards agents that beat
   *us*, not the field. Experiment #53 was rejected partly for the same reason: its
   only sparring partner (`spoiler`) was too weak to discriminate.

2. **We are far from what actually wins.** Recon over the top-Elo band (3100+, 148
   winners) shows a clear modal winner:

   | Rank of comp | crops | animals | hands | land | share |
   |---|---|---|---|---|---|
   | 1 (x89) | WHEAT 1 | COW 9, SHEEP 4 | 10 | NE/NW/SW | **30%** |
   | 2 (x73) | WHEAT 2 | COW 9, SHEEP 5 | 9 | NE/NW/SW | |
   | 3 (x17) | — | COW 9, SHEEP 1 | 9 | NE/NW/SW | |

   Winners bank ~85k median. **Fertilizer is universal** (296/296 top farms, first
   day 2, ~5 orders each). Build order: fertilizer d2 → wheat d2 → milk d8 →
   melon d10 → strawberry d14. Meanwhile our champion line `ranch_hands` runs a
   **single** cow + **single** sheep (2 animals vs the field's 13) and uses **no**
   fertilizer. The two levers the data screams are **livestock scale** and
   **fertilizer** — exactly what our unshipped c94 prototype ("feed-first /
   fertilizer-split", ~169k smoke) encodes.

The work is split so each piece has one hypothesis and the right kind of validation
(ADR-0007). Piece 1 makes the gate honest; Piece 2 uses it.

## Piece 1 — readonly benchmark opponents (harness/infra)

**Validation:** engine/correctness → green tests, no promotion gate. Normal PR.

### Readonly-opponent mechanism

A `Strategy` subclass may set a class attribute `benchmark = True` (default `False`
on the base). Semantics:

- **Still auto-discovered** — dropping `strategies/<name>.py` registers it; we never
  edit `strategies/__init__.py` (repo convention).
- **Always an opponent** — benchmark bots are included in the tournament and as
  promotion sparring partners, so every agent is measured against them.
- **Never a champion** — `harness.promotion --designate` and any round-robin that
  writes `champion.json` **exclude** `benchmark` strategies from the candidate set.
  `champion.json` can never name a benchmark bot. A challenger may still be *gated
  against* a benchmark (as opponent), but a benchmark can never *be* the champion.

This is the "readonly" contract: a fixed external-style reference that shapes the
fitness landscape but is never something we ship.

### `meta_bot` — the first readonly opponent

A frozen agent hard-coded to the modal top-Elo winner: **9 COW + 4 SHEEP + 1 WHEAT
(feed) + 10 hands + FERTILIZER from day 2**, land NE/NW/SW. Authored entirely from
our recon data — no third-party code, no license entanglement for our CC-BY-4.0
repo. It is deliberately *not tuned* to beat anyone; it represents the field.

`meta_bot` reuses existing machinery where possible: the animal/feed state loop from
`ranch_hands`, the fertilizer action loop from `fertilized_hands`. New logic is kept
in pure module-level helpers (repo convention) so it unit-tests without a full game.

### Phase 0 — feasibility (first plan step)

Before building `meta_bot` to the comp, verify in our installed sim that the target
is legal and reachable: animal-tile capacity for 9 cows + 4 sheep, the hand cap
(vs the field's 10), and the fertilizer buy → carry → `FERTILIZE` / `COLLECT_FERTILIZER`
loop. If any element is infeasible, record the real reachable comp and build to that
(noting the delta from the observed meta).

### Frozen enforcement

A seeded **behavior-pin** test: `meta_bot`'s opening move plus a short seeded
action-trace hash to fixed golden values, so any edit to `meta_bot` breaks CI. This
delivers "can't be changed" without a brittle whole-file checksum. (Rejected
alternative: convention/comment only — too weak given the explicit "can't be
changed" requirement.)

### Harness changes

`harness/tournament.py` (opponent pool) and `harness/promotion.py`
(`round_robin_rank` / `designate_champion` candidate filter) learn to read the
`benchmark` flag. The no-crash gate already iterates all registered strategies, so
`meta_bot` is covered there for free. Tests assert: a benchmark bot appears as an
opponent, is excluded from designation, and `champion.json` never names it.

## Piece 2 — `meta_rancher` (strategy experiment)

**Validation:** "is it better?" → promotion gate (200 seeded games, ≥55% win, p<0.05)
vs the **designated champion**, plus reported results vs `meta_bot` and `ranch_hands`.
Opened as its own `experiment` issue once Piece 1 is merged.

**Hypothesis:** an agent matching the winning comp — `ranch_hands`' animal/feed
machinery **scaled to ~9 cow + 4 sheep**, **fertilizer from day 2**, minimal
wheat-as-feed — banks materially more than our current line, because milk ($160) and
wool ($200) scale with animals where crops crash fast (strawberry cliffs at 62
units). Built fresh in our two-file TDD style; c94's ~169k smoke is the *target*, not
the source (we do not import the 75k notebook `main.py`).

**Champion question to resolve in Piece 2:** the designated champion is
`market_farmer`, itself a live under-performer. Piece 2 will consider re-designating
against the improved pool (which now includes `meta_bot`) before gating, so
`meta_rancher` is measured against a champion chosen with realistic opponents.

**The real proof is the ladder,** not smoke or self-play. If `meta_rancher` passes
its gate, it becomes a submission candidate (latest-2 rule), and the scheduled
ladder-check watches whether it actually climbs past `ranch_hands`' 530.7.

## Explicitly out of scope (YAGNI)

- Vendoring real competitor agents from GitHub — deferred; added later only where a
  repo's license clearly permits, each with attribution.
- Whole-file checksum locking — the behavior-pin test is sufficient.
- Any change to the economy tables or sim — `meta_bot`/`meta_rancher` are pure
  strategy + harness work.
