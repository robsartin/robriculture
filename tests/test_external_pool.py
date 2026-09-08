"""Loader for locally-fetched external competitor agents (#78) -- measurement only.

`harness.external_pool.discover_external_agents` reads a gitignored local
directory (never committed) and returns opponent callables for measurement
tools. These tests exercise it against tmp_path fixtures only -- no network,
no dependency on a real `external_agents/` directory existing on disk, so the
suite behaves identically in CI, a clean clone, and any other machine.
"""

from __future__ import annotations

import hashlib
import json
import sys
import textwrap

from harness import external_pool


def test_discover_returns_empty_when_directory_is_absent(tmp_path):
    """A clean clone / CI / a machine that never ran the fetch script must all
    behave identically: no crash, just nothing to add (#78)."""
    missing = tmp_path / "does_not_exist"
    assert external_pool.discover_external_agents(str(missing)) == {}


def test_discover_returns_empty_for_an_empty_directory(tmp_path):
    assert external_pool.discover_external_agents(str(tmp_path)) == {}


def test_discover_loads_a_valid_agent_module(tmp_path):
    (tmp_path / "good_agent.py").write_text(textwrap.dedent(
        """
        def agent(obs, config=None):
            return {"farmer": ["PASS"], "hands": [], "market": []}
        """
    ))
    agents = external_pool.discover_external_agents(str(tmp_path))
    assert set(agents) == {"good_agent"}
    assert callable(agents["good_agent"])
    assert agents["good_agent"]({}, {}) == {"farmer": ["PASS"], "hands": [], "market": []}


def test_discover_skips_a_file_with_no_agent_callable(tmp_path):
    (tmp_path / "no_agent.py").write_text("x = 1\n")
    warnings = []
    agents = external_pool.discover_external_agents(str(tmp_path), warn=warnings.append)
    assert agents == {}
    assert any("no_agent" in w for w in warnings)


def test_discover_skips_a_file_that_fails_to_import(tmp_path):
    (tmp_path / "broken.py").write_text("def agent(:\n    pass\n")  # syntax error
    warnings = []
    agents = external_pool.discover_external_agents(str(tmp_path), warn=warnings.append)
    assert agents == {}
    assert any("broken" in w for w in warnings)
    # The loader registers the module in sys.modules *before* exec'ing it (to
    # satisfy slotted-dataclass annotation resolution, see the slots test
    # below) -- a failed import must not leave that placeholder registered
    # behind, or a later, unrelated import of the same stem could resolve
    # against a half-built stranger's module.
    assert "_external_agent_broken" not in sys.modules


def test_discover_skips_a_file_whose_agent_attribute_is_not_callable(tmp_path):
    (tmp_path / "weird.py").write_text("agent = 42\n")
    warnings = []
    agents = external_pool.discover_external_agents(str(tmp_path), warn=warnings.append)
    assert agents == {}
    assert any("weird" in w for w in warnings)


def test_discover_ignores_non_python_files(tmp_path):
    (tmp_path / "readme.txt").write_text("not code")
    (tmp_path / "some_agent.py.meta.json").write_text("{}")
    assert external_pool.discover_external_agents(str(tmp_path)) == {}


def test_discover_loads_an_agent_module_that_defines_a_slotted_dataclass(tmp_path):
    """A module-level `@dataclass(slots=True)` under `from __future__ import
    annotations` (PEP 563 -- annotations become strings) calls CPython's
    `_is_type`, which resolves those strings via `sys.modules[cls.__module__]`
    -- if the loader never registers the module there before exec'ing it, that
    lookup returns None and the whole import blows up with an unrelated
    AttributeError (#151, found by the real-network fetch of
    premaananda108_ecobot_v7, which hits exactly this: a slots=True frozen
    dataclass at module scope, under `from __future__ import annotations`)."""
    (tmp_path / "dataclass_agent.py").write_text(textwrap.dedent(
        """
        from __future__ import annotations
        from dataclasses import dataclass

        @dataclass(slots=True, frozen=True)
        class Config:
            hands: int = 8

        def agent(obs, config=None):
            return {"farmer": ["PASS"], "hands": [], "market": []}
        """
    ))
    warnings = []
    agents = external_pool.discover_external_agents(str(tmp_path), warn=warnings.append)
    assert warnings == []
    assert set(agents) == {"dataclass_agent"}


def test_discover_loads_multiple_agents_keyed_by_filename_stem(tmp_path):
    (tmp_path / "agent_a.py").write_text("def agent(obs, config=None):\n    return 'a'\n")
    (tmp_path / "agent_b.py").write_text("def agent(obs, config=None):\n    return 'b'\n")
    agents = external_pool.discover_external_agents(str(tmp_path))
    assert set(agents) == {"agent_a", "agent_b"}
    assert agents["agent_a"](None, None) == "a"
    assert agents["agent_b"](None, None) == "b"


def test_discover_uses_the_default_warn_when_none_is_given(tmp_path, capsys):
    (tmp_path / "no_agent.py").write_text("x = 1\n")
    external_pool.discover_external_agents(str(tmp_path))
    assert "no_agent" in capsys.readouterr().err


def test_default_dir_points_at_repo_root_external_agents():
    """Kept in sync with .gitignore and the fetch script's own default dest."""
    assert external_pool.DEFAULT_DIR.endswith("external_agents")


# --- resolve_opponents: one place that decides who a genome is scored against (#149) ---


def _stub(name):
    def agent(obs, config=None):
        return {"farmer": ["PASS"], "hands": [], "market": []}
    agent.__name__ = name
    return agent


def test_resolve_opponents_default_is_named_anchors_and_never_discovers():
    """The frozen comparability bar must not depend on what happens to be sitting
    in the gitignored external_agents/ directory, so discovery is not attempted."""
    called = []

    def fake_discover():
        called.append(True)
        return {"pilkwang": _stub("pilkwang")}

    agents = external_pool.resolve_opponents(
        ["meta_bot"], include_external=False,
        discover_fn=fake_discover, build=lambda names: {n: _stub(n) for n in names})

    assert set(agents) == {"meta_bot"}
    assert called == []


def test_resolve_opponents_merges_discovered_agents_when_included(tmp_path):
    manifest_path = _write_manifest(tmp_path, ["pilkwang"])

    agents = external_pool.resolve_opponents(
        ["meta_bot"], include_external=True,
        discover_fn=lambda: {"pilkwang": _stub("pilkwang")},
        build=lambda names: {n: _stub(n) for n in names},
        manifest_path=manifest_path)

    assert set(agents) == {"meta_bot", "pilkwang"}


def test_resolve_opponents_raises_when_external_requested_but_none_found():
    """Asking for external opponents and silently getting none is the dead-instrument
    failure: the run reports a clean number that was measured against the wrong pool
    entirely (#67, #127). Fail loudly instead -- external_agents/ is gitignored and
    is empty until scripts/fetch_external_agents.py has been run."""
    import pytest

    with pytest.raises(RuntimeError, match="fetch_external_agents"):
        external_pool.resolve_opponents(
            ["meta_bot"], include_external=True,
            discover_fn=lambda: {},
            build=lambda names: {n: _stub(n) for n in names})


# --- resolve_opponents: shortfall guard against a manifest that silently
# shrunk (#153) ---


def _write_manifest(tmp_path, stems):
    """A fixture manifest with the same shape as harness/external_agents.json,
    naming just the given filename stems -- never the real pool."""
    manifest = tmp_path / "fixture_manifest.json"
    entries = [{"name": stem, "dest_filename": f"{stem}.py"} for stem in stems]
    manifest.write_text(json.dumps({"agents": entries}))
    return str(manifest)


def test_resolve_opponents_raises_naming_missing_agents_when_pool_is_short_by_one(tmp_path):
    """The #133/#151 failure mode: a manifest entry silently fails to download
    and resolve_opponents must say exactly which one is missing, not just that
    the pool is nonempty."""
    import pytest

    manifest_path = _write_manifest(tmp_path, ["agent_a", "agent_b"])

    with pytest.raises(RuntimeError, match="agent_b"):
        external_pool.resolve_opponents(
            ["meta_bot"], include_external=True,
            discover_fn=lambda: {"agent_a": _stub("agent_a")},
            build=lambda names: {n: _stub(n) for n in names},
            manifest_path=manifest_path)


def test_resolve_opponents_warns_and_returns_partial_pool_when_allow_partial(tmp_path, capsys):
    """allow_partial=True is the explicit opt-out: the operator accepts a
    shortfall, so the loud raise becomes a loud warning instead, and the run
    proceeds against whatever was actually found (#153)."""
    manifest_path = _write_manifest(tmp_path, ["agent_a", "agent_b"])

    # Precondition: this pool really is short by one -- prove it the same way
    # the raise test does, before trusting that allow_partial changed anything.
    with __import__("pytest").raises(RuntimeError):
        external_pool.resolve_opponents(
            ["meta_bot"], include_external=True,
            discover_fn=lambda: {"agent_a": _stub("agent_a")},
            build=lambda names: {n: _stub(n) for n in names},
            manifest_path=manifest_path)

    agents = external_pool.resolve_opponents(
        ["meta_bot"], include_external=True, allow_partial=True,
        discover_fn=lambda: {"agent_a": _stub("agent_a")},
        build=lambda names: {n: _stub(n) for n in names},
        manifest_path=manifest_path)

    assert set(agents) == {"meta_bot", "agent_a"}
    err = capsys.readouterr().err
    assert "agent_b" in err


def test_resolve_opponents_passes_unchanged_when_pool_is_complete(tmp_path, capsys):
    """A pool that matches the manifest exactly must neither raise nor warn --
    the guard only fires on an actual shortfall (#153)."""
    manifest_path = _write_manifest(tmp_path, ["agent_a", "agent_b"])

    agents = external_pool.resolve_opponents(
        ["meta_bot"], include_external=True,
        discover_fn=lambda: {"agent_a": _stub("agent_a"), "agent_b": _stub("agent_b")},
        build=lambda names: {n: _stub(n) for n in names},
        manifest_path=manifest_path)

    assert set(agents) == {"meta_bot", "agent_a", "agent_b"}
    assert capsys.readouterr().err == ""


def test_resolve_opponents_includes_a_discovered_agent_absent_from_the_manifest(tmp_path):
    """An extra file on disk that the manifest never listed is not a shortfall
    -- it is merged in the same as any other discovered agent, matching what
    discover_external_agents already returns to its caller (#153)."""
    manifest_path = _write_manifest(tmp_path, ["agent_a"])

    agents = external_pool.resolve_opponents(
        ["meta_bot"], include_external=True,
        discover_fn=lambda: {"agent_a": _stub("agent_a"), "bonus_agent": _stub("bonus_agent")},
        build=lambda names: {n: _stub(n) for n in names},
        manifest_path=manifest_path)

    assert set(agents) == {"meta_bot", "agent_a", "bonus_agent"}


# --- pins (#152): a hash in the committed manifest makes the un-committed pool verifiable ---


def _write_pinned_manifest(tmp_path, pins):
    """A fixture manifest whose entries carry the given {stem: sha256-or-None}."""
    manifest = tmp_path / "pinned_manifest.json"
    entries = []
    for stem, pin in pins.items():
        entry = {"name": stem, "dest_filename": f"{stem}.py"}
        if pin is not None:
            entry["sha256"] = pin
        entries.append(entry)
    manifest.write_text(json.dumps({"agents": entries}))
    return str(manifest)


def _sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def test_external_anchors_are_the_five_declared_gate_anchors_in_order():
    assert external_pool.EXTERNAL_ANCHORS == (
        "pilkwang_structured_economic_policy",
        "lonespear_kaggriculture_v21",
        "premaananda108_ecobot_v7",
        "shashankjangid_agent_v1000_sovereign_prime",
        "madhur_sabherwal_hub_geometry_agent",
    )


def test_file_sha256_hashes_the_bytes_on_disk(tmp_path):
    p = tmp_path / "a.py"
    p.write_text("def agent(obs, config=None):\n    return {}\n")
    assert external_pool.file_sha256(str(p)) == _sha("def agent(obs, config=None):\n    return {}\n")


def test_manifest_pins_reads_a_pin_or_none_per_entry(tmp_path):
    manifest = _write_pinned_manifest(tmp_path, {"a": "0" * 64, "b": None})
    assert external_pool.manifest_pins(manifest) == {"a": "0" * 64, "b": None}


def test_verify_pins_reports_each_of_the_four_states(tmp_path):
    good = "def agent(obs, config=None):\n    return {}\n"
    (tmp_path / "ok.py").write_text(good)
    (tmp_path / "changed.py").write_text(good + "# edited\n")
    (tmp_path / "loose.py").write_text(good)
    manifest = _write_pinned_manifest(tmp_path, {
        "ok": _sha(good), "changed": _sha(good), "loose": None, "gone": _sha(good)})
    assert external_pool.verify_pins(str(tmp_path), manifest) == {
        "ok": "ok", "changed": "mismatch", "loose": "unpinned", "gone": "missing"}


def test_verify_pins_reports_missing_when_the_directory_is_absent(tmp_path):
    manifest = _write_pinned_manifest(tmp_path, {"a": "0" * 64})
    assert external_pool.verify_pins(str(tmp_path / "nope"), manifest) == {"a": "missing"}


# --- resolve_opponents + external_anchor_agents honour the pins (#152) ---

_GOOD = "def agent(obs, config=None):\n    return {'farmer': ['PASS'], 'hands': [], 'market': []}\n"


def test_resolve_opponents_raises_on_a_pin_mismatch_even_when_partial_is_allowed(tmp_path):
    """A short pool is a known-partial pool; a mismatched file is code nobody reviewed."""
    import pytest

    (tmp_path / "x.py").write_text(_GOOD + "# edited\n")
    manifest = _write_pinned_manifest(tmp_path, {"x": _sha(_GOOD)})
    with pytest.raises(RuntimeError, match="do not match the manifest pin.*x"):
        external_pool.resolve_opponents(
            ["meta_bot"], include_external=True, allow_partial=True,
            build=lambda names: {n: _stub(n) for n in names},
            manifest_path=manifest, directory=str(tmp_path))


def test_resolve_opponents_warns_and_merges_an_unpinned_agent(tmp_path):
    (tmp_path / "x.py").write_text(_GOOD)
    manifest = _write_pinned_manifest(tmp_path, {"x": None})
    warnings = []
    agents = external_pool.resolve_opponents(
        ["meta_bot"], include_external=True,
        build=lambda names: {n: _stub(n) for n in names},
        manifest_path=manifest, directory=str(tmp_path), warn=warnings.append)
    assert set(agents) == {"meta_bot", "x"}
    assert any("unpinned" in w and "x" in w and "--pin" in w for w in warnings)


def test_resolve_opponents_is_silent_when_every_pin_verifies(tmp_path):
    (tmp_path / "x.py").write_text(_GOOD)
    manifest = _write_pinned_manifest(tmp_path, {"x": _sha(_GOOD)})
    warnings = []
    agents = external_pool.resolve_opponents(
        ["meta_bot"], include_external=True,
        build=lambda names: {n: _stub(n) for n in names},
        manifest_path=manifest, directory=str(tmp_path), warn=warnings.append)
    assert set(agents) == {"meta_bot", "x"} and warnings == []


def test_external_anchor_agents_returns_the_named_agents_in_order_when_all_verify(tmp_path):
    for stem in ("b", "a"):
        (tmp_path / f"{stem}.py").write_text(_GOOD)
    manifest = _write_pinned_manifest(tmp_path, {"a": _sha(_GOOD), "b": _sha(_GOOD), "c": _sha(_GOOD)})
    agents = external_pool.external_anchor_agents(
        names=("b", "a"), directory=str(tmp_path), manifest_path=manifest)
    assert list(agents) == ["b", "a"] and all(callable(v) for v in agents.values())


def test_external_anchor_agents_raises_naming_each_unverified_anchor(tmp_path):
    """The gate never runs against an unverified external: missing, unpinned and
    mismatched are all refusals, named, with the command that repairs them."""
    import pytest

    (tmp_path / "loose.py").write_text(_GOOD)
    (tmp_path / "changed.py").write_text(_GOOD + "# edited\n")
    manifest = _write_pinned_manifest(tmp_path, {"loose": None, "changed": _sha(_GOOD)})
    with pytest.raises(RuntimeError) as exc:
        external_pool.external_anchor_agents(
            names=("loose", "changed", "absent"), directory=str(tmp_path), manifest_path=manifest)
    message = str(exc.value)
    assert "loose (unpinned)" in message and "changed (mismatch)" in message and "absent (missing)" in message
    assert "--pin" in message


def test_external_anchor_agents_raises_when_a_verified_file_does_not_import(tmp_path):
    import pytest

    broken = "def agent(:\n    pass\n"
    (tmp_path / "x.py").write_text(broken)
    manifest = _write_pinned_manifest(tmp_path, {"x": _sha(broken)})
    with pytest.raises(RuntimeError, match="failed to import.*x"):
        external_pool.external_anchor_agents(
            names=("x",), directory=str(tmp_path), manifest_path=manifest)


def test_resolve_opponents_verifies_the_file_each_discovered_agent_came_from(tmp_path):
    """The reviewer's scenario: discovery injected, `directory` left alone, a pinned
    name served from a tampered file elsewhere. The pin is checked against the bytes
    the agent was actually imported from, so it still raises."""
    import pytest

    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / "x.py").write_text(_GOOD + "# tampered\n")
    served = external_pool.discover_external_agents(str(elsewhere))
    manifest = _write_pinned_manifest(tmp_path, {"x": _sha(_GOOD)})
    with pytest.raises(RuntimeError, match="do not match the manifest pin.*x"):
        external_pool.resolve_opponents(
            ["meta_bot"], include_external=True, discover_fn=lambda: served,
            build=lambda names: {n: _stub(n) for n in names}, manifest_path=manifest)


def test_external_anchor_agents_verifies_the_file_each_anchor_was_imported_from(tmp_path):
    import pytest

    (tmp_path / "x.py").write_text(_GOOD)                      # verifies on disk ...
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / "x.py").write_text(_GOOD + "# tampered\n")    # ... but discovery serves this
    served = external_pool.discover_external_agents(str(elsewhere))
    manifest = _write_pinned_manifest(tmp_path, {"x": _sha(_GOOD)})
    with pytest.raises(RuntimeError, match="do not match the manifest pin.*x"):
        external_pool.external_anchor_agents(
            names=("x",), directory=str(tmp_path), manifest_path=manifest, discover_fn=lambda: served)


# --- a fresh callable per load, and a source read off the callable (#152 review) ---


def test_load_external_agent_returns_a_fresh_callable_each_call(tmp_path):
    """The gate serves a fresh callable per game, like the registry does, so
    state a competitor keeps across calls cannot leak between games."""
    (tmp_path / "x.py").write_text("calls = []\ndef agent(obs, config=None):\n    calls.append(1)\n    return len(calls)\n")
    first = external_pool.load_external_agent(str(tmp_path / "x.py"))
    second = external_pool.load_external_agent(str(tmp_path / "x.py"))
    assert first({}) == 1 and first({}) == 2
    assert second({}) == 1                        # its own module, its own state
    assert external_pool._source_of(second) == str(tmp_path / "x.py")


def test_source_of_reads_the_file_off_the_callable_not_the_module_registry(tmp_path):
    import functools

    (tmp_path / "x.py").write_text(_GOOD)
    agent = external_pool.load_external_agent(str(tmp_path / "x.py"))
    (tmp_path / "y.py").write_text(_GOOD)
    external_pool.load_external_agent(str(tmp_path / "y.py"))   # a later load must not redirect x
    assert external_pool._source_of(agent) == str(tmp_path / "x.py")
    assert external_pool._source_of(functools.partial(agent, config=None)) == str(tmp_path / "x.py")


def test_source_of_handles_a_callable_instance(tmp_path):
    (tmp_path / "x.py").write_text(
        "class _A:\n    def __call__(self, obs, config=None):\n        return {}\nagent = _A()\n")
    agent = external_pool.load_external_agent(str(tmp_path / "x.py"))
    assert external_pool._source_of(agent) == str(tmp_path / "x.py")


def test_mismatched_sources_does_not_flag_a_partial_over_a_pinned_file(tmp_path):
    import functools

    (tmp_path / "x.py").write_text(_GOOD)
    agent = external_pool.load_external_agent(str(tmp_path / "x.py"))
    pins = {"x": _sha(_GOOD)}
    assert external_pool.mismatched_sources({"x": functools.partial(agent, config=None)}, pins) == []


def test_external_anchor_paths_returns_the_verified_path_per_anchor_without_importing(tmp_path):
    """The gate verifies once and loads per game, so the path lookup must not
    import: a file that explodes on import still yields its path."""
    boom = "raise RuntimeError('imported!')\n"
    (tmp_path / "a.py").write_text(boom)
    manifest = _write_pinned_manifest(tmp_path, {"a": _sha(boom)})
    assert external_pool.external_anchor_paths(
        names=("a",), directory=str(tmp_path), manifest_path=manifest) == {
            "a": str(tmp_path / "a.py")}


def test_external_anchor_paths_refuses_an_unverified_anchor(tmp_path):
    import pytest

    manifest = _write_pinned_manifest(tmp_path, {"a": _sha(_GOOD)})
    with pytest.raises(RuntimeError, match="not verified.*a \\(missing\\)"):
        external_pool.external_anchor_paths(
            names=("a",), directory=str(tmp_path), manifest_path=manifest)


def test_load_external_agent_leaves_no_module_registered_when_the_file_is_bad(tmp_path):
    """The unique module name is registered before exec (slotted dataclasses);
    a failed load must not leave that placeholder behind. The old fixed name
    made this visible to `test_discover_skips_a_file_that_fails_to_import`;
    with a uuid in the name, only a prefix scan can still see it."""
    import pytest

    before = {m for m in sys.modules if m.startswith("_external_agent_")}
    (tmp_path / "broken.py").write_text("def agent(:\n    pass\n")   # syntax error
    (tmp_path / "no_agent.py").write_text("x = 1\n")
    with pytest.raises(SyntaxError):
        external_pool.load_external_agent(str(tmp_path / "broken.py"))
    with pytest.raises(ValueError, match="no callable module-level"):
        external_pool.load_external_agent(str(tmp_path / "no_agent.py"))
    leaked = {m for m in sys.modules if m.startswith("_external_agent_")} - before
    assert leaked == set()
