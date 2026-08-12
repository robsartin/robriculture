# Design: meta_rancher — tuned top-Elo-comp contender

**Date:** 2026-08-12
**Issue:** #61 (`experiment`). Piece 2 of the benchmark-realism initiative (#59, merged).
**Status:** approved (brainstorming), pending implementation plan.

## Motivation

#59 shipped two things: a readonly-benchmark mechanism and `meta_bot`, a *frozen*
agent built to the observed top-Elo Kaggriculture comp (9 cow + 4 sheep + land NE/SW
+ free-`COLLECT_FERTILIZER` byproduct + a melon/wheat crew). `meta_bot` already
outscores our own champions in self-play (~59k vs starter ~3.5k) — but it is a
benchmark opponent, deliberately not a contender, and it can never be submitted or
promoted.

The session's headline lesson: **self-play win-rate does not predict the ladder.**
Self-play crowned `market_farmer` (public 474.0) over the `ranch_hands` (530.7) it
replaced. So the real question — *does building to the field's modal winning comp
score better on the ladder?* — can only be answered by putting a meta-comp
**contender** on the ladder. That contender is `meta_rancher`.

## What it is

`strategies/meta_rancher.py`, a `Strategy` subclass with `name = "meta_rancher"` and
`benchmark = False` (a champion contender). It is the **tunable sibling** of the
frozen `meta_bot`: same winning composition, optimized to bank more and be
ladder-worthy.

### Code relationship — standalone, meta_bot untouched

`meta_bot` is frozen by a seeded behavior-pin test (#59). Refactoring shared helpers
*out* of it would change its behavior and break that pin. Therefore `meta_rancher`:

- is its own file and does **not** import `meta_bot`'s internals;
- reuses the same *stable shared primitives* `meta_bot` uses — from
  `strategies/ranch_hands.py` (livestock feed/care/harvest loop, `_sell_orders_keep_feed`,
  buffers), `strategies/hired_hands.py` (`step_toward`, `tile_at`, hiring plumbing,
  `TURNS_PER_DAY`), `strategies/fertilized_hands.py` (fertilizer helpers), and
  `kaggisim/` (economy, actions);
- **re-implements the meta-specific logic it wants to tune** (land purchase, pasture
  build, animal placement, labor routing, seed-restock).

This accepts a small amount of constant/structure duplication between `meta_bot` and
`meta_rancher`. That is deliberate and justified: the two artifacts have different
lifecycles — one is a frozen field snapshot, the other evolves — so coupling them
would be the wrong abstraction (and would jeopardize the freeze). We do **not**
refactor `meta_bot`.

## Tuning targets — the hypothesis

Bounded (YAGNI on open-ended optimization). Each is a measurable improvement over
`meta_bot`'s known weaknesses, kept in a pure, independently unit-tested helper:

1. **Eliminate the 2/13 late-game animal escapes.** `meta_bot` loses 2 of 13 animals
   near the buzzer to feed/care routing gaps. `meta_rancher` should keep the whole
   herd fed/cared through the final day (e.g., prioritize at-risk animals, size the
   livestock crew to reach all 13 pastures daily).
2. **Fix the `n_hire = MAX_HANDS` market-slot contention.** On heavy-sell mornings,
   forcing a full re-hire can consume market-order slots that should go to sells /
   land / animal buys (the 10-order cap truncates the tail). Order hiring so it never
   displaces a sell or a herd-critical buy.
3. **Extract + tune seed-restock.** The review flagged that `meta_bot`'s seed-restock
   logic lives inline in `act()` rather than a helper. `meta_rancher` extracts it into
   a pure `seed_restock_orders(...)` helper (unit-tested) and tunes the buffer sizing.
4. **Tune the melon-vs-livestock labor split.** `meta_bot` peels 5 hands off to
   livestock as land unlocks; revisit the split so melon income and herd upkeep are
   balanced for maximum bank.

`act()` stays thin (wire helpers + `market[:10]` clamp); sells lead the market list.

## Gate (ADR-0007)

A strategy experiment is promoted only if it beats the **designated champion**:
`meta_rancher` vs `market_farmer`, **200 seeded games**, promote iff win-rate ≥ 55%
AND binomial test rejects the 50% null at p < 0.05. Record N / win-rate / p on #61.

**Also report** (informative, not pass/fail):
- `meta_rancher` vs `meta_bot` (200 games) — does the tuned contender beat the frozen
  field-proxy? This is the most meaningful self-play signal (the field, not our bots).
- `meta_rancher` vs `ranch_hands` (200 games) — vs our actual ladder leader (530.7).

No champion re-designation: a self-play re-designation would likely just re-crown the
misleading pick (`market_farmer`), at hours of compute. Gating vs the current champion
and reporting vs the two references is more informative and honest.

## Testing

TDD throughout: pure-helper units for each tuning target (they test without a 720-turn
game); the no-crash gate covers `meta_rancher` through full games under
`ROBRICULTURE_STRICT=1`. Full CI gate: line ≥ 85%, branch ≥ 65%.

## After the gate

If it passes: PR to `main`, reviewed (not auto-merged). Then **Rob submits**
`meta_rancher` to the ladder (his Kaggle creds; `scripts/submit.py meta_rancher`) — the
only real proof. It becomes a latest-2 active submission; the scheduled ladder-check
watches whether it climbs past `ranch_hands`' 530.7. If it does, the meta-matching bet
is validated on the real field; if not, the ladder result (recorded on #61) tells us
where the self-play/ladder gap actually is.

## Out of scope (YAGNI)

- Sharing or refactoring `meta_bot`'s frozen code.
- Champion re-designation.
- Unbounded optimization beyond the four targets above.
- Vendoring competitor agents (a separate, later, license-gated effort).
