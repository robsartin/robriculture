"""Loader for locally-fetched external competitor agents (#78) -- measurement only.

`harness.external_pool.discover_external_agents` reads a gitignored local
directory (never committed) and returns opponent callables for measurement
tools. These tests exercise it against tmp_path fixtures only -- no network,
no dependency on a real `external_agents/` directory existing on disk, so the
suite behaves identically in CI, a clean clone, and any other machine.
"""

from __future__ import annotations

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
