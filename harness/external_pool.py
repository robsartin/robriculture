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
        module_name = f"_external_agent_{name}"
        try:
            spec = importlib.util.spec_from_file_location(module_name, path)
            module = importlib.util.module_from_spec(spec)
            # Register before exec: a module-level `@dataclass(slots=True)` under
            # `from __future__ import annotations` resolves its (stringified)
            # field annotations via `sys.modules[cls.__module__]` while the class
            # body runs. Skipping this step makes that lookup return None and
            # crashes the import with an unrelated AttributeError (#151) -- a
            # failure a hand-written fake agent would never trigger.
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
        except Exception as exc:  # a stranger's code -- anything can go wrong here
            sys.modules.pop(module_name, None)
            warn(f"external agent {fname!r} failed to import ({exc!r}); skipping")
            continue

        candidate = getattr(module, "agent", None)
        if not callable(candidate):
            warn(f"external agent {fname!r} has no callable module-level `agent`; skipping")
            continue
        agents[name] = candidate

    return agents


def resolve_opponents(anchor_names, include_external=False, discover_fn=None, build=None):
    """Return ``{name: agent}`` for the opponents a genome should be scored against.

    One place decides this, so the evolution fitness pool (`harness.evolve`) and
    the frozen benchmark (`harness.genome_bench`) cannot drift apart on the
    question of who counts as an opponent.

    Default is exactly the named anchors, and discovery is **not attempted** --
    the frozen comparability bar across evolution runs must never depend on what
    happens to be sitting in the gitignored ``external_agents/`` directory
    (CLAUDE.md).

    ``include_external=True`` merges in the locally-fetched real competitors
    (#78). It raises when none are found rather than quietly returning the
    internal-only set: a run that asked for external opponents and silently got
    none reports a confident number measured against the wrong pool, which is
    indistinguishable from a clean result -- the failure mode that wasted a whole
    session in #133 and returned "every candidate is unlicensed" in #67.

    Externals are opponents and gate opponents only, never submission
    candidates: `scripts/submit.py` must not package a competitor's agent
    (ADR-0005 licensing, enforced via `submit_default`).
    """
    if build is None:  # lazy: keeps this module importable without the strategy registry
        from harness.tournament import build_agents as build
    agents = build(list(anchor_names))
    if include_external:
        discover_fn = discover_fn or discover_external_agents
        external = discover_fn()
        if not external:
            raise RuntimeError(
                "include_external was requested but no external agents were found in "
                f"{DEFAULT_DIR!r}. That directory is gitignored and empty until you run "
                "scripts/fetch_external_agents.py. Refusing to score against the "
                "internal-only pool while reporting an external result."
            )
        agents.update(external)
    return agents
