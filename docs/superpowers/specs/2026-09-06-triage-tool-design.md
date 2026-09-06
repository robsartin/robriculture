# #172 Stage 2: an offline triage tool, calibrated on recorded verdicts

- **Issue:** #172 (Stage 2, reframed 2026-09-06 from "runtime planner" to "offline pre-filter")
- **Date:** 2026-09-06
- **Depends on:** Stage 1 (#214: a mirror-opponent, final-money rollout ranks policy variants at
  rho 0.66), ADR-0007 (declared criteria; the champion is the gate), ADR-0003 (portfolio)
- **Decides:** whether a four-minute self-play ranking can stand in front of the 200-game gate

## Context

Stage 1 validated the objective and killed the knob: the mirror/final-money rollout ranks
sell-discipline variants of the champion at median rho 0.66, and no price floor above 0.3 ever
beat plain liquidation on any of the ten states. A runtime sell/hold planner on that knob would
choose "liquidate" every turn. The objective, not the planner, is the asset.

Every experiment this month (#187, #193, #196, #202, #206, #207) paid for a 16-seed
head-to-head against the gate opponent before learning anything, at 6,000-11,200 of noise per
pairing (#181). A ranking that costs seconds and agrees with those verdicts most of the time is
worth having in front of that gate, as long as it is only ever asked to *rank* (#177: rho 0.4
ranks, it does not choose).

## Question and pass criterion (declared before code, ADR-0007)

**Question.** Does mean final money in seeded self-play rank whole strategies the same way
their recorded 16-seed win-rates against `meta_bot` rank them?

**Prediction.** For each strategy, one number: the mean over seeds `{0, 1, 2, 3}` of the mean
of both seats' final reward when the strategy plays itself (`harness.tournament.play_rewards`
with the same strategy on both farms). Both seats are averaged because they are the same
policy and averaging halves the seed noise for free; four seeds because Stage 1 measured
~0.7 s per half-game rollout and a full game is ~2 s, so a strategy costs ~8 s.

**Truth.** The win-rate against `meta_bot` recorded on an issue, measured on the repo's
standard protocol: 16 seeds, sides alternated. The calibration set is **every registered
strategy with such a record**, and must hold **at least five**; fewer voids the calibration.
Verified members, each to be re-confirmed against its issue by the implementer before it is
written down:

| strategy | recorded vs `meta_bot` | source |
|---|---|---|
| `neuropilot` | 16/16 | #193 / #202 table |
| `dense_farm` | 88% (seeds 100-115, confirmed 200-215) | #202, `strategies/dense_farm.py` |
| `dung_farm` | 12/16 (seeds 300-315) | #206 |
| `balanced_farm` | 9/16 | #193 |

Candidates the implementer must check for a recorded rate and add if one exists: `splitbrain`
(#196), `field_rival` (#181), `meta_rancher`, `ranch_hands`, `market_farmer`,
`ranch_adaptive`, `wheat_hands` (#193's anchor rows record `balanced_farm`'s rate against them,
not theirs against `meta_bot` — that does not count). No fresh head-to-heads are run to fill
the set (Rob's decision, 2026-09-06): the point is to test against what the notebook already
says, and the seed sets differ across records, which is why this is a **rank** check and not
a point-estimate one. The table above is illustrative; the committed source of truth is
`harness/calibration_verdicts.json` (name, recorded rate as wins/games, seeds, issue), and
the tool cites that file rather than repeating it.

**Statistic.** Spearman rho (`harness.ladder_correlation.spearman`, tie-averaged) between the
self-play score and the recorded rate over the calibration set.

**Pass:** rho **>= 0.40**, with both controls holding. **Fail:** anything else — the tool is
not shipped as a pre-filter and the issue records the table. **Void:** fewer than five members
or a failed control. The bar is Stage 1's bar and is not moved after numbers exist.

**Controls, run first:**

1. **Floor.** `lean` (the weakest registered agent by pool share in `champion.json`) must
   rank below every calibration member. A ranker that cannot separate the floor from the
   field ranks nothing.
2. **Determinism.** Two runs on the same seeds produce identical scores to the value; a score
   that drifts is a measurement of the machine, not the strategy.

**Recorded, not gated:** the per-strategy scores and per-seed values; whether the top-ranked
strategy is the recorded best (ranking, not choosing); wall-clock per strategy.

## Decisions

1. **Self-play from turn 0, not mid-game states.** Stage 1's state set is the champion's own
   farms at days 3-15; handing a foreign strategy a farm it did not build measures the
   hand-over, not the strategy. Whole strategies start from an empty farm. Stage 1's
   `objective_check` stays as the tool for *variants of the champion*; this tool does not
   duplicate it.
2. **Self-play, not play-against-`meta_bot`.** Playing the gate opponent directly is the gate.
   The claim under test is that the *mirror* — the only opponent a planner could ever have —
   carries enough signal to rank; that is what Stage 1 found and what this generalises.
3. **Averaging both seats.** Decided above; recorded here so nobody "fixes" it to seat 0.
4. **The tool never promotes.** It prints a ranking and, with `--top K`, the names that
   proceed to the ADR-0007 gate. It does not read or write `champion.json` except to name the
   floor control, and it registers nothing.

## Design

Two units, one data file; nothing touches any strategy.

### `harness/triage.py`

```
SEEDS = (0, 1, 2, 3)
BAR = 0.40
FLOOR = "lean"

def self_play_score(name, seeds=SEEDS, play=play_rewards) -> dict
    # {"name", "score": mean over seeds of (ra + rb)/2, "per_seed": [...], "seconds"}
def rank(names, seeds=SEEDS, play=play_rewards) -> list[dict]      # sorted, best first
def calibrate(scores: dict[str, float], verdicts: dict[str, float], bar=BAR) -> dict
    # {"rho", "n", "passed", "top_predicted", "top_recorded"}; n < 5 -> "void": True
def floor_holds(scores, floor_score) -> bool
def format_ranking(rows) -> str
def main(argv=None)  # pragma: no cover
    # python -m harness.triage NAME [NAME ...] [--top K] [--seeds 0 1 2 3]
    # python -m harness.triage --calibrate         (reads harness/calibration_verdicts.json)
    # exit 0 PASS / ranking printed, 1 FAIL, 2 VOID (controls or n < 5)
```

`play` is injected so the pure parts test in milliseconds with a fake; the real
`harness.tournament.play_rewards` is used by `main` only. Strict mode
(`ROBRICULTURE_STRICT=1`) is set first in `main`, as `objective_check` does: an instrument must
surface a crash rather than record a PASS bot's score.

### `harness/calibration_verdicts.json`

```
{"protocol": "16 seeds vs meta_bot, sides alternated (ADR-0007 / #181)",
 "members": [{"name": "dense_farm", "wins": 14, "games": 16, "seeds": "100-115", "issue": 202}, ...]}
```

Rates are stored as wins/games, never as a percentage, so a reader can see the sample size.
A test asserts every member is a registered strategy and every `issue` is an integer; the
implementer confirms each row against its issue and says so in the commit message.

### Tests (pure TDD)

- `self_play_score` averages both seats and all seeds, records per-seed values, uses the
  injected `play` (fake returning known rewards).
- `rank` sorts best first and is stable on ties.
- `calibrate`: rho via `spearman`; `passed` at exactly 0.40 and not at 0.39; `n < 5` reports
  void and never passes; undefined rho (all-tied recorded rates) is void, not zero.
- `floor_holds`: true only when every member beats the floor score; a tie fails.
- `format_ranking`: one line per strategy, score and per-seed values visible.
- verdicts file: every name registered, every rate wins/games with `wins <= games`.
- One integration test, marked slow, plays `lean` and `dense_farm` in self-play on one short
  game (`episodeSteps` small) through the real `play_rewards` and asserts `dense_farm` scores
  higher — the floor control in miniature, with the precondition that both scores are > 0.

## Cost

Calibration: ~7 strategies x 4 seeds x ~2 s, plus the floor, under two minutes. A triage of
ten contenders: about 80 s.

## Out of scope

Any runtime planner; wiring into `act()`; changing `objective_check`, `GRID`, or Stage 1's
bar; fresh head-to-heads to grow the calibration set; using the score for anything but rank.

## Alternatives rejected

- **Runtime sell/hold planner on `min_frac` (Stage 2 as first written).** Stage 1's table:
  the floor never helps, so the decision is constant. Rejected on the numbers.
- **Rank from Stage 1's mid-game state set.** Measures the hand-over to a foreign strategy,
  not the strategy. Rejected; kept for variants.
- **Calibrate with fresh 16-seed head-to-heads for every member.** Most rigorous and about an
  hour of compute; rejected for now because the question is whether the tool agrees with
  the *existing* notebook, and fresh numbers can be added later without changing the tool.
- **Score against `meta_bot` instead of the mirror.** That is the gate itself, only shorter;
  it would not test the mirror claim and would overfit the pre-filter to one opponent.
