"""Dedup survey candidates against the external-agent manifest (#296).

The recurring #67 re-survey used to dedup against a hardcoded "already
proposed" list inside its own instructions. That list drifts from the pool with
every batch added, and by 2026-09-18 it had twice caused the survey to
re-propose agents already vendored. `harness/external_agents.json` is the
source of truth, so this module reads it and answers one question per
candidate:

    HAVE    already vendored -- the exact repo+path, or the kernel_ref
    REVIEW  that repo is vendored, but at a different path: a rung/lineage
            judgement per #295, not an automatic add or drop
    NEW     absent from the manifest

Usage (candidates are `owner/repo`, `owner/repo:path`, or a Kaggle
`owner/kernel-slug`):

    python -m scripts.survey_dedup OWNER/REPO:path/to/agent.py OWNER/KERNEL
"""

from __future__ import annotations

import sys
from typing import NamedTuple

from scripts.fetch_external_agents import load_manifest


class Verdict(NamedTuple):
    status: str
    matched: str | None


def _same_ref(a, b):
    # GitHub owner/repo and Kaggle owner/kernel are case-insensitive; the path
    # inside a repo is not.
    return a is not None and b is not None and a.lower() == b.lower()


def classify(ref, path=None, entries=None):
    same_repo = None
    for entry in entries or ():
        if _same_ref(entry.get("kernel_ref"), ref):
            return Verdict("HAVE", entry["name"])
        if _same_ref(entry.get("repo"), ref):
            if entry.get("path") == path:
                return Verdict("HAVE", entry["name"])
            same_repo = same_repo or entry["name"]
    if same_repo is not None:
        return Verdict("REVIEW", same_repo)
    return Verdict("NEW", None)


def split_candidate(candidate):
    """`owner/repo:path` -> ("owner/repo", "path"); no colon -> path None."""
    ref, sep, path = candidate.partition(":")
    return ref, (path if sep else None)


def main(argv=None):
    candidates = list(sys.argv[1:] if argv is None else argv)
    entries = load_manifest()
    for candidate in candidates:
        ref, path = split_candidate(candidate)
        verdict = classify(ref, path=path, entries=entries)
        print(f"{verdict.status}\t{candidate}\t{verdict.matched or ''}".rstrip())
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
