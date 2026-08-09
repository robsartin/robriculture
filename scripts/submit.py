"""Build + submit a strategy to the kaggriculture competition (issue #21).

One command: build the submission tarball (via ``build.package``, which runs a
post-build smoke test) and submit it with the Kaggle CLI. The strategy defaults
to the current champion (``harness/champion.json``) and the message to
``"<strategy> <short-sha>"``. ``--dry-run`` builds + smoke-tests only.

**Rob runs this**, not the agent: ``kaggle competitions submit`` needs Kaggle CLI
credentials (``kaggle.json``, gitignored) and competition-rules acceptance. Only
the **latest 2** submissions are active on the ladder, so run it for the two best
(champion + challenger).

    python scripts/submit.py                        # champion, auto message
    python scripts/submit.py dairy_hands -m "note"   # explicit strategy + message
    python scripts/submit.py --dry-run               # build + smoke test only, no submit
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

#: The recorded champion (default strategy) and where built tarballs land.
CHAMPION_PATH = os.path.join(REPO_ROOT, "harness", "champion.json")
DIST_DIR = os.path.join(REPO_ROOT, "dist")


def load_champion(path=CHAMPION_PATH):
    """The strategy name recorded as the current champion."""
    with open(path) as fh:
        return json.load(fh)["champion"]


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


def short_git_sha(repo_root=REPO_ROOT):  # pragma: no cover - shells out to git
    r = subprocess.run(
        ["git", "-C", repo_root, "rev-parse", "--short", "HEAD"],
        capture_output=True, text=True,
    )
    return r.stdout.strip() or "nogit"


def prepare(strategy=None, out=None, champion_path=CHAMPION_PATH):
    """Resolve the (strategy, tarball-path) to build, defaulting to the champion."""
    strategy = strategy or load_champion(champion_path)
    out = out or os.path.join(DIST_DIR, f"{strategy}.tar.gz")
    return strategy, out


def run(strategy=None, message=None, out=None, dry_run=False, no_smoke=False,
        *, champion_path=CHAMPION_PATH, build_fn=None, smoke_fn=None,
        sha_fn=short_git_sha, runner=subprocess.run):
    """Build the tarball (with smoke test), then submit it unless ``dry_run``.

    Dependencies are injected for testing: ``build_fn`` / ``smoke_fn`` / ``sha_fn``
    / ``runner`` default to the real ``build.package`` helpers, git, and
    ``subprocess.run``. Returns the Kaggle CLI argv that was (or would be) run.
    """
    build_fn = build_fn or build_package.build
    smoke_fn = smoke_fn or build_package.smoke_test

    strategy, out = prepare(strategy, out, champion_path)
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
    ap.add_argument("strategy", nargs="?", help="strategy name (default: current champion)")
    ap.add_argument("-m", "--message", help="submission message (default: '<strategy> <sha>')")
    ap.add_argument("-o", "--out", help="tarball output path (default: dist/<strategy>.tar.gz)")
    ap.add_argument("--dry-run", action="store_true", help="build + smoke test only; do not submit")
    ap.add_argument("--no-smoke", action="store_true", help="skip the post-build smoke test")
    args = ap.parse_args(argv)
    run(args.strategy, message=args.message, out=args.out,
        dry_run=args.dry_run, no_smoke=args.no_smoke)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
