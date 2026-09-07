# Pinned External Anchors Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let hash-pinned external competitor agents serve as gate anchors (paired non-regression), ranking opponents and opt-in evolution anchors, and record the decision as ADR amendments (#152).

**Architecture:** `harness/external_pool.py` gains the pin verification and the declared `EXTERNAL_ANCHORS` loader; `scripts/fetch_external_agents.py` gains verification on fetch and `--pin`; `harness/rival_bench.criterion` gains a third, paired limb; `harness/promotion` and `harness/evolve` consume the loader; two ADR amendments and the docstrings that state the old rule are corrected. Spec: `docs/superpowers/specs/2026-09-07-external-anchors-design.md`.

**Tech Stack:** Python 3.12 in `.venv` (`.venv/bin/python`, never bare `python3`), pytest, kaggle-environments 1.32.7 (pinned), `gh` CLI, `kaggle` CLI at `.venv/bin/kaggle`.

## Global Constraints

- Work in the worktree `/Users/sartin/code/rb-152`, branch `152-external-anchors`. `.venv` and `external_agents` there are symlinks into the main checkout; never `git add` either. **Stage by explicit path; never `git add -A`.**
- Pure TDD: write the test, **run it and observe the failure for the right reason**, then the minimum code, then green, then commit. Reports state what the red run actually said.
- No third-party code is ever committed (ADR-0005/ADR-0008). Only `harness/external_agents.json` (the manifest) changes; `external_agents/` stays gitignored.
- `EXTERNAL_ANCHORS`, verbatim and in this order: `pilkwang_structured_economic_policy`, `lonespear_kaggriculture_v21`, `premaananda108_ecobot_v7`, `shashankjangid_agent_v1000_sovereign_prime`, `madhur_sabherwal_hub_geometry_agent`.
- A pin is the sha256 of the file **as written to disk** (after `extract_agent_cell` and after `append_entrypoint_alias`), 64 lowercase hex. A `github_file` pin also rewrites `ref` to the 40-hex commit fetched.
- A hash **mismatch always raises**; `allow_partial` never covers it. `unpinned` is a warning for measurement and an error for the gate.
- The gate's external limb: for each external anchor, contender `wins >= champion wins` on the **same seeds** in the same run; ties are not wins; rows on different seeds raise `ValueError`. With no pairs the verdict is exactly today's.
- Live games run under `ROBRICULTURE_STRICT=1`. Fresh seeds for the baseline record: **848-863**. Long commands run **blocking** (never backgrounded by a subagent).
- Commit messages end with `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.
- Test names describe behaviour (`test_<what>_when_<condition>` style used in this repo); every test in `tests/`.

---

### Task 1: Pins in `harness/external_pool.py` — `file_sha256`, `manifest_pins`, `verify_pins`, `EXTERNAL_ANCHORS`

**Files:**
- Modify: `harness/external_pool.py` (module constants after `MANIFEST_PATH`; `_manifest_stems` becomes a thin wrapper)
- Test: `tests/test_external_pool.py`

**Interfaces:**
- Consumes: `MANIFEST_PATH`, `DEFAULT_DIR` (existing).
- Produces: `EXTERNAL_ANCHORS: tuple[str, ...]`; `file_sha256(path) -> str`; `manifest_pins(manifest_path=MANIFEST_PATH) -> dict[str, str | None]` (filename stem → pin or None); `verify_pins(directory=DEFAULT_DIR, manifest_path=MANIFEST_PATH) -> dict[str, str]` (stem → `"ok" | "unpinned" | "mismatch" | "missing"`, one key per manifest entry).

- [ ] **Step 1: Write the failing tests** (append to `tests/test_external_pool.py`; the file already has `_write_manifest` and `_stub`)

```python
# --- pins (#152): a hash in the committed manifest makes the un-committed pool verifiable ---

import hashlib


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
```

- [ ] **Step 2: Run the tests and observe them fail**

Run: `.venv/bin/python -m pytest tests/test_external_pool.py -q -k "external_anchors or file_sha256 or manifest_pins or verify_pins"`
Expected: 5 failures, each `AttributeError: module 'harness.external_pool' has no attribute ...`.

- [ ] **Step 3: Implement** (in `harness/external_pool.py`; add `import hashlib` to the imports, and the block below after `MANIFEST_PATH`)

```python
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
```

and replace the body of `_manifest_stems` with:

```python
def _manifest_stems(manifest_path=MANIFEST_PATH):
    """The sorted filename stems the manifest expects to be fetched (#153)."""
    return sorted(manifest_pins(manifest_path))
```

- [ ] **Step 4: Run the tests and observe them pass**

Run: `.venv/bin/python -m pytest tests/test_external_pool.py -q`
Expected: all pass (the existing `_manifest_stems` callers included).

- [ ] **Step 5: Commit**

```bash
git add harness/external_pool.py tests/test_external_pool.py
git commit -m "external_pool: sha256 pins and the declared EXTERNAL_ANCHORS (#152)

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 2: `resolve_opponents` verifies pins; `external_anchor_agents` is the gate's loader

**Files:**
- Modify: `harness/external_pool.py` (`resolve_opponents`; new `external_anchor_agents`)
- Test: `tests/test_external_pool.py`

**Interfaces:**
- Consumes: Task 1's `verify_pins`, `EXTERNAL_ANCHORS`, `discover_external_agents`.
- Produces: `resolve_opponents(anchor_names, include_external=False, discover_fn=None, build=None, allow_partial=False, manifest_path=MANIFEST_PATH, warn=None, directory=DEFAULT_DIR)` — new keyword `directory`; raises `RuntimeError` on any `"mismatch"` regardless of `allow_partial`; warns and merges `"unpinned"` agents. `external_anchor_agents(names=EXTERNAL_ANCHORS, directory=DEFAULT_DIR, manifest_path=MANIFEST_PATH, discover_fn=None) -> dict[str, callable]` — raises `RuntimeError` if any name is missing, unpinned or mismatched (or fails to import); returns exactly the named agents in order.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_external_pool.py`)

```python
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
```

- [ ] **Step 2: Run the tests and observe them fail**

Run: `.venv/bin/python -m pytest tests/test_external_pool.py -q -k "pin_mismatch or unpinned_agent or every_pin_verifies or external_anchor_agents"`
Expected: the three `resolve_opponents` tests fail with `TypeError: ... unexpected keyword argument 'directory'`; the three `external_anchor_agents` tests fail with `AttributeError`.

- [ ] **Step 3: Implement.** Change `resolve_opponents`'s signature to add `directory=DEFAULT_DIR` as the last keyword, and replace its `if include_external:` block with:

```python
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
```

Add the gate loader after `resolve_opponents`:

```python
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
```

- [ ] **Step 4: Run the tests and observe them pass**

Run: `.venv/bin/python -m pytest tests/test_external_pool.py tests/test_genome_bench.py tests/test_evolve.py -q`
Expected: all pass (the existing `resolve_opponents` tests pass their fixture manifests, whose stems are not on disk under `DEFAULT_DIR`, so they read `"missing"` and are untouched by the new checks).

- [ ] **Step 5: Commit**

```bash
git add harness/external_pool.py tests/test_external_pool.py
git commit -m "external_pool: verify pins in resolve_opponents; external_anchor_agents for the gate (#152)

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 3: The fetch script verifies pins and can write them (`--pin`)

**Files:**
- Modify: `scripts/fetch_external_agents.py` (`fetch_one`; new `verify_pin`, `read_manifest`, `save_manifest`, `pin_entries`, `resolve_commit_sha`; `main` gains `--pin`)
- Test: `tests/test_fetch_external_agents.py`

**Interfaces:**
- Consumes: Task 1's `harness.external_pool.file_sha256`.
- Produces: `verify_pin(entry, path) -> str | None` (raises `SystemExit`, removes the file and its `.meta.json`, on mismatch; `None` when unpinned); `read_manifest(path=MANIFEST_PATH) -> dict` (the whole document, `_comment` included); `save_manifest(path, document) -> None` (2-space indent, trailing newline); `pin_entries(entries, hashes, resolved_refs=None) -> list[dict]` (pure); `resolve_commit_sha(entry, runner=subprocess.run) -> str` (40-hex).

- [ ] **Step 1: Write the failing tests** (append to `tests/test_fetch_external_agents.py`)

```python
# --- pins (#152): verify on fetch, and --pin writes the manifest ---

import hashlib
import os
import re


def _sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def test_fetch_one_passes_a_pinned_entry_whose_bytes_match(tmp_path):
    body = "def agent(obs):\n    pass\n"
    entry = {"name": "foo", "source_type": "github_file", "repo": "r/r", "path": "a.py",
             "license": "MIT", "attribution": "x", "dest_filename": "foo.py", "sha256": _sha(body)}
    path = fea.fetch_one(entry, str(tmp_path), runner=_runner(stdout=body))
    assert (tmp_path / "foo.py").read_text() == body
    assert os.path.exists(path + ".meta.json")


def test_fetch_one_removes_the_file_and_raises_on_a_pin_mismatch(tmp_path):
    body = "def agent(obs):\n    pass\n"
    entry = {"name": "foo", "source_type": "github_file", "repo": "r/r", "path": "a.py",
             "license": "MIT", "attribution": "x", "dest_filename": "foo.py", "sha256": _sha("other")}
    with pytest.raises(SystemExit) as exc:
        fea.fetch_one(entry, str(tmp_path), runner=_runner(stdout=body))
    message = str(exc.value)
    assert _sha(body) in message and _sha("other") in message and "--pin" in message
    assert not (tmp_path / "foo.py").exists()
    assert not (tmp_path / "foo.py.meta.json").exists()


def test_fetch_one_pins_the_bytes_after_the_entrypoint_alias(tmp_path):
    """The pin is over the file as written -- alias line included -- so the
    bytes the loader imports are the bytes that were pinned."""
    body = "def my_agent(obs):\n    pass\n"
    aliased = body + "\n# entrypoint alias appended by scripts/fetch_external_agents.py\nagent = my_agent\n"
    entry = {"name": "foo", "source_type": "github_file", "repo": "r/r", "path": "a.py",
             "license": "MIT", "attribution": "x", "dest_filename": "foo.py",
             "entrypoint": "my_agent", "sha256": _sha(aliased)}
    fea.fetch_one(entry, str(tmp_path), runner=_runner(stdout=body))
    assert (tmp_path / "foo.py").read_text() == aliased


def test_fetch_one_skips_verification_for_an_unpinned_entry(tmp_path):
    entry = {"name": "foo", "source_type": "github_file", "repo": "r/r", "path": "a.py",
             "license": "MIT", "attribution": "x", "dest_filename": "foo.py"}
    fea.fetch_one(entry, str(tmp_path), runner=_runner(stdout="x = 1\n"))
    assert (tmp_path / "foo.py").exists()


def test_pin_entries_fills_only_unpinned_entries_and_only_branch_refs():
    entries = [
        {"name": "a", "source_type": "github_file", "ref": "main"},
        {"name": "b", "source_type": "github_file", "ref": "main", "sha256": "1" * 64},
        {"name": "c", "source_type": "kaggle_kernel", "kernel_ref": "u/k"},
        {"name": "d", "source_type": "github_file", "ref": "f" * 40},
    ]
    out = fea.pin_entries(entries, {"a": "a" * 64, "b": "9" * 64, "c": "c" * 64, "d": "d" * 64},
                          {"a": "e" * 40, "b": "e" * 40, "d": "0" * 40})
    assert out[0] == {"name": "a", "source_type": "github_file", "ref": "e" * 40, "sha256": "a" * 64}
    assert out[1] == entries[1]                                   # already pinned: untouched
    assert out[2] == {"name": "c", "source_type": "kaggle_kernel", "kernel_ref": "u/k", "sha256": "c" * 64}
    assert out[3]["ref"] == "f" * 40 and out[3]["sha256"] == "d" * 64   # a commit ref stays
    assert entries[0] == {"name": "a", "source_type": "github_file", "ref": "main"}  # pure


def test_manifest_round_trips_comment_and_order(tmp_path):
    p = tmp_path / "m.json"
    doc = {"_comment": ["one", "two"], "agents": [{"name": "b"}, {"name": "a"}]}
    fea.save_manifest(str(p), doc)
    assert p.read_text().endswith("}\n") and '\n  "_comment"' in p.read_text()
    assert fea.read_manifest(str(p)) == doc


def test_resolve_commit_sha_returns_the_40_hex_sha_for_the_entry_ref():
    seen = {}
    sha = fea.resolve_commit_sha(
        {"name": "a", "repo": "r/r", "ref": "master"},
        runner=_runner(stdout="a" * 40 + "\n", side_effect=lambda args: seen.setdefault("args", args)))
    assert sha == "a" * 40
    assert "repos/r/r/commits/master" in seen["args"] and "--jq" in seen["args"]


def test_resolve_commit_sha_raises_on_a_nonzero_exit_or_a_non_sha():
    with pytest.raises(SystemExit, match="gh api"):
        fea.resolve_commit_sha({"name": "a", "repo": "r/r", "ref": "main"}, runner=_runner(returncode=1, stderr="no"))
    with pytest.raises(SystemExit, match="no commit sha"):
        fea.resolve_commit_sha({"name": "a", "repo": "r/r", "ref": "main"}, runner=_runner(stdout="not-a-sha\n"))
```

- [ ] **Step 2: Run the tests and observe them fail**

Run: `.venv/bin/python -m pytest tests/test_fetch_external_agents.py -q -k "pinned_entry or pin_mismatch or entrypoint_alias or unpinned_entry or pin_entries or round_trips or resolve_commit_sha"`
Expected: `test_fetch_one_passes_a_pinned_entry_whose_bytes_match` and `..._skips_verification...` PASS already (no verification exists yet); `..._removes_the_file_and_raises...` FAILS with `DID NOT RAISE`; `..._pins_the_bytes_after...` passes or fails on content only; the `pin_entries`, `save_manifest`/`read_manifest` and `resolve_commit_sha` tests fail with `AttributeError`. Record which of the eight were red.

- [ ] **Step 3: Implement.** In `scripts/fetch_external_agents.py` add `import re` and `from harness.external_pool import file_sha256` to the imports, then:

```python
_HEX40 = re.compile(r"^[0-9a-f]{40}$")


def read_manifest(path=MANIFEST_PATH):
    """The whole manifest document (`_comment` included), for writing back."""
    with open(path) as fh:
        return json.load(fh)


def save_manifest(path, document):
    """Write the manifest back in its committed shape: 2-space indent, trailing newline."""
    with open(path, "w") as fh:
        json.dump(document, fh, indent=2)
        fh.write("\n")


def verify_pin(entry, path):
    """Compare a pinned entry's fetched bytes to its manifest pin (#152).

    On a mismatch the file (and any stale sidecar) is removed before raising,
    so `discover_external_agents` never imports bytes the manifest does not
    vouch for. Returns the hash on a match, None when the entry is unpinned.
    """
    pinned = entry.get("sha256")
    if not pinned:
        return None
    got = file_sha256(path)
    if got != pinned:
        os.remove(path)
        sidecar = path + ".meta.json"
        if os.path.exists(sidecar):
            os.remove(sidecar)
        raise SystemExit(
            f"{entry['name']!r}: fetched sha256 {got} does not match the manifest pin "
            f"{pinned}; file removed. If the author published a new version you have "
            "checked, re-pin with: python -m scripts.fetch_external_agents --pin"
        )
    return got


def pin_entries(entries, hashes, resolved_refs=None):
    """Pure: copies of `entries` with `sha256` filled for unpinned names in
    `hashes`, and a `github_file` branch `ref` replaced by `resolved_refs[name]`.
    Already-pinned entries and 40-hex refs are returned unchanged."""
    resolved_refs = resolved_refs or {}
    out = []
    for entry in entries:
        e = dict(entry)
        name = e["name"]
        if not e.get("sha256") and name in hashes:
            e["sha256"] = hashes[name]
        if (e.get("source_type") == "github_file" and name in resolved_refs
                and not _HEX40.match(str(e.get("ref", "")))):
            e["ref"] = resolved_refs[name]
        out.append(e)
    return out


def resolve_commit_sha(entry, runner=subprocess.run):
    """The commit a `github_file` entry's `ref` points at right now, via `gh api`."""
    ref = entry.get("ref") or "HEAD"
    args = ["gh", "api", "--method", "GET", f"repos/{entry['repo']}/commits/{ref}", "--jq", ".sha"]
    result = runner(args, capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemExit(
            f"gh api failed resolving the commit for {entry['name']!r} "
            f"(exit {result.returncode}): {result.stderr.strip()}"
        )
    sha = result.stdout.strip()
    if not _HEX40.match(sha):
        raise SystemExit(f"gh api returned no commit sha for {entry['name']!r}: {sha!r}")
    return sha
```

In `fetch_one`, after the `append_entrypoint_alias` block and before `write_meta`, insert `verify_pin(entry, path)`.

In `main`, add the flag and the pin flow:

```python
    ap.add_argument("--pin", action="store_true",
                    help="after fetching, record each unpinned entry's sha256 (and, for a "
                         "github_file, the commit fetched) in the manifest (#152)")
    args = ap.parse_args(argv)

    document = read_manifest(args.manifest)
    entries = document["agents"]
    failed_names = []
    hashes, resolved_refs = {}, {}
    for entry in entries:
        print(f"fetching {entry['name']} ({entry['source_type']}) ...")
        fetch_entry = dict(entry)
        try:
            if (args.pin and entry.get("source_type") == "github_file"
                    and not entry.get("sha256") and not _HEX40.match(str(entry.get("ref", "")))):
                # Resolve first, then fetch at that commit, so the pinned ref and
                # the pinned bytes are the same snapshot.
                fetch_entry["ref"] = resolved_refs[entry["name"]] = resolve_commit_sha(entry)
            path = fetch_one(fetch_entry, dest_dir=args.dest)
        except (SystemExit, ValueError, OSError) as exc:
            print(f"  FAILED: {exc}", file=sys.stderr)
            failed_names.append(entry["name"])
            resolved_refs.pop(entry["name"], None)
            continue
        print(f"  -> {path}  [{entry['license']}]")
        if args.pin and not entry.get("sha256"):
            hashes[entry["name"]] = file_sha256(path)
            print(f"  pinned sha256={hashes[entry['name']]}")

    if args.pin and (hashes or resolved_refs):
        document["agents"] = pin_entries(entries, hashes, resolved_refs)
        save_manifest(args.manifest, document)
        print(f"manifest updated: {len(hashes)} entr{'y' if len(hashes) == 1 else 'ies'} pinned")

    if failed_names:
        print(failure_summary(failed_names, len(entries)), file=sys.stderr)
        return 1
    return 0
```

(`load_manifest` stays as is; `read_manifest` is the document-level reader.) Update the module docstring's usage block with `python -m scripts.fetch_external_agents --pin` and one sentence: a pinned entry is verified on every fetch and refused on a mismatch.

- [ ] **Step 4: Run the tests and observe them pass**

Run: `.venv/bin/python -m pytest tests/test_fetch_external_agents.py -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/fetch_external_agents.py tests/test_fetch_external_agents.py
git commit -m "fetch_external_agents: verify pins on fetch; --pin writes them to the manifest (#152)

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 4: Pin the real manifest

**Files:**
- Modify: `harness/external_agents.json` (via `--pin`; no hand edits)
- Test: `tests/test_fetch_external_agents.py`

**Interfaces:**
- Consumes: Task 3's `--pin`; Task 1's `EXTERNAL_ANCHORS`.
- Produces: a manifest where every entry carries `sha256` and every `github_file` entry a 40-hex `ref`.

This task touches the network (`gh` and `kaggle`, both authenticated on this machine; `kaggle` is `.venv/bin/kaggle`). Run every command **blocking**, from `/Users/sartin/code/rb-152`.

- [ ] **Step 1: Write the failing manifest test** (append to `tests/test_fetch_external_agents.py`)

```python
def test_every_external_anchor_is_pinned_in_the_committed_manifest():
    """The gate never loads an unpinned anchor (#152): each EXTERNAL_ANCHOR has a
    64-hex sha256, and a github_file anchor's ref is the 40-hex commit fetched."""
    from harness.external_pool import EXTERNAL_ANCHORS

    entries = {e["dest_filename"][:-3]: e for e in fea.load_manifest()}
    for name in EXTERNAL_ANCHORS:
        entry = entries[name]
        assert re.fullmatch(r"[0-9a-f]{64}", entry.get("sha256", "")), name
        if entry["source_type"] == "github_file":
            assert re.fullmatch(r"[0-9a-f]{40}", entry["ref"]), name
```

- [ ] **Step 2: Run it and observe it fail**

Run: `.venv/bin/python -m pytest tests/test_fetch_external_agents.py -q -k every_external_anchor_is_pinned`
Expected: FAIL with `AssertionError: pilkwang_structured_economic_policy` (no `sha256` yet).

- [ ] **Step 3: Snapshot what is on disk, then pin**

```bash
shasum -a 256 external_agents/*.py > /private/tmp/claude-501/-Users-sartin/2195f188-57a5-4834-a6b9-acc4ec519961/scratchpad/152-before.txt
PATH="$PWD/.venv/bin:$PATH" .venv/bin/python -m scripts.fetch_external_agents --pin
shasum -a 256 external_agents/*.py > /private/tmp/claude-501/-Users-sartin/2195f188-57a5-4834-a6b9-acc4ec519961/scratchpad/152-after.txt
diff /private/tmp/claude-501/-Users-sartin/2195f188-57a5-4834-a6b9-acc4ec519961/scratchpad/152-before.txt /private/tmp/claude-501/-Users-sartin/2195f188-57a5-4834-a6b9-acc4ec519961/scratchpad/152-after.txt && echo "no agent changed on refetch"
```

Expected: 20 `pinned sha256=` lines, `manifest updated: 20 entries pinned`, exit 0, and `no agent changed on refetch`. If the `diff` shows a changed file, the author moved that agent since 2026-09-07; report it in the task report (name and both hashes) — do not revert it, the pin is of what was fetched. If a fetch fails, report BLOCKED with the stderr; do not hand-edit the manifest.

- [ ] **Step 4: Check the manifest diff is additive only**

```bash
git diff --stat harness/external_agents.json
.venv/bin/python - <<'EOF'
import json, subprocess
old = json.loads(subprocess.run(["git", "show", "HEAD:harness/external_agents.json"], capture_output=True, text=True).stdout)
new = json.load(open("harness/external_agents.json"))
assert old["_comment"] == new["_comment"]
assert [e["name"] for e in old["agents"]] == [e["name"] for e in new["agents"]]
for o, n in zip(old["agents"], new["agents"]):
    extra = set(n) - set(o)
    assert extra <= {"sha256"}, (n["name"], extra)
    changed = {k for k in o if o[k] != n.get(k)}
    assert changed <= {"ref"}, (n["name"], changed)
    if "ref" in changed:
        assert o["source_type"] == "github_file" and len(n["ref"]) == 40, n["name"]
print("manifest diff: sha256 added on", sum("sha256" in n for n in new["agents"]), "entries; refs pinned on",
      sum(1 for o, n in zip(old["agents"], new["agents"]) if o.get("ref") != n.get("ref")))
EOF
```

Expected: the assertion script prints `manifest diff: sha256 added on 20 entries; refs pinned on <k>`.

- [ ] **Step 5: Run the test suite for the fetch script and the pool loader**

Run: `.venv/bin/python -m pytest tests/test_fetch_external_agents.py tests/test_external_pool.py -q`
Expected: all pass, the manifest test included. Also run `.venv/bin/python -c "from harness.external_pool import external_anchor_agents; print(sorted(external_anchor_agents()))"` and expect the five anchor names (this proves the gate loader accepts the real, pinned pool).

- [ ] **Step 6: Commit** (the manifest and the test only — never `external_agents/`)

```bash
git add harness/external_agents.json tests/test_fetch_external_agents.py
git commit -m "manifest: pin all 20 external agents by sha256, github refs to commits (#152)

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 5: The gate's external limb in `harness/rival_bench.py`

**Files:**
- Modify: `harness/rival_bench.py` (`criterion`; new `format_external`, `paired_external_rows`, `_gate_agents`)
- Test: `tests/test_rival_bench.py`

**Interfaces:**
- Consumes: `harness.triage.head_to_head_rate(name, opponent, seeds, play, agents)` (rows `{"name","opponent","wins","ties","games","seeds"}`), `harness.triage._default_agents()`, Task 2's `external_anchor_agents`, Task 1's `EXTERNAL_ANCHORS`.
- Produces: `criterion(champion_row, anchor_rows, external_pairs=(), champion_bar=CHAMPION_BAR, anchor_bar=ANCHOR_BAR)` — return dict gains `"external": {name: (contender_wins, champion_wins)}`, failing externals listed as `"external:<name>"`; `format_external(pairs) -> str`; `paired_external_rows(contender, champion, seeds, names=None, play=None, agents=None) -> list[dict]` of `{"opponent", "contender": row, "champion": row}`.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_rival_bench.py`)

```python
# --- the external limb (#152): paired non-regression against EXTERNAL_ANCHORS ---

def _pair(name, contender_wins, champion_wins, seeds="848-863", champion_seeds=None):
    return {"opponent": name,
            "contender": {"name": "x", "opponent": name, "wins": contender_wins, "ties": 0,
                          "games": 16, "seeds": seeds},
            "champion": {"name": "y", "opponent": name, "wins": champion_wins, "ties": 0,
                         "games": 16, "seeds": champion_seeds or seeds}}


def _six_anchors():
    return [_row(n, 15) for n in ("meta_bot", "ranch_hands", "market_farmer",
                                  "ranch_adaptive", "wheat_hands", "field_rival")]


def test_criterion_with_no_pairs_is_unchanged_and_reports_an_empty_external_map():
    verdict = rb.criterion(_row("dense_farm", 10), _six_anchors())
    assert verdict["passed"] is True and verdict["failing"] == [] and verdict["external"] == {}


def test_criterion_fails_an_external_where_the_contender_wins_fewer_than_the_champion():
    pairs = [_pair("lonespear_kaggriculture_v21", 0, 1), _pair("pilkwang_structured_economic_policy", 2, 2)]
    verdict = rb.criterion(_row("dense_farm", 10), _six_anchors(), pairs)
    assert verdict["passed"] is False
    assert verdict["failing"] == ["external:lonespear_kaggriculture_v21"]
    assert verdict["external"] == {"lonespear_kaggriculture_v21": (0, 1),
                                   "pilkwang_structured_economic_policy": (2, 2)}


def test_criterion_passes_an_external_on_equal_wins_and_a_tie_is_not_a_win():
    equal = _pair("a", 3, 3)
    tied = _pair("b", 2, 3)
    tied["contender"]["ties"] = 5          # 2 wins + 5 ties still reads 2
    verdict = rb.criterion(_row("dense_farm", 10), _six_anchors(), [equal, tied])
    assert verdict["failing"] == ["external:b"]


def test_criterion_raises_when_a_pair_was_not_played_on_the_same_seeds():
    import pytest

    with pytest.raises(ValueError, match="not paired"):
        rb.criterion(_row("dense_farm", 10), _six_anchors(),
                     [_pair("a", 3, 3, seeds="848-863", champion_seeds="700-715")])


def test_format_external_marks_a_regression():
    text = rb.format_external([_pair("a", 3, 3), _pair("b", 1, 2)])
    lines = text.splitlines()
    assert lines[1].startswith("a") and lines[1].rstrip().endswith("ok")
    assert lines[2].startswith("b") and lines[2].rstrip().endswith("REGRESSED")
    assert "3/16" in lines[1] and "1/16" in lines[2] and "2/16" in lines[2]


def test_paired_external_rows_plays_both_strategies_on_the_same_seeds():
    """The agents hook answers names; the fake play makes the contender win
    every seed and the champion lose every seed, so the rows are checkable."""
    played = []

    def play(a, b, seed):
        played.append((a, b, seed))
        if "cont" in (a, b):
            return (1.0, 0.0) if a == "cont" else (0.0, 1.0)
        return (0.0, 1.0) if a == "champ" else (1.0, 0.0)

    pairs = rb.paired_external_rows("cont", "champ", [848, 849, 850, 851], names=("ext1", "ext2"),
                                    play=play, agents=lambda name: name)
    assert [p["opponent"] for p in pairs] == ["ext1", "ext2"]
    for p in pairs:
        assert p["contender"]["seeds"] == p["champion"]["seeds"] == "848-851"
        assert p["contender"]["wins"] == 4 and p["champion"]["wins"] == 0
    # sides alternate by list position for both strategies
    assert ("cont", "ext1", 848) in played and ("ext1", "cont", 849) in played
    assert ("champ", "ext1", 848) in played and ("ext1", "champ", 849) in played
    verdict = rb.criterion(_row("dense_farm", 10), _six_anchors(), pairs)
    assert verdict["passed"] is True
```

- [ ] **Step 2: Run the tests and observe them fail**

Run: `.venv/bin/python -m pytest tests/test_rival_bench.py -q -k "external or pair"`
Expected: `..._no_pairs_...` fails with `KeyError: 'external'`; the two `criterion` limb tests fail with `TypeError: criterion() takes from 2 to 4 positional arguments but 5 were given`; the `ValueError` test fails with the same `TypeError`; `format_external` and `paired_external_rows` fail with `AttributeError`.

- [ ] **Step 3: Implement.** Replace `criterion` and add the three functions after `format_rows`:

```python
def criterion(champion_row, anchor_rows, external_pairs=(), champion_bar=CHAMPION_BAR,
              anchor_bar=ANCHOR_BAR):
    """The declared verdict: the champion bar, each anchor's bar, and -- when
    `external_pairs` are given (#152) -- paired non-regression against each
    external anchor: the contender's wins on the seeds must be >= the
    champion's wins on the *same* seeds in the same run. Ties never count as
    wins on either side. With no pairs the verdict is exactly the pre-#152 one.
    """
    champion_rate = _rate(champion_row)
    anchor_rates = {r["opponent"]: _rate(r) for r in anchor_rows}
    external = {}
    for pair in external_pairs:
        contender, champion = pair["contender"], pair["champion"]
        if contender["seeds"] != champion["seeds"]:
            raise ValueError(
                f"external pair {pair['opponent']!r} is not paired: contender on seeds "
                f"{contender['seeds']}, champion on {champion['seeds']}"
            )
        external[pair["opponent"]] = (contender["wins"], champion["wins"])
    failing = ([champion_row["opponent"]] if champion_rate < champion_bar else []) + \
              [n for n, rate in anchor_rates.items() if rate < anchor_bar] + \
              [f"external:{n}" for n, (ours, theirs) in external.items() if ours < theirs]
    return {"passed": not failing, "champion_rate": champion_rate,
            "anchor_rates": anchor_rates, "external": external, "failing": failing}
```

```python
def format_external(pairs):
    """One line per external anchor: contender W/G, champion W/G, ok or REGRESSED."""
    lines = [f"{'external':<44} {'contender':>10} {'champion':>10}  verdict"]
    for p in pairs:
        c, k = p["contender"], p["champion"]
        verdict = "ok" if c["wins"] >= k["wins"] else "REGRESSED"
        lines.append(f"{p['opponent']:<44} {c['wins']:>3}/{c['games']:<6} "
                     f"{k['wins']:>3}/{k['games']:<6}  {verdict}")
    return "\n".join(lines)


def paired_external_rows(contender, champion, seeds, names=None, play=None, agents=None):
    """Both strategies against each external anchor on the same `seeds`, sides
    alternated by list position (`harness.triage.head_to_head_rate`), in the
    shape `criterion`'s `external_pairs` reads. `names` defaults to
    `external_pool.EXTERNAL_ANCHORS`; `agents` defaults to `_gate_agents()`."""
    from harness.triage import head_to_head_rate

    if names is None:
        from harness.external_pool import EXTERNAL_ANCHORS as names
    agents = agents or _gate_agents()
    seeds = list(seeds)
    return [{"opponent": name,
             "contender": head_to_head_rate(contender, name, seeds, play, agents),
             "champion": head_to_head_rate(champion, name, seeds, play, agents)}
            for name in names]


def _gate_agents():  # pragma: no cover -- the registry plus the gitignored, pinned externals
    """`head_to_head_rate`'s agents hook: registry names from the registry,
    anchor names from `external_anchor_agents()` (which refuses an unverified pool)."""
    from harness.external_pool import external_anchor_agents
    from harness.triage import _default_agents

    registry = _default_agents()
    externals = external_anchor_agents()

    def agents(name):
        return externals[name] if name in externals else registry(name)
    return agents
```

- [ ] **Step 4: Run the tests and observe them pass**

Run: `.venv/bin/python -m pytest tests/test_rival_bench.py tests/test_clock_bench.py tests/test_pasture_bench.py tests/test_herder_bench.py tests/test_opening_bench.py -q`
Expected: all pass (the other benches import `criterion` and pass no pairs).

- [ ] **Step 5: Commit**

```bash
git add harness/rival_bench.py tests/test_rival_bench.py
git commit -m "rival_bench: paired non-regression limb against EXTERNAL_ANCHORS (#152)

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 6: `--designate --include-external` ranks with the pinned externals

**Files:**
- Modify: `harness/promotion.py` (new `designation_inputs`; `main`'s `--designate` block)
- Test: `tests/test_promotion.py`

**Interfaces:**
- Consumes: Task 2's `external_anchor_agents`; existing `designate`, `build_agents`, `benchmark_names`.
- Produces: `designation_inputs(registry_names, anchor_names, include_external=False, build=build_agents, benchmarks=None, external_loader=None) -> (candidates: dict, pool: dict, benchmarks: set)`.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_promotion.py`; `_named` and `_stub_rewards` exist above)

```python
# --- designation_inputs (#152): the ranking may include the pinned gate externals ---

def _fake_build(names):
    return {n: _named(n) for n in names}


def test_designation_inputs_without_externals_is_the_registry_against_the_anchors():
    cands, pool, bench = promotion.designation_inputs(
        ["a", "bb"], ["bb"], include_external=False, build=_fake_build, benchmarks={"bb"},
        external_loader=lambda: {"zzzz": _named("zzzz")})
    assert set(cands) == {"a", "bb"} and set(pool) == {"bb"} and bench == {"bb"}


def test_designation_inputs_with_externals_adds_them_to_pool_candidates_and_benchmarks():
    cands, pool, bench = promotion.designation_inputs(
        ["a", "bb"], ["bb"], include_external=True, build=_fake_build, benchmarks={"bb"},
        external_loader=lambda: {"zzzz": _named("zzzz")})
    assert set(cands) == {"a", "bb", "zzzz"} and set(pool) == {"bb", "zzzz"}
    assert bench == {"bb", "zzzz"}
    body = promotion.designate(cands, pool, games=2, rewards_fn=_stub_rewards, benchmarks=bench)
    flags = {r["name"]: r["benchmark"] for r in body["ranking"]}
    assert flags["zzzz"] is True and body["gate_opponent"] == "zzzz"
    assert body["submit_default"] == "a"        # never an external
```

- [ ] **Step 2: Run the tests and observe them fail**

Run: `.venv/bin/python -m pytest tests/test_promotion.py -q -k designation_inputs`
Expected: 2 failures, `AttributeError: module 'harness.promotion' has no attribute 'designation_inputs'`.

- [ ] **Step 3: Implement** (in `harness/promotion.py`, after `designate`)

```python
def designation_inputs(registry_names, anchor_names, include_external=False, build=build_agents,
                       benchmarks=None, external_loader=None):
    """What `--designate` ranks and against whom (#152).

    Candidates are the registry; the pool is the anchors. With
    `include_external` the pinned gate externals (`external_pool.EXTERNAL_ANCHORS`,
    loaded by `external_anchor_agents`, which refuses an unverified pool) join
    both -- and the benchmark set, so one can lead the ranking as
    `gate_opponent` but never land as `submit_default` (ADR-0005).
    """
    if benchmarks is None:
        from harness.tournament import benchmark_names
        benchmarks = benchmark_names()
    candidates = build(list(registry_names))
    pool = build(list(anchor_names))
    benchmarks = set(benchmarks)
    if include_external:
        if external_loader is None:
            from harness.external_pool import external_anchor_agents as external_loader
        externals = external_loader()
        candidates.update(externals)
        pool.update(externals)
        benchmarks |= set(externals)
    return candidates, pool, benchmarks
```

In `main`, add `ap.add_argument("--include-external", action="store_true", help="--designate: rank with the pinned gate externals (external_pool.EXTERNAL_ANCHORS) in the pool and the candidates (#152)")`, and replace the three lines `bench = benchmark_names()` / `pool = build_agents(list(DEFAULT_ANCHORS))` / `candidates = build_agents(list(REGISTRY))` with:

```python
        candidates, pool, bench = designation_inputs(
            list(REGISTRY), list(DEFAULT_ANCHORS), include_external=args.include_external)
```

(keep the `designate(candidates, pool, games=args.games, benchmarks=bench)` call; drop the now-unused `benchmark_names` import inside that block if nothing else uses it).

- [ ] **Step 4: Run the tests and observe them pass**

Run: `.venv/bin/python -m pytest tests/test_promotion.py tests/test_succession.py tests/test_rounds.py tests/test_champion_excludes_benchmark.py -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add harness/promotion.py tests/test_promotion.py
git commit -m "promotion: --designate --include-external ranks with the pinned externals (#152)

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 7: An evolve checkpoint records the pins it ran against

**Files:**
- Modify: `harness/evolve.py` (new `run_pool_pins` next to `run_pool_names`; `run_settings` in `main`)
- Test: `tests/test_evolve.py`

**Interfaces:**
- Consumes: Task 1's `external_pool.manifest_pins`.
- Produces: `run_pool_pins(include_external, resolved_external, pins) -> dict[str, str]`.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_evolve.py`, next to the `run_pool_names` tests)

```python
def test_run_pool_pins_is_empty_when_externals_were_not_included():
    assert ev.run_pool_pins(False, None, {"x": "a" * 64}) == {}


def test_run_pool_pins_records_the_pin_of_each_resolved_external_only():
    """A checkpoint says which bytes it was scored against (#152): the anchors
    have no pin, an unpinned external has none to record, and an external the
    run did not resolve is not listed."""
    resolved = {"meta_bot": object(), "x": object(), "loose": object()}
    pins = {"x": "a" * 64, "loose": None, "other": "b" * 64}
    assert ev.run_pool_pins(True, resolved, pins) == {"x": "a" * 64}
```

- [ ] **Step 2: Run the tests and observe them fail**

Run: `.venv/bin/python -m pytest tests/test_evolve.py -q -k run_pool_pins`
Expected: 2 failures, `AttributeError: module 'harness.evolve' has no attribute 'run_pool_pins'`.

- [ ] **Step 3: Implement** (after `run_pool_names`)

```python
def run_pool_pins(include_external, resolved_external, pins):
    """{stem: sha256} for the externals a run resolved (#152); {} when none.

    `pins` is `external_pool.manifest_pins()`. Anchors are not in the manifest
    and an unpinned external has nothing to record, so both are left out.
    """
    if not include_external or not resolved_external:
        return {}
    return {n: pins[n] for n in sorted(resolved_external) if pins.get(n)}
```

and in `main`'s `run_settings`, after the `"resolved_pool"` line:

```python
        "external_pins": run_pool_pins(
            args.include_external, resolved_external,
            external_pool.manifest_pins() if args.include_external else {}),
```

- [ ] **Step 4: Run the tests and observe them pass**

Run: `.venv/bin/python -m pytest tests/test_evolve.py -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add harness/evolve.py tests/test_evolve.py
git commit -m "evolve: a checkpoint records the external pins it ran against (#152)

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 8: ADR amendments, CLAUDE.md, and the docstrings that state the old rule

**Files:**
- Modify: `docs/adr/0008-neuroevolution-against-a-diverse-pool.md` (Consequences, before `## Alternatives considered`)
- Modify: `docs/adr/0007-experiment-driven-development-process.md` (append to Amendments)
- Modify: `CLAUDE.md` (the `--designate` bullet; the "Beat the designated gate opponent" bullet; one new command bullet)
- Modify: `harness/external_pool.py` (module docstring), `harness/genome_bench.py` (module docstring paragraph on `--include-external`, the `opponents` docstring, the argparse help), `harness/herder_bench.py` and `harness/pasture_bench.py` (the `EXTERNAL` comment), `harness/external_agents.json` (`_comment`), `.gitignore` (the `external_agents/` comment), `scripts/fetch_external_agents.py` (module docstring first paragraph)
- Verify: `tests/test_adr_integrity.py`, full suite, and a grep that must come back empty.

**Interfaces:** none — documentation only. **Honest exception to TDD:** these are prose. Verification is (a) the ADR integrity test, (b) the grep in Step 4 proving no file under `harness/`, `scripts/`, `CLAUDE.md` or `.gitignore` still states the old rule, and (c) the full suite. Say so in the report.

- [ ] **Step 1: ADR-0008.** Insert these bullets at the end of `## Consequences` (after the "remaining pool is narrower" bullet, before `## Alternatives considered`):

```markdown
- **Pinned externals may be gate anchors, ranking opponents and opt-in evolution
  anchors (#152, 2026-09-07).** This corrects the #78 amendment's "measurement
  only" rule. Three things changed after it: every contender since #219 beat all
  six `DEFAULT_ANCHORS` 16/16, so the frozen bar stopped separating a better agent
  from a worse one (and pool share against it crowned a gate-REJECTED contender,
  #241); twenty licence-checked externals sat in the manifest, five of which beat
  the champion `third_herder` on both of seeds 700-701 (our reward share:
  `pilkwang_structured_economic_policy` 0.197, `lonespear_kaggriculture_v21`
  0.362, `premaananda108_ecobot_v7` 0.411,
  `shashankjangid_agent_v1000_sovereign_prime` 0.475,
  `madhur_sabherwal_hub_geometry_agent` 0.488; the other fifteen lost 2/2 at
  0.60-1.00); and `harness/evolve.py --include-external` had been putting externals
  in the fitness anchor list all along, contradicting the rule. The
  reproducibility objection is answered by a pin, not a vendoring: every manifest
  entry now carries the sha256 of the fetched file, a `github_file` entry's `ref`
  is the commit fetched, the fetch refuses a mismatch, `resolve_opponents` raises
  on one, and the gate loads only anchors that verify
  (`harness.external_pool.external_anchor_agents`). What stands from #78: no
  third-party code is committed, `scripts/submit.py` never packages one, and an
  external is never the gate opponent (ours by succession, #241). The gate's
  external limb and its declared set (`harness.external_pool.EXTERNAL_ANCHORS`)
  are ADR-0007's amendment of the same date. Rejected: keeping #78 and fixing the
  code (leaves the gate blind to the field; the ghost bench has the same
  gitignored-data problem and cannot react); vendoring after all (re-litigates a
  licensing decision a pin makes unnecessary). Cost: a gate run needs
  `external_agents/` fetched and verified on the machine that runs it; CI does
  not run the gate and never did.
```

- [ ] **Step 2: ADR-0007.** Append to `## Amendments`:

```markdown
### 2026-09-07 — the gate gains a paired external limb (#152)

**What this corrects.** The criterion above had two limbs: the champion bar and
the ≥ 90% floor against each `DEFAULT_ANCHOR`. Since #219 every contender has
cleared the floor 16/16, so it no longer separates contenders. A third limb is
added; the two existing ones are unchanged.

**The limb.** For each external anchor in `harness.external_pool.EXTERNAL_ANCHORS`
(cite the code, not a copy: the tuple is the authority and changing it is a
dated amendment here), the contender and the champion are both played on the
declared seeds in the same run, sides alternated by list position, and the
contender's win count must be **at least the champion's**. Ties are not wins on
either side. A pair not played on the same seeds is an error, not a verdict
(`harness.rival_bench.criterion`, `paired_external_rows`). Paired non-regression
was chosen over a fixed bar because the champion loses to these anchors 0/2 today:
a fixed 90% could never be met, and "recorded, not gated" would keep the field out
of the verdict — which is what the limb exists to change.

**Reproducibility.** The anchors are not committed (ADR-0008 amendment of this
date); they are pinned by sha256 in `harness/external_agents.json`, and the gate
refuses to load an anchor that is missing, unpinned or mismatched.

**Cost.** Five anchors × 16 seeds × two strategies = 160 games per gate run, on
top of the 112 the first two limbs cost.
```

- [ ] **Step 3: CLAUDE.md and the docstrings.**

In `CLAUDE.md`: (a) change the `--designate` bullet's text to `- \`python -m harness.promotion --designate --games 2 [--include-external]\` — rank all strategies by **pool share** against the fixed anchors (#76), with the pinned gate externals in the pool and the candidates on \`--include-external\` (#152). Informational since #241: ...` keeping the rest of the sentence; (b) in the "Beat the *designated gate opponent*" bullet, replace `which **may be a vendored external benchmark** because the gate wants the most demanding representative bar` with `which is always ours (the last challenger to PROMOTE, #241); the field enters through the gate's paired external limb against \`external_pool.EXTERNAL_ANCHORS\` (#152)`; (c) add a command bullet after the `--designate` one: `- \`python -m scripts.fetch_external_agents [--pin]\` — fetch the licence-checked external agents named in \`harness/external_agents.json\` into the gitignored \`external_agents/\`; a pinned entry is verified by sha256 and refused on a mismatch, \`--pin\` records the hash (and the GitHub commit) of an unpinned entry (#152). The gate's external limb will not run without a verified pool.`

In `harness/external_pool.py`, replace the module docstring's second and third paragraphs (from `This module is deliberately **measurement-only**` through `directory that isn't checked into git.`) with:

```
Since #152 (ADR-0008 amendment 2026-09-07) a *pinned* external may be a gate
anchor (``EXTERNAL_ANCHORS``, loaded by ``external_anchor_agents``), a ranking
opponent (``harness.promotion --designate --include-external``) or an opt-in
evolution anchor (``harness.evolve --include-external``). The pin is the
manifest's ``sha256`` of the fetched file; a mismatch always raises, an
unpinned agent is measurement-only and never a gate anchor. ``DEFAULT_ANCHORS``
never contains an external: the six named anchors remain the committed floor.
```

In `harness/genome_bench.py`, replace the module-docstring sentence `Off by default, and opt-in only: the named anchors alone remain the frozen, reproducible comparability bar.` with `Off by default; the pool is verified against the manifest pins (#152), so the number is reproducible on any machine holding the same bytes.`; in `opponents`, replace `(#78) -- opt-in only; never wired into \`\`DEFAULT_ANCHORS\`\` or \`\`harness.promotion.designate\`\`.` with `(#78), pinned and verified (#152) -- opt-in here; never a member of \`\`DEFAULT_ANCHORS\`\`.`; in the argparse help drop `; measurement only, off by default so the frozen bar stays reproducible` in favour of `(#78, pinned per #152); off by default`.

In `harness/herder_bench.py` and `harness/pasture_bench.py`, replace the `EXTERNAL` comment's last two sentences (`Never an anchor and never a gate opponent -- \`external_agents/\` is gitignored, so a gate that depended on it could not be reproduced from a clean clone (ADR-0008 amendment).`) with `Recorded here as a single reference row; since #152 it is also a member of \`external_pool.EXTERNAL_ANCHORS\`, the gate's paired external limb, which later benches use instead of this row.`

In `harness/external_agents.json`, replace the `_comment` list's first two strings with `"Single source of truth for real external competitor agents (#78; roles widened by"`, `"#152, ADR-0008 amendment 2026-09-07). Each entry's sha256 pins the fetched file;"`, and change the fifth string `"(external_agents/ by default). No third-party code is committed to git."` to `"(external_agents/ by default) and refuses a pin mismatch. No third-party code is committed to git."` — edit with a tiny Python script (`json.load` → edit the list → `save_manifest`-style dump with `indent=2`), never by hand, so the file shape stays byte-consistent with `--pin`'s writer.

In `.gitignore`, replace the two comment lines `# for MEASUREMENT ONLY (harness/genome_bench.py --include-external). Never` / `# vendored: no third-party code is committed to this repo.` with `# pinned by sha256 in the manifest (#152) and used as gate anchors, ranking and` / `# opt-in evolution opponents. Never vendored: no third-party code is committed.`

In `scripts/fetch_external_agents.py`, replace the module docstring's first paragraph's last sentence `(``harness/genome_bench.py --include-external``); nothing else ever reads this directory.` with `-- the gate's external limb, the ranking and evolution, each opt-in (#152); every entry is pinned by sha256 and verified on fetch.`

- [ ] **Step 4: Verify** (documentation, so the proof is a grep that must be empty plus the tests)

```bash
grep -rn "measurement only\|measurement-only\|MEASUREMENT ONLY\|never wired\|Never an anchor and never a gate\|may be a vendored external benchmark\|nothing else ever reads this directory" harness scripts CLAUDE.md .gitignore | grep -v "unpinned\|measurement only; never a gate anchor\|measurement-only and never a gate anchor"
```

Expected: no output. (The two excluded phrases are the new rule's own wording in `external_pool.py`.) Then:

```bash
.venv/bin/python -m pytest tests/test_adr_integrity.py tests/test_fetch_external_agents.py tests/test_external_pool.py -q
.venv/bin/python -c "import json; json.load(open('harness/external_agents.json')); print('manifest parses')"
```

Expected: all pass; `manifest parses`.

- [ ] **Step 5: Commit**

```bash
git add docs/adr/0008-neuroevolution-against-a-diverse-pool.md docs/adr/0007-experiment-driven-development-process.md CLAUDE.md harness/external_pool.py harness/genome_bench.py harness/herder_bench.py harness/pasture_bench.py harness/external_agents.json .gitignore scripts/fetch_external_agents.py
git commit -m "docs: ADR-0008/0007 amendments -- pinned externals as gate anchors (#152)

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 9: The baseline record on #152 (controller-run, after the final review)

**Files:** none committed. Output goes to a comment on issue #152.

**Interfaces:**
- Consumes: Task 5's `paired_external_rows`, `format_external`, `criterion`; Task 2's `external_anchor_agents` via `_gate_agents`.

- [ ] **Step 1: Run the baseline, blocking, under strict mode** (seeds 848-863, fresh; champion on both sides so the pair is the identity control)

```bash
ROBRICULTURE_STRICT=1 .venv/bin/python - <<'EOF'
import time
from harness.rival_bench import paired_external_rows, format_external, criterion
from harness.triage import head_to_head_rate
t = time.time()
rows = {name: head_to_head_rate("third_herder", name, list(range(848, 864)), None, __import__("harness.rival_bench", fromlist=["_gate_agents"])._gate_agents())
        for name in __import__("harness.external_pool", fromlist=["EXTERNAL_ANCHORS"]).EXTERNAL_ANCHORS}
pairs = [{"opponent": n, "contender": r, "champion": r} for n, r in rows.items()]
print(format_external(pairs))
print("identity control:", "OK" if criterion({"opponent": "x", "wins": 16, "games": 16}, [], pairs)["passed"] else "FAILED")
print(f"{time.time() - t:.0f}s")
EOF
```

Expected: five rows, `identity control: OK`, and third_herder's wins per external on 848-863 (the reference row for the next contender).

- [ ] **Step 2: Post the table on #152** as "Baseline, recorded not gated, 2026-09-07: `third_herder` vs each `EXTERNAL_ANCHOR`, seeds 848-863, sides alternated, strict mode" with the `--pin` summary from Task 4 (20 pinned; any agent that changed on refetch, by name).
