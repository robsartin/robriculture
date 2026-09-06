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

That per-file leniency, though, means a directory that quietly lost one
download still "succeeds": ``discover_external_agents`` returns fewer agents
with only a stderr warning, and nothing downstream notices the pool shrank.
``resolve_opponents`` closes that gap by cross-checking what was discovered
against the manifest and raising by default on any shortfall -- an operator
can still opt into a known-partial pool, but never falls into one by accident
(#153).
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys

#: Where scripts/fetch_external_agents.py downloads by default; kept in sync
#: with the .gitignore entry and the fetch script's own default destination.
DEFAULT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "external_agents"
)

#: The single source of truth for which agents the pool is supposed to
#: contain (scripts/fetch_external_agents.py reads the same file).
MANIFEST_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "external_agents.json")


def _manifest_stems(manifest_path=MANIFEST_PATH):
    """Return the sorted filename stems the manifest expects to be fetched.

    Derived from each entry's ``dest_filename`` -- the same filename-stem key
    ``discover_external_agents`` returns agents under -- so the two can be
    compared directly (#153).
    """
    with open(manifest_path) as fh:
        data = json.load(fh)
    stems = []
    for entry in data["agents"]:
        dest = entry["dest_filename"]
        stems.append(dest[: -len(".py")] if dest.endswith(".py") else dest)
    return sorted(stems)


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


def resolve_opponents(anchor_names, include_external=False, discover_fn=None, build=None,
                       allow_partial=False, manifest_path=MANIFEST_PATH, warn=None):
    """Return ``{name: agent}`` for the opponents a genome should be scored against.

    One place decides this, so the evolution fitness pool (`harness.evolve`) and
    the frozen benchmark (`harness.genome_bench`) cannot drift apart on the
    question of who counts as an opponent.

    Default is exactly the named anchors, and discovery is **not attempted** --
    the frozen comparability bar across evolution runs must never depend on what
    happens to be sitting in the gitignored ``external_agents/`` directory
    (CLAUDE.md).

    ``include_external=True`` merges in the locally-fetched real competitors
    (#78), and cross-checks the discovered filename stems against every entry
    in the manifest (``harness/external_agents.json`` by default). Any
    manifest entry absent from the discovered set -- including the case where
    nothing was discovered at all -- raises a ``RuntimeError`` naming the
    missing agent(s), rather than quietly returning a shrunken pool: a pool
    that silently changed invalidates every comparison made against it, the
    failure mode behind #133, #67 and #151 (see this module's docstring and
    #153). ``allow_partial=True`` downgrades that raise to a loud warning
    (printed via `warn`, default stderr) and returns whatever was actually
    found -- an explicit opt-in for a run the operator knowingly accepts as
    partial, never the default.

    An agent discovered on disk but absent from the manifest is not a
    shortfall -- it is merged in same as any other discovered agent, matching
    what `discover_external_agents` already returns.

    Externals are opponents and gate opponents only, never submission
    candidates: `scripts/submit.py` must not package a competitor's agent
    (ADR-0005 licensing, enforced via `submit_default`).
    """
    if build is None:  # lazy: keeps this module importable without the strategy registry
        from harness.tournament import build_agents as build
    agents = build(list(anchor_names))
    if include_external:
        discover_fn = discover_fn or discover_external_agents
        warn = warn or _default_warn
        external = discover_fn()
        expected = _manifest_stems(manifest_path)
        missing = [name for name in expected if name not in external]
        if missing:
            message = (
                f"include_external was requested but the external pool is missing "
                f"{len(missing)} of {len(expected)} manifest agent(s): "
                f"{', '.join(missing)}. external_agents/ is gitignored -- re-run "
                "scripts/fetch_external_agents.py to repair it."
            )
            if not allow_partial:
                raise RuntimeError(message)
            warn(message)
        agents.update(external)
    return agents
