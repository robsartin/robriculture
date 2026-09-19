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
- **Pool composition must be weighted, not merely diverse (#70, 2026-08-14).** The
  first implementation averaged all opponents equally, so a population sample and
  Hall-of-Fame that were half the pool supplied all the gradient — and saturated,
  pinning fitness at 0.5833 while the agent lost to every real anchor. Fitness is
  now an anchor-dominant blend of shaped score shares. Win/loss alone gives no
  gradient below the finish line.
- **The pool has never contained a genuinely external agent (#78, 2026-08-18).**
  The Decision above describes the pool as including "real external competitor
  agents vendored as readonly benchmark opponents." That was wrong when written
  and has been wrong since #59: `strategies/meta_bot.py`'s own docstring says it
  is "hard-coded to the field's top-Elo comp" — **our reconstruction** of a
  composition observed in the field, written by us. It is not vendored
  third-party code. So the anchor pool has contained zero external agents from
  the start; phase 3 was never begun, not merely incomplete.
- **Phase 3 as specified is not happening (#78, 2026-08-18).** The repo owner has
  decided against vendoring external agents into this repo at all, on licensing
  grounds — see the #67 survey. Real competitor agents will live in a gitignored
  local directory, outside the repo, and be used for **measurement only**: never
  as promotion gates, designation opponents, or evolution anchors. Fitness will
  therefore keep being measured against our own bots, for the foreseeable future.
  This is a correction of the Decision, not a status update on a pending task —
  there is no plan to resume vendoring.
- **`spoiler` removed from `DEFAULT_ANCHORS` (#78, 2026-08-18).** By its own
  docstring, `spoiler` is "a test opponent, not a contender" — a melon-market
  flooder built to stress one specific weakness. Its pool share (0.3348) sat well
  below the 0.47–0.63 field and it was the only anchor the evolved neuropilot
  ever beat (#70), making it the pool's free win rather than a fair bar. It
  remains a registered strategy, available as an explicit opponent, but no
  longer votes on fitness.
- **The remaining pool is narrower than "five agents" suggests (#78, 2026-08-18).**
  Of the five default anchors (`meta_bot`, `ranch_hands`, `market_farmer`,
  `ranch_adaptive`, `wheat_hands`), three — `ranch_hands`, `ranch_adaptive`, and
  `wheat_hands` — are near-duplicate forks of one lineage. The pool has fewer
  independent voices than its count implies, on top of being entirely
  self-authored (see above).
- **Pinned externals may be gate anchors, ranking opponents and opt-in evolution
  anchors (#152, 2026-09-07).** This corrects the #78 amendment's "measurement
  only" rule. Three things changed after it: every contender since #219 beat all
  six `DEFAULT_ANCHORS` 16/16, so the frozen bar stopped separating a better agent
  from a worse one (and pool share against it crowned a gate-REJECTED contender,
  #241); twenty licence-checked externals sat in the manifest, five of which beat
  the champion `third_herder` on both of seeds 700-701 (our reward share:
  `pilkwang_structured_economic_policy` 0.197, `lonespear_kaggriculture_v21`
  0.362, `premaananda108_ecobot_v7` 0.411,
  `shashankjangid_agent_v1000_sovereign_prime` 0.475,
  `madhur_sabherwal_hub_geometry_agent` 0.488; the other fifteen lost 2/2 at
  0.60-1.00); and `harness/evolve.py --include-external` had been putting externals
  in the fitness anchor list all along, contradicting the rule. The
  reproducibility objection is answered by a pin, not a vendoring: every manifest
  entry now carries the sha256 of the fetched file, a `github_file` entry's `ref`
  is the commit fetched, the fetch refuses a mismatch, `resolve_opponents` raises
  on one, and the gate loads only anchors that verify
  (`harness.external_pool.external_anchor_agents`). What stands from #78: no
  third-party code is committed, `scripts/submit.py` never packages one, and an
  external is never the gate opponent (ours by succession, #241). The gate's
  external limb and its declared set (`harness.external_pool.EXTERNAL_ANCHORS`)
  are ADR-0007's amendment of the same date. Rejected: keeping #78 and fixing the
  code (leaves the gate blind to the field; the ghost bench has the same
  gitignored-data problem and cannot react); vendoring after all (re-litigates a
  licensing decision a pin makes unnecessary). Cost: a gate run needs
  `external_agents/` fetched and verified on the machine that runs it; CI does
  not run the gate and never did. The 2026-09-07 pin run also found
  `adilshamim8_kaggriculture_grandmaster_starter` (a Kaggle kernel taken by the
  2026-09-06 re-survey, #229) returning a permanent 404; it was removed from the
  manifest, since an entry nobody can fetch breaks the manifest's own contract,
  leaving nineteen entries, all pinned. `--pin` resolved every GitHub branch ref
  to the commit fetched on 2026-09-07; `naisha123_kaggriculture_agent` had moved
  upstream since its 2026-09-06 fetch, so its pinned bytes differ from the ones
  #229 measured, and it is not an anchor.

- **The manifest holds twenty-three pinned entries, and a pin detects drift
  without preserving the source (#295, #317, 2026-09-18).** The 2026-09-15
  re-survey (#67) confirmed four vendorable agents genuinely new to the
  manifest once deduplicated against the manifest itself rather than the
  issue's own prose (#296); PR #318 added them, fetched and pinned with no
  substitution, and recorded `ten_melon` 4-0-0 against each on seeds
  1320-1323 (the first full-episode evidence any of them survives 720
  turns). The entries, their sources, licences and pins are the manifest
  (`harness/external_agents.json`), and each entry's reasoning is a named
  test, not this prose. `EXTERNAL_ANCHORS` is untouched: these are
  measurement opponents, and an anchor is a measured decision plus a dated
  ADR-0007 amendment. Two findings landed with the widening and are
  recorded here as findings, not decisions. First (#317): three of the
  nineteen earlier entries can no longer be rebuilt from their source -- one
  Kaggle kernel deleted, one restructured so no agent cell remains, one
  republished with different bytes, which the pin correctly refused. Two of
  the three are ADR-0007 gate anchors (`pilkwang_structured_economic_policy`,
  `premaananda108_ecobot_v7`), so the gate's external limb runs today from
  files cached on one machine and cannot be rebuilt from a clean clone;
  `resolve_opponents(include_external=True)` already raises the #153
  shortfall on the third. The 2026-09-07 premise above -- reproducibility by
  pin -- gave detection, which worked, but not durability; every external
  row recorded since 2026-09-07 was measured against files that cannot now
  be re-obtained. Second (#316): `pilkwang` is a ten-tape route replayer
  wrapped in a repair controller, the archetype the pool's own triage now
  rejects (#297), and the pool's strongest entry. Neither finding changes a
  recorded verdict; what to do about durability (#317) and about `pilkwang`
  (#316) are open, and each will be a dated amendment here and, if it
  touches the gate's set, in ADR-0007.

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
