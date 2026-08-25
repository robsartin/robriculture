"""Build + submit a strategy to the kaggriculture competition (issue #21).

One command: build the submission tarball (via ``build.package``, which runs a
post-build smoke test) and submit it with the Kaggle CLI. The strategy defaults
to the recorded ``submit_default`` (``harness/champion.json``) and the message
to ``"<strategy> <short-sha>"``. ``--dry-run`` builds + smoke-tests only.

**Slot-aware (issues #79, #126).** Only the **latest 2** submissions are
live (ADR-0003); this rule was documented but not enforced anywhere in the
tooling, which is how a submission silently evicted our best agent and cost
~2 days at ~50 points below where we could have been (see the issue for the
incident). Before submitting, this prints the current live pair and the pair
that would result, and requires confirmation when the submission would evict
the *best-scoring* live agent (by current reading — ladder scores drift, see
ADR-0007). ``--slots`` reports the live pair without submitting.

    python scripts/submit.py                        # submit_default, auto message
    python scripts/submit.py dairy_hands -m "note"   # explicit strategy + message
    python scripts/submit.py --dry-run               # build + smoke test only, no submit
    python scripts/submit.py --slots                 # read-only: report the live pair, don't submit
    python scripts/submit.py neuropilot --yes        # skip the eviction confirmation

**Rob runs this**, not the agent: ``kaggle competitions submit`` needs Kaggle CLI
credentials (``kaggle.json``, gitignored) and competition-rules acceptance.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:  # allow `python scripts/submit.py` to find the packages
    sys.path.insert(0, REPO_ROOT)

from build import package as build_package  # noqa: E402

#: The Kaggle competition slug we submit to.
COMPETITION = "kaggriculture"

#: The recorded submit_default (default strategy) and where built tarballs land.
CHAMPION_PATH = os.path.join(REPO_ROOT, "harness", "champion.json")
DIST_DIR = os.path.join(REPO_ROOT, "dist")


def load_submit_default(path=CHAMPION_PATH):
    """The strategy recorded as the default to submit (never a benchmark, #76)."""
    with open(path) as fh:
        data = json.load(fh)
    if "submit_default" not in data:
        raise ValueError(
            f"{path!r} has no 'submit_default' — it predates the two-role split (#76). "
            f"re-designate with: python -m harness.promotion --designate --games 2"
        )
    return data["submit_default"]


def default_message(strategy, sha):
    """Submission message: strategy name + short commit SHA, so a ladder entry
    is traceable back to the exact build it came from."""
    return f"{strategy} {sha}".strip()


def submit_command(tarball, message, competition=COMPETITION):
    """The Kaggle CLI argv that submits ``tarball`` to the competition."""
    return [
        "kaggle", "competitions", "submit", competition,
        "-f", tarball, "-m", message,
    ]


#: The score-drift caveat (ADR-0007): the same agent has scored 501.6-600.0
#: across five identical submissions, so "best" means best-by-current-reading,
#: never settled truth.
NOISE_BAND_NOTE = (
    'note: ladder scores drift (~100 points across identical resubmits, '
    'ADR-0007) - "best" means best-by-current-reading, not settled truth.'
)


def _strategy_of(record):
    """The strategy name a submission record names, from its tarball filename.

    ``build.package``/``prepare`` always name the tarball ``<strategy>.tar.gz``,
    which is a more reliable source of the strategy name than ``description``
    (free text, format varies across historical submissions).
    """
    name = record.get("fileName", "")
    return name[: -len(".tar.gz")] if name.endswith(".tar.gz") else name


def _status_of(record):
    """Normalize Kaggle's status field to a bare lowercase word.

    The Kaggle CLI's JSON output serializes the status enum via ``str()``,
    giving values like ``"SubmissionStatus.COMPLETE"`` rather than a plain
    ``"complete"``.
    """
    return str(record.get("status", "")).rsplit(".", 1)[-1].lower()


def _score_of(record):
    """The public score as a float, or None if blank (pending/errored submissions)."""
    try:
        return float(record.get("publicScore"))
    except (TypeError, ValueError):
        return None


def parse_submissions(raw_records):
    """Normalize raw ``kaggle competitions submissions --format json`` records.

    Isolates the messy, API-shaped input (enum reprs, blank-string scores)
    from the pure slot logic below, so that logic stays simple and testable
    against fixture lists. Pure — no I/O.
    """
    return [
        {
            "strategy": _strategy_of(r),
            "status": _status_of(r),
            "score": _score_of(r),
            "date": r.get("date", ""),
        }
        for r in raw_records
    ]


def live_pair(submissions):
    """The two most-recent COMPLETE submissions (ADR-0003), newest first.

    Fewer than two are returned if fewer than two COMPLETE submissions exist.
    """
    complete = [s for s in submissions if s["status"] == "complete"]
    complete.sort(key=lambda s: s["date"], reverse=True)
    return tuple(complete[:2])


#: Statuses that will hold a live slot once everything finishes scoring: one
#: already scored, one still in flight. ERROR is deliberately absent -- a failed
#: submission never scores, so it never takes a slot (#126).
_SLOT_STATUSES = frozenset({"complete", "pending"})


def future_pair(submissions):
    """The two most-recent submissions that will be live once all have scored.

    `live_pair` answers "what is on the ladder right now" and correctly counts
    only COMPLETE. This answers the forward-looking question -- "after the dust
    settles, which two are live" -- and must count PENDING too, because an
    in-flight submission is going to take a slot.

    Sharing `live_pair`'s COMPLETE-only view for that made the eviction check
    wrong in both directions (#126): it warned about evicting an agent a
    just-issued resubmit had already saved, and -- the half that matters -- it
    could stay silent about an eviction that really was about to happen.
    """
    inflight = [s for s in submissions if s["status"] in _SLOT_STATUSES]
    inflight.sort(key=lambda s: s["date"], reverse=True)
    return tuple(inflight[:2])


def best_of(records):
    """The highest-scored of ``records``, or None if none are scored yet.

    Scores drift (ADR-0007), so this is "best by current reading," not a
    settled ranking. Ties resolve to whichever comes first.
    """
    scored = [r for r in records if r["score"] is not None]
    return max(scored, key=lambda r: r["score"]) if scored else None


def evicted_by(new_strategy, submissions):
    """The live submission that would age out if ``new_strategy`` were submitted now.

    Kaggle keeps only the latest 2 COMPLETE submissions live (ADR-0003); a new
    submission always ages the OLDER of the current live pair out of that
    list. Returns None when fewer than 2 are live yet, or when the strategy
    aging out is ``new_strategy`` itself — a resubmit of the same agent loses
    no *distinct* agent from the live set (this is exactly how the incident
    in issue #79 was fixed: resubmitting meta_rancher).
    """
    # #126: forward-looking on purpose. A submission still PENDING is going to
    # occupy a slot, so it has to count here even though it is not live yet.
    pair = future_pair(submissions)
    if len(pair) < 2:
        return None
    _newest, oldest = pair
    if oldest["strategy"] == new_strategy:
        return None
    return oldest


def _format_slot(record):
    """One live-slot's display text: 'name score' or 'name (unscored)'."""
    if record["score"] is None:
        return f"{record['strategy']} (unscored)"
    return f"{record['strategy']} {record['score']}"


def _format_pair(pair):
    """'name score, name score', or a message when nothing is live yet."""
    if not pair:
        return "(no live submissions yet)"
    return ", ".join(_format_slot(r) for r in pair)


def slots_report(submissions):
    """The ``--slots`` text: the current live pair, best-by-reading, and the drift caveat."""
    pair = live_pair(submissions)
    lines = [f"live slots: {_format_pair(pair)}"]
    best = best_of(pair)
    if best is not None:
        lines.append(f"best live (by current reading): {_format_slot(best)}")
    lines.append(NOISE_BAND_NOTE)
    return "\n".join(lines)


def submission_preview(new_strategy, submissions):
    """The preflight text before submitting ``new_strategy``, and whether to gate on it.

    Shows the live pair now and the pair that would result, and includes a
    WARNING line iff the submission would evict the best-scoring live agent
    (by current reading, ADR-0007). Returns ``(text, evicts_best)`` so the
    caller can gate on ``evicts_best`` without re-parsing the text.
    """
    pair = live_pair(submissions)
    evicted = evicted_by(new_strategy, submissions)
    best = best_of(pair)
    # #126: the survivor is the newest entry that will hold a slot, which may be
    # a PENDING submission rather than the newest COMPLETE one.
    forward = future_pair(submissions)
    survivor = forward[0] if forward else None
    after = tuple(r for r in ({"strategy": new_strategy, "score": None}, survivor) if r is not None)

    in_flight = [r for r in submissions if r["status"] == "pending"]
    lines = [
        f"about to submit: {new_strategy}",
        f"live slots now:    {_format_pair(pair)}",
    ]
    if in_flight:
        names = ", ".join(sorted({r["strategy"] for r in in_flight}))
        lines.append(f"in flight (will take a slot): {names}")
    lines.append(f"live slots after:  {_format_pair(after)}")
    evicts_best = evicted is not None and best is not None and evicted["strategy"] == best["strategy"]
    if evicts_best:
        lines.append(f"WARNING: this evicts {_format_slot(evicted)}, your best live agent.")
    lines.append(NOISE_BAND_NOTE)
    return "\n".join(lines), evicts_best


def _confirm_or_abort(text, *, evicts_best, assume_yes, isatty, input_fn=input):
    """Print the preflight report; gate on confirmation only when it warns.

    Never blocks a non-interactive run: without a TTY, evicting the best live
    agent requires ``--yes`` up front — refuse and say so rather than call
    ``input()``, which would hang forever on a prompt nothing will ever
    answer. When nothing is evicted (or nothing best), this never prompts at
    all, so an ordinary submit stays fully non-interactive.
    """
    print(text)
    if not evicts_best or assume_yes:
        return
    if not isatty:
        raise SystemExit(
            "refusing to submit non-interactively while it would evict the best "
            "live agent -- rerun with --yes to confirm, or run interactively"
        )
    answer = input_fn("continue? [y/N] ")
    if answer.strip().lower() != "y":
        raise SystemExit("aborted: submission would evict the best live agent")


def fetch_submissions(competition=COMPETITION, runner=subprocess.run):  # pragma: no cover - shells out to kaggle
    """The raw submission records from the Kaggle CLI (newest first), unparsed."""
    result = runner(
        ["kaggle", "competitions", "submissions", competition, "--format", "json"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise SystemExit(
            f"kaggle competitions submissions failed (exit {result.returncode}): {result.stderr.strip()}"
        )
    return json.loads(result.stdout)


def short_git_sha(repo_root=REPO_ROOT):  # pragma: no cover - shells out to git
    r = subprocess.run(
        ["git", "-C", repo_root, "rev-parse", "--short", "HEAD"],
        capture_output=True, text=True,
    )
    return r.stdout.strip() or "nogit"


def prepare(strategy=None, out=None, champion_path=CHAMPION_PATH):
    """Resolve the (strategy, tarball-path) to build, defaulting to the submit default.

    Refuses benchmark-flagged strategies outright. They are vendored external
    competitors; packaging one under our name is an ADR-0005 licensing and
    attribution problem, so this guard holds even when the name is given
    explicitly.
    """
    from harness.tournament import benchmark_names

    strategy = strategy or load_submit_default(champion_path)
    if strategy in benchmark_names():
        raise SystemExit(
            f"{strategy!r} is a readonly benchmark opponent (vendored external agent) "
            f"— refusing to package it for submission"
        )
    out = out or os.path.join(DIST_DIR, f"{strategy}.tar.gz")
    return strategy, out


def run(strategy=None, message=None, out=None, dry_run=False, no_smoke=False,
        *, champion_path=CHAMPION_PATH, build_fn=None, smoke_fn=None,
        sha_fn=short_git_sha, runner=subprocess.run,
        submissions_fn=None, assume_yes=False,
        isatty_fn=lambda: sys.stdin.isatty()):
    """Build the tarball (with smoke test), then submit it unless ``dry_run``.

    Dependencies are injected for testing: ``build_fn`` / ``smoke_fn`` / ``sha_fn``
    / ``runner`` / ``submissions_fn`` / ``isatty_fn`` default to the real
    ``build.package`` helpers, git, ``subprocess.run``, the live Kaggle
    submissions list, and ``sys.stdin.isatty``. Returns the Kaggle CLI argv
    that was (or would be) run.

    Slot-aware (issue #79): unless ``dry_run``, fetches the live submissions
    list and gates on confirmation *before building* when the submission
    would evict the best-scoring live agent (ADR-0003 / ADR-0007) — see
    ``submission_preview`` and ``_confirm_or_abort``. ``--dry-run`` never
    submits, so it skips this entirely (no network call, no prompt).
    """
    build_fn = build_fn or build_package.build
    smoke_fn = smoke_fn or build_package.smoke_test
    submissions_fn = submissions_fn or fetch_submissions

    strategy, out = prepare(strategy, out, champion_path)

    if not dry_run:
        submissions = parse_submissions(submissions_fn())
        text, evicts_best = submission_preview(strategy, submissions)
        _confirm_or_abort(text, evicts_best=evicts_best, assume_yes=assume_yes, isatty=isatty_fn())

    build_fn(strategy, out)
    if not no_smoke and not smoke_fn(out):
        raise SystemExit("smoke test FAILED — not submitting this build")

    message = message or default_message(strategy, sha_fn())
    cmd = submit_command(out, message)
    if dry_run:
        print("[dry-run] built and smoke-tested OK; would submit:\n  " + " ".join(cmd))
        return cmd

    print("submitting:\n  " + " ".join(cmd))
    result = runner(cmd)
    if getattr(result, "returncode", 0) != 0:
        raise SystemExit(f"kaggle submit failed (exit {result.returncode})")
    print(f"submitted {strategy} ({out}).")
    return cmd


def main(argv=None):  # pragma: no cover - CLI wiring
    ap = argparse.ArgumentParser(
        description="build + submit a strategy to the kaggriculture competition"
    )
    ap.add_argument("strategy", nargs="?", help="strategy name (default: the recorded submit_default)")
    ap.add_argument("-m", "--message", help="submission message (default: '<strategy> <sha>')")
    ap.add_argument("-o", "--out", help="tarball output path (default: dist/<strategy>.tar.gz)")
    ap.add_argument("--dry-run", action="store_true", help="build + smoke test only; do not submit")
    ap.add_argument("--no-smoke", action="store_true", help="skip the post-build smoke test")
    ap.add_argument("--slots", action="store_true",
                     help="report the current live pair and scores, then exit; do not submit")
    ap.add_argument("-y", "--yes", action="store_true",
                     help="skip the eviction confirmation (required for a non-interactive "
                          "submit that would evict the best live agent)")
    args = ap.parse_args(argv)
    if args.slots:
        print(slots_report(parse_submissions(fetch_submissions())))
        return 0
    run(args.strategy, message=args.message, out=args.out,
        dry_run=args.dry_run, no_smoke=args.no_smoke, assume_yes=args.yes)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
