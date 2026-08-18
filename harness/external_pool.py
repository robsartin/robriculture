"""Loader for locally-fetched external competitor agents (#78) -- measurement only.

Real competitor agents (kaggle_environments-style: a module-level
``agent(observation, configuration)`` callable) live in a gitignored local
directory, downloaded by ``scripts/fetch_external_agents.py`` from the
manifest at ``harness/external_agents.json``. No third-party code is ever
committed to this repo (ADR-0005, ADR-0008 amendment 2026-08-18).

This module is deliberately **measurement-only**: it is never imported by
``harness/evolve.py``'s ``DEFAULT_ANCHORS``, ``harness/promotion.py``'s
``designate``, or the evolution loop itself. The only sanctioned entry point
is an explicit opt-in flag on a measurement tool
(``harness/genome_bench.py --include-external``), off by default, so the
frozen comparability bar never depends on what happens to be sitting in a
directory that isn't checked into git.

An absent directory is a no-op returning ``{}``: a clean clone, CI, and a
machine that never ran the fetch script must all behave identically. A file
that fails to import, or has no callable module-level ``agent``, is skipped
with a warning rather than crashing the run -- one malformed download must
never take down a benchmark.
"""

from __future__ import annotations

import importlib.util
import os
import sys

#: Where scripts/fetch_external_agents.py downloads by default; kept in sync
#: with the .gitignore entry and the fetch script's own default destination.
DEFAULT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "external_agents"
)


def _default_warn(message):
    print(f"warning: {message}", file=sys.stderr)


def discover_external_agents(directory=DEFAULT_DIR, warn=None):
    """Return ``{name: agent_callable}`` for every importable agent in `directory`.

    ``name`` is the filename stem. Only ``*.py`` files are considered -- the
    ``.meta.json`` license/attribution sidecars the fetch script writes
    alongside each download are ignored here (see
    ``scripts/fetch_external_agents.py``).
    """
    warn = warn or _default_warn
    agents: dict = {}
    if not os.path.isdir(directory):
        return agents

    for fname in sorted(os.listdir(directory)):
        if not fname.endswith(".py"):
            continue
        name = fname[: -len(".py")]
        path = os.path.join(directory, fname)
        try:
            spec = importlib.util.spec_from_file_location(f"_external_agent_{name}", path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        except Exception as exc:  # a stranger's code -- anything can go wrong here
            warn(f"external agent {fname!r} failed to import ({exc!r}); skipping")
            continue

        candidate = getattr(module, "agent", None)
        if not callable(candidate):
            warn(f"external agent {fname!r} has no callable module-level `agent`; skipping")
            continue
        agents[name] = candidate

    return agents
