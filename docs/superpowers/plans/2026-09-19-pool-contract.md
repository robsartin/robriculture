# Pool Contract Implementation Plan (#317)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the three external-pool entries that can no longer be fetched as pinned, shrink the gate's declared anchor set to the three that still verify, and record both consequences as dated ADR amendments.

**Architecture:** `harness/external_agents.json` loses three entries (23 → 20). `harness/external_pool.py` gains a frozen `ANCHORS_2026_09_07` tuple for the historical bench suite and shrinks `EXTERNAL_ANCHORS` to three for the gate. The two orphaned `.py` files are deleted from the gitignored pool directory, because `resolve_opponents` merges any on-disk agent absent from the manifest. That merge behaviour stays, but now warns.

**Tech Stack:** Python 3.12, pytest. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-09-19-pool-contract-design.md` — read its Amendments section too.

## Global Constraints

- **TDD, red → green → refactor.** Run each test and observe it fail *for the right reason* before writing the code that satisfies it. A collection error or `ImportError` is NOT a red — make the assertion itself fire. Quote the actual failure text in your report.
- **Green at every committed step** (CLAUDE.md / Mikado). No commit may leave the suite red. Task 1's three parts land in one commit for exactly this reason.
- **Never edit `strategies/__init__.py`.** The registry auto-discovers.
- **Stage commits by explicit path.** Never `git add -A` or `git add .` — this worktree is shared.
- **Coverage gate:** line ≥ 85%, branch ≥ 65%.
- **Test style:** plain pytest, snake_case names reading as `test_<expected>_when_<condition>`, each with a one-line docstring or comment stating intent.
- **No third-party code is committed.** `external_agents/` is gitignored; deleting files there is not a git operation.
- **ADR amendments are append-only.** Never edit an original decision to match what the code became.
- Commit trailer: `Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>`
- `source .venv/bin/activate` first; the default `python3` is too old.

**The three entries being removed, and why:**

| name | why it fails the contract |
|---|---|
| `premaananda108_ecobot_v7` | Kaggle kernel returns 404 |
| `pilkwang_structured_economic_policy` | notebook lost its `%%agentfile`/`%%writefile` cell |
| `georgymamarin_visualized_what_every_crop_pays` | republished upstream; failed its pin and was deleted |

---

### Task 1: Shrink the manifest and the anchor set, freeze the bench tuple

All three parts land in **one commit**. Splitting them leaves a red step: `external_anchor_paths` verifies every member of `EXTERNAL_ANCHORS` against the manifest, so removing a manifest entry without removing the anchor raises; and the bench suite imports `EXTERNAL_ANCHORS` positionally, so shrinking it without the frozen tuple breaks fourteen modules at import.

**Files:**
- Modify: `harness/external_agents.json` — remove three entries
- Modify: `harness/external_pool.py:52-64` — add `ANCHORS_2026_09_07`, shrink `EXTERNAL_ANCHORS`
- Modify: `harness/pace_bench.py:56`, `harness/reserve_bench.py:58`, and `LONESPEAR = EXTERNAL_ANCHORS[1]` in `harness/{split,town,eight,twelve,four8,melon,straw,fourth,even,fert,sheep,six}_bench.py`
- Modify: `tests/test_external_pool.py:287` — the anchor-set assertion
- Modify: `tests/test_seat_check.py:11` — `len(sc.OPPONENTS) == 7` becomes 5
- Test: `tests/test_fetch_external_agents.py` (manifest guards), `tests/test_external_pool.py` (anchor guards)

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `external_pool.ANCHORS_2026_09_07` (a 5-tuple, frozen) and `external_pool.EXTERNAL_ANCHORS` (a 3-tuple). Task 2 relies on neither; Task 3 documents both.

- [ ] **Step 1: Write the failing manifest guard test**

Add to `tests/test_fetch_external_agents.py`, beside the other manifest guards:

```python
def test_manifest_excludes_the_three_unfetchable_entries():
    # #317: an entry nobody can fetch breaks the manifest's own contract -- the
    # rule ADR-0008 already used to remove adilshamim8 for a permanent 404.
    # premaananda108's kernel 404s; pilkwang's notebook lost its %%agentfile
    # cell; georgymamarin republished and failed its pin. A future survey will
    # report all three as NEW, which is why this guard exists.
    names = {e["name"] for e in fea.load_manifest()}
    removed = {
        "pilkwang_structured_economic_policy",
        "premaananda108_ecobot_v7",
        "georgymamarin_visualized_what_every_crop_pays",
    }
    assert not (names & removed), f"unfetchable entries are back: {sorted(names & removed)}"
```

- [ ] **Step 2: Run it and watch it fail**

Run: `python -m pytest tests/test_fetch_external_agents.py::test_manifest_excludes_the_three_unfetchable_entries -v`
Expected: FAIL — `AssertionError: unfetchable entries are back: ['georgymamarin_visualized_what_every_crop_pays', 'pilkwang_structured_economic_policy', 'premaananda108_ecobot_v7']`

- [ ] **Step 3: Write the failing anchor guard test**

Replace the existing 5-tuple assertion at `tests/test_external_pool.py:287` with:

```python
def test_external_anchors_holds_only_the_three_that_still_verify():
    # #317: pilkwang and premaananda108 cannot be fetched from source any more,
    # so they cannot be gate anchors. Changing this tuple is a dated ADR-0007
    # amendment (#152's own rule).
    assert external_pool.EXTERNAL_ANCHORS == (
        "lonespear_kaggriculture_v21",
        "shashankjangid_agent_v1000_sovereign_prime",
        "madhur_sabherwal_hub_geometry_agent",
    )


def test_anchors_2026_09_07_is_frozen_for_the_historical_benches():
    # #317: a bench is a dated record of a run against a dated anchor set, so it
    # indexes this frozen tuple, not the live EXTERNAL_ANCHORS. Its ORDER is
    # load-bearing -- every bench's `assert LONESPEAR.startswith(...)` pins it.
    assert external_pool.ANCHORS_2026_09_07 == (
        "pilkwang_structured_economic_policy",
        "lonespear_kaggriculture_v21",
        "premaananda108_ecobot_v7",
        "shashankjangid_agent_v1000_sovereign_prime",
        "madhur_sabherwal_hub_geometry_agent",
    )
```

- [ ] **Step 4: Run both and watch them fail**

Run: `python -m pytest tests/test_external_pool.py -k "external_anchors_holds_only or anchors_2026" -v`
Expected: the first FAILs on the tuple comparison (still the 5-tuple); the second FAILs with `AttributeError: module 'harness.external_pool' has no attribute 'ANCHORS_2026_09_07'`. **The AttributeError is not a real red** — add the constant as an empty placeholder first if you want the assertion itself to fire, then fill it. Report which you did.

- [ ] **Step 5: Add the frozen tuple and shrink the anchors**

In `harness/external_pool.py`, keep the existing `EXTERNAL_ANCHORS` comment block (lines 52-57) attached to `EXTERNAL_ANCHORS` and add above it:

```python
#: The gate's external anchors as declared on 2026-09-07 (#152). Frozen: a bench
#: is a dated record of a run against a dated anchor set, so it must not follow
#: later changes to EXTERNAL_ANCHORS (#317). Its ORDER is load-bearing -- the
#: bench suite indexes it, and each bench asserts the name it expects.
ANCHORS_2026_09_07 = (
    "pilkwang_structured_economic_policy",
    "lonespear_kaggriculture_v21",
    "premaananda108_ecobot_v7",
    "shashankjangid_agent_v1000_sovereign_prime",
    "madhur_sabherwal_hub_geometry_agent",
)
```

Then replace the `EXTERNAL_ANCHORS` tuple body with the three survivors, and append to its comment block:

```
#: Shrunk 2026-09-19 (#317): pilkwang and premaananda108 left the manifest
#: because neither can be fetched from source. Paired external rows recorded
#: before that date are not comparable with rows recorded after it.
```

- [ ] **Step 6: Point the fourteen benches at the frozen tuple**

In `harness/pace_bench.py:56` and `harness/reserve_bench.py:58`, change `external_pool.EXTERNAL_ANCHORS[N]` to `external_pool.ANCHORS_2026_09_07[N]`. Keep the index and the assert exactly as they are.

In each of `harness/{split,town,eight,twelve,four8,melon,straw,fourth,even,fert,sheep,six}_bench.py`, change `LONESPEAR = EXTERNAL_ANCHORS[1]` to `LONESPEAR = ANCHORS_2026_09_07[1]` and update that module's `from harness.external_pool import ...` line to import `ANCHORS_2026_09_07`. Some import `EXTERNAL_ANCHORS` for other uses — check each; only remove the import if nothing else in the module uses it.

**Do not change any index and do not delete any `assert ... startswith(...)` guard.** They are the proof this step preserved each bench's meaning.

- [ ] **Step 7: Remove the three manifest entries**

Delete the three objects from the `agents` list in `harness/external_agents.json`. Leave the other twenty byte-identical. Verify the file is still valid JSON and has 20 entries:

```bash
python -c "import json; a=json.load(open('harness/external_agents.json'))['agents']; print(len(a))"
```
Expected: `20`

- [ ] **Step 8: Fix the one derived count**

`tests/test_seat_check.py:11` asserts `len(sc.OPPONENTS) == 7` (5 anchors + `field_rival` + `third_herder`). With three anchors it is 5. Read `harness/seat_check.py` first to confirm it derives from `EXTERNAL_ANCHORS` and not from the frozen tuple — if it is a historical probe like the benches, point it at `ANCHORS_2026_09_07` instead and leave the count at 7. State which you chose and why.

- [ ] **Step 9: Run the full gate, blocking**

Run: `pytest -q -n auto --cov --cov-branch --cov-report=json`
Then: `python -c "import json;t=json.load(open('coverage.json'))['totals'];l=100*t['covered_lines']/t['num_statements'];b=100*t['covered_branches']/t['num_branches'];print(f'line {l:.2f} branch {b:.2f}')"`
Expected: all pass; line ≥ 85, branch ≥ 65. **Do not background it.**

If a bench test fails, the most likely cause is a missed import line in Step 6 — fix it there, do not weaken the test.

- [ ] **Step 10: Delete the orphaned pool files**

These are gitignored, so this is not a git operation:

```bash
rm external_agents/pilkwang_structured_economic_policy.py \
   external_agents/pilkwang_structured_economic_policy.py.meta.json \
   external_agents/premaananda108_ecobot_v7.py \
   external_agents/premaananda108_ecobot_v7.py.meta.json
ls external_agents/*.py | wc -l
```
Expected: `20`. (`georgymamarin`'s file is already absent — it was deleted when its pin mismatched.)

Then confirm the pool resolves:

```bash
python -c "
from harness.external_pool import resolve_opponents, external_anchor_agents
print('pool:', len(resolve_opponents((), include_external=True)))
print('anchors:', len(external_anchor_agents()))"
```
Expected: `pool: 20`, `anchors: 3`, no exception.

- [ ] **Step 11: Commit**

```bash
git add harness/external_agents.json harness/external_pool.py \
        harness/pace_bench.py harness/reserve_bench.py \
        harness/split_bench.py harness/town_bench.py harness/eight_bench.py \
        harness/twelve_bench.py harness/four8_bench.py harness/melon_bench.py \
        harness/straw_bench.py harness/fourth_bench.py harness/even_bench.py \
        harness/fert_bench.py harness/sheep_bench.py harness/six_bench.py \
        tests/test_external_pool.py tests/test_fetch_external_agents.py \
        tests/test_seat_check.py
git commit
```

Message: `fix(#317): drop three unfetchable entries; EXTERNAL_ANCHORS 5 -> 3`, with a body explaining that the entries, the anchor set and the frozen bench tuple land together because splitting them leaves a red step.

---

### Task 2: Warn on an orphaned pool file

**Files:**
- Modify: `harness/external_pool.py` — `resolve_opponents`, beside the existing `unpinned` warning (~line 356)
- Test: `tests/test_external_pool.py`

**Interfaces:**
- Consumes: nothing from Task 1.
- Produces: no new public names. Behaviour only: `resolve_opponents(include_external=True)` calls `warn(...)` for each discovered stem absent from the manifest.

**Why:** `resolve_opponents`' docstring says "An agent discovered on disk but absent from the manifest is not a shortfall — it is merged in same as any other discovered agent." That stays true. But nothing currently says it out loud, so a stale file keeps playing unverified — the exact way `pilkwang` and `premaananda108` would have survived Task 1 had their files not been deleted. Warn; do **not** raise. A local test agent is a legitimate use.

- [ ] **Step 1: Write the failing test**

```python
def test_resolve_opponents_warns_about_an_agent_absent_from_the_manifest(tmp_path):
    # #317: discovery reads the directory, not the manifest, so a file whose
    # entry was removed keeps playing -- unpinned and, until now, unannounced.
    (tmp_path / "x.py").write_text(_GOOD)
    (tmp_path / "orphan.py").write_text(_GOOD)
    manifest = _write_pinned_manifest(tmp_path, {"x": _sha(_GOOD)})
    warnings = []
    agents = external_pool.resolve_opponents(
        ["meta_bot"], include_external=True,
        build=lambda names: {n: _stub(n) for n in names},
        manifest_path=manifest, directory=str(tmp_path), warn=warnings.append)
    assert set(agents) == {"meta_bot", "x", "orphan"}   # still merged in
    assert any("orphan" in w and "not in the manifest" in w for w in warnings)
```

- [ ] **Step 2: Run it and watch it fail**

Run: `python -m pytest tests/test_external_pool.py::test_resolve_opponents_warns_about_an_agent_absent_from_the_manifest -v`
Expected: FAIL on the second assertion — the agent is merged (first assertion passes) but no warning names it.

- [ ] **Step 3: Implement**

In `resolve_opponents`, after the existing `unpinned` warning block and before `agents.update(external)`:

```python
        orphans = sorted(set(external) - set(expected))
        if orphans:
            warn(
                f"external agent(s) on disk but not in the manifest (merged in, "
                f"unverified -- no pin vouches for these bytes): {', '.join(orphans)}. "
                "Remove the file, or add and pin an entry with: python -m "
                "scripts.fetch_external_agents --pin"
            )
```

- [ ] **Step 4: Run it and watch it pass**

Run: `python -m pytest tests/test_external_pool.py -q`
Expected: all pass, including the pre-existing `test_resolve_opponents_warns_and_merges_an_unpinned_agent` (an unpinned *manifest* entry must still produce its own distinct warning, not this one).

- [ ] **Step 5: Run the full gate, blocking**

Run: `pytest -q -n auto --cov --cov-branch --cov-report=json` plus the coverage check from Task 1 Step 9.

- [ ] **Step 6: Commit**

```bash
git add harness/external_pool.py tests/test_external_pool.py
git commit
```

Message: `feat(#317): warn when a pool file has no manifest entry`

---

### Task 3: The two dated ADR amendments

**Files:**
- Modify: `docs/adr/0007-experiment-driven-development-process.md` — append under `## Amendments`
- Modify: `docs/adr/0008-neuroevolution-against-a-diverse-pool.md` — append a bullet under `## Consequences`

**Interfaces:**
- Consumes: the final state from Tasks 1 and 2.
- Produces: documentation only.

**Format:** ADR-0007's amendments are `### YYYY-MM-DD — title (#issue, PR #n)` headings under its `## Amendments` section, with bolded lead-ins (`**What this corrects.**`, `**The rule.**`, `**What it does not do.**`). ADR-0008 has no Amendments section — its amendments are bullets under `## Consequences` beginning `- **Claim (#issue, YYYY-MM-DD).**`. **Match each file's own existing style; read the last amendment in each before writing.** Append only — never edit an original decision.

- [ ] **Step 1: Append the ADR-0007 amendment**

Heading: `### 2026-09-19 — the external anchor set shrinks to three (#317)`

(Issue-only is correct here and matches `### 2026-09-05 — … (#211)`. Do not invent a PR number — the PR does not exist yet.)

It must say:
- Which two left (`pilkwang_structured_economic_policy`, `premaananda108_ecobot_v7`) and why — neither can be fetched from source, and #152's own rule is that every member must be pinned in the manifest before the gate will load it.
- **The cost, undiluted:** of the five agents #152 recorded as beating `third_herder`, this drops the strongest (our reward share 0.197) and the third (0.411), keeping 0.362 / 0.475 / 0.488. The limb is easier. Paired external rows recorded before 2026-09-19 are not comparable with rows recorded after it.
- The partial mitigation, as mitigation and not excuse: `pilkwang` is a ten-tape route-portfolio replayer (#316), so part of that "hardest anchor" reading was a canned route's difficulty, not a policy's.
- **What it does not do:** it does not replace the dropped anchors. Choosing new ones is a measured decision plus its own amendment.

- [ ] **Step 2: Append the ADR-0008 amendment — the DECISION, not the finding**

**Read ADR-0008's last Consequences bullet first (PR #319, merged 2026-09-18).** A parallel session already recorded the *finding* there: the three unfetchable entries, that two are gate anchors, that "reproducibility by pin gave detection … but not durability", and the `pilkwang` replayer. It closes with: "what to do about durability (#317) and about `pilkwang` (#316) are open, and each will be a dated amendment here."

**Do not restate any of that.** Repeating a recorded finding in a second place is exactly the drift the single-source rule forbids. This amendment records only what #317 *decided*, and cites the existing bullet for the why.

A bullet under `## Consequences`, beginning `- **The three unfetchable entries leave the manifest (#317, 2026-09-19).**`

It must say, and little else:
- The three names, removed under the rule the 2026-09-07 amendment itself applied to `adilshamim8`: an entry nobody can fetch breaks the manifest's contract. Manifest is now twenty entries.
- The orphaned files were deleted from `external_agents/`, because discovery reads the directory and would otherwise keep playing them unverified; `resolve_opponents` now warns when it finds one.
- `georgymamarin` was **not** re-pinned to its new upstream. One rule: an entry that cannot be fetched *as pinned* leaves.
- Durability is **still open**. This is the contract repair, not the durability answer, and it does not re-open vendoring (declined #78, #152).
- `pilkwang` leaving the pool closes #316 as a side effect — it is no longer an opponent of any kind, so its replayer status no longer needs a separate verdict.
- The gate's set shrank on the same date; point at the ADR-0007 amendment from Step 1 rather than repeating its content.

- [ ] **Step 3: Run the ADR integrity tests**

Run: `python -m pytest tests/test_adr_integrity.py -q`
Expected: all pass. That suite checks index integrity, status consistency and required sections (`Context`, `Decision`, `Consequences`, `Alternatives`) — an appended amendment must not disturb them.

- [ ] **Step 4: Run the full gate, blocking**

Run: `pytest -q -n auto --cov --cov-branch --cov-report=json` plus the coverage check.

- [ ] **Step 5: Commit**

```bash
git add docs/adr/0007-experiment-driven-development-process.md \
        docs/adr/0008-neuroevolution-against-a-diverse-pool.md
git commit
```

Message: `docs(#317): ADR amendments — anchor set shrinks, a pin is not durability`

---

## Final verification (controller, after Task 3)

- `python -m scripts.preflight`
- `python -m scripts.fetch_external_agents` (no `--pin`) — all 20 verify `ok`, nothing is re-downloaded as missing
- `pytest -q -n auto --cov --cov-branch` — green, line ≥ 85, branch ≥ 65
- Green at **every** commit on the branch, checked per commit and not only at the tip
- PR body states the anchor-set cost and links #316 (closed by `pilkwang` leaving the pool) and #295's spec amendment precedent
