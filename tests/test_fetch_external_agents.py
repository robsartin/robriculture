"""Unit tests for scripts/fetch_external_agents.py (#78).

The fetch script reads harness/external_agents.json (the single source of
truth for which external agents to download) and pulls each into a gitignored
local directory for measurement only. Every network-touching call is
exercised here with an injected fake `runner` -- nothing touches the real
`gh` or `kaggle` CLIs, or the network.
"""

from __future__ import annotations

import json
import types

import pytest

from scripts import fetch_external_agents as fea


def _runner(returncode=0, stdout="", stderr="", side_effect=None):
    def run(args, **kwargs):
        if side_effect is not None:
            side_effect(args)
        return types.SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)
    return run


# --- the real manifest, as a reproducibility/regression pin ---

def test_load_manifest_reads_the_committed_manifest():
    entries = fea.load_manifest()
    assert len(entries) == 4
    for entry in entries:
        for key in ("name", "source_type", "license", "attribution", "dest_filename"):
            assert entry[key]


def test_manifest_excludes_the_rejected_candidate_v7_plus_variants():
    """The v7_public_v18/v19/v20/v21 blob-replayers were explicitly rejected (#78)."""
    entries = fea.load_manifest()
    paths = [e.get("path", "") for e in entries]
    assert not any("v7" in p or "v18" in p or "v19" in p or "v20" in p or "v21" in p for p in paths)


# --- load_manifest: pure parsing ---

def test_load_manifest_reads_the_agents_list(tmp_path):
    p = tmp_path / "manifest.json"
    p.write_text(json.dumps({"agents": [{"name": "x"}]}))
    assert fea.load_manifest(str(p)) == [{"name": "x"}]


# --- dest_path / meta_path ---

def test_dest_path_joins_dest_dir_and_filename():
    entry = {"dest_filename": "foo.py"}
    assert fea.dest_path(entry, "/tmp/out") == "/tmp/out/foo.py"


def test_meta_path_appends_meta_json_suffix():
    entry = {"dest_filename": "foo.py"}
    assert fea.meta_path(entry, "/tmp/out") == "/tmp/out/foo.py.meta.json"


def test_write_meta_records_license_and_attribution(tmp_path):
    entry = {
        "name": "foo", "dest_filename": "foo.py", "source_type": "github_file",
        "license": "MIT", "attribution": "Someone, MIT License.", "url": "https://example.com",
    }
    fea.write_meta(entry, str(tmp_path))
    saved = json.loads((tmp_path / "foo.py.meta.json").read_text())
    assert saved["license"] == "MIT"
    assert saved["attribution"] == "Someone, MIT License."
    assert saved["name"] == "foo"


# --- extract_agent_cell: pure notebook-JSON parsing ---

def test_extract_agent_cell_strips_the_agentfile_magic_line():
    notebook = {"cells": [
        {"cell_type": "markdown", "source": ["# hello\n"]},
        {"cell_type": "code", "source": ["%%agentfile\n", "def agent(obs):\n", "    return {}\n"]},
    ]}
    assert fea.extract_agent_cell(notebook) == "def agent(obs):\n    return {}\n"


def test_extract_agent_cell_strips_the_writefile_magic_line():
    notebook = {"cells": [
        {"cell_type": "code", "source": ["%%writefile /kaggle/working/main.py\n", "import math\n"]},
    ]}
    assert fea.extract_agent_cell(notebook) == "import math\n"


def test_extract_agent_cell_handles_source_stored_as_a_single_string():
    """nbformat allows a code cell's `source` as either a list of lines or one
    plain string; real kaggle kernels pull downloads use the latter (#78)."""
    notebook = {"cells": [
        {"cell_type": "code", "source": "%%agentfile\ndef agent(obs):\n    pass\n"},
    ]}
    assert fea.extract_agent_cell(notebook) == "def agent(obs):\n    pass\n"


def test_extract_agent_cell_ignores_non_code_cells():
    notebook = {"cells": [
        {"cell_type": "markdown", "source": ["%%agentfile looks like this in prose\n"]},
        {"cell_type": "code", "source": ["%%writefile main.py\n", "x = 1\n"]},
    ]}
    assert fea.extract_agent_cell(notebook) == "x = 1\n"


def test_extract_agent_cell_skips_empty_code_cells():
    notebook = {"cells": [
        {"cell_type": "code", "source": []},
        {"cell_type": "code", "source": ["%%agentfile\n", "y = 2\n"]},
    ]}
    assert fea.extract_agent_cell(notebook) == "y = 2\n"


def test_extract_agent_cell_raises_when_no_tagged_cell_is_present():
    notebook = {"cells": [{"cell_type": "code", "source": ["x = 1\n"]}]}
    with pytest.raises(ValueError, match="agentfile"):
        fea.extract_agent_cell(notebook)


# --- fetch_github_file: DI over `runner` ---

def test_fetch_github_file_writes_the_raw_content(tmp_path):
    entry = {
        "name": "foo", "repo": "someone/repo", "path": "src/agent.py", "ref": "main",
        "dest_filename": "foo.py",
    }
    path = fea.fetch_github_file(entry, str(tmp_path), runner=_runner(stdout="def agent(obs):\n    pass\n"))
    assert path == str(tmp_path / "foo.py")
    assert (tmp_path / "foo.py").read_text() == "def agent(obs):\n    pass\n"


def test_fetch_github_file_command_includes_the_ref(tmp_path):
    seen = {}
    entry = {"name": "foo", "repo": "someone/repo", "path": "src/agent.py", "ref": "main", "dest_filename": "foo.py"}
    fea.fetch_github_file(entry, str(tmp_path), runner=_runner(side_effect=lambda args: seen.setdefault("args", args)))
    assert "repos/someone/repo/contents/src/agent.py" in seen["args"]
    assert "ref=main" in seen["args"]


def test_fetch_github_file_raises_on_a_nonzero_exit(tmp_path):
    entry = {"name": "foo", "repo": "someone/repo", "path": "src/agent.py", "dest_filename": "foo.py"}
    with pytest.raises(SystemExit, match="gh api"):
        fea.fetch_github_file(entry, str(tmp_path), runner=_runner(returncode=1, stderr="not found"))


# --- fetch_kaggle_kernel: DI over `runner`, which simulates `kaggle kernels pull`'s
# side effect of writing a .ipynb into the -p directory ---

def _fake_kaggle_pull(notebook, filename="kernel.ipynb"):
    def runner(args, **kwargs):
        outdir = args[args.index("-p") + 1]
        with open(f"{outdir}/{filename}", "w") as fh:
            json.dump(notebook, fh)
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")
    return runner


def test_fetch_kaggle_kernel_extracts_the_agent_cell(tmp_path):
    notebook = {"cells": [{"cell_type": "code", "source": ["%%agentfile\n", "def agent(obs):\n", "    pass\n"]}]}
    entry = {"name": "foo", "kernel_ref": "someone/kernel", "dest_filename": "foo.py"}
    path = fea.fetch_kaggle_kernel(entry, str(tmp_path), runner=_fake_kaggle_pull(notebook))
    assert path == str(tmp_path / "foo.py")
    assert (tmp_path / "foo.py").read_text() == "def agent(obs):\n    pass\n"


def test_fetch_kaggle_kernel_raises_on_a_nonzero_exit(tmp_path):
    entry = {"name": "foo", "kernel_ref": "someone/kernel", "dest_filename": "foo.py"}
    with pytest.raises(SystemExit, match="kaggle kernels pull"):
        fea.fetch_kaggle_kernel(entry, str(tmp_path), runner=_runner(returncode=1, stderr="404"))


def test_fetch_kaggle_kernel_raises_when_no_ipynb_is_produced(tmp_path):
    entry = {"name": "foo", "kernel_ref": "someone/kernel", "dest_filename": "foo.py"}

    def runner(args, **kwargs):
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")

    with pytest.raises(SystemExit, match="no .ipynb"):
        fea.fetch_kaggle_kernel(entry, str(tmp_path), runner=runner)


# --- fetch_one: dispatch + meta sidecar ---

def test_fetch_one_dispatches_github_file_and_writes_meta(tmp_path):
    entry = {
        "name": "foo", "source_type": "github_file", "repo": "someone/repo", "path": "a.py",
        "dest_filename": "foo.py", "license": "MIT", "attribution": "attr", "url": "https://x",
    }
    fea.fetch_one(entry, str(tmp_path), runner=_runner(stdout="CODE"))
    assert (tmp_path / "foo.py").read_text() == "CODE"
    assert (tmp_path / "foo.py.meta.json").exists()


def test_fetch_one_dispatches_kaggle_kernel_and_writes_meta(tmp_path):
    notebook = {"cells": [{"cell_type": "code", "source": ["%%agentfile\n", "x = 1\n"]}]}
    entry = {
        "name": "foo", "source_type": "kaggle_kernel", "kernel_ref": "someone/kernel",
        "dest_filename": "foo.py", "license": "Apache-2.0", "attribution": "attr", "url": "https://x",
    }
    fea.fetch_one(entry, str(tmp_path), runner=_fake_kaggle_pull(notebook))
    assert (tmp_path / "foo.py").read_text() == "x = 1\n"
    assert (tmp_path / "foo.py.meta.json").exists()


def test_fetch_one_raises_on_an_unknown_source_type(tmp_path):
    entry = {"name": "foo", "source_type": "carrier_pigeon", "dest_filename": "foo.py"}
    with pytest.raises(ValueError, match="carrier_pigeon"):
        fea.fetch_one(entry, str(tmp_path))
