# External Measurement Pool Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `premaananda108`'s EcoBot v7 and two measured `ShashankJangid` rungs to the measurement-only external agent pool, and make multi-cell Kaggle notebooks safe to fetch.

**Architecture:** Three manifest entries in `harness/external_agents.json` plus one small capability in `scripts/fetch_external_agents.py` — an optional `cell_file` field letting an entry name *which* `%%writefile`/`%%agentfile` cell holds the agent. No third-party code is committed; the fetch script downloads into the gitignored `external_agents/` directory, exactly as today.

**Tech Stack:** Python 3.12 (stdlib only), pytest, `gh` CLI, `kaggle` CLI.

## Global Constraints

- **Measurement only, in intent.** Do NOT add these agents to `DEFAULT_ANCHORS` (`harness/evolve.py:200`), to promotion gates, or to `harness/promotion.py`'s `designate`. ADR-0008 amendment (#78, 2026-08-18) forbids using externals as evolution anchors. In fact the pool is reachable via the opt-in `--include-external` flag on both `harness/genome_bench.py` and `harness/evolve.py` (the latter feeds resolved externals into `evolve`'s own `anchor_agents_override`, i.e. the fitness anchor list) and by name through `harness/production_report.py`. The `evolve` path already contradicts the #78 amendment; that open contradiction is tracked, not resolved, by issue #152.
- **No third-party code in git.** `external_agents/` is gitignored (`.gitignore:73`). Never `git add` a fetched agent or its `.meta.json` sidecar.
- **Stdlib only** in anything shipped (ADR-0004). No new dependencies.
- **Strict TDD.** Write the test, run it, *observe it fail for the right reason*, then implement. A test that has never been seen red has proven nothing.
- **Stage commits by explicit path.** Never `git add -A` or `git add .` — this repo is worked by parallel sessions. Name each file.
- **Existing behavior is pinned.** The four current manifest entries have no `cell_file` and must keep working through the unchanged first-match path.
- Branch: `151-external-measurement-pool`. Commits reference `#151`.

---

### Task 1: Optional `cell_file` selects the agent cell

`extract_agent_cell()` returns the **first** cell tagged `%%writefile` or `%%agentfile`. premaananda's notebook has two — `main.py` (cell 2) and `arena.py` (cell 10) — so today's correctness depends only on cell order. If the author reorders, the fetch silently writes the arena harness; `discover_external_agents` then finds no module-level `agent`, skips it with a warning, and the pool quietly shrinks by one, producing a confident benchmark number measured against the wrong pool.

**Files:**
- Modify: `scripts/fetch_external_agents.py` (`extract_agent_cell` at :88, `fetch_kaggle_kernel` at :160)
- Test: `tests/test_fetch_external_agents.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `extract_agent_cell(notebook, cell_file=None)` — `cell_file` is `str | None`; returns `str` (cell source, magic line stripped); raises `ValueError` when `cell_file` matches no cell, and (unchanged) when no tagged cell exists at all. `fetch_kaggle_kernel` passes `entry.get("cell_file")` through. Task 2 relies on the manifest key being spelled exactly `cell_file`.

- [ ] **Step 1: Write the three failing tests**

Add to `tests/test_fetch_external_agents.py`, after the existing `extract_agent_cell` tests (near line 119). That file builds cell dicts inline rather than through a helper — match it.

```python
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
```

- [ ] **Step 2: Run the tests and observe them fail**

```bash
cd /Users/sartin/code/robriculture && .venv/bin/python -m pytest tests/test_fetch_external_agents.py -k cell_file -v
```

Expected: all three FAIL. The first two with `TypeError: extract_agent_cell() takes 1 positional argument but 2 were given` (the fallback test passes a single arg, so it may instead fail on the assertion — either way, confirm it is red *before* implementing). The third with `TypeError` as well. **Record the actual message; do not proceed on an assumed failure.**

- [ ] **Step 3: Implement `cell_file` matching**

In `scripts/fetch_external_agents.py`, replace the `extract_agent_cell` definition. The magic line looks like `%%writefile main.py` or `%%writefile /kaggle/working/main.py`, so match on the basename of the magic's argument — an entry should be able to say `main.py` without knowing the author's directory prefix.

```python
def extract_agent_cell(notebook, cell_file=None):
    """Return the source of the notebook's tagged agent cell, magic line stripped.

    ``cell_file`` names which tagged cell to take, matched against the basename
    of the magic's target (so ``main.py`` matches both ``%%writefile main.py``
    and ``%%writefile /kaggle/working/main.py``). It is required for notebooks
    that tag more than one cell -- premaananda108's writes both a ``main.py``
    agent and an ``arena.py`` harness, and taking the wrong one silently
    vendors a file with no module-level ``agent`` (#151).

    Omitted, the first tagged cell wins, which is the behavior every manifest
    entry predating #151 relies on.

    Raises ValueError if no cell is tagged ``%%agentfile``/``%%writefile``, or
    if ``cell_file`` matches none of them -- a notebook that doesn't follow the
    convention must fail loudly at fetch time rather than silently vendoring
    the wrong (narrative/plotting) cell.
    """
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
```

- [ ] **Step 4: Run the tests and observe them pass**

```bash
cd /Users/sartin/code/robriculture && .venv/bin/python -m pytest tests/test_fetch_external_agents.py -v
```

Expected: the three new tests PASS and every pre-existing test in the file still passes (the fallback path is unchanged).

- [ ] **Step 5: Write the failing test for the pass-through**

This exercises the wiring from manifest entry to matcher, not the matcher itself. Write it and see it red **before** touching `fetch_kaggle_kernel`.

Reuse the file's existing `_fake_kaggle_pull` helper (line ~154), which already simulates `kaggle kernels pull`'s side effect of writing a `.ipynb` into the `-p` directory. Do not write a second staging helper.

```python
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
```

- [ ] **Step 6: Run it and observe it fail**

```bash
cd /Users/sartin/code/robriculture && .venv/bin/python -m pytest tests/test_fetch_external_agents.py -k honours_cell_file -v
```

Expected: FAIL with `AssertionError` — `fetch_kaggle_kernel` still ignores `cell_file`, so it writes the first tagged cell and the file contains `ARENA = 1\n`. **Confirm that exact wrong value before implementing** — it proves the test would catch the bug.

- [ ] **Step 7: Pass `cell_file` through from the manifest entry**

In `fetch_kaggle_kernel`, change the extraction call:

```python
        source = extract_agent_cell(notebook, entry.get("cell_file"))
```

- [ ] **Step 8: Run the tests and observe them pass**

```bash
cd /Users/sartin/code/robriculture && .venv/bin/python -m pytest tests/test_fetch_external_agents.py -v
```

Expected: PASS, whole file green.

- [ ] **Step 9: Commit**

```bash
cd /Users/sartin/code/robriculture
git add scripts/fetch_external_agents.py tests/test_fetch_external_agents.py
git commit -m "#151: let a manifest entry name which notebook cell holds the agent

extract_agent_cell took the first %%writefile/%%agentfile cell, so a
notebook that tags two of them (premaananda108 writes main.py AND arena.py)
was fetched correctly only by cell order. Taking the wrong cell writes a
file with no module-level agent, which discover_external_agents skips with
a warning -- the pool shrinks silently and the benchmark reports a
confident number against the wrong pool.

cell_file is optional: absent, the first tagged cell still wins, which is
what the four pre-existing manifest entries rely on.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Add the three manifest entries

Rung choice is measured, not guessed. Each candidate was scored with `benchmark_genome(rung, agents_override=build_agents(DEFAULT_ANCHORS), games=4)` at two seed bases (0 and 770000); `share` is the rung's mean score share against our five anchors, where 0.5 is parity.

| Agent | share @0 | share @770000 |
|---|---|---|
| `agent_v25_master` | 0.0954 | — |
| `agent_v2` | 0.1603 | — |
| `agent_v100_sota` | 0.2818 | — |
| `agent_v9` | 0.3405 | — |
| `agent_v600_apex_ranch` | 0.4536 | 0.4507 |
| **`agent_v300_champion`** | **0.5327** | **0.5388** |
| `agent_v900_apex_sovereign` | 0.6518 | 0.6419 |
| `agent_v1500_sovereign_apex` | 0.6763 | 0.6734 |
| **`agent_v1000_sovereign_prime`** | **0.6771** | **0.6776** |
| **`premaananda108` EcoBot v7** | **0.7929** | **0.7904** |

Run-to-run spread is ≈±0.01, so: `v1000` and `v1500` are indistinguishable (0.004 apart) — taking both would buy nothing. The four weakest rungs sit far below parity; as opponents they are free wins that supply no gradient, which is exactly why ADR-0008 dropped `spoiler` from the anchor set. **Chosen: `v300_champion` (near parity) and `v1000_sovereign_prime` (clearly stronger), plus premaananda as the strongest voice in the pool.**

Version number does not track strength — `v25_master` is the weakest agent measured, and `v9` beats `v100_sota`. The #67 comment's "version ladder … a whole range of anchor strengths" was inferred from filenames; the ordering claim was wrong even though a real spread exists.

**Files:**
- Modify: `harness/external_agents.json`
- Test: `tests/test_fetch_external_agents.py`

**Interfaces:**
- Consumes: the `cell_file` key from Task 1.
- Produces: three entries whose `dest_filename` stems become the names `discover_external_agents` reports — `premaananda108_ecobot_v7`, `shashankjangid_agent_v300_champion`, `shashankjangid_agent_v1000_sovereign_prime`. Task 3 asserts on exactly these names.

- [ ] **Step 1: Write the failing regression pin**

This mirrors the existing `test_manifest_excludes_the_rejected_candidate_v7_plus_variants` (line 38) — the manifest is checked-in configuration, so a future edit that drops `cell_file` must fail the build rather than silently reinstating the ambiguity.

```python
def test_manifest_pins_the_premaananda_agent_cell():
    # Its notebook tags both main.py (the agent) and arena.py (a harness);
    # without cell_file the fetch depends on cell order (#151).
    entries = fea.load_manifest()
    entry = next(e for e in entries if e["name"] == "premaananda108_ecobot_v7")
    assert entry["cell_file"] == "main.py"


def test_manifest_takes_only_the_two_measured_shashankjangid_rungs():
    # 57 agent files in that repo; v300 (~0.536 share) and v1000 (~0.677) were
    # chosen by measurement against DEFAULT_ANCHORS. v1500 measures within noise
    # of v1000 and must not be added alongside it.
    entries = fea.load_manifest()
    paths = {e.get("path") for e in entries
             if e.get("repo") == "ShashankJangid/kaggriculture-agent"}
    assert paths == {"agent_v300_champion.py", "agent_v1000_sovereign_prime.py"}
```

- [ ] **Step 2: Run the tests and observe them fail**

```bash
cd /Users/sartin/code/robriculture && .venv/bin/python -m pytest tests/test_fetch_external_agents.py -k "premaananda or shashankjangid" -v
```

Expected: both FAIL — the first with `StopIteration` (no such entry), the second with `AssertionError` comparing `set()` against the two paths.

- [ ] **Step 3: Add the entries**

Append these three objects to the `agents` array in `harness/external_agents.json`, after the existing `alexandergremyakov` entry. Keep the file's 2-space indentation.

```json
    {
      "name": "premaananda108_ecobot_v7",
      "source_type": "kaggle_kernel",
      "kernel_ref": "premaananda108/economics-driven-rule-agent-ecobot-v7-arena",
      "url": "https://www.kaggle.com/code/premaananda108/economics-driven-rule-agent-ecobot-v7-arena",
      "license": "Apache-2.0",
      "attribution": "premaananda108, \"Economics-Driven Rule Agent (EcoBot v7) + Arena\" (https://www.kaggle.com/code/premaananda108/economics-driven-rule-agent-ecobot-v7-arena), Apache License 2.0.",
      "dest_filename": "premaananda108_ecobot_v7.py",
      "cell_file": "main.py",
      "notes": "Public 819.0 / best 995.2 -- the strongest agent in this pool, and well above our own ~520-535. Its notebook tags TWO cells: main.py (the agent) and arena.py (a self-play harness); cell_file pins the former, so do not remove it (#151). Measured share ~0.792 vs DEFAULT_ANCHORS. Roughly 2.5x slower per game than the other externals."
    },
    {
      "name": "shashankjangid_agent_v300_champion",
      "source_type": "github_file",
      "repo": "ShashankJangid/kaggriculture-agent",
      "path": "agent_v300_champion.py",
      "ref": "main",
      "url": "https://github.com/ShashankJangid/kaggriculture-agent/blob/main/agent_v300_champion.py",
      "license": "MIT",
      "attribution": "Shashank Jangid, kaggriculture-agent (https://github.com/ShashankJangid/kaggriculture-agent), agent_v300_champion.py, MIT License.",
      "dest_filename": "shashankjangid_agent_v300_champion.py",
      "notes": "The near-parity rung: measured share ~0.536 vs DEFAULT_ANCHORS (0.5 is parity). Chosen with v1000 to span a real measured spread. That repo has 57 agent files whose version numbers do NOT track strength -- v25_master is the weakest measured (~0.095) and v9 beats v100_sota -- so do not add rungs by version number without measuring (#151)."
    },
    {
      "name": "shashankjangid_agent_v1000_sovereign_prime",
      "source_type": "github_file",
      "repo": "ShashankJangid/kaggriculture-agent",
      "path": "agent_v1000_sovereign_prime.py",
      "ref": "main",
      "url": "https://github.com/ShashankJangid/kaggriculture-agent/blob/main/agent_v1000_sovereign_prime.py",
      "license": "MIT",
      "attribution": "Shashank Jangid, kaggriculture-agent (https://github.com/ShashankJangid/kaggriculture-agent), agent_v1000_sovereign_prime.py, MIT License.",
      "dest_filename": "shashankjangid_agent_v1000_sovereign_prime.py",
      "notes": "The strong rung: measured share ~0.677 vs DEFAULT_ANCHORS, beating every one of our anchors. Do NOT also add agent_v1500_sovereign_apex -- it measures ~0.674, within the ~0.01 run-to-run noise, so it is a duplicate voice for double the runtime (#151)."
    }
```

- [ ] **Step 4: Run the tests and observe them pass**

```bash
cd /Users/sartin/code/robriculture && .venv/bin/python -m pytest tests/test_fetch_external_agents.py -v && .venv/bin/python -c "import json; json.load(open('harness/external_agents.json')); print('manifest parses')"
```

Expected: whole file PASSES, manifest parses.

- [ ] **Step 5: Commit**

```bash
cd /Users/sartin/code/robriculture
git add harness/external_agents.json tests/test_fetch_external_agents.py
git commit -m "#151: add premaananda108 + two measured ShashankJangid rungs

Measurement-only entries (ADR-0008 #78 amendment) -- manifest only, no
third-party code committed.

Rungs were chosen by scoring nine candidates with benchmark_genome against
DEFAULT_ANCHORS at two seed bases, not by version number: v300_champion
(~0.536 share, near parity) and v1000_sovereign_prime (~0.677, beats every
anchor). v1500 measures within noise of v1000 and was left out as a
duplicate voice. The four weakest rungs are free wins that supply no
gradient, the same reason ADR-0008 dropped spoiler.

Version numbers do not track strength in that repo: v25_master is the
weakest measured and v9 beats v100_sota. The #67 survey's 'version ladder'
ordering was inferred from filenames and was wrong.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Prove it against the real network, then open the PR

Every test so far used a fake runner. **A fake runner cannot catch a bad download** — a renamed file, a moved default branch, a notebook whose cells were reordered. This task is the actual proof.

**Files:**
- No source changes expected. If this task finds a defect, fix it under TDD (failing test first) before proceeding.

**Interfaces:**
- Consumes: the three `dest_filename` stems from Task 2.
- Produces: the measured evidence block for the PR body.

- [ ] **Step 1: Run the real fetch**

```bash
cd /Users/sartin/code/robriculture && .venv/bin/python -m scripts.fetch_external_agents
```

Expected: all seven entries succeed (the four pre-existing plus the three new). If any fail, stop and report — do not paper over a failure by editing the manifest until you understand it.

- [ ] **Step 2: Confirm the three new agents land, import, and are discovered**

```bash
cd /Users/sartin/code/robriculture && .venv/bin/python -c "
from harness.external_pool import discover_external_agents
found = discover_external_agents()
for n in ['premaananda108_ecobot_v7', 'shashankjangid_agent_v300_champion', 'shashankjangid_agent_v1000_sovereign_prime']:
    print(('OK  ' if n in found else 'MISSING ') + n)
print('pool size:', len(found))
"
```

Expected: all three `OK`, pool size 7. A `MISSING` here means the wrong cell or file was fetched — exactly what this task exists to catch.

- [ ] **Step 3: Confirm the premaananda fetch took the agent, not the arena**

```bash
cd /Users/sartin/code/robriculture && head -3 external_agents/premaananda108_ecobot_v7.py && grep -c "def agent" external_agents/premaananda108_ecobot_v7.py && grep -c "ARENA\|argparse" external_agents/premaananda108_ecobot_v7.py
```

Expected: the docstring `"""Kaggle Submission — Single File Bundle."""`, at least one `def agent`, and no argparse/arena markers. This is the specific regression `cell_file` was added to prevent.

- [ ] **Step 4: Confirm the sidecars carry the licenses**

```bash
cd /Users/sartin/code/robriculture && for f in premaananda108_ecobot_v7 shashankjangid_agent_v300_champion shashankjangid_agent_v1000_sovereign_prime; do .venv/bin/python -c "
import json; m=json.load(open('external_agents/$f.py.meta.json'))
print(m['license'], '|', m['attribution'][:60])
"; done
```

Expected: `Apache-2.0`, `MIT`, `MIT`, each with a non-empty attribution.

- [ ] **Step 5: Confirm nothing third-party became stageable**

```bash
cd /Users/sartin/code/robriculture && git status --porcelain external_agents/
```

Expected: **empty output.** Any output means `.gitignore` is not covering a downloaded file — stop and fix before committing anything.

- [ ] **Step 6: Run the full gate**

```bash
cd /Users/sartin/code/robriculture && .venv/bin/python -m pytest -q
```

Expected: all pass. Also run `.venv/bin/python -m scripts.preflight` if it completes in reasonable time; report its result either way.

- [ ] **Step 7: Push and open the PR**

```bash
cd /Users/sartin/code/robriculture
git push -u origin 151-external-measurement-pool
```

Open a PR against `main` titled `#151: add premaananda108 + two measured ShashankJangid rungs to the measurement pool`. The body must include:
- the measured share table from Task 2, both seed bases;
- the reasoning for excluding `v1500` (within noise of `v1000`) and the four weak rungs (free wins, no gradient);
- the correction that version number does not track strength, so the #67 comment's ladder ordering was wrong;
- the verbatim output of Steps 2–5 as evidence;
- `Closes #151` and a pointer to #152 for the anchors question.

Stop at the open PR. **Do not merge** — this goes up for Rob's review.

---

## Notes for the implementer

- The scratch measurement script lives outside the repo at `/private/tmp/claude-501/-Users-sartin/11c9b998-5a06-4676-a83b-bea893c2671c/scratchpad/survey/measure_rungs.py`. It is throwaway; do not commit it. Re-run it only if you need to re-derive the table.
- `findings/` is gitignored, so the measured table cannot be recorded there. The PR body is its home.
- If the `kaggle` CLI is unauthenticated, Task 3 Step 1 will fail on the premaananda entry only; the two GitHub rungs use `gh`. Report which failed rather than skipping the step.
