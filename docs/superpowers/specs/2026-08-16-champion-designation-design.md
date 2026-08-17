# Re-designating the champion: pool share, and splitting gate opponent from submit default

- **Issue:** [#76](https://github.com/robsartin/robriculture/issues/76)
- **Date:** 2026-08-16
- **Status:** Approved (design)
- **Relates to:** ADR-0007 (the promotion gate), ADR-0008 (diverse pool), ADR-0003
  (latest-2 ladder slots), ADR-0005 (licensing of vendored agents)

## Context

`harness/champion.json` designates **`market_farmer`** as champion, on a perfect
160/160 local round-robin record. `market_farmer` scored **476.7** on the ladder —
the worst of all our heuristic submissions.

CLAUDE.md is explicit that "an experiment is measured against exactly that agent,"
and ADR-0007's promotion gate runs its 200 seeded games against the designated
champion. So the measuring stick for the entire experiment process has been
pointing at an agent ADR-0008 already documented as unrepresentative.

### Why win-rate produced this

Measured 2026-08-16 — mean score share against the anchor pool, self-matches
excluded, 2 games per pairing:

| candidate | pool share | head-to-head win-rate | ladder |
|---|---|---|---|
| **meta_bot** (external) | **0.6325** | — | — |
| meta_rancher | 0.6066 | — | 556.6 |
| ranch_hands | 0.5085 | 0.875 | 515.4 |
| market_farmer | 0.5082 | **1.000** | 476.7 |
| ranch_adaptive | 0.5070 | — | 520.6 |
| wheat_hands | 0.4906 | 0.625 | — |
| mixed_hands | 0.4781 | 0.500 | 501.8 |
| spoiler | 0.3348 | — | — |

`market_farmer`'s unbeaten record is **thin margins amplified by binary scoring**.
Its share is 0.5082 — within 0.0015 of `ranch_hands` (0.5085) and `ranch_adaptive`
(0.5070). Those three are indistinguishable, and win/loss scoring inflated a
razor-thin edge into 160/160. This is the same defect #70 found in the
neuroevolution fitness: discarding margin destroys the information that separates
agents.

`meta_rancher` and `meta_bot` both separate cleanly above the pack.

Spearman(share, ladder) is +0.50 over the five agents with ladder scores. With
n=5 that is weak and not significant on its own — quantifying it properly is
[#80](https://github.com/robsartin/robriculture/issues/80), not this issue. The
claim here does not rest on that correlation; it rests on the 0.0015 spread
showing head-to-head's leader is noise-level rather than dominant.

## Decision

### 1. Designate on pool share, not head-to-head win-rate

Rank candidates by **mean score share against the anchor pool** (`match_share` /
`opponent_record` from #70 — reuse, do not reimplement), excluding self-matches.

### 2. Split the champion's two roles into two fields

The `champion` field currently serves two incompatible purposes:

- the **gate opponent** ADR-0007 measures challengers against, and
- the **submit default** — `scripts/submit.py` with no arguments packages and
  submits `champion.json`'s champion.

The champion should be a demanding, representative *bar*, which argues for
allowing vendored external competitors. But an external must **never** be the
submit default: submitting a vendored competitor's agent is competitively
pointless and an ADR-0005 licensing and attribution problem.

One field cannot answer both questions. `harness/champion.json` becomes:

```json
{
  "criterion": "pool_share",
  "gate_opponent": "meta_bot",
  "submit_default": "meta_rancher",
  "games": 2,
  "pool": ["meta_bot", "ranch_hands", "market_farmer", "ranch_adaptive", "wheat_hands", "spoiler"],
  "ranking": [
    {"name": "meta_bot", "share": 0.6325, "benchmark": true},
    {"name": "meta_rancher", "share": 0.6066, "benchmark": false}
  ]
}
```

- `gate_opponent` — the ranking leader, **benchmarks eligible**. Today `meta_bot`.
- `submit_default` — the leading **non-benchmark**, via the existing
  `top_contender`. Today `meta_rancher`, which is also the ladder leader (556.6),
  so both signals agree.

This is why `top_contender`'s benchmark exclusion existed even though no ADR
records it. The exclusion was correct for the old conflated meaning and remains
correct for `submit_default`; it was never right for a gate opponent.

### 3. Close the revert trap in `rounds.py`

`harness/rounds.py` designates too, by windowed win-rate over `rounds.json`.
Changing only `promotion.py` would leave the next `python -m harness.rounds`
silently overwriting `champion.json` and re-crowning `market_farmer`. A fix that
one routine command reverts, invisibly, is worse than no fix.

`rounds.py`'s designation step therefore calls the same share-based function.
Round *history* recording is unchanged — it remains a useful record.

Consequence to accept explicitly: `window` and `decay` no longer influence
designation. #12 built windowing to smooth noise across rounds; #77 has since
measured 40 games across 4 pairings with **zero** outcome flips, so it was
smoothing a quantity that barely moves. Rather than leave dead parameters,
`designate_from_history` loses them, and #12's history-keeping survives as
history.

## Components

### `harness/promotion.py`

- `pool_share_rank(candidates, pool, games, seed_base, rewards_fn) -> list[dict]` —
  best-first rows of `{"name", "share", "benchmark"}`. A candidate is never its
  own opponent.
- `designate(candidates, pool, benchmarks, ...) -> dict` — returns the full
  artifact body: `criterion`, `gate_opponent`, `submit_default`, `games`, `pool`,
  `ranking`. `gate_opponent` is `ranking[0]["name"]`; `submit_default` is
  `top_contender([r["name"] for r in ranking], benchmarks)`.
- `top_contender(names, benchmarks) -> str` — **kept and generalized** to take
  best-first *names* rather than `(label, win_rate, wins, played)` tuples. Its
  logic ("first label not in `benchmarks`, else raise") is unchanged; only the
  row shape it accepts changes, because `pool_share_rank` emits
  `{"name", "share", "benchmark"}` dicts and unpacking those as tuples would
  silently iterate dict keys. Now serves `submit_default` only.
- The benchmark set comes from the existing
  `harness.tournament.benchmark_names()`, which derives it from each strategy's
  `benchmark` class flag — no new registry of names to keep in sync.
- `save_champion(path, body)` — writes the artifact.
- `gate_opponent(path)` and `submit_default(path)` replace `current_champion`.
- `promotion_test` defaults its opponent to `gate_opponent(...)`.

### `scripts/submit.py`

Defaults to `submit_default`. Independently **refuses** to package any strategy
whose `benchmark` flag is true, so a hand-edited artifact still cannot submit a
vendored agent. Belt and braces, because the cost of getting this wrong is a
licensing problem rather than a bad score.

### `harness/rounds.py`

`designate_from_history` and `run_and_record` call `promotion.designate`.

## Error handling

- **Old-format artifact** (has `champion`, lacks the new fields): both readers
  raise a clear `ValueError` naming the re-designation command. They must not
  `KeyError`, and must not silently fall back to the old field — a silent
  fallback here re-points the gate at `market_farmer` without anyone noticing,
  which is the bug this spec exists to fix. Same loud-failure rule as #70's
  `load_genome`.
- **Every candidate is a benchmark**: `top_contender` already raises; that
  propagates, so there is no `submit_default`-less artifact.
- **Empty pool or no candidates**: raise rather than write a degenerate artifact.

## Testing

TDD throughout, red before green, suite green at every commit.

- `pool_share_rank`: ordering is by share descending; a candidate never plays
  itself; `benchmark` flags are carried through; deterministic for fixed seeds.
- `designate`: `gate_opponent` may be a benchmark; `submit_default` never is;
  both come from the same ranking.
- Migration: an old-format `champion.json` raises with a message naming the fix,
  for both readers.
- `submit.py`: defaults to `submit_default`; refuses a benchmark-flagged strategy
  even when named explicitly.
- `rounds.py`: `run_and_record` writes an artifact whose `gate_opponent` and
  `submit_default` match `promotion.designate` — the regression guard against the
  revert trap.
- `test_champion_excludes_benchmark.py` is **rewritten, not deleted**. Its six
  tests split three ways:
  - the two pure `top_contender` cases keep their assertions, with rows changed
    from tuples to names to match the generalized signature;
  - the `designate_champion` / `designate_from_history` / `run_and_record` cases
    are re-pointed at the new artifact — a benchmark may now be `gate_opponent`,
    and each must assert `submit_default` is *not* a benchmark;
  - the raises-when-all-benchmarks case is unchanged in intent.

  No assertion is dropped without a replacement asserting the new rule.

Coverage gate stays line ≥ 85% / branch ≥ 65%; CLI `main()`s keep
`# pragma: no cover`.

## Out of scope

- **The gate's scoring** stays win-rate-based. #77 covers the finding that
  head-to-head outcomes barely flip, making the binomial test's effective N far
  below 200. This spec changes *who* the opponent is, not *how* the match is
  scored.
- **Pool composition.** `spoiler` at 0.3348 is a clear outlier and likely
  supplies a free win that inflates every share;
  [#78](https://github.com/robsartin/robriculture/issues/78) owns that, along
  with vendoring more external agents.
- **Quantifying local-vs-ladder correlation** is
  [#80](https://github.com/robsartin/robriculture/issues/80).

## Consequence for the record

Re-designation changes the bar mid-stream, so promotion results recorded before
and after are not directly comparable. Any challenger promoted against
`market_farmer` cleared a weaker and unrepresentative bar. Worth a note in the
ADR trail rather than a silent cutover.
