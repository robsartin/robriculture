# Adding premaananda108 and measured ShashankJangid rungs to the measurement pool

- **Issue:** #151
- **Date:** 2026-08-30
- **Follow-up:** #152 (whether externals should ever be anchors)

## Context

The #67 re-survey (2026-08-30) confirmed eleven new competitor agents with
permissive licenses, each smoke-tested against `kaggle_environments`. Two
sources are worth adding to the external pool:

- `premaananda108/economics-driven-rule-agent-ecobot-v7-arena` — Kaggle,
  Apache-2.0, public 819.0 / best 995.2. A 2430-line single-file rule engine.
  Our own best sits around 520–535, so this is a materially stronger opponent
  than anything in the pool.
- `ShashankJangid/kaggriculture-agent` — GitHub, MIT. Fifty-seven agent files
  from one author.

These join the pool as **measurement-only** opponents, per ADR-0008's amendment
(#78, 2026-08-18): fetched by `scripts/fetch_external_agents.py` into the
gitignored `external_agents/` directory. No third-party code is committed.

Using them as evolution anchors is explicitly out of scope; that reverses a
recorded decision and is issue #152. In practice, though, the pool is reachable
via the opt-in `--include-external` flag on both `harness/genome_bench.py` and
`harness/evolve.py`, and by name through `harness/production_report.py`'s
`resolve_agent`. `evolve.py --include-external` passes the resolved externals
as `anchor_agents_override`, which *is* the fitness anchor list — so externals
already do reach evolution anchors today, contradicting the amendment above.
That contradiction is open and tracked in issue #152, not resolved here.

### A correction this spec carries

The #67 comment called ShashankJangid's files "a version ladder" giving "a whole
range of anchor strengths." That was inferred from filenames. The numbering is
non-monotonic (`v9`, `v25`, `v100`, `v1000`, `v1500_sovereign_apex`), the repo
has no public Kaggle score, and its README benchmarks are self-reported. Nothing
has established that these rungs differ in strength, or in which direction. The
design therefore measures before choosing.

## Decision

Three pieces of work, in order.

### 1. Choose rungs by measurement

No new production code. `benchmark_genome()` (`harness/genome_bench.py:33`)
already takes a plain callable as its subject and an `agents_override` for the
opponent side, so a scratch script can score any rung against `DEFAULT_ANCHORS`
using the repo's own `share` metric — the same quantity fitness uses.

Method:

- Fetch a sample of rungs spanning the naming range via `gh api` into a scratch
  directory outside the repo.
- Score each with `benchmark_genome(rung, agents_override=build_agents(DEFAULT_ANCHORS))`
  at a fixed `seed_base`, so the result reproduces exactly.
- Select 2–3 rungs whose measured `share` values are separated by more than the
  run-to-run noise.

**If the rungs cluster within noise, add exactly one and record that the ladder
framing was wrong.** A manufactured spread is worse than a single honest entry.

The scratch script is throwaway and is not committed. The measured table goes in
the PR description: `findings/` is gitignored and cannot hold it.

### 2. Manifest entries

Add to `harness/external_agents.json`, matching the shape of the existing four
entries (`name`, `source_type`, `license`, `attribution`, `url`,
`dest_filename`, `notes`):

- `premaananda108_ecobot_v7` as `source_type: kaggle_kernel`, carrying the new
  `cell_file: "main.py"` field from part 3.
- Each chosen rung as `source_type: github_file` — an already-supported source
  type needing no code change, only an entry.

Attribution strings, both licenses confirmed during the #67 survey (Apache-2.0
read off the rendered Kaggle page; MIT via `gh api repos/.../license`):

```
premaananda108, "Economics-Driven Rule Agent (EcoBot v7) + Arena"
(https://www.kaggle.com/code/premaananda108/economics-driven-rule-agent-ecobot-v7-arena),
Apache License 2.0.

Shashank Jangid, kaggriculture-agent
(https://github.com/ShashankJangid/kaggriculture-agent), MIT License.
```

### 3. An optional `cell_file` field for ambiguous notebooks

`extract_agent_cell()` (`scripts/fetch_external_agents.py:88`) returns the
**first** cell tagged `%%writefile` or `%%agentfile`. premaananda's notebook has
two: `main.py` at cell 2 and `arena.py` at cell 10. First-match is correct today
only because of cell order.

The failure this invites is quiet, not loud. If the author reorders cells, the
fetch writes the 6.8KB arena harness in place of the agent;
`discover_external_agents` finds no module-level `agent`, skips it with a
warning, and the pool silently shrinks by one. A benchmark then reports a
confident number measured against the wrong pool — the exact failure
`harness/external_pool.py`'s docstring exists to prevent, and the one that cost
a session in #133.

Design:

- A manifest entry may carry `cell_file`, naming the magic's target (e.g.
  `main.py`).
- When present, `extract_agent_cell` returns the cell whose magic line names
  that target, and raises `ValueError` when no cell matches.
- When absent, behavior is exactly today's first-match, so the four existing
  entries are unaffected.

Deliberately **not** included: making "more than one tagged cell" an error by
itself. That would change behavior for existing entries whose notebooks have not
been re-pulled, and `cell_file` already closes the hazard where it bites. YAGNI.

## Testing

Every code change is TDD: the failing test runs and is observed failing for the
right reason before the implementation exists.

New tests in `tests/test_fetch_external_agents.py`, following that file's
existing `test_<subject>_<behavior>` naming (CLAUDE.md's
`should<Expected>When<Condition>` rule, with its `@DisplayName`, is JUnit
guidance; matching the surrounding Python is what applies here):

- `test_extract_agent_cell_returns_the_named_cell_when_cell_file_is_given` — a
  notebook with two tagged cells returns the named one, not the first.
- `test_extract_agent_cell_falls_back_to_first_match_without_cell_file` — pins
  that the existing four entries keep working.
- `test_extract_agent_cell_raises_when_cell_file_matches_nothing` — a typo'd
  target fails loudly at fetch time rather than vendoring the wrong cell.
- A manifest regression pin, following
  `test_manifest_excludes_the_rejected_candidate_v7_plus_variants`: the
  premaananda entry carries `cell_file`, so a future edit that drops it fails
  the build rather than silently reinstating the ambiguity.

**Unit tests here use fake runners and cannot catch a bad download.** So the
change is not complete until the real fetch runs end to end:

```
python -m scripts.fetch_external_agents
```

and each new agent is confirmed to (a) land on disk with its `.meta.json`
sidecar, (b) import, and (c) appear in `discover_external_agents()`. That check
is the actual proof and its output belongs in the PR.

The full gate — `pytest`, plus whatever CI runs — passes before the PR goes up.

## Consequences

- The measurement pool gains its first opponent meaningfully stronger than our
  own bots, which makes `--include-external` numbers more informative about the
  ladder.
- `--include-external` runs get slower in proportion to the entries added; this
  is why rung count is held to 2–3 and justified by measurement.
- `cell_file` makes multi-cell notebooks safe to add, which widens what the #67
  survey can recommend in future runs.
- The licensing posture is unchanged: still nothing third-party in git, still a
  confirmed permissive license and attribution per entry.
- The stale premise in the recurring survey task — its goal line still says
  candidates are "to potentially add to our neuroevolution anchor pool" — is
  **not** fixed here. That text lives outside the repo, in the scheduled task
  definition, and updating it is a separate manual step.
