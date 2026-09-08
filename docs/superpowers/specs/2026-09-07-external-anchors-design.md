# Pinned external anchors for the gate and the ranking (#152)

**Issue:** #152 — should external competitor agents be evolution anchors? (revisit the #78 amendment)
**Branch:** `152-external-anchors`
**Decided with Rob, 2026-09-07:** externals may be gate anchors and ranking opponents, and
evolve's opt-in path is ratified; the gate scores them by paired non-regression; the anchor
set is a declared subset, lonespear first.

## Context

ADR-0008's #78 amendment (2026-08-18) made real competitor agents **measurement only**:
never promotion gates, designation opponents or evolution anchors, and never committed to
this repo. Three things have changed since:

1. **The frozen bar is vacuous.** Every contender since #219 beats all six `DEFAULT_ANCHORS`
   16/16, and pool share against them crowned a gate-REJECTED contender (#241). The gate's
   anchor limb (≥ 90% vs each anchor) no longer separates a better agent from a worse one.
2. **Twenty externals are in the manifest**, every one licence-checked by #67, fetched to a
   gitignored directory. Five of them beat the current champion on both of seeds 700-701
   (measured 2026-09-07, `third_herder`, sides alternated; our reward share in brackets):
   `pilkwang_structured_economic_policy` (0.197), `lonespear_kaggriculture_v21` (0.362),
   `premaananda108_ecobot_v7` (0.411), `shashankjangid_agent_v1000_sovereign_prime` (0.475),
   `madhur_sabherwal_hub_geometry_agent` (0.488). The other fifteen lose 2/2 at shares
   0.60-1.00.
3. **The code already contradicts #78.** `harness/evolve.py --include-external` puts
   externals in the fitness anchor list; CLAUDE.md says the gate opponent "may be a vendored
   external benchmark"; `harness/external_pool.py`'s docstring says the evolution loop never
   imports it. (The gate-opponent half resolved itself with #241: the gate opponent is ours
   by succession.)

The blocker #152 named is **reproducibility**: the manifest pins nothing. Every GitHub entry
is `ref: main` and Kaggle kernels are mutable, so two machines can hold different code under
one name, and a checkpoint or verdict "against pilkwang" does not say which pilkwang.

## Decision

Externals may hold three roles, **only when pinned by content hash in the committed manifest**:

- **gate anchors** — a third limb of the ADR-0007 criterion (paired non-regression, below);
- **ranking opponents** — `python -m harness.promotion --designate --include-external`;
- **evolution anchors** — `python -m harness.evolve --include-external`, opt-in, ratified.

They are still **never** committed to the repo (Rob's licensing decision on #78 stands),
**never** packaged by `scripts/submit.py`, and **never** the gate opponent (a challenger is
ours, and the gate opponent is the last challenger to PROMOTE, #241). `DEFAULT_ANCHORS`
keeps its six members as the ≥ 90% floor; this decision adds a limb, it does not replace one.

### Alternatives rejected

- *Keep #78, fix the code to match.* Leaves the gate with no limb that can see the field;
  the ghost bench (#204) has the same gitignored-data problem and its ghosts cannot react.
- *Vendor the agents after all.* Re-litigates a licensing decision Rob made; not needed once
  a hash makes the un-committed pool verifiable.
- *Fixed 90% bar where beatable; record the rest.* Lonespear and pilkwang would never enter
  a verdict — exactly the agents the limb exists for.
- *Aggregate share against the set.* One number hides a regression against one anchor
  behind gains on another.
- *The whole manifest as anchors.* Twenty paired comparisons at 16 seeds: one seed flip on a
  marginal agent fails the gate, for 640 games.
- *Lonespear only.* A single-agent limb is the "one self-play specialist" problem #78 named.

## Design

### 1. The anchor set

`harness/external_pool.py`:

```python
#: Gate anchors (#152). The externals the champion loses to, strongest first, measured
#: 2026-09-07 on seeds 700-701. Changing this tuple is a dated ADR-0007 amendment, as
#: adding `field_rival` to DEFAULT_ANCHORS was (#181).
EXTERNAL_ANCHORS = (
    "pilkwang_structured_economic_policy",
    "lonespear_kaggriculture_v21",
    "premaananda108_ecobot_v7",
    "shashankjangid_agent_v1000_sovereign_prime",
    "madhur_sabherwal_hub_geometry_agent",
)
```

Cost of the limb: 5 anchors × 16 seeds × 2 (contender and champion) = 160 games, ~3 s each.

### 2. Pins

**Manifest.** Every entry in `harness/external_agents.json` gains `"sha256": "<64 hex>"`,
the hash of the fetched file **as written to disk** — after `extract_agent_cell` for a
kernel and after `append_entrypoint_alias` when the entry has an `entrypoint`, so the bytes
the loader imports are the bytes that were pinned. A `github_file` entry's `ref` is
rewritten from a branch name to the commit SHA the pin was taken from, so a later fetch
returns the same bytes instead of whatever the branch moved to. A `kaggle_kernel` cannot be
fetched at a version: if its author changes it, the fetch fails the pin and re-pinning is a
manifest change in git, dated in the entry's `notes`.

**`scripts/fetch_external_agents.py`.**

- `fetch_one(entry, ...)` verifies a pinned entry after writing: on a mismatch it deletes
  the file and its `.meta.json` and raises `SystemExit` naming the entry, the pinned hash
  and the fetched hash, and the re-pin command. An unverified file is never left where
  `discover_external_agents` would import it.
- `pin_entries(entries, hashes, resolved_refs) -> list` (pure): returns the entries with
  `sha256` filled for each name in `hashes` that lacks one, and `ref` replaced by
  `resolved_refs[name]` for `github_file` entries whose `ref` is not already a 40-hex SHA.
  Entries already pinned are returned unchanged.
- `save_manifest(path, data)` writes the manifest back with `_comment` and entry order
  preserved, 2-space indent, trailing newline (the shape `test_load_manifest_reads_the_committed_manifest` reads).
- `--pin`: fetch as normal, then for each unpinned entry compute `file_sha256` and, for
  `github_file`, resolve the commit via `gh api repos/{repo}/commits/{ref} --jq .sha`; write
  the manifest through `pin_entries` + `save_manifest`; print one line per newly pinned
  entry. Exit 1 if any fetch failed (no partial pin of a failed entry).
- `resolve_commit_sha(entry, runner=subprocess.run) -> str` wraps the `gh api` call and
  raises `SystemExit` on a non-zero exit, like `fetch_github_file`.

**`harness/external_pool.py`.**

- `file_sha256(path) -> str`.
- `manifest_pins(manifest_path=MANIFEST_PATH) -> dict[str, str | None]`: stem → `sha256`
  (or `None` when unpinned).
- `verify_pins(directory=DEFAULT_DIR, manifest_path=MANIFEST_PATH) -> dict[str, str]`:
  stem → one of `"ok"`, `"unpinned"`, `"mismatch"`, `"missing"`, for every manifest entry.
- `resolve_opponents(..., include_external=True)`: after discovery, runs `verify_pins`.
  Any `"mismatch"` raises `RuntimeError` naming the agents — **`allow_partial` does not
  cover a mismatch**: a short pool is a known-partial pool, a mismatched file is code nobody
  reviewed. `"unpinned"` agents are merged with a warning (measurement may use an unpinned
  agent; the gate may not). `"missing"` keeps today's shortfall behaviour.
- `external_anchor_agents(names=EXTERNAL_ANCHORS, directory=DEFAULT_DIR, manifest_path=MANIFEST_PATH, discover_fn=None) -> dict[str, agent]`:
  the gate's loader. Raises `RuntimeError` if any named anchor is missing, unpinned or
  mismatched, with the fetch / `--pin` command to run. Never partial, never a warning.

### 3. The gate limb

`harness/rival_bench.py` (the criterion module every bench imports):

```python
def criterion(champion_row, anchor_rows, external_pairs=(), champion_bar=CHAMPION_BAR,
              anchor_bar=ANCHOR_BAR):
```

`external_pairs` is an iterable of `{"opponent": name, "contender": row, "champion": row}`
where both rows are `harness.triage.head_to_head_rate` rows played on the **same seeds** in
the **same run** (a `ValueError` if their `seeds` differ — a pair measured on different
seeds is not paired). The limb passes for an opponent iff `contender["wins"] >=
champion["wins"]`; ties are not wins on either side. Each failing opponent joins `failing`
as `"external:<name>"`. The return dict gains `"external": {name: (contender_wins,
champion_wins)}`. With `external_pairs=()` (the default) the verdict is exactly today's, so
`clock_bench`, `pasture_bench`, `herder_bench` and their tests are unchanged.

`paired_external_rows(contender, champion, seeds, names=EXTERNAL_ANCHORS, play=None, agents=None) -> list`
plays both strategies against each named external on `seeds` via `head_to_head_rate`
(sides alternated by list position, as everywhere) and returns the `external_pairs` shape.
`agents` defaults to a hook that answers registry names from the registry and anchor names
from `external_anchor_agents()`.

`format_external(pairs)` renders one line per opponent: `opponent  contender W/G  champion W/G  ok|REGRESSED`.

The next contender's bench declares its seeds, plays `paired_external_rows` alongside the
champion and anchor rows, and passes them to `criterion`. The three limbs are then:
champion ≥ 60%, each `DEFAULT_ANCHOR` ≥ 90%, each `EXTERNAL_ANCHOR` no worse than the
champion on the same seeds.

### 4. Ranking and evolution

- `python -m harness.promotion --designate --include-external`: the pool is
  `DEFAULT_ANCHORS` + `EXTERNAL_ANCHORS`, the externals from `external_anchor_agents()`.
  Externals are flagged `"benchmark": true` in the ranking rows (never `submit_default`).
  The ranking remains informational under a succession artifact (#241).
- `python -m harness.evolve --include-external`: ratified as is. The checkpoint's
  `run_settings` gains `"external_pins": {stem: sha256}` for the externals the run resolved,
  so a checkpoint says which bytes it was scored against.

### 5. Documentation

- **ADR-0008 amendment (dated 2026-09-07, #152)** under Consequences, in the style of the
  #78 bullets: what it corrects (the three roles now allowed, pinned), what stands (never
  committed, never submitted, never the gate opponent), the measured table above, the
  alternatives rejected, and the cost (a gate run needs `external_agents/` fetched and
  verified; CI does not run the gate and never did).
- **ADR-0007 amendment (dated 2026-09-07, #152)**: the criterion gains the paired
  non-regression limb; `EXTERNAL_ANCHORS` is cited as the authority for the set, not copied.
- **CLAUDE.md**: the gate-opponent sentence (line 64) drops "may be a vendored external
  benchmark"; the `--designate` line gains `--include-external`; the fetch line gains `--pin`.
- Docstrings that state the old rule: `harness/external_pool.py` (module),
  `harness/genome_bench.py` (module and `opponents`), `harness/herder_bench.py` and
  `harness/pasture_bench.py` (`EXTERNAL`), the manifest `_comment`, the `.gitignore` comment.

## Error handling

| condition | behaviour |
|---|---|
| gate run, `external_agents/` absent or an anchor missing | `RuntimeError` naming the anchors and `scripts/fetch_external_agents.py` |
| gate run, an anchor unpinned | `RuntimeError` naming it and `--pin` |
| any external use, a pinned file's hash differs | `RuntimeError` (loader) / `SystemExit` + file removed (fetch); both name both hashes |
| `external_pairs` rows on different seeds | `ValueError` |
| `--pin` with a failed fetch | exit 1, manifest untouched for that entry |

## Testing (pure TDD; every test red before its code)

- `tests/test_external_pool.py`: `file_sha256` on a temp file; `manifest_pins` reads
  `sha256`/`None`; `verify_pins` returns each of the four states; `resolve_opponents`
  raises on a mismatch even with `allow_partial=True`, warns and merges an unpinned agent;
  `external_anchor_agents` raises on missing / unpinned / mismatch and returns exactly the
  named agents when all are `"ok"`.
- `tests/test_fetch_external_agents.py`: `fetch_one` deletes and raises on a mismatch
  (fake runner), passes on a match, skips verification when unpinned; `pin_entries` fills
  only unpinned entries and only rewrites branch refs; `save_manifest` round-trips
  `_comment` and order; a **manifest test**: every `EXTERNAL_ANCHORS` name is a manifest
  entry with a 64-hex `sha256`, and every `github_file` anchor has a 40-hex `ref`.
- `tests/test_rival_bench.py`: `criterion` unchanged with no pairs; fails on
  `contender < champion`; passes on equal; ties not wins; `ValueError` on seed mismatch;
  `format_external` marks REGRESSED; `paired_external_rows` with a fake `play` produces
  matching seeds on both rows.
- `tests/test_promotion.py`: `--designate --include-external` pool composition via an
  injected loader; externals flagged benchmark and never `submit_default`.
- `tests/test_evolve.py`: `run_settings["external_pins"]` present iff externals resolved.
- ADR integrity test stays green; the no-crash gate does not run externals.

## Verification record (on #152, after the code)

- `scripts/fetch_external_agents.py --pin` output: twenty hashes, committed in the manifest.
- The baseline row for the next contender, **recorded, not gated**: `third_herder` vs each
  `EXTERNAL_ANCHOR` on fresh seeds **848-863** (spent: 100-115, 200-215, 300-331, 400-415,
  500-515, 600-615, 700-703, 800-847), `ROBRICULTURE_STRICT=1`, via `paired_external_rows`
  with the champion on both sides (the pair is then identity: the control that the limb
  passes a strategy against itself).

## Out of scope

Replacing or trimming `DEFAULT_ANCHORS`; the ghost bench as a gate; committing any agent;
fetching a Kaggle kernel at a version; changing the 60% / 90% bars.
