"""Loader for locally-fetched external competitor agents (#78), pinned per #152.

Real competitor agents (kaggle_environments-style: a module-level
``agent(observation, configuration)`` callable) live in a gitignored local
directory, downloaded by ``scripts/fetch_external_agents.py`` from the
manifest at ``harness/external_agents.json``. No third-party code is ever
committed to this repo (ADR-0005, ADR-0008 amendment 2026-08-18).

Since #152 (ADR-0008 amendment 2026-09-07) a *pinned* external may be a gate
anchor (``EXTERNAL_ANCHORS``, loaded by ``external_anchor_agents``), a ranking
opponent (``harness.promotion --designate --include-external``) or an opt-in
evolution anchor (``harness.evolve --include-external``). The pin is the
manifest's ``sha256`` of the fetched file; a mismatch always raises, an
unpinned agent is measurement-only and never a gate anchor. ``DEFAULT_ANCHORS``
never contains an external: the six named anchors remain the committed floor.

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

import functools
import hashlib
import importlib.util
import json
import os
import sys
import uuid

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


def load_external_agent(path):
    """Import `path` under a unique module name; return its module-level `agent`.

    A **fresh** callable per call: every load builds its own module object, so
    whatever state a stranger's agent keeps across calls cannot leak from one
    game into the next -- the registry already hands out a new strategy
    instance per game (`harness.triage._default_agents`), and the paired
    external limb (#152) is exactly the comparison such leakage would bias.

    Import errors propagate; a file with no callable module-level `agent`
    raises `ValueError`. `discover_external_agents` is the lenient caller that
    turns both into a skip-with-warning.
    """
    fname = os.path.basename(path)
    stem = fname[: -len(".py")] if fname.endswith(".py") else fname
    module_name = f"_external_agent_{stem}_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    # Register before exec: a module-level `@dataclass(slots=True)` under
    # `from __future__ import annotations` resolves its (stringified)
    # field annotations via `sys.modules[cls.__module__]` while the class
    # body runs. Skipping this step makes that lookup return None and
    # crashes the import with an unrelated AttributeError (#151) -- a
    # failure a hand-written fake agent would never trigger.
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
        candidate = getattr(module, "agent", None)
        if not callable(candidate):
            raise ValueError(f"{path!r} has no callable module-level `agent`")
    except BaseException:
        # The unique name is this function's own; nothing else can clean it up.
        sys.modules.pop(module_name, None)
        raise
    # Registered only for the duration of exec (see above); the callable keeps
    # its own module globals alive, and leaving the name behind leaks one module
    # per game on the reloading paths (#247).
    sys.modules.pop(module_name, None)
    return candidate


def _source_of(agent):
    """The file an agent callable was compiled in, or None if unknowable.

    Read off the callable itself, never through `sys.modules` /
    `inspect.getmodule`: those resolve by module *name*, so a later load of the
    same filename stem rebinds that name and silently redirects an
    already-captured agent to somebody else's file -- and a `functools.partial`
    reports `functools.py`, the defining module of its *type*, which made the
    gate refuse a legitimately pinned agent (#152 review).
    """
    while isinstance(agent, functools.partial):
        agent = agent.func
    source = getattr(agent, "__external_source__", None)        # a FreshPerGame wrapper (#247)
    if source is not None:
        return source
    namespace = getattr(agent, "__globals__", None)              # a plain function
    if namespace is None:
        bound = getattr(agent, "__func__", None)                 # a bound method
        namespace = getattr(bound, "__globals__", None)
    if namespace is None:
        call = getattr(type(agent), "__call__", None)            # a callable instance
        namespace = getattr(call, "__globals__", None)
    return namespace.get("__file__") if isinstance(namespace, dict) else None


def mismatched_sources(agents, pins):
    """Names in `agents` whose pin does not match the bytes of the file the
    agent was imported from (#152 review). A name with no pin is skipped;
    a pinned agent with no discoverable source counts as a mismatch."""
    bad = []
    for name, agent in agents.items():
        pin = pins.get(name)
        if not pin:
            continue
        source = _source_of(agent)
        if source is None or not os.path.isfile(source) or file_sha256(source) != pin:
            bad.append(name)
    return sorted(bad)


def _manifest_stems(manifest_path=MANIFEST_PATH):
    """The sorted filename stems the manifest expects to be fetched (#153)."""
    return sorted(manifest_pins(manifest_path))


def _default_warn(message):
    print(f"warning: {message}", file=sys.stderr)


class FreshPerGame:
    """A discovered external that plays every game on a freshly imported module (#247).

    The gate (`external_anchor_agents` / `rival_bench._gate_agents`) imports a
    fresh module per game; the evolve / genome_bench / `--designate` path keeps
    one callable per run and plays it across every game, so an external that
    keeps module-level state -- day counters, cached plans, memoised prices --
    started its second game with its first game's memory, and the gate and the
    ranking measured different opponents under one name.

    Two mechanisms, in order of preference:

    * `fresh()` -- `harness.evolve.opponent_record` calls it between games, so
      the import runs outside the sim's per-step timer (lonespear's numpy +
      scipy import costs ~0.4 s of a 1 s step) and a failure raises in the
      harness loop, where it stops the run, instead of inside the sim, where
      it would be scored as a 0-reward ERROR.
    * the step-0 fallback in `__call__` -- for a consumer that keeps the
      callable and never calls `fresh()`; it reloads inside the timer and its
      failure is only as loud as the sim makes it.

    Both re-check the file's sha256 against the bytes discovery verified, so a
    file edited on disk mid-run raises instead of being played (#133).

    kaggle_environments trims ``(observation, configuration)`` to a function's
    ``co_argcount``; an instance has no ``__code__``, so kaggle hands the
    wrapper both and `__call__` applies the same rule to the inner agent.
    `_source_of` reads the file off `__external_source__`, so pin
    verification (#152) still sees the real file.
    """

    def __init__(self, path, agent):
        self.__external_source__ = path
        self._sha = file_sha256(path)
        self._agent = agent          # the module discovery already imported
        self._used = False

    def fresh(self):
        """Re-import the verified file; returns self so a caller can chain."""
        if file_sha256(self.__external_source__) != self._sha:
            raise RuntimeError(
                f"external agent {self.__external_source__!r} changed on disk since it "
                "was verified; re-run python -m scripts.fetch_external_agents")
        self._agent = load_external_agent(self.__external_source__)
        self._used = False
        return self

    def __call__(self, *args, **kwargs):
        obs = args[0] if args else kwargs.get("obs")
        step = obs.get("step") if isinstance(obs, dict) else getattr(obs, "step", None)
        if step == 0 and self._used:
            self.fresh()
        self._used = True
        inner = self._agent
        if hasattr(inner, "__code__") and hasattr(inner.__code__, "co_argcount"):
            args = args[: inner.__code__.co_argcount]
        return inner(*args, **kwargs)


def discover_external_agents(directory=DEFAULT_DIR, warn=None):
    """Return ``{name: agent_callable}`` for every importable agent in `directory`.

    ``name`` is the filename stem. Only ``*.py`` files are considered -- the
    ``.meta.json`` license/attribution sidecars the fetch script writes
    alongside each download are ignored here (see
    ``scripts/fetch_external_agents.py``).
    Each agent is a `FreshPerGame` wrapper, so a consumer that keeps the callable for
    a whole run still plays a fresh module per game (#247).
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
            agents[name] = FreshPerGame(path, load_external_agent(path))
        except Exception as exc:  # a stranger's code -- anything can go wrong here
            # One malformed download never takes down a benchmark: the loader's
            # own message (no callable `agent`, or the import error) rides along.
            warn(f"external agent {fname!r} failed to load ({exc!r}); skipping")

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
                "python -m scripts.fetch_external_agents to repair it."
            )
            if not allow_partial:
                raise RuntimeError(message)
            warn(message)
        states = verify_pins(directory, manifest_path)
        mismatched = sorted(set(
            n for n, s in states.items() if s == "mismatch"
        ) | set(mismatched_sources(external, manifest_pins(manifest_path))))
        if mismatched:
            # Never downgraded by allow_partial: a short pool is a known-partial
            # pool, a mismatched file is code nobody reviewed (#152).
            raise RuntimeError(
                f"external agent(s) on disk do not match the manifest pin: "
                f"{', '.join(mismatched)}. Re-run python -m scripts.fetch_external_agents (it "
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


def external_anchor_paths(names=EXTERNAL_ANCHORS, directory=DEFAULT_DIR,
                          manifest_path=MANIFEST_PATH):
    """`{name: path}` for the gate anchors (#152), verifying every one of them.

    Missing, unpinned and mismatched are all refusals -- an ADR-0007 verdict
    is never measured against an external whose bytes the manifest does not
    vouch for. No partial pool, no warning: raise, naming each anchor and the
    command that repairs it.

    Nothing is imported here: the caller verifies once and then loads a file
    as often as it likes (`load_external_agent` per game, in the gate's hook).
    """
    states = verify_pins(directory, manifest_path)
    problems = {n: states.get(n, "missing") for n in names if states.get(n) != "ok"}
    if problems:
        detail = ", ".join(f"{n} ({s})" for n, s in problems.items())
        raise RuntimeError(
            f"gate anchors are not verified: {detail}. Run python -m scripts.fetch_external_agents "
            "(--pin for an unpinned entry) and commit the manifest; the gate never runs "
            "against an unverified external."
        )
    return {n: os.path.join(directory, n + ".py") for n in names}


def external_anchor_agents(names=EXTERNAL_ANCHORS, directory=DEFAULT_DIR,
                           manifest_path=MANIFEST_PATH, discover_fn=None):
    """One loaded agent per verified gate anchor, in `names` order (#152).

    `external_anchor_paths` performs the refusal; each verified path is then
    imported with `load_external_agent`. `discover_fn` is the injection seam
    for a caller that serves its own pool -- injected or loaded, the bytes the
    callable actually came from are re-checked against the pin below, so
    injection can never bypass verification.

    Each is a `FreshPerGame` wrapper: `--designate` keeps them for the whole
    ranking run and `opponent_record` reloads them between games (#247).
    """
    paths = external_anchor_paths(names, directory, manifest_path)
    if discover_fn is None:
        found = {}
        for name, path in paths.items():
            try:
                found[name] = FreshPerGame(path, load_external_agent(path))
            except Exception as exc:   # a stranger's code -- refuse, and say why
                raise RuntimeError(
                    f"gate anchor(s) failed to import: {name} ({exc!r}). The file verified "
                    "against its pin, so this is the agent's own code or a missing "
                    "dependency, not a fetch problem."
                ) from exc
    else:
        found = discover_fn()
    absent = [n for n in names if n not in found]
    if absent:
        raise RuntimeError(f"gate anchor(s) failed to import: {', '.join(absent)}")
    mismatched = mismatched_sources({n: found[n] for n in names}, manifest_pins(manifest_path))
    if mismatched:
        raise RuntimeError(
            f"external agent(s) on disk do not match the manifest pin: "
            f"{', '.join(mismatched)}. Re-run python -m scripts.fetch_external_agents (it "
            "refuses a mismatch); if the author published a new version you have "
            "checked, re-pin with --pin and commit the manifest."
        )
    return {n: found[n] for n in names}
