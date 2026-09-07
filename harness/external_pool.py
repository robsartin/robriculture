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

import hashlib
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

#: Gate anchors (#152): the externals the champion loses to, strongest first,
#: measured 2026-09-07 (`third_herder`, seeds 700-701, sides alternated; our
#: reward share 0.197 / 0.362 / 0.411 / 0.475 / 0.488). Changing this tuple is
#: a dated ADR-0007 amendment, as adding `field_rival` to DEFAULT_ANCHORS was
#: (#181). Every member must be pinned in the manifest before the gate will
#: load it (`external_anchor_agents`).
EXTERNAL_ANCHORS = (
    "pilkwang_structured_economic_policy",
    "lonespear_kaggriculture_v21",
    "premaananda108_ecobot_v7",
    "shashankjangid_agent_v1000_sovereign_prime",
    "madhur_sabherwal_hub_geometry_agent",
)


def file_sha256(path):
    """Hex sha256 of the file's bytes -- the pin is over the file *as written*."""
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _stem(entry):
    dest = entry["dest_filename"]
    return dest[: -len(".py")] if dest.endswith(".py") else dest


def manifest_pins(manifest_path=MANIFEST_PATH):
    """{filename stem: sha256 or None} for every manifest entry (#152)."""
    with open(manifest_path) as fh:
        data = json.load(fh)
    return {_stem(entry): entry.get("sha256") for entry in data["agents"]}


def verify_pins(directory=DEFAULT_DIR, manifest_path=MANIFEST_PATH):
    """One of "ok" / "unpinned" / "mismatch" / "missing" per manifest entry.

    "missing" is the file not being on disk (the #153 shortfall); "unpinned"
    is a file with no pin to check against; "mismatch" is the one that
    matters -- bytes on disk that are not the bytes the manifest recorded.
    """
    states = {}
    for stem, pin in manifest_pins(manifest_path).items():
        path = os.path.join(directory, stem + ".py")
        if not os.path.isfile(path):
            states[stem] = "missing"
        elif pin is None:
            states[stem] = "unpinned"
        elif file_sha256(path) == pin:
            states[stem] = "ok"
        else:
            states[stem] = "mismatch"
    return states


def _manifest_stems(manifest_path=MANIFEST_PATH):
    """The sorted filename stems the manifest expects to be fetched (#153)."""
    return sorted(manifest_pins(manifest_path))


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
                       allow_partial=False, manifest_path=MANIFEST_PATH, warn=None,
                       directory=DEFAULT_DIR):
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
        discover_fn = discover_fn or (lambda: discover_external_agents(directory))
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
        states = verify_pins(directory, manifest_path)
        mismatched = sorted(n for n, s in states.items() if s == "mismatch")
        if mismatched:
            # Never downgraded by allow_partial: a short pool is a known-partial
            # pool, a mismatched file is code nobody reviewed (#152).
            raise RuntimeError(
                f"external agent(s) on disk do not match the manifest pin: "
                f"{', '.join(mismatched)}. Re-run scripts/fetch_external_agents.py (it "
                "refuses a mismatch); if the author published a new version you have "
                "checked, re-pin with --pin and commit the manifest."
            )
        unpinned = sorted(n for n, s in states.items() if s == "unpinned" and n in external)
        if unpinned:
            warn(
                f"external agent(s) unpinned in the manifest (measurement only; never a "
                f"gate anchor): {', '.join(unpinned)}. Pin with: python -m "
                "scripts.fetch_external_agents --pin"
            )
        agents.update(external)
    return agents


def external_anchor_agents(names=EXTERNAL_ANCHORS, directory=DEFAULT_DIR,
                           manifest_path=MANIFEST_PATH, discover_fn=None):
    """The gate's loader for `EXTERNAL_ANCHORS` (#152): every name must verify.

    Missing, unpinned and mismatched are all refusals -- an ADR-0007 verdict
    is never measured against an external whose bytes the manifest does not
    vouch for. No partial pool, no warning: raise, naming each anchor and the
    command that repairs it.
    """
    states = verify_pins(directory, manifest_path)
    problems = {n: states.get(n, "missing") for n in names if states.get(n) != "ok"}
    if problems:
        detail = ", ".join(f"{n} ({s})" for n, s in problems.items())
        raise RuntimeError(
            f"gate anchors are not verified: {detail}. Run scripts/fetch_external_agents.py "
            "(--pin for an unpinned entry) and commit the manifest; the gate never runs "
            "against an unverified external."
        )
    discover_fn = discover_fn or (lambda: discover_external_agents(directory))
    found = discover_fn()
    absent = [n for n in names if n not in found]
    if absent:
        raise RuntimeError(f"gate anchor(s) failed to import: {', '.join(absent)}")
    return {n: found[n] for n in names}
