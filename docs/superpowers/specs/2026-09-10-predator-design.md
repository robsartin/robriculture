# predator — breed the adversary on the benchmark's own seams (#199, stage 1)

**Issue:** #199 (wild: breed the predator). Stage 1 only; stage 2 is filed separately if
stage 1 passes.
**Branch:** `199-predator`, from `main` at 824c553 (never stacked).
**Decided with Rob, 2026-09-10:** the predator's genome is a *schedule* over the frozen
benchmark's fourteen seams, not neuropilot's MLP; the design below, unchanged.

## Premise, corrected for today

The issue was drafted when `balanced_farm` was the contender. The champion is now
`lean_feed` (#262, PR #263/#264, submitted 2026-09-10). Its external record on seeds 960-975:
pilkwang 0/16, lonespear 0/16, premaananda 1/16, shashank 3/16, madhur 16/16. Every hole
we have found so far (#244 through #262) was found by hand. Stage 1 asks a narrower
question than the issue's hypothesis: **inside two hours, can a search over legal farming
schedules breed an opponent that beats `lean_feed` at least half the time, without cheating?**

One game is 2.2 s (`lean_feed` vs `field_rival`, seed 976), so two hours is ~3,000 games.

## 1. The predator: `strategies/predator.py`

`PredatorStrategy(FieldRivalStrategy)`, `name = "predator"`, `benchmark = True` (a
benchmark opponent: `scripts/submit.py` and the designation never pick it). It is built from
a **genome**: a list of 25 floats in [0, 1], decoded by a pure `decode(genome) -> Schedule`
into values the benchmark's seams return. `Schedule` is a frozen dataclass; `encode(schedule)
-> genome` is its inverse for representable values, and `FROZEN = encode(Schedule.frozen())`
decodes to the benchmark's own constants, so `PredatorStrategy()` (no genome) *is*
`field_rival` to the value — the identity control below proves it.

| Schedule field | count | range | seam it drives | frozen value |
|---|---|---|---|---|
| `hands` at days 0/6/12/16 | 4 | 1..10, running max | `hire_target(day)` (step table) | 6/7/9/10 at 0/8/12/16 → 6,7,9,10 on the genome's days: 6/6/9/10 |
| `ne_day`, `sw_day` | 2 | 0..31, ≥30 = never; `sw_day ≥ ne_day` | `land_target(day)` = 1 + [day ≥ ne_day] + [day ≥ sw_day] | 12, 16 |
| `head` at days 0/4/8/12/16 | 5 | 0..12, running max | `herd_target(day)`; and `pasture_count(day, animals)` = max(herd_target(day), animals) — the frozen rule on the genome's ramp | 1/3/4/8/10 |
| `nw_pasture`, `ne_pasture` | 2 | 0..8 each | `layout()` = (NW tiles [1:1+nw] + NE tiles [1:1+ne], every other owned tile in the frozen order) | 5, 7 |
| `herders` | 1 | 0..3 | `livestock_workers(day)` = (1, 2, 3)[:herders] | 2 |
| `cap_melon`, `cap_straw`, `cap_wheat` | 3 | 0..24, 0..40, 0..24 | `CAPS` | 12, 15, 5 |
| `pivot` | 1 | 4..16 | `pivot_day()` | 10 |
| `cluster` | 1 | 2..8 | `cluster_size()` | 4 |
| `order` | 1 | 0..23, index into `sorted(permutations(BUY_ORDER))` | `buy_order()` | index of ("hires","land","seed","herd") |
| `reserve` | 1 | 0..3000 | `capital_reserve()` | 1200 |
| `floor` | 1 | 0..2000, 0 = no floor (`None`) | `spend_floor()` | 0 |
| `carry`, `stock` | 2 | 1..8, 1..16 | `feed_carry()`, `feed_stock()` | 8, `None` (stock = frozen `feed_buffer`, encoded as 0 → `None`) |
| `prefer` | 1 | none / SHEEP / COW | `herd_preference(obs)` | none |

Decoding is `lo + round(u * (hi - lo))` per field, then the running-max and ordering rules.
The hands ramp's frozen breakpoints are at days 0/8/12/16; the genome's are at 0/6/12/16, so
the frozen schedule is represented as 6/6/9/10 (identical values on every day). The stock
field's 0 means "frozen rule" so `FROZEN` stays exact; every other field's frozen value is
representable directly.

Every genome is a legal farming schedule run by `field_rival`'s own code; a sim exploit is
unreachable by construction. Exceptions are still possible (an empty layout, a zero cluster
with a herder count that leaves no crop worker); those are what the strict-parity limb is for.

## 2. The search: `harness/predator.py`

A (μ+λ) search reusing `harness.evolve`'s `mutate`, `select_elites`, `next_generation` and
`share`, over genomes clamped to [0, 1] after mutation.

- **Fitness** of a genome = 1 − mean score share of `lean_feed` over 4 games against it,
  sides alternated by game index (predator seat 0 on games 0 and 2). Score share is smooth;
  the in-run win-rate (wins + ½ ties over 4) is recorded next to it, never optimised.
- **Seeds:** generation `g` plays seeds `10000 + 100·g + i`, `i` in 0..3 — the same four for
  every genome in the generation (a fair comparison), fresh every generation (no overfitting
  to a map). These never touch the gate's seeds.
- **Reference:** `FROZEN` is evaluated every generation on that generation's seeds, as a
  reference row, never as a member. Control 2 reads it.
- **Population 16**, generation 0 = `FROZEN` + 7 mutants of it (σ 0.15) + 8 uniform-random
  genomes. Elites = top 4; next generation = elites verbatim + mutants (σ 0.15). **40
  generations.** Cost: 17 × 4 × 2.2 s ≈ 150 s per generation ≈ 100 minutes.
- **Checkpoint** every generation to `harness/genomes/199-predator.json` (temp file +
  `os.replace`, as `evolve.checkpoint_genome`): the best genome so far, its decoded schedule,
  fitness and win-rate on its generation's seeds, the reference row for the same generation,
  generation count, settings, and the per-generation history. The gate reads this file.
- CLI: `python -m harness.predator --generations 40 --pop 16 --games 4 --sigma 0.15 --seed 0
  --champion lean_feed --out harness/genomes/199-predator.json`. Runs under
  `ROBRICULTURE_STRICT=1` (a predator that raises mid-search is a bug to see, not a loss to
  score).

## 3. The gate: `harness/predator_bench.py`

Same shape as `feed_bench`: `--controls`, `--criterion`, or both; exit 0 / 1 / 2. Declared
constants: `CHAMPION = "lean_feed"`, `REFERENCE = "field_rival"`, `GENOME =
"harness/genomes/199-predator.json"`, `SEEDS = range(976, 992)`, `CONTROL_SEED = 976`,
`WIN_BAR = 8` (of 16), `PROFILE_DAY = 16`, `PROFILE_BOUNDS = {"planted": (14, 40),
"animals": (5, 15), "hands": (5, 10)}` (0.5×–1.5× of #181's archetype row 27 / 10 / 10),
`RECORD_DAY = 8`.

**Controls (a failed control is VOID, exit 2, nothing else runs):**
1. **Identity.** `PredatorStrategy()` vs `lean_feed` on seed 976 equals `field_rival` vs
   `lean_feed` on seed 976, both seats, to the reward; precondition: the reference scores > 0.
2. **Search moved.** In the checkpoint's final generation, the best genome's fitness is
   strictly greater than the reference row's on the same seeds, and its decoded schedule
   differs from `Schedule.frozen()` in at least one field.

**Criterion:** the checkpoint's best genome vs `lean_feed` on seeds 976–991, sides alternated
by list position (`triage.head_to_head_rate` with `agents=` building the predator from the
genome). **Wins ≥ 8 of 16; a tie is not a win.**

**Non-degeneracy limbs (both must hold for a PASS):**
- **A, strict parity.** The same 16 games replayed with the predator built under
  `ROBRICULTURE_STRICT=1` and again with it unset: every game completes, and the per-game
  reward pairs are identical. (Strict is read when `make_agent` wraps the strategy, so the
  bench builds each set of agents under its own setting.)
- **B, profile.** Over the 16 criterion games, the predator's median day-16 planted tiles,
  animals placed and crew size (`feed_bench.board_on_day` / `hands_on_day`,
  `farm_census.planted_by_crop` / `animals_placed`) each fall inside `PROFILE_BOUNDS`. The
  day-8 profile and the same three numbers for `lean_feed` are printed, not gated.

**Verdict line and exits:**
- Criterion met and both limbs hold → `PASS`, exit 0: stage 2 is filed as its own issue.
- Criterion not met → `REJECT`, exit 1: no predator inside the budget (the issue's
  alternative 2 reworded for stage 1: the schedule space as seamed cannot express a counter
  to `lean_feed` in 40 generations).
- Criterion met, a limb fails → `DEGENERATE`, exit 1, naming the limb (alternative 3).
- Either way the record goes on #199 and the issue closes; the predator, search and bench
  stay on main as infrastructure.

## 4. Seeds

Gate seeds 976–991 are fresh (spent: 100–115, 200–215, 300–331, 400–415, 500–515,
600–615, 700–703, 800–928, 944, 960–975; 929–943 and 945–959 declared and never played,
not reused). Search seeds 10000+ are a separate range and are not "spent" in the promotion
sense, but are recorded in the checkpoint. The timing probe on seed 976 (one game,
`lean_feed` vs `field_rival`) preceded this declaration and is disclosed here; the identity
control on 976 is a control, not a criterion game, and the criterion's 16 seeds include it
by design (the seat alternation and the opponent differ).

## 5. Tests (pure TDD, red observed before green)

- `decode`/`encode` round-trip on `Schedule.frozen()`; `FROZEN` decodes to the benchmark's
  constants field by field; running max and `sw_day ≥ ne_day` enforced; `order` maps 0..23
  onto distinct permutations; `stock` 0 → `None`; out-of-range floats clamp.
- `PredatorStrategy()`'s seams return exactly the frozen values (`hire_target(d)` equals
  `field_rival.hire_target(d)` for d in 0..29, likewise land and herd; `layout()` equals the
  frozen tiles; `buy_order()` equals `BUY_ORDER`; `feed_stock()` is `None`), and a mutant
  genome's seams reflect its schedule.
- The search loop against a stub rewards function: seeds per generation as declared, elites
  kept verbatim, genomes stay in [0, 1], the reference row evaluated each generation,
  checkpoint written each generation with the declared fields.
- The bench's pure parts: the declared constants; seed freshness; the criterion and limb
  logic on stubbed rows/boards (a 7/16 is REJECT, an 8/16 with a limb failing is DEGENERATE
  naming the limb, an 8/16 with both limbs is PASS); control 2 on a stubbed checkpoint.
- The full games are run by the bench, not the tests.

## 6. Out of scope

Stage 2 (adding predators to the anchors and re-evolving the champion); changing any
benchmark constant; a predator that is anything other than a `field_rival` schedule.
