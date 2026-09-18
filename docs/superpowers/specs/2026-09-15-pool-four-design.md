# Widen the external measurement pool by four (#295)

- **Date:** 2026-09-15
- **Issue:** #295, child of the recurring #67
- **Status:** approved

## Context

The 2026-09-15 re-survey of public `kaggriculture` competitors (comment on #67)
confirmed a batch of permissively-licensed, smoke-tested agents. Deduped against
`harness/external_agents.json` rather than the survey's own comment history,
**four are genuinely new**; two others the survey called new —
`loubaliber_kaggriculture_loubal` and `darunesh1_kaggriculture_baseline_v1` —
were already entries pointing at the identical files. That dedup gap is #296,
not this change.

The pool holds 19 entries. This takes it to 23.

Per the ADR-0008 amendment of 2026-09-07 (#152), the pool is a *manifest of
pinned fetches*, not vendored code: `scripts/fetch_external_agents.py` reads the
manifest, downloads each entry into the gitignored `external_agents/`, and
records the sha256 of the file as written. No third-party code is committed.

## Decision

Add four manifest entries, fetch and pin them, and record a head-to-head against
the champion.

| name | source | ref / cell | licence |
|---|---|---|---|
| `conchocon154_kaggriculture_agent` | `conchocon154/kaggriculture-agent` `main.py` | `8f4addee7a8db49678b748ac1cfd79c2f0d39518` | MIT |
| `rangga_jakti_kaggriculture_agent` | `rangga-jakti/kaggriculture-agent` `main.py` | `6184db0749a96db3ecbe48a488c109f241f461e9` | MIT |
| `rinkaname_apex_grandmaster` | `RinKaname/kaggriculture-test2` `main.py` | `a1106545dd5dd48513da3769a17f695b2bea197e` | Apache-2.0 |
| `xuantianfengwu_terminal_logistics` | Kaggle `xuantianfengwu/kaggriculture-terminal-logistics` | `cell_file: "submission.py"` | Apache-2.0 |

Each exposes a module-level `agent`, so `load_external_agent` and the
`FreshPerGame` wrapper handle all four unchanged; no `entrypoint` alias is
needed. Licences were confirmed on the rendered notebook page or via
`gh api repos/<owner>/<repo>/license`.

Strategic shape, which is the point of a *diverse* pool:

- **conchocon154** — stdlib-only; derives a melon-then-flock season from the
  engine's own price curves, with `BUY_LAND` and cheap-hand reasoning made
  explicit in the docstring.
- **rangga-jakti** — purely reactive: flat job list scored by priority tier then
  distance, no lookahead. A deliberately low-variance shape.
- **RinKaname** — class-based heuristic with hardcoded quadrant and pasture
  geometry.
- **xuantianfengwu** — quadrant-staggered crop plan with market-aware sell
  floors and per-product caps.

`EXTERNAL_ANCHORS` is untouched. Membership of the manifest is measurement;
becoming a gate anchor is a measured decision plus a dated ADR-0007 amendment,
and nothing here supplies that evidence.

## Two exclusions that must survive as tests

The manifest's existing convention is that an entry's *reasoning* lives in a
named test, not only in prose — `test_manifest_pins_the_premaananda_agent_cell`,
`test_manifest_takes_only_the_three_measured_shashankjangid_rungs`,
`test_manifest_excludes_the_rejected_candidate_v7_plus_variants`. Three
decisions here need the same treatment, because each is invisible in the entry
itself and would be silently undone by a well-meaning future edit:

1. **`RinKaname` takes `main.py` only.** The same repo ships
   `subin_an_tape.py`, a 327KB tape replayer. A path change there would swap a
   policy for a tape without changing anything else about the entry.
2. **Exactly one `xuantianfengwu` entry.** `terminal-logistics`,
   `adaptive-land-allocator-r10` and `hour-4-financing-allocator` are one
   lineage (a shared "melon v3" base plus per-version overrides). Adding the
   other two would inflate the pool's count without adding a voice.
3. **`Driw0x` `jet1.py` / `submissions/agent1.py` stay out.** Confirmed
   2026-09-15: `agent()` returns `_LEGACY_ACTIONS[step]` with weed-repair
   patches applied on top. Readable, licensed, and passes a one-step smoke
   test — which is exactly why the exclusion needs to be written down. Scoped
   to that repo, not a substring search across every entry.

## Implementation

RED → GREEN, one behaviour per loop, the failing test observed before the
manifest is touched:

1. Test: the four names are present in `load_manifest()`. Fails — entries absent.
2. Test: the `xuantianfengwu` entry pins `cell_file == "submission.py"`. Fails.
   Without it the fetch depends on cell order.
3. Test: exactly one entry has a `xuantianfengwu` kernel_ref. Fails.
4. Test: no `Driw0x/Kaggriculture` entry has `path` `jet1.py` or
   `submissions/agent1.py`. Passes immediately against today's manifest — so it
   is a regression guard, not a red, and is written as such rather than
   pretending to a failure it cannot produce.
5. Add the four entries; the reds go green.

## Verification that is not unit-testable

Stated explicitly rather than left to implication — none of the following is
covered by the tests above:

- `python -m scripts.fetch_external_agents --pin` downloads all four and writes
  a sha256 per entry.
- `harness.external_pool.resolve_opponents` loads **23** with no shortfall under
  the #153 guard, and no pin mismatch.
- `ten_melon` vs each of the four, 4 seeds, sides alternated, via
  `harness.triage.head_to_head_rate`. This doubles as the real correctness
  check: the survey smoke-tested a single step, so this is the first evidence
  any of the four survives a full 720-turn episode without crashing. Recorded
  as a table on #295.

## Out of scope

`EXTERNAL_ANCHORS` changes (#152); any strategy change; committing third-party
code. The survey's dedup gap is #296; the `driw0x_chi7` replayer audit is #297.

## Amendments

### 2026-09-18 — the 23-with-no-shortfall criterion is not met (#317)

**What this corrects.** The "Verification that is not unit-testable" section
above states that `harness.external_pool.resolve_opponents` must load 23 with
no shortfall under the #153 guard. That criterion is **not met** as of this
date, and will not be until #317 is resolved. The original decision above is
unchanged — this records the current state of an outstanding verification
step, not a change to what was decided.

**The error, reproduced against `main` today:**

```
RuntimeError: include_external was requested but the external pool is missing
1 of 23 manifest agent(s): georgymamarin_visualized_what_every_crop_pays.
```

**The cause is entirely in the original nineteen entries, not the four added
by this change:**

- `premaananda108_ecobot_v7`'s Kaggle kernel now returns 404.
- `pilkwang_structured_economic_policy`'s notebook no longer contains a
  `%%agentfile`/`%%writefile` cell.
- `georgymamarin_visualized_what_every_crop_pays` changed upstream and
  correctly failed its pin — the fetch script deletes the file on a sha256
  mismatch (#152), so it is absent from the local pool rather than silently
  stale. It is the one the RuntimeError above names as missing; the other two
  above are pinned-but-unreachable at fetch time.

**The four entries added here are not implicated.** Each was pinned from its
own freshly fetched bytes and verified `ok`, and all four completed 16 full
720-turn episodes against `ten_melon` without crashing — which is the
correctness question this criterion existed to answer (see "Verification
that is not unit-testable" above and the table recorded on #295).

**What this costs.** Two of the five `EXTERNAL_ANCHORS` —
`pilkwang_structured_economic_policy` and `premaananda108_ecobot_v7` — are
among the unfetchable entries, so this also affects the ADR-0007 gate's
external limb, not just this pool's own 23-count criterion. Tracked as #317.
