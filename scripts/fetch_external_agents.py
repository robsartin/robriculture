"""Fetch real external competitor agents for local measurement only (#78).

The owner decided against vendoring external agents into this repo at all
(ADR-0008 amendment, 2026-08-18): no third-party code is ever committed to
git. Instead this script reads ``harness/external_agents.json`` -- the single
source of truth for which agents to fetch, their licenses, and required
attribution -- and downloads each into a gitignored local directory
(``external_agents/`` by default). ``harness/external_pool.py`` then
discovers agents there for measurement tools that opt in
(``harness/genome_bench.py --include-external``); nothing else ever reads
this directory.

Two source kinds:

- ``github_file`` -- a single ``.py`` file, fetched via ``gh api`` (raw
  content).
- ``kaggle_kernel`` -- a Kaggle notebook, pulled via ``kaggle kernels pull``.
  Kaggle simulation-competition notebooks conventionally write their
  submittable agent through a ``%%writefile`` or ``%%agentfile`` cell magic;
  everything else in the notebook is narrative/plotting for the writeup. This
  script extracts *only* that tagged cell -- the rest of the notebook is
  never fetched into a runnable form.

Every download gets a ``<dest_filename>.meta.json`` sidecar recording its
name, license, attribution, and source URL, so the license obligation travels
with the file even though the file itself is gitignored.

Usage (from repo root, venv active, ``gh`` and ``kaggle`` CLIs authenticated):

    python -m scripts.fetch_external_agents
    python -m scripts.fetch_external_agents --dest /tmp/other_dir
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: The single source of truth for what gets fetched (#78).
MANIFEST_PATH = os.path.join(REPO_ROOT, "harness", "external_agents.json")

#: Kept in sync with .gitignore and harness/external_pool.py's DEFAULT_DIR.
DEST_DIR = os.path.join(REPO_ROOT, "external_agents")

#: Cell-magic markers that tag a Kaggle notebook's actual submittable agent.
_AGENT_CELL_MAGICS = ("%%agentfile", "%%writefile")


def load_manifest(path=MANIFEST_PATH):
    """The list of agent entries to fetch. Pure parsing, no I/O beyond the read."""
    with open(path) as fh:
        data = json.load(fh)
    return data["agents"]


def dest_path(entry, dest_dir=DEST_DIR):
    return os.path.join(dest_dir, entry["dest_filename"])


def meta_path(entry, dest_dir=DEST_DIR):
    return dest_path(entry, dest_dir) + ".meta.json"


def write_meta(entry, dest_dir=DEST_DIR):
    """Record license + attribution alongside the (gitignored) downloaded file."""
    meta = {
        "name": entry["name"],
        "source_type": entry["source_type"],
        "license": entry["license"],
        "attribution": entry["attribution"],
        "url": entry.get("url", ""),
    }
    os.makedirs(dest_dir, exist_ok=True)
    with open(meta_path(entry, dest_dir), "w") as fh:
        json.dump(meta, fh, indent=2)
        fh.write("\n")
    return meta_path(entry, dest_dir)


def extract_agent_cell(notebook, cell_file=None, cell_index=None):
    """Return the source of the notebook's tagged agent cell, magic line stripped.

    ``cell_index`` selects a cell by its position in the raw ``cells`` list
    directly, bypassing the ``%%agentfile``/``%%writefile`` tag search
    entirely -- for notebooks that never use that convention at all (#229;
    e.g. chaimaamatrag/kaggriculture-competition and the dianatofficial/
    paiky1995 kernels, whose submittable agent sits in a plain code cell with
    no cell magic). Given, it takes priority over ``cell_file`` and the whole
    magic-tag search below. There is no magic line to strip, so the cell's
    source is returned verbatim. Raises ``ValueError`` if the index is out of
    range or does not name a code cell.

    ``cell_file`` names which tagged cell to take, matched against the basename
    of the magic's target (so ``main.py`` matches both ``%%writefile main.py``
    and ``%%writefile /kaggle/working/main.py``). It is required for notebooks
    that tag more than one cell -- premaananda108's writes both a ``main.py``
    agent and an ``arena.py`` harness, and taking the wrong one silently
    vendors a file with no module-level ``agent`` (#151).

    Omitted, the first tagged cell wins, which is the behavior every manifest
    entry predating #151 relies on.

    The match target is taken as the first token after the magic (e.g.
    ``main.py`` in ``%%writefile main.py``); a flagged magic like
    ``%%writefile -a main.py`` yields ``-a`` instead, so it is never matched
    and the cell is skipped -- correctly failing loudly rather than silently
    vendoring the wrong cell.

    Raises ValueError if no cell is tagged ``%%agentfile``/``%%writefile``, or
    if ``cell_file`` matches none of them -- a notebook that doesn't follow the
    convention must fail loudly at fetch time rather than silently vendoring
    the wrong (narrative/plotting) cell.
    """
    if cell_index is not None:
        cells = notebook.get("cells", [])
        if not 0 <= cell_index < len(cells):
            raise ValueError(
                f"cell_index {cell_index} out of range for notebook with {len(cells)} cell(s)"
            )
        cell = cells[cell_index]
        if cell.get("cell_type") != "code":
            raise ValueError(
                f"cell_index {cell_index} is not a code cell (got {cell.get('cell_type')!r})"
            )
        raw = cell.get("source", [])
        return raw if isinstance(raw, str) else "".join(raw)

    for cell in notebook.get("cells", []):
        if cell.get("cell_type") != "code":
            continue
        # nbformat allows a code cell's `source` to be either a single string
        # or a list of line strings; normalize before splitting on lines.
        raw = cell.get("source", [])
        text = raw if isinstance(raw, str) else "".join(raw)
        lines = text.splitlines(keepends=True)
        if not lines:
            continue
        first = lines[0].strip()
        if not any(first.startswith(magic) for magic in _AGENT_CELL_MAGICS):
            continue
        if cell_file is not None:
            parts = first.split()
            target = parts[1] if len(parts) > 1 else ""
            if os.path.basename(target) != os.path.basename(cell_file):
                continue
        return "".join(lines[1:])
    if cell_file is not None:
        raise ValueError(
            f"no cell tagged %%agentfile or %%writefile targets {cell_file!r} -- "
            "cannot identify the submittable agent"
        )
    raise ValueError(
        "no cell tagged %%agentfile or %%writefile found in notebook -- "
        "cannot identify the submittable agent"
    )


def fetch_github_file(entry, dest_dir=DEST_DIR, runner=subprocess.run):
    """Fetch a single file's raw content from GitHub via `gh api`."""
    url = f"repos/{entry['repo']}/contents/{entry['path']}"
    # --method GET is required: gh api defaults to POST whenever -F/-f fields
    # are present, which 404s against the read-only contents endpoint.
    args = ["gh", "api", "--method", "GET", "-H", "Accept: application/vnd.github.raw", url]
    if entry.get("ref"):
        args += ["-F", f"ref={entry['ref']}"]
    result = runner(args, capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemExit(
            f"gh api failed for {entry['name']!r} (exit {result.returncode}): "
            f"{result.stderr.strip()}"
        )
    os.makedirs(dest_dir, exist_ok=True)
    path = dest_path(entry, dest_dir)
    with open(path, "w") as fh:
        fh.write(result.stdout)
    return path


def resolve_kaggle_cmd(executable=None, which=shutil.which):
    """Resolve the argv prefix for invoking the `kaggle` CLI (#92).

    A bare "kaggle" only resolves via ambient PATH -- and the invocation form
    this repo documents everywhere, ``.venv/bin/python script.py``, does not
    put the venv's ``bin/`` on PATH. So resolution is anchored to the
    *running interpreter* instead of the environment:

    1. A ``kaggle`` script next to ``sys.executable`` (how venvs install
       console-script entry points) -- found without touching PATH at all.
    2. ``shutil.which("kaggle")`` -- an explicit, one-time PATH lookup, for
       interpreters that aren't in a venv with a sibling script.
    3. ``[sys.executable, "-m", "kaggle"]`` -- the module entrypoint of the
       *same* interpreter, which needs no PATH or filesystem lookup at all.
       Verified locally that ``kernels pull`` works through this form too.
    """
    executable = executable if executable is not None else sys.executable
    sibling = os.path.join(os.path.dirname(executable), "kaggle")
    if os.path.isfile(sibling):
        return [sibling]
    found = which("kaggle")
    if found:
        return [found]
    return [executable, "-m", "kaggle"]


def fetch_kaggle_kernel(entry, dest_dir=DEST_DIR, runner=subprocess.run, work_dir=None):
    """Pull a Kaggle notebook, extract its tagged agent cell, write it as a .py file."""
    with tempfile.TemporaryDirectory(dir=work_dir) as tmp:
        args = resolve_kaggle_cmd() + ["kernels", "pull", entry["kernel_ref"], "-p", tmp]
        result = runner(args, capture_output=True, text=True)
        if result.returncode != 0:
            raise SystemExit(
                f"kaggle kernels pull failed for {entry['name']!r} "
                f"(exit {result.returncode}): {result.stderr.strip()}"
            )
        notebooks = [f for f in os.listdir(tmp) if f.endswith(".ipynb")]
        if not notebooks:
            raise SystemExit(
                f"kaggle kernels pull for {entry['name']!r} produced no .ipynb file"
            )
        with open(os.path.join(tmp, notebooks[0])) as fh:
            notebook = json.load(fh)
        source = extract_agent_cell(notebook, entry.get("cell_file"), entry.get("cell_index"))

    os.makedirs(dest_dir, exist_ok=True)
    path = dest_path(entry, dest_dir)
    with open(path, "w") as fh:
        fh.write(source)
    return path


def append_entrypoint_alias(path, entrypoint):
    """Append a module-level ``agent = <entrypoint>`` binding to a fetched file.

    ``harness.external_pool`` only ever loads a callable module-level
    ``agent`` -- that loader's fixed contract does not change for one
    manifest entry (#229). Some vendorable notebooks/files define their
    submittable callable under a non-standard name (``apex_agent``,
    ``my_agent``) or only via a parameterised factory
    (``make_farm_agent(sell_mode)``); the manifest's optional ``entrypoint``
    field names the expression the loaded module should bind to ``agent``,
    and this appends ``agent = <entrypoint>`` verbatim as the file's last
    line -- Python re-evaluates it at import time, same as any other
    module-level statement, so a factory call or a plain name both work.
    """
    with open(path, "a") as fh:
        fh.write(f"\n\nagent = {entrypoint}\n")


def fetch_one(entry, dest_dir=DEST_DIR, runner=subprocess.run, work_dir=None):
    """Fetch one manifest entry and write its license/attribution sidecar."""
    source_type = entry.get("source_type")
    if source_type == "github_file":
        path = fetch_github_file(entry, dest_dir, runner=runner)
    elif source_type == "kaggle_kernel":
        path = fetch_kaggle_kernel(entry, dest_dir, runner=runner, work_dir=work_dir)
    else:
        raise ValueError(f"unknown source_type {source_type!r} for agent {entry.get('name')!r}")
    entrypoint = entry.get("entrypoint")
    if entrypoint:
        append_entrypoint_alias(path, entrypoint)
    write_meta(entry, dest_dir)
    return path


def failure_summary(failed_names, total):
    """Build the exit-time summary line, naming exactly which agents are
    missing (#92) -- a bare "N of M failed" leaves a half-populated
    external_agents/ silently ambiguous about *which* competitors a later
    `genome_bench --include-external` run will quietly be missing.
    """
    names = ", ".join(failed_names)
    return f"{len(failed_names)} of {total} agent(s) failed to fetch: {names}"


def main(argv=None):  # pragma: no cover - orchestration, shells out to gh/kaggle
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--manifest", default=MANIFEST_PATH, help="path to the agent manifest")
    ap.add_argument("--dest", default=DEST_DIR, help="local (gitignored) directory to fetch into")
    args = ap.parse_args(argv)

    entries = load_manifest(args.manifest)
    failed_names = []
    for entry in entries:
        print(f"fetching {entry['name']} ({entry['source_type']}) ...")
        try:
            path = fetch_one(entry, dest_dir=args.dest)
        except (SystemExit, ValueError, OSError) as exc:
            print(f"  FAILED: {exc}", file=sys.stderr)
            failed_names.append(entry["name"])
            continue
        print(f"  -> {path}  [{entry['license']}]")

    if failed_names:
        print(failure_summary(failed_names, len(entries)), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
