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
    # A floor, not an exact count: this pool is explicitly growing (#151), so an
    # exact-count pin forces an unrelated bump on every future addition. >= 4
    # still catches a truncated/emptied manifest.
    assert len(entries) >= 4
    names = [e["name"] for e in entries]
    assert len(names) == len(set(names)), f"duplicate agent names: {names}"
    # A count floor alone would let any one of the four original entries be
    # deleted (leaving >= 4 via later additions) without the suite noticing.
    # Pin them by name too.
    assert {"pilkwang_structured_economic_policy", "madhur_sabherwal_hub_geometry_agent",
            "seyamalam_candidate_v6_adaptive_livestock",
            "alexandergremyakov_harvest_pulse_goose_dividend_v2"} <= set(names)
    for entry in entries:
        for key in ("name", "source_type", "license", "attribution", "dest_filename"):
            assert entry[key]


def test_manifest_excludes_the_rejected_candidate_v7_plus_variants():
    """The Seyamalam candidate_v7_public_v18/v19/v20/v21 blob-replayers were
    explicitly rejected (#78). Scoped to that repo, not a blanket substring
    search over every entry's path -- lonespear/kaggriculture's legitimately
    vendored `main_v21.py` (#229) coincidentally contains "v21" too, and a
    repo-agnostic check would misfire on it."""
    entries = fea.load_manifest()
    paths = [e.get("path", "") for e in entries if e.get("repo") == "Seyamalam/Kaggriculture"]
    assert not any("v7" in p or "v18" in p or "v19" in p or "v20" in p or "v21" in p for p in paths)


def test_manifest_pins_the_premaananda_agent_cell():
    # Its notebook tags both main.py (the agent) and arena.py (a harness);
    # without cell_file the fetch depends on cell order (#151).
    entries = fea.load_manifest()
    entry = next(e for e in entries if e["name"] == "premaananda108_ecobot_v7")
    assert entry["cell_file"] == "main.py"


def test_manifest_takes_only_the_three_measured_shashankjangid_rungs():
    # 57 agent files in that repo; v300 (~0.536 share) and v1000 (~0.677) were
    # chosen by measurement against DEFAULT_ANCHORS. v1500 measures within noise
    # of v1000 and must not be added alongside it. v9 (#229) is a third rung,
    # explicitly recorded (#151) as beating v100_sota despite its low number.
    entries = fea.load_manifest()
    paths = {e.get("path") for e in entries
             if e.get("repo") == "ShashankJangid/kaggriculture-agent"}
    assert paths == {"agent_v300_champion.py", "agent_v1000_sovereign_prime.py", "agent_v9.py"}


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


def test_extract_agent_cell_returns_the_named_cell_when_cell_file_is_given():
    # Two tagged cells: the agent is the SECOND one, so first-match would be wrong.
    notebook = {"cells": [
        {"cell_type": "code", "source": ["%%writefile arena.py\n", "ARENA = 1\n"]},
        {"cell_type": "code", "source": ["%%writefile main.py\n", "AGENT = 1\n"]},
    ]}
    assert fea.extract_agent_cell(notebook, "main.py") == "AGENT = 1\n"


def test_extract_agent_cell_matches_cell_file_against_a_path_prefixed_target():
    # Kaggle notebooks commonly write to /kaggle/working/main.py; an entry
    # should not have to know the author's directory prefix.
    notebook = {"cells": [
        {"cell_type": "code", "source": ["%%writefile /kaggle/working/main.py\n", "AGENT = 1\n"]},
    ]}
    assert fea.extract_agent_cell(notebook, "main.py") == "AGENT = 1\n"


def test_extract_agent_cell_falls_back_to_first_match_without_cell_file():
    # Pins the four existing manifest entries, none of which set cell_file.
    notebook = {"cells": [
        {"cell_type": "code", "source": ["%%writefile main.py\n", "FIRST = 1\n"]},
        {"cell_type": "code", "source": ["%%writefile arena.py\n", "SECOND = 2\n"]},
    ]}
    assert fea.extract_agent_cell(notebook) == "FIRST = 1\n"


def test_extract_agent_cell_raises_when_cell_file_matches_nothing():
    notebook = {"cells": [
        {"cell_type": "code", "source": ["%%writefile main.py\n", "AGENT = 1\n"]},
    ]}
    with pytest.raises(ValueError, match="typo.py"):
        fea.extract_agent_cell(notebook, "typo.py")


# --- extract_agent_cell: cell_index, for notebooks that never tag a cell with
# %%agentfile/%%writefile at all (#229). The 2026-09-06 survey found real
# candidates -- chaimaamatrag/kaggriculture-competition, dianatofficial's and
# paiky1995's notebooks -- whose submittable agent sits in a plain code cell
# with no cell magic; cell_file's tag-matching has nothing to match. cell_index
# selects a cell by its position in the raw `cells` list directly, bypassing
# the tag search, and returns it verbatim (there is no magic line to strip).

def test_extract_agent_cell_returns_the_cell_at_cell_index_with_no_tag_present():
    notebook = {"cells": [
        {"cell_type": "markdown", "source": ["# no tags anywhere\n"]},
        {"cell_type": "code", "source": ["def agent(obs):\n", "    return {}\n"]},
    ]}
    assert fea.extract_agent_cell(notebook, cell_index=1) == "def agent(obs):\n    return {}\n"


def test_extract_agent_cell_cell_index_ignores_untagged_first_lines():
    """Unlike the tag-search path, cell_index never strips a first line --
    there is no magic to strip when the notebook doesn't use the convention."""
    notebook = {"cells": [
        {"cell_type": "code", "source": ["x = 1\n", "def apex_agent(obs):\n", "    return x\n"]},
    ]}
    assert fea.extract_agent_cell(notebook, cell_index=0) == (
        "x = 1\ndef apex_agent(obs):\n    return x\n"
    )


def test_extract_agent_cell_raises_when_cell_index_is_out_of_range():
    notebook = {"cells": [{"cell_type": "code", "source": ["x = 1\n"]}]}
    with pytest.raises(ValueError, match="out of range"):
        fea.extract_agent_cell(notebook, cell_index=5)


def test_extract_agent_cell_raises_when_cell_index_targets_a_non_code_cell():
    notebook = {"cells": [{"cell_type": "markdown", "source": ["# hi\n"]}]}
    with pytest.raises(ValueError, match="not a code cell"):
        fea.extract_agent_cell(notebook, cell_index=0)


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


def test_fetch_kaggle_kernel_honours_cell_index_from_the_entry(tmp_path):
    """chaimaamatrag's notebook (#229) never tags a cell -- cell_index must
    reach extract_agent_cell so the agent cell can still be selected."""
    notebook = {"cells": [
        {"cell_type": "markdown", "source": ["# preamble\n"]},
        {"cell_type": "code", "source": ["def agent(obs):\n", "    return {}\n"]},
    ]}
    entry = {"name": "foo", "kernel_ref": "someone/kernel",
             "dest_filename": "foo.py", "cell_index": 1}
    path = fea.fetch_kaggle_kernel(entry, str(tmp_path), runner=_fake_kaggle_pull(notebook))
    assert (tmp_path / "foo.py").read_text() == "def agent(obs):\n    return {}\n"


def test_fetch_kaggle_kernel_honours_cell_file_from_the_entry(tmp_path):
    # Agent is the second tagged cell, so a fetch ignoring cell_file writes
    # the arena harness instead (#151).
    notebook = {"cells": [
        {"cell_type": "code", "source": ["%%writefile arena.py\n", "ARENA = 1\n"]},
        {"cell_type": "code", "source": ["%%writefile main.py\n", "AGENT = 1\n"]},
    ]}
    entry = {"name": "foo", "kernel_ref": "someone/kernel",
             "dest_filename": "foo.py", "cell_file": "main.py"}
    path = fea.fetch_kaggle_kernel(entry, str(tmp_path), runner=_fake_kaggle_pull(notebook))
    assert (tmp_path / "foo.py").read_text() == "AGENT = 1\n"


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


# --- resolve_kaggle_cmd: must not depend on ambient PATH (#92) ---
#
# The bug: the script shelled out to a bare "kaggle", which only resolves
# when the venv's bin/ happens to be on PATH -- and the documented
# ".venv/bin/python script.py" invocation form does NOT put it there. These
# tests pin that the resolved command is derived from sys.executable (or an
# explicit shutil.which lookup), never a bare string handed to PATH search,
# and that an empty PATH cannot change the outcome.

def test_resolve_kaggle_cmd_prefers_the_sibling_of_sys_executable(tmp_path):
    """A `kaggle` script living next to the interpreter (as venv installs it)
    must be found via sys.executable's directory, not via PATH search."""
    venv_bin = tmp_path / "bin"
    venv_bin.mkdir()
    fake_kaggle = venv_bin / "kaggle"
    fake_kaggle.write_text("#!/bin/sh\n")
    fake_kaggle.chmod(0o755)
    fake_python = venv_bin / "python"
    fake_python.write_text("")

    cmd = fea.resolve_kaggle_cmd(executable=str(fake_python), which=lambda name: None)
    assert cmd == [str(fake_kaggle)]


def test_resolve_kaggle_cmd_ignores_ambient_path_entirely(tmp_path, monkeypatch):
    """Wiping PATH must not change the resolution when the sibling script
    exists -- proof the lookup no longer depends on the environment."""
    venv_bin = tmp_path / "bin"
    venv_bin.mkdir()
    fake_kaggle = venv_bin / "kaggle"
    fake_kaggle.write_text("#!/bin/sh\n")
    fake_kaggle.chmod(0o755)
    fake_python = venv_bin / "python"
    fake_python.write_text("")

    monkeypatch.delenv("PATH", raising=False)
    cmd = fea.resolve_kaggle_cmd(executable=str(fake_python), which=lambda name: None)
    assert cmd == [str(fake_kaggle)]


def test_resolve_kaggle_cmd_falls_back_to_which_when_no_sibling_script(tmp_path):
    """No script next to the interpreter (e.g. a system python) -- fall back
    to an explicit shutil.which lookup rather than assuming PATH search
    happened implicitly inside subprocess."""
    empty_bin = tmp_path / "bin"
    empty_bin.mkdir()
    fake_python = empty_bin / "python"
    fake_python.write_text("")

    cmd = fea.resolve_kaggle_cmd(executable=str(fake_python), which=lambda name: "/usr/local/bin/kaggle")
    assert cmd == ["/usr/local/bin/kaggle"]


def test_resolve_kaggle_cmd_falls_back_to_module_invocation_as_last_resort(tmp_path):
    """Neither a sibling script nor a PATH hit -- invoke the kaggle package
    as a module of the *same* interpreter, which needs no PATH at all."""
    empty_bin = tmp_path / "bin"
    empty_bin.mkdir()
    fake_python = empty_bin / "python"
    fake_python.write_text("")

    cmd = fea.resolve_kaggle_cmd(executable=str(fake_python), which=lambda name: None)
    assert cmd == [str(fake_python), "-m", "kaggle"]


def test_fetch_kaggle_kernel_uses_resolved_command_not_bare_kaggle(tmp_path, monkeypatch):
    """End-to-end: fetch_kaggle_kernel must build its subprocess argv from
    resolve_kaggle_cmd, so a bare 'kaggle' never appears as argv[0]."""
    notebook = {"cells": [{"cell_type": "code", "source": ["%%agentfile\n", "x = 1\n"]}]}
    entry = {"name": "foo", "kernel_ref": "someone/kernel", "dest_filename": "foo.py"}
    monkeypatch.setattr(fea, "resolve_kaggle_cmd", lambda: ["/opt/venv/bin/kaggle"])

    seen = {}

    def runner(args, **kwargs):
        seen["args"] = args
        outdir = args[args.index("-p") + 1]
        with open(f"{outdir}/kernel.ipynb", "w") as fh:
            json.dump(notebook, fh)
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")

    fea.fetch_kaggle_kernel(entry, str(tmp_path), runner=runner)
    assert seen["args"][0] == "/opt/venv/bin/kaggle"
    assert seen["args"] != ["kaggle"]


# --- append_entrypoint_alias: bind a non-standard entrypoint to `agent` (#229) ---
#
# harness.external_pool only ever loads a callable module-level `agent` --
# that loader's contract does not change for one manifest entry. Some
# vendorable notebooks/files define their submittable callable under a
# different name (`apex_agent`) or only via a parameterised factory
# (`make_farm_agent(sell_mode)`); an optional manifest `entrypoint` field
# names the expression that should be bound to `agent`, appended as the last
# line of the fetched file.

def test_append_entrypoint_alias_appends_an_agent_binding(tmp_path):
    p = tmp_path / "foo.py"
    p.write_text("def apex_agent(obs):\n    return {}\n")
    fea.append_entrypoint_alias(str(p), "apex_agent")
    assert p.read_text() == "def apex_agent(obs):\n    return {}\n\n\nagent = apex_agent\n"


def test_append_entrypoint_alias_supports_a_factory_call_expression(tmp_path):
    p = tmp_path / "foo.py"
    p.write_text("def make_farm_agent(sell_mode):\n    return sell_mode\n")
    fea.append_entrypoint_alias(str(p), 'make_farm_agent("daily")')
    assert p.read_text().endswith('\n\nagent = make_farm_agent("daily")\n')


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


def test_fetch_one_applies_the_entrypoint_alias_when_the_entry_declares_one(tmp_path):
    """naisha123's file (#229) defines its submittable callable as `my_agent`,
    not `agent` -- fetch_one must append the alias so the downloaded file
    resolves under harness.external_pool's fixed `agent` contract."""
    entry = {
        "name": "foo", "source_type": "github_file", "repo": "someone/repo", "path": "a.py",
        "dest_filename": "foo.py", "license": "MIT", "attribution": "attr", "url": "https://x",
        "entrypoint": "my_agent",
    }
    fea.fetch_one(entry, str(tmp_path), runner=_runner(stdout="def my_agent(obs):\n    pass\n"))
    assert (tmp_path / "foo.py").read_text() == (
        "def my_agent(obs):\n    pass\n\n\nagent = my_agent\n"
    )


def test_fetch_one_does_not_append_anything_when_no_entrypoint_is_declared(tmp_path):
    entry = {
        "name": "foo", "source_type": "github_file", "repo": "someone/repo", "path": "a.py",
        "dest_filename": "foo.py", "license": "MIT", "attribution": "attr", "url": "https://x",
    }
    fea.fetch_one(entry, str(tmp_path), runner=_runner(stdout="def agent(obs):\n    pass\n"))
    assert (tmp_path / "foo.py").read_text() == "def agent(obs):\n    pass\n"


# --- failure_summary: names the missing agents, not just a count (#92) ---

def test_failure_summary_names_each_failed_agent():
    """A bare '2 of 4 failed' leaves an operator unable to tell which
    competitors are missing from a half-populated external_agents/ without
    re-reading the whole log; the summary must name them."""
    msg = fea.failure_summary(["pilkwang_structured_economic_policy", "alexandergremyakov_harvest_pulse_goose_dividend_v2"], 4)
    assert msg == (
        "2 of 4 agent(s) failed to fetch: "
        "pilkwang_structured_economic_policy, alexandergremyakov_harvest_pulse_goose_dividend_v2"
    )


def test_failure_summary_reports_zero_when_the_failed_list_is_empty():
    assert fea.failure_summary([], 4) == "0 of 4 agent(s) failed to fetch: "
