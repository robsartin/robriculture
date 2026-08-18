"""Local-vs-ladder correlation (#80): does either local signal predict the ladder?

ADR-0008 pivoted the whole project on a claim: self-play against our own bots
is a broken fitness signal, and we need a local signal that actually correlates
with the ladder. Two local signals have existed since #70/#76 — tournament
head-to-head win-rate and genome_bench's shaped pool share against the fixed
anchors — and neither has ever had its ladder correlation measured. This
module measures both, for every agent we have a recorded ladder score for.

It deliberately does not reimplement either local signal: `head_to_head_win_rates`
wraps `harness.promotion.round_robin_rank` (the existing tournament signal) and
`pool_share_scores` wraps `harness.promotion.pool_share_rank` (the #70 shaped
signal, generalized here from genomes to any registered strategy).

Correlation is **Spearman rank correlation**, implemented in stdlib (no scipy):
we care about ordering, not exact values, because the ladder's own noise band
(ADR-0007) makes exact values untrustworthy anyway.

Usage:
    python -m harness.ladder_correlation --games 20 --pool-games 4
"""

from __future__ import annotations

import argparse
import itertools
import statistics
import sys
from dataclasses import dataclass

from harness.evolve import DEFAULT_ANCHORS
from harness.promotion import pool_share_rank, round_robin_rank
from harness.tournament import build_agents
from harness.tournament import play as _play
from harness.tournament import play_rewards as _play_rewards


@dataclass(frozen=True)
class LadderEntry:
    """One recorded ladder submission: the public score and when it's dated.

    `date` is an ISO date where the repo records one, or the literal string
    "undated" — never a guess. A guessed date would look reproducible without
    being true to the record; "undated" says plainly that this repo does not
    otherwise track it.
    """

    score: float
    date: str


# Ladder scores are hardcoded here, not fetched live: re-running this module
# must reproduce the same table every time (ADR-0005). Every agent below is
# still registered in strategies/, so a local score can be computed for it too.
#
# Sources: the score list is issue #80 (opened 2026-08-18). meta_rancher's
# 561.8 is dated from issue #61, which records it submitted 2026-08-13
# alongside ranch_hands. The four earliest ranch_hands scores (536.8, 515.4,
# 509.5, 600.0) and the "byte-identical code" finding come from ADR-0007
# (issue #74, measured 2026-08-16); the fifth (501.6) is the new point issue
# #80 adds, widening the recorded noise band to 98.4. No other per-submission
# dates are tracked elsewhere in this repo, so those entries are "undated"
# rather than guessed.
LADDER_SCORES: dict[str, list[LadderEntry]] = {
    "meta_rancher": [
        LadderEntry(561.8, "2026-08-13"),
        LadderEntry(551.4, "undated"),
    ],
    "ranch_hands": [
        LadderEntry(536.8, "undated"),
        LadderEntry(515.4, "undated"),
        LadderEntry(509.5, "undated"),
        LadderEntry(600.0, "undated"),
        LadderEntry(501.6, "undated"),
    ],
    "ranch_adaptive": [LadderEntry(520.6, "undated")],
    "mixed_hands": [LadderEntry(501.8, "undated")],
    "market_farmer": [LadderEntry(476.7, "undated")],
    "neuropilot": [
        LadderEntry(412.1, "undated"),
        LadderEntry(422.3, "undated"),
    ],
}

#: ADR-0007's ladder noise band, refreshed by issue #80's fifth ranch_hands
#: submission (501.6): five submissions of byte-identical code spanned
#: 501.6-600.0, a 98.4-point band. A gap this small or smaller between two
#: agents' medians is not evidence of a real difference.
NOISE_BAND = 600.0 - 501.6


def median_ladder_score(name, scores=LADDER_SCORES):
    """The per-agent median ladder score.

    Median, not mean or latest: ADR-0007's noise band means any single
    submission (ranch_hands has landed anywhere from 501.6 to 600.0 on
    unchanged code) is unreliable on its own, and the median resists the
    outlier pull a mean would suffer from a single wild run.
    """
    return statistics.median(entry.score for entry in scores[name])


def ladder_medians(scores=LADDER_SCORES):
    """Median ladder score for every recorded agent, name -> median."""
    return {name: median_ladder_score(name, scores) for name in scores}


def pairs_beyond_noise_band(medians, band=NOISE_BAND):
    """Agent pairs whose median ladder gap exceeds the noise band.

    These are the only pairs the ladder can actually distinguish from noise;
    everything else is a gap the band alone could explain. Returns
    `(name_a, name_b, gap)` tuples, gap descending.
    """
    pairs = [
        (a, b, abs(medians[a] - medians[b]))
        for a, b in itertools.combinations(medians, 2)
        if abs(medians[a] - medians[b]) > band
    ]
    pairs.sort(key=lambda row: row[2], reverse=True)
    return pairs


# --- Spearman rank correlation, ties averaged, stdlib only ---

def _average_ranks(values):
    """1-based ranks; a tied block gets the average rank across its span.

    e.g. [1, 2, 2, 4] -> [1, 2.5, 2.5, 4]: the two 2's occupy positions 2 and 3,
    so both get rank (2+3)/2 = 2.5.
    """
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg_rank = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[order[k]] = avg_rank
        i = j + 1
    return ranks


def spearman(xs, ys):
    """Spearman rank correlation of `xs` against `ys`.

    Computed as the Pearson correlation of the rank vectors (ties averaged via
    `_average_ranks`), which is exactly Spearman's rho even with ties — the
    tie-free shortcut formula (`1 - 6*sum(d^2)/(n*(n^2-1))`) is NOT used because
    it silently gives the wrong answer once any value repeats.

    Returns `None`, not a number, when the correlation is undefined: fewer than
    two points, or one series has zero rank variance (every value tied).
    Fabricating a coefficient in either case would misrepresent "no evidence"
    as "no relationship".
    """
    if len(xs) != len(ys):
        raise ValueError(f"xs and ys must be the same length ({len(xs)} != {len(ys)})")
    n = len(xs)
    if n < 2:
        return None
    rx, ry = _average_ranks(xs), _average_ranks(ys)
    mean_rx, mean_ry = sum(rx) / n, sum(ry) / n
    cov = sum((a - mean_rx) * (b - mean_ry) for a, b in zip(rx, ry))
    var_x = sum((a - mean_rx) ** 2 for a in rx)
    var_y = sum((b - mean_ry) ** 2 for b in ry)
    if var_x == 0 or var_y == 0:
        return None
    return cov / (var_x * var_y) ** 0.5


# --- Local signals: thin wrappers, not reimplementations ---

def head_to_head_win_rates(names, games=20, play_fn=_play, build=build_agents):
    """Round-robin win-rate among `names` only.

    This is the existing tournament signal (`harness.promotion.round_robin_rank`,
    the same one `harness.tournament`'s CLI reports), restricted to just the
    agents we have ladder scores for so the win-rate is directly comparable to
    the ladder table rather than diluted by every other registered strategy.
    """
    ranking = round_robin_rank(build(list(names)), games=games, play_fn=play_fn)
    return {name: win_rate for name, win_rate, *_rest in ranking}


def pool_share_scores(names, anchor_names=DEFAULT_ANCHORS, games=4, seed_base=0,
                      rewards_fn=_play_rewards, build=build_agents):
    """Shaped score share for `names` against the fixed anchor pool (#70).

    Generalizes `genome_bench`'s idea from evolved genomes to any registered
    strategy by building real agents for `names` and handing them to
    `harness.promotion.pool_share_rank` — the ranking logic itself is reused,
    not reimplemented.
    """
    candidates = build(list(names))
    pool = build(list(anchor_names))
    rows = pool_share_rank(candidates, pool, games=games, seed_base=seed_base,
                           rewards_fn=rewards_fn)
    return {row["name"]: row["share"] for row in rows}


# --- The report: table + both correlations, honestly captioned ---

@dataclass(frozen=True)
class CorrelationReport:
    """The assembled correlation table plus both Spearman coefficients.

    `n` is the number of agents compared — small by construction (we only have
    ladder scores for a handful of agents), and callers must not present
    `head_to_head_rho`/`pool_share_rho` without also surfacing `n`: a
    correlation coefficient from ~6 points is a hint, not a settled answer.
    """

    rows: list
    n: int
    head_to_head_rho: float | None
    pool_share_rho: float | None
    noise_band: float
    beyond_band: list


def build_report(names=None, head_to_head=None, pool_share=None,
                 medians=None, noise_band=NOISE_BAND):
    """Assemble the correlation table and both Spearman coefficients.

    `head_to_head` and `pool_share` are name -> score maps — required, and
    injectable so tests (and any offline re-analysis) never have to play real
    games to exercise this assembly logic. `names`/`medians` default to the
    full recorded `LADDER_SCORES` table.
    """
    medians = medians if medians is not None else ladder_medians()
    names = list(names) if names is not None else list(medians)
    rows = [
        {
            "name": name,
            "ladder_median": medians[name],
            "n_submissions": len(LADDER_SCORES.get(name, [])),
            "head_to_head_win_rate": head_to_head[name],
            "pool_share": pool_share[name],
        }
        for name in names
    ]
    ladder_vals = [r["ladder_median"] for r in rows]
    h2h_rho = spearman(ladder_vals, [r["head_to_head_win_rate"] for r in rows])
    share_rho = spearman(ladder_vals, [r["pool_share"] for r in rows])
    beyond = pairs_beyond_noise_band(
        {r["name"]: r["ladder_median"] for r in rows}, band=noise_band
    )
    return CorrelationReport(
        rows=rows,
        n=len(rows),
        head_to_head_rho=h2h_rho,
        pool_share_rho=share_rho,
        noise_band=noise_band,
        beyond_band=beyond,
    )


# --- CLI: thin glue over the tested functions above ---

def _fmt_rho(rho):
    return f"{rho:.4f}" if rho is not None else "undefined (no rank variance)"


def main(argv=None):  # pragma: no cover
    ap = argparse.ArgumentParser(
        description="robriculture local-vs-ladder correlation (#80)"
    )
    ap.add_argument("--games", type=int, default=20,
                    help="round-robin games per pairing for head-to-head (default 20)")
    ap.add_argument("--pool-games", type=int, default=4,
                    help="games per anchor for pool share (default 4, matches genome_bench)")
    args = ap.parse_args(argv)

    names = list(LADDER_SCORES)
    print(f"Playing head-to-head round-robin among {names} ({args.games} games/pairing)...")
    h2h = head_to_head_win_rates(names, games=args.games)
    print(f"Playing pool share vs anchors {list(DEFAULT_ANCHORS)} ({args.pool_games} games/anchor)...")
    share = pool_share_scores(names, games=args.pool_games)
    report = build_report(names, head_to_head=h2h, pool_share=share)

    print()
    header = f"{'agent':16s} {'ladder(median)':>14s} {'n_sub':>6s} {'h2h win-rate':>13s} {'pool share':>11s}"
    print(header)
    for r in sorted(report.rows, key=lambda row: row["ladder_median"], reverse=True):
        print(f"{r['name']:16s} {r['ladder_median']:14.1f} {r['n_submissions']:6d} "
              f"{r['head_to_head_win_rate']:13.4f} {r['pool_share']:11.4f}")

    total_pairs = report.n * (report.n - 1) // 2
    print()
    print(f"n = {report.n} agents ({total_pairs} pairs). This is a small sample; "
          f"treat any correlation below as a hint, not a settled answer.")
    print(f"Ladder noise band: {report.noise_band:.1f} points (ADR-0007). "
          f"{len(report.beyond_band)}/{total_pairs} agent pairs are separated "
          f"by more than the band (the only pairs the ladder can actually distinguish):")
    for a, b, gap in report.beyond_band:
        print(f"    {a} vs {b}: {gap:.1f} points apart")

    print()
    print(f"Spearman rho, head-to-head win-rate vs ladder median: {_fmt_rho(report.head_to_head_rho)}")
    print(f"Spearman rho, pool share vs ladder median:            {_fmt_rho(report.pool_share_rho)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
