# Restore the external pool's manifest contract (#317)

- **Date:** 2026-09-19
- **Issue:** #317 (closes #316 as a side effect)
- **Status:** approved

## Context

`harness/external_agents.json` is a manifest of **pinned fetches**:
`scripts/fetch_external_agents.py` downloads each entry into the gitignored
`external_agents/` and verifies it by sha256 (ADR-0008 amendment 2026-09-07,
#152). No third-party code is committed.

On 2026-09-18, pinning four new entries (#295) surfaced that **three of the
original nineteen can no longer be fetched from source**, verified by re-fetching
each with the repo's own `fetch_external_agents.resolve_kaggle_cmd` /
`extract_agent_cell` into a temp dir:

| entry | state |
|---|---|
| `premaananda108_ecobot_v7` | Kaggle kernel returns **404** — deleted or made private |
| `pilkwang_structured_economic_policy` | notebook restructured; **no `%%agentfile`/`%%writefile` cell** remains, so `extract_agent_cell` raises |
| `georgymamarin_visualized_what_every_crop_pays` | fetches, but the author republished; extracted cell hashes `5895dbb1…` against the pinned `8df88e30…` |

`resolve_opponents(include_external=True)` consequently raises:

```
RuntimeError: include_external was requested but the external pool is missing 1 of 23
manifest agent(s): georgymamarin_visualized_what_every_crop_pays.
```

Two of the three — `pilkwang` and `premaananda108` — are members of
`harness.external_pool.EXTERNAL_ANCHORS`, the **ADR-0007 gate's external limb**.
They resolve today only because Sep-7 cached files happen to satisfy their pins;
a failed fetch writes nothing, which is why this stayed invisible. `georgymamarin`
became visible precisely because it *did* fetch and then failed its pin, and
`fetch_one` deletes on mismatch — so that file is already gone.

**The finding is not the three dead links.** ADR-0008's #152 amendment states:

> "The reproducibility objection is answered by a pin, not a vendoring … Rejected:
> vendoring after all (re-litigates a licensing decision a pin makes unnecessary)."

A pin **detects** drift. It does not **preserve** availability. Eleven days after
that was written, three of nineteen entries were unfetchable. Per CLAUDE.md, when
code and an ADR disagree that is a finding to report, not something to document
away.

**Not in question:** the CI angle. ADR-0008 already says "a gate run needs
`external_agents/` fetched and verified on the machine that runs it; CI does not
run the gate and never did." Issue #317's original text overstated this and is
corrected there.

**Precedent.** The same 2026-09-07 pin run found
`adilshamim8_kaggriculture_grandmaster_starter` returning a permanent 404 and
removed it from the manifest, "since an entry nobody can fetch breaks the
manifest's own contract." This change applies that existing rule to three more
entries. It does **not** re-open the vendoring decision, which the owner has
declined twice (#78, #152).

## Decision

Remove the three unfetchable entries; shrink the gate's declared external set to
the three anchors that still verify; delete the orphaned files; record both
consequences as dated ADR amendments.

### 1. Manifest: 23 entries → 20

Remove `pilkwang_structured_economic_policy`, `premaananda108_ecobot_v7` and
`georgymamarin_visualized_what_every_crop_pays` from `harness/external_agents.json`.

### 2. `EXTERNAL_ANCHORS`: 5 → 3

```
EXTERNAL_ANCHORS = (
    "lonespear_kaggriculture_v21",
    "shashankjangid_agent_v1000_sovereign_prime",
    "madhur_sabherwal_hub_geometry_agent",
)
```

**The cost, stated plainly.** Of the five agents #152 recorded as beating
`third_herder`, this drops the strongest (`pilkwang`, our reward share 0.197) and
the third (`premaananda108`, 0.411), keeping 0.362 / 0.475 / 0.488. The external
limb gets easier, and paired external rows recorded before this date are not
comparable with rows recorded after it.

Partial mitigation, not an excuse: `pilkwang` is a ten-tape route-portfolio
replayer (#316) — ten compressed 719-action tapes selected on public state. Its
difficulty was a canned route's, not a policy's, so some of that "hardest anchor"
reading was never a robustness bar.

### 3. Delete the orphaned files

`resolve_opponents`' docstring is explicit: "An agent discovered on disk but
absent from the manifest is not a shortfall — it is merged in same as any other
discovered agent." `discover_external_agents` reads the **directory** by filename
stem, not the manifest. So removing a manifest entry without deleting its file
leaves the agent in the measurement pool, now with no pin backing it and no
warning (the `unpinned` warning covers only entries that *are* in the manifest).

Delete from `external_agents/`:

```
pilkwang_structured_economic_policy.py        + .py.meta.json
premaananda108_ecobot_v7.py                   + .py.meta.json
```

`georgymamarin`'s file is already absent. The directory goes from 22 `.py` to 20,
matching the manifest.

### 4. Warn on orphans

Add to `resolve_opponents(include_external=True)`: any discovered stem absent from
the manifest is named in a loud warning via the existing `warn` seam. It is **not**
raised — the merge-in behaviour is deliberate and a local test agent is a
legitimate use. This is the smallest change that stops the failure mode above from
recurring silently.

## What must survive as tests

The manifest's convention is that an entry's reasoning lives in a named test, not
only in prose (`test_manifest_excludes_the_rejected_candidate_v7_plus_variants`,
`test_manifest_takes_only_the_three_measured_shashankjangid_rungs`). Three here:

1. **The three removed names are absent from the manifest**, with the reason in the
   test: an entry nobody can fetch breaks the manifest's contract. Guards against a
   future survey re-adding one. Note `scripts/survey_dedup.py` will now report all
   three as `NEW`, which is correct and is exactly why this guard is needed.
2. **`pilkwang` and `premaananda108` are absent from `EXTERNAL_ANCHORS`**, and the
   set has exactly the three named members.
3. **`resolve_opponents` warns on an orphan.** Assert on the warning, through the
   injected `warn` seam and `discover_fn` — no real directory, no network.

## Verification that is not unit-testable

Stated explicitly rather than left to implication:

- `resolve_opponents((), include_external=True)` returns **20** and does not raise.
- `external_anchor_agents()` loads **3**.
- `python -m scripts.fetch_external_agents` (no `--pin`) verifies all 20 `ok`.
- The full gate: `pytest -q -n auto --cov --cov-branch`, line ≥ 85%, branch ≥ 65%.

## ADR amendments — dated, append-only

Both append; neither edits an original decision to match what the code became.

- **ADR-0007** — the declared external anchor set is now three, with the cost above.
- **ADR-0008** — corrects "the reproducibility objection is answered by a pin, not a
  vendoring." A pin detects drift; it does not preserve availability. Records the
  three entries and the 11-day interval. Does **not** re-open vendoring; states that
  the pool is best-effort and that a gate reading depends on artifacts the repo
  cannot reconstitute.

## Out of scope

- **Vendoring the bytes**, or any durable off-repo cache. Declined in #78 and #152;
  this change is the cheap contract repair, not the durability answer.
- **Re-pinning `georgymamarin`** to its new upstream. Considered and rejected: one
  rule — an entry that cannot be fetched *as pinned* leaves the manifest.
- **Making the pool strictly manifest-determined** (raising on an orphan rather than
  warning). Reverses a deliberately documented behaviour; not needed to fix #317.
- **Replacing the dropped anchors.** Choosing new gate anchors is a measured decision
  plus its own ADR-0007 amendment; nothing here supplies that evidence. Three
  candidates are already unhomed from the 2026-09-18 survey if that is wanted later.
- Any strategy change; `DEFAULT_ANCHORS`; `submit_default`.

## Amendments

### 2026-09-19 — the bench suite indexes `EXTERNAL_ANCHORS` positionally

Found while writing the implementation plan, before any code was touched. The
design above treats `EXTERNAL_ANCHORS` as if only the gate reads it. Fourteen
bench modules also read it, **by position**:

```
harness/pace_bench.py:56     PILKWANG  = external_pool.EXTERNAL_ANCHORS[0]
harness/reserve_bench.py:58  MADHUR    = external_pool.EXTERNAL_ANCHORS[4]
harness/{split,town,eight,twelve,four8,melon,straw,fourth,even,fert,sheep,six}_bench.py
                             LONESPEAR = EXTERNAL_ANCHORS[1]
```

`PILKWANG` and `MADHUR` are defined once and re-exported across the suite
(`from harness.reserve_bench import MADHUR, PILKWANG, REFERENCE`), so the blast
radius is wider than the fourteen definitions.

Shrinking the tuple to three would make `reserve_bench` raise `IndexError` at
import, `pace_bench` fail its own `assert PILKWANG.startswith("pilkwang")`, and
the other twelve bind `LONESPEAR` to `shashankjangid_agent_v1000_sovereign_prime`.
All fourteen have tests; the suite would go red at import.

**Not a silent failure, to the credit of an earlier review.** Every positional
binding already carries a module-level guard — `assert LONESPEAR.startswith(
"lonespear"), LONESPEAR  # the pool order is the pin (review)`. The tuple's order
was already understood to be load-bearing.

**Decision: add a frozen tuple and point the benches at it.**

```python
#: The gate's external anchors as declared on 2026-09-07 (#152). Frozen: a bench
#: is a dated record of a run against a dated anchor set, so it must not follow
#: later changes to EXTERNAL_ANCHORS (#317).
ANCHORS_2026_09_07 = (
    "pilkwang_structured_economic_policy",
    "lonespear_kaggriculture_v21",
    "premaananda108_ecobot_v7",
    "shashankjangid_agent_v1000_sovereign_prime",
    "madhur_sabherwal_hub_geometry_agent",
)
```

Each bench changes one reference; its positional index and its existing assert
keep working unchanged, so no bench's meaning moves. `EXTERNAL_ANCHORS` then
shrinks to three for the gate alone.

**Consequence, recorded not hidden — the paragraph originally here was wrong,
corrected 2026-09-19 on this same branch (fix wave):** it claimed an old bench
re-run today would ask the pool for `pilkwang` or `premaananda108` and be
refused. It would not. `ANCHORS_2026_09_07` preserves each dated bench's
**label** for the row it reports, not the opponent set it actually plays.
`paired_external_rows` (`harness/rival_bench.py`) resolves `names=None` to the
**live** `EXTERNAL_ANCHORS`, and every bench calls it with that default
(e.g. `harness/pace_bench.py`) — so the external limb always played, and still
plays, the live anchor set. Nothing is refused. What changes is only the
lookup: each bench's `.get(FROZEN_NAME)` (`harness/pace_bench.py:247`, and the
same pattern in the other thirteen mains) now finds no row for a departed
anchor among the live games just played, so the bench prints `None` for it
instead. Freezing the names keeps the *label* honest rather than silently
re-pointing a historical bench's printed name at a different opponent; it does
not, and never did, freeze who gets played.

**Rejected:** literal name strings in all fourteen (duplicates the names across
fourteen files and makes the existing asserts tautological); re-indexing the
positions to fit a 3-tuple (keeps the positional fragility and breaks again on the
next change).

### 2026-09-19 — the ADR-0008 finding is already recorded (PR #319)

Found while planning. A parallel session merged an ADR-0008 Consequences bullet on
2026-09-18 (PR #319) that already records the **finding** this spec is built on:
the three unfetchable entries, that two of them are ADR-0007 gate anchors, that
"reproducibility by pin gave detection, which worked, but not durability", and the
`pilkwang` replayer (#316). It closes: "what to do about durability (#317) and
about `pilkwang` (#316) are open, and each will be a dated amendment here."

The spec's "ADR amendments" section above therefore overstates what ADR-0008 still
needs. Corrected: this change's ADR-0008 amendment records the **decision** only —
the three entries leave, the orphans are deleted, `georgymamarin` is not re-pinned,
durability stays open, and #316 closes because `pilkwang` is no longer an opponent.
It must **not** restate the finding; citing the existing bullet is the single-source
rule working as intended.

The ADR-0007 amendment is unaffected — PR #319 explicitly anticipates it ("if it
touches the gate's set, in ADR-0007").

### 2026-09-19 — `seat_check` stays live, `scoreboard_probe` freezes (fix wave)

Found in a whole-branch review: `harness/seat_check.py` and
`harness/scoreboard_probe.py` both import `external_pool`'s anchors, and #317
had left them pointed two different ways without saying why that split is
correct.

**The criterion.** `seat_check` reads the live `EXTERNAL_ANCHORS`: it has no
positional index into the tuple and asserts no anchor by name (`OPPONENTS =
tuple(EXTERNAL_ANCHORS) + ("field_rival", "third_herder")`), and it runs on
fresh seeds (1024-1039) — it tests a current phenomenon (`lean_feed`'s ladder
seat split, #272), so a re-run should exercise whatever the pool holds today.
`scoreboard_probe` is the opposite shape: a dated probe (#197 Stage 1) with a
committed record (`harness/scoreboard/trigger_readings.json`) on spent seeds
864-879, whose own docstring states the fixed opponent count ("the champion
vs itself and the five pinned externals... 96 games"). Reading it were it live
would silently change the number of opponents underneath a record that
already exists, the same failure mode #317 found in the fourteen dated
benches. It is pinned to `ANCHORS_2026_09_07` for the same reason they are.

**The rule, for reuse.** Whether a module reading `external_pool`'s anchors
should follow the live tuple or freeze to a dated one is not a property of
the module's *name* or *age* — it is whether it has a committed record made
against a specific anchor set. No record and no positional/name pin → live.
A committed record on spent seeds → frozen to the anchor set that produced
it. The same question will recur for any future module that reads the tuple;
answer it by this criterion, not by analogy to whichever of these two it
resembles more.
