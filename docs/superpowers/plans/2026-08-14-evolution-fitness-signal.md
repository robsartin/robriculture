# Evolution Fitness Signal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the neuroevolution search a gradient to climb by replacing binary win/loss fitness with a shaped score-share signal dominated by the fixed anchor opponents, and make runs comparable, resumable, and seedable.

**Architecture:** All changes live in `harness/` — nothing here ships in the submitted tarball. `harness/tournament.py` gains a `play_rewards()` primitive that returns raw rewards; `harness/evolve.py` gains pure scoring helpers (`share`, `opponent_record`, `match_share`, `blended_fitness`, `seeded_population`) plus per-generation checkpointing and two new CLI flags; a new `harness/genome_bench.py` provides the frozen, reproducible success bar.

**Tech Stack:** Python 3.12 (venv at `.venv`), pytest, stdlib only. `kaggle_environments` supplies the sim.

**Spec:** `docs/superpowers/specs/2026-08-14-evolution-fitness-signal-design.md`
**Issue:** [#70](https://github.com/robsartin/robriculture/issues/70)

## Global Constraints

- **Run every command through the venv:** `PYTHONPATH=. .venv/bin/python -m pytest ...`. The system `python3` is 3.9 and will fail; the repo root must be on `PYTHONPATH` for `kaggisim`/`strategies`/`harness` to import.
- **TDD, strictly:** the failing test is written and *observed failing* before the implementation exists. Red → green → refactor → commit.
- **The suite is green at every commit.** No task ends with a known-failing test. If a change breaks an existing test, fixing that test is part of the same task.
- **Stdlib only** in anything reachable from a submitted strategy (ADR-0004). This work is harness-side, but do not add third-party imports anywhere.
- **Never edit `strategies/__init__.py`** — the registry auto-discovers.
- **Do not modify `strategies/neuropilot.py` or `strategies/champion_genome.json`.** Baking a new champion is a separate, later decision.
- **Coverage gate:** line ≥ 85%, branch ≥ 65%. CLI `main()` entrypoints and live-game loops get `# pragma: no cover` at the `def`.
- **Test naming:** `test_<expected>_when_<condition>` style, each with a one-line docstring or comment stating intent. Follow `tests/test_evolve.py`.
- **Reproducibility (ADR-0005):** seeds fixed everywhere; new run settings recorded in the saved genome's `meta`.
- **No stub-and-fill-later.** Every function committed is complete. A helper is introduced in the same task that implements it.
- **Commit trailer** on every commit:
  ```
  Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
  ```

## File Structure

| file | responsibility | change |
|---|---|---|
| `harness/tournament.py` | live game execution | **Modify** — extract `play_rewards()`, make `play()` its sign |
| `harness/evolve.py` | the evolution loop and its pure scoring helpers | **Modify** — add 6 helpers, remove 2 superseded ones, add checkpointing + 2 flags |
| `harness/genome_bench.py` | frozen per-opponent benchmark of one genome | **Create** |
| `tests/test_evolve.py` | unit tests for the scoring helpers and loop | **Modify** — port 5 tests, add ~17 |
| `tests/test_genome_bench.py` | unit tests for the benchmark | **Create** |

---

### Task 1: `play_rewards()` and `share()`

The scoring primitive. `play()` currently throws away the raw rewards and returns only a sign — that discarded magnitude is precisely the gradient the search has been missing.

**Files:**
- Modify: `harness/tournament.py:50-60`
- Modify: `harness/evolve.py` (add `share` near the top, after `mutate`)
- Test: `tests/test_evolve.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces:
  - `harness.tournament.play_rewards(agent_a, agent_b, seed=None) -> tuple[float, float]` — raw `(reward_a, reward_b)`, each coerced to `0` when falsy.
  - `harness.evolve.share(mine, theirs) -> float` — clamped score share in `[0.0, 1.0]`.

- [ ] **Step 1: Write the failing tests for `share`**

Add to `tests/test_evolve.py`:

```python
def test_share_is_half_when_scores_are_equal():
    """A tie in reward is a 0.5 share — the same value a tied game scores."""
    assert ev.share(100.0, 100.0) == 0.5


def test_share_is_half_when_both_scores_are_zero():
    """Degenerate both-zero games must not divide by zero."""
    assert ev.share(0, 0) == 0.5
    assert ev.share(None, None) == 0.5


def test_share_clamps_negative_scores_to_zero():
    """A negative reward is floored at 0 so share stays inside [0, 1]."""
    assert ev.share(-50.0, 50.0) == 0.0
    assert ev.share(50.0, -50.0) == 1.0


def test_share_is_one_when_opponent_scores_nothing():
    """Outscoring an opponent who earned nothing is a full share."""
    assert ev.share(20000.0, 0.0) == 1.0


def test_share_is_proportional_between_the_extremes():
    """The champion's real 20570-vs-59136 game lands at its reward proportion."""
    assert ev.share(20570.0, 59136.0) == 20570.0 / (20570.0 + 59136.0)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `PYTHONPATH=. .venv/bin/python -m pytest tests/test_evolve.py -k share -v`
Expected: FAIL — `AttributeError: module 'harness.evolve' has no attribute 'share'`

- [ ] **Step 3: Implement `share` in `harness/evolve.py`**

Insert after the `mutate` function:

```python
def share(mine, theirs) -> float:
    """Score share `mine / (mine + theirs)` — a smooth generalization of win-rate.

    0.5 at a tie, above 0.5 when ahead, and continuously informative when behind.
    Binary win/loss gives the search no gradient until it crosses the finish line;
    this does (#70). Each side is clamped to >= 0 independently so a negative
    reward can never push the result outside [0, 1].
    """
    a = max(0.0, float(mine or 0.0))
    b = max(0.0, float(theirs or 0.0))
    total = a + b
    return 0.5 if total == 0.0 else a / total
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `PYTHONPATH=. .venv/bin/python -m pytest tests/test_evolve.py -k share -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Extract `play_rewards` in `harness/tournament.py`**

Replace the existing `play` function (currently lines 50-60) with:

```python
def play_rewards(agent_a, agent_b, seed=None):  # pragma: no cover
    """Play one game. Return the raw (reward_a, reward_b).

    The magnitude matters: neuroevolution scores on reward share, not just the
    sign, so that losing by less is measurably better than losing by more (#70).
    """
    config = {"episodeSteps": 720}
    if seed is not None:
        config["seed"] = seed
    env = make("kaggriculture", configuration=config)
    env.run([agent_a, agent_b])
    ra, rb = (s.reward for s in env.steps[-1])
    return (ra or 0), (rb or 0)


def play(agent_a, agent_b, seed=None):  # pragma: no cover
    """Play one game. Return 1 if A wins, -1 if B wins, 0 tie."""
    ra, rb = play_rewards(agent_a, agent_b, seed)
    return (ra > rb) - (ra < rb)
```

- [ ] **Step 6: Verify the refactor broke nothing**

Run: `PYTHONPATH=. .venv/bin/python -m pytest tests/ -q`
Expected: PASS — the full suite, same count as before plus the 5 new `share` tests.

- [ ] **Step 7: Commit**

```bash
git add harness/tournament.py harness/evolve.py tests/test_evolve.py
git commit -m "feat(evolve): score-share primitive + play_rewards (#70)

play() threw away the raw rewards and returned only a sign. That discarded
magnitude is exactly the gradient the search was missing: the champion improved
12x in reward while its anchor win-rate stayed pinned at 0.000. Extract
play_rewards() and add share(), a smooth generalization of win-rate.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 2: Anchor-dominant blended fitness

The change that actually moves the plateau. `opponent_record`, `match_share`, `blended_fitness`, and the `evolve()` rewiring land together: removing `match_winrate` necessarily breaks `evolve()`, so splitting them would leave the suite red at a commit.

**Files:**
- Modify: `harness/evolve.py` — replace `match_winrate` (lines 43-57) and `evaluate_population` (lines 59-62); rewrite `evolve` (lines 91-116)
- Test: `tests/test_evolve.py` — port the 5 `match_winrate` tests (lines 53-92), remove the `evaluate_population` test (lines 95-101), update the determinism test (lines 122-143)

**Interfaces:**
- Consumes: `harness.evolve.share` (Task 1).
- Produces:
  - `opponent_record(agent, opponent, games, seed_base, rewards_fn=_play_rewards) -> dict` with keys `"w"`, `"t"`, `"l"`, `"games"`, `"win_rate"`, `"share"`. Zero games → `win_rate` and `share` both `0.5`, counts all `0`.
  - `match_share(agent, opponents, games, seed_base, rewards_fn=_play_rewards) -> float` — mean of each opponent's `"share"`. Empty opponent list → `0.5`.
  - `blended_fitness(anchor_share, pool_share, anchor_weight=DEFAULT_ANCHOR_WEIGHT) -> float`
  - `DEFAULT_ANCHOR_WEIGHT = 0.75`
  - `evolve(generations, pop_size, games, sigma, sample_k, hof_cap, anchor_names=DEFAULT_ANCHORS, seed=0, rewards_fn=_play_rewards, anchor_weight=DEFAULT_ANCHOR_WEIGHT, anchor_agents_override=None)` — the keyword is now `rewards_fn`, **not** `play_fn`.
  - `rewards_fn` signature: `(agent_a, agent_b, seed) -> (reward_a, reward_b)`.
- Later tasks extend `evolve()`'s signature further: Task 3 adds `seed_genome`, Task 4 adds `checkpoint_fn`. Do **not** add them here.

- [ ] **Step 1: Write the failing tests**

In `tests/test_evolve.py`, **delete** `test_match_winrate_counts_ties_as_half`, `test_match_winrate_all_wins_is_one`, `test_match_winrate_all_losses_is_zero`, `test_match_winrate_alternates_sides_to_cancel_first_player_advantage`, `test_match_winrate_zero_games_falls_back_to_half`, `test_match_winrate_no_opponents_falls_back_to_half`, and `test_evaluate_population_returns_genome_fitness_pairs` (lines 53-101). Keep the `_stub_play` / `_tagged` helpers — `_tagged` is reused throughout; delete `_stub_play` only if nothing else references it after the edit.

Add in their place:

```python
def _stub_rewards(a, b, seed=None):
    """Deterministic rewards: an agent tagged "win" scores 300 to the other's 100."""
    if getattr(a, "tag", "") == "win":
        return (300.0, 100.0)
    if getattr(b, "tag", "") == "win":
        return (100.0, 300.0)
    return (100.0, 100.0)


def test_opponent_record_counts_ties_as_half_win_rate():
    """Evenly-matched agents draw every game: win-rate and share both 0.5."""
    rec = ev.opponent_record(_tagged(""), _tagged(""), games=4, seed_base=0,
                             rewards_fn=_stub_rewards)
    assert rec["t"] == 4 and rec["w"] == 0 and rec["l"] == 0
    assert rec["win_rate"] == 0.5
    assert rec["share"] == 0.5


def test_opponent_record_all_wins_is_win_rate_one():
    """Winning every game reports win_rate 1.0 and a share above 0.5."""
    rec = ev.opponent_record(_tagged("win"), _tagged(""), games=2, seed_base=0,
                             rewards_fn=_stub_rewards)
    assert rec["w"] == 2 and rec["win_rate"] == 1.0
    assert rec["share"] == 0.75          # 300 / (300 + 100)


def test_opponent_record_all_losses_is_win_rate_zero():
    """Losing every game reports win_rate 0.0 — but a share that is still graded."""
    rec = ev.opponent_record(_tagged(""), _tagged("win"), games=4, seed_base=0,
                             rewards_fn=_stub_rewards)
    assert rec["l"] == 4 and rec["win_rate"] == 0.0
    assert rec["share"] == 0.25          # 100 / (100 + 300) — the gradient #70 needs


def test_opponent_record_alternates_sides_to_cancel_first_player_advantage():
    """A sim where seat A always wins must score 0.5, not 1.0, if sides alternate."""
    def first_player_wins(a, b, seed=None):
        return (300.0, 100.0)

    rec = ev.opponent_record(_tagged(""), _tagged(""), games=4, seed_base=0,
                             rewards_fn=first_player_wins)
    assert rec["win_rate"] == 0.5
    assert rec["share"] == 0.5


def test_opponent_record_zero_games_falls_back_to_half():
    """No games played is not evidence of anything — report the neutral 0.5."""
    rec = ev.opponent_record(_tagged(""), _tagged(""), games=0, seed_base=0,
                             rewards_fn=_stub_rewards)
    assert rec["games"] == 0
    assert rec["win_rate"] == 0.5 and rec["share"] == 0.5


def test_opponent_record_win_loss_counts_agree_with_share():
    """The record and the share are derived from the same rewards, so they agree."""
    rec = ev.opponent_record(_tagged("win"), _tagged(""), games=4, seed_base=0,
                             rewards_fn=_stub_rewards)
    assert rec["w"] + rec["t"] + rec["l"] == rec["games"] == 4
    assert rec["share"] > 0.5 and rec["win_rate"] == 1.0


def test_match_share_averages_across_opponents():
    """Fitness weights every opponent equally, regardless of pool size."""
    opps = [_tagged("win"), _tagged("")]     # shares 0.25 and 0.50
    assert ev.match_share(_tagged(""), opps, games=2, seed_base=0,
                          rewards_fn=_stub_rewards) == 0.375


def test_match_share_no_opponents_falls_back_to_half():
    """An empty pool is neutral, not a loss — generation 0 has no Hall-of-Fame."""
    assert ev.match_share(_tagged(""), [], games=4, seed_base=0,
                          rewards_fn=_stub_rewards) == 0.5


def test_blended_fitness_weights_anchors_more_heavily():
    """Anchors are the real field, so they dominate: 0.75 anchor / 0.25 sibling."""
    assert ev.blended_fitness(0.8, 0.4, 0.75) == 0.75 * 0.8 + 0.25 * 0.4


def test_blended_fitness_ignores_an_empty_sibling_pool():
    """Generation 0 has no Hall-of-Fame; a missing pool is neutral, not a zero.

    Scoring the absent pool as 0.0 would drag every gen-0 genome down by a
    constant and make gen 0 incomparable to later generations.
    """
    assert ev.blended_fitness(0.8, None, 0.75) == 0.8


def test_blended_fitness_full_anchor_weight_ignores_the_pool():
    """anchor_weight 1.0 makes the sibling pool contribute nothing."""
    assert ev.blended_fitness(0.6, 0.9, 1.0) == 0.6


def test_evolve_fitness_is_dominated_by_the_anchors():
    """The #70 regression guard: beating siblings must NOT be able to mask
    losing to every anchor. This is the exact failure that pinned fitness at
    0.5833 while the agent went 0-for-5 against the real field."""
    def rewards(a, b, seed=None):
        # Every neuropilot genome loses badly to the lone anchor and ties siblings.
        if getattr(a, "tag", "") == "anchor":
            return (900.0, 100.0)
        if getattr(b, "tag", "") == "anchor":
            return (100.0, 900.0)
        return (100.0, 100.0)

    result = ev.evolve(generations=2, pop_size=4, games=2, sigma=0.1, sample_k=2,
                       hof_cap=2, anchor_names=(), seed=1, rewards_fn=rewards,
                       anchor_weight=0.75, anchor_agents_override=[_tagged("anchor")])
    # anchor share 0.10, sibling share 0.50 -> 0.75*0.10 + 0.25*0.50 = 0.20
    assert result["best_fitness"] == 0.2
```

Then **replace** `test_evolve_is_deterministic_and_reports_history` (lines 122-143) with this version — the determinism and history assertions are unchanged; only the stub's return type and the keyword differ:

```python
def test_evolve_is_deterministic_and_reports_history():
    # Stub: reward tracks the genome mean, so mutation toward higher weights wins; no real games.
    def stub(a, b, seed=None):
        return (getattr(a, "_score", 0.0) + 1.0, getattr(b, "_score", 0.0) + 1.0)
    # Monkeypatch genome_agent to tag the agent with its genome mean for the stub.
    import harness.evolve as E
    orig = E.genome_agent
    def tagged_agent(g):
        ag = _tagged("")
        ag._score = sum(g) / len(g)
        return ag
    E.genome_agent = tagged_agent
    try:
        out = E.evolve(generations=3, pop_size=6, games=1, sigma=0.2, sample_k=2,
                       hof_cap=2, anchor_names=[], seed=1, rewards_fn=stub,
                       anchor_agents_override=[_tagged("")])
        assert set(out) == {"best_genome", "best_fitness", "history"}
        assert len(out["history"]) == 3
        out2 = E.evolve(generations=3, pop_size=6, games=1, sigma=0.2, sample_k=2,
                        hof_cap=2, anchor_names=[], seed=1, rewards_fn=stub,
                        anchor_agents_override=[_tagged("")])
        assert out2["best_fitness"] == out["best_fitness"]     # deterministic
    finally:
        E.genome_agent = orig
```

The `+ 1.0` keeps both rewards strictly positive so `share` never hits its both-zero fallback, and `anchor_agents_override` supplies a stub anchor now that `anchor_names=[]` no longer produces one.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `PYTHONPATH=. .venv/bin/python -m pytest tests/test_evolve.py -v`
Expected: FAIL — `AttributeError: module 'harness.evolve' has no attribute 'opponent_record'`

- [ ] **Step 3: Implement the scoring helpers**

Change the import at line 4 of `harness/evolve.py` from:

```python
from harness.tournament import play as _play
```

to:

```python
from harness.tournament import play_rewards as _play_rewards
```

Then delete `match_winrate` (lines 43-57) and `evaluate_population` (lines 59-62) entirely, replacing them with:

```python
def opponent_record(agent, opponent, games, seed_base, rewards_fn=_play_rewards):
    """Play `games` games against one opponent; report the record and the score share.

    Both statistics come from the same rewards in a single pass — playing each game
    twice to collect them separately would double the cost for nothing. Sides
    alternate on odd games so first-player advantage cancels.

    Zero games returns the neutral 0.5 for both rates rather than 0: no evidence is
    not evidence of failure.
    """
    w = t = l = 0
    shares = []
    for g in range(games):
        seed = seed_base + g
        if g % 2 == 0:
            mine, theirs = rewards_fn(agent, opponent, seed)
        else:
            theirs, mine = rewards_fn(opponent, agent, seed)
        shares.append(share(mine, theirs))
        if mine > theirs:
            w += 1
        elif mine == theirs:
            t += 1
        else:
            l += 1
    n = len(shares)
    return {
        "w": w, "t": t, "l": l, "games": n,
        "win_rate": (w + 0.5 * t) / n if n else 0.5,
        "share": sum(shares) / n if n else 0.5,
    }


def match_share(agent, opponents, games, seed_base, rewards_fn=_play_rewards):
    """Mean score share across every opponent — each opponent weighted equally."""
    if not opponents:
        return 0.5
    return sum(
        opponent_record(agent, opp, games, seed_base + oi * 100000, rewards_fn)["share"]
        for oi, opp in enumerate(opponents)
    ) / len(opponents)


DEFAULT_ANCHOR_WEIGHT = 0.75


def blended_fitness(anchor_share, pool_share, anchor_weight=DEFAULT_ANCHOR_WEIGHT) -> float:
    """Combine the anchor and sibling-pool shares, anchors dominant.

    The anchors are the only opponents that stand in for the real field. Scoring
    them at equal weight with the population sample and Hall-of-Fame let
    sibling-beating supply all the gradient — and that component saturates, which
    is what pinned fitness at 0.5833 (#70).

    `pool_share` of None means there were no sibling opponents (generation 0, or a
    disabled Hall-of-Fame): fall back to the anchor share rather than scoring the
    absent pool as a loss.
    """
    if pool_share is None:
        return anchor_share
    return anchor_weight * anchor_share + (1.0 - anchor_weight) * pool_share
```

- [ ] **Step 4: Rewrite `evolve()`**

Replace the whole `evolve` function (lines 91-116) with:

```python
def evolve(generations, pop_size, games, sigma, sample_k, hof_cap,
           anchor_names=DEFAULT_ANCHORS, seed=0, rewards_fn=_play_rewards,
           anchor_weight=DEFAULT_ANCHOR_WEIGHT, anchor_agents_override=None):
    """Run the neuroevolution loop; return best genome/fitness and per-generation history.

    Fitness is the anchor-dominant blend of score shares (#70), not win-rate:
    win/loss gives no gradient at all until the agent starts winning, and it was
    not winning.
    """
    rng = random.Random(seed)
    anchors = (anchor_agents_override if anchor_agents_override is not None
               else anchor_agents(anchor_names))
    population = initial_population(pop_size, seed)
    hof_genomes = []
    best_genome, best_fit, history = None, -1.0, []
    for gen in range(generations):
        pop_agents = [genome_agent(g) for g in population]
        hof_agents = [genome_agent(g) for g in hof_genomes]
        scored = []
        for i, g in enumerate(population):
            base = seed + gen * 7919 + i
            siblings = build_opponents([pa for j, pa in enumerate(pop_agents) if j != i],
                                       [], hof_agents, sample_k, rng)
            a_share = match_share(pop_agents[i], anchors, games, base, rewards_fn)
            p_share = (match_share(pop_agents[i], siblings, games, base + 50000, rewards_fn)
                       if siblings else None)
            scored.append((g, blended_fitness(a_share, p_share, anchor_weight)))
        scored.sort(key=lambda gf: gf[1], reverse=True)
        gen_best_g, gen_best_f = scored[0]
        mean_f = sum(f for _, f in scored) / len(scored)
        history.append({"gen": gen, "best": gen_best_f, "mean": mean_f})
        if gen_best_f > best_fit:
            best_fit, best_genome = gen_best_f, gen_best_g
        elites = [g for g, _ in scored[:max(1, pop_size // 4)]]
        hof_genomes = update_hof(hof_genomes, [gen_best_g], hof_cap)
        population = next_generation(elites, pop_size, sigma, rng)
    return {"best_genome": best_genome, "best_fitness": best_fit, "history": history}
```

`build_opponents` is called with an empty anchor list because anchors are now scored separately so they can be weighted.

- [ ] **Step 5: Add the `--anchor-weight` flag**

In `main()`, alongside the existing arguments:

```python
    ap.add_argument("--anchor-weight", type=float, default=DEFAULT_ANCHOR_WEIGHT,
                    help="weight on the anchor share vs the sibling pool (default 0.75)")
```

Pass `anchor_weight=args.anchor_weight` into the `evolve(...)` call, and add
`"anchor_weight": args.anchor_weight` to the `meta` dict in the `save_genome` call so
runs stay reproducible (ADR-0005).

- [ ] **Step 6: Run the full suite**

Run: `PYTHONPATH=. .venv/bin/python -m pytest tests/ -q`
Expected: PASS — everything green, no failures, no errors.

- [ ] **Step 7: Commit**

```bash
git add harness/evolve.py tests/test_evolve.py
git commit -m "feat(evolve): anchor-dominant blended fitness (#70)

Score anchors and siblings separately and blend them 0.75/0.25 instead of
averaging all twelve opponents together. Under the old uniform mean, the six
sibling opponents supplied all the gradient and saturated at 12/12 by gen 4 —
14/24 = 0.5833, the plateau — while the agent went 0-for-5 against every real
anchor. Fitness is now the shaped score share, so losing by less scores better.

opponent_record replaces match_winrate: one pass over the games yields both the
W/T/L record and the mean share, where calling both would have played every game
twice for two numbers from the same rewards. evaluate_population goes too — it
was already dead, since evolve() inlines its own scoring loop.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 3: `seeded_population()` and the `--seed-genome` flag

Start a run from the 20,000-reward champion instead of re-deriving basics from 1,700-reward randoms.

**Files:**
- Modify: `harness/evolve.py` (add `seeded_population` and `load_genome`; extend `evolve` and `main`)
- Test: `tests/test_evolve.py`

**Interfaces:**
- Consumes: `mutate`, `GENOME_LEN`, `save_genome` (all existing); `evolve` (Task 2).
- Produces:
  - `seeded_population(seed_genome, size, sigma, rng) -> list[list[float]]`
  - `load_genome(path) -> list[float]` — raises `ValueError` on a missing, unreadable, or wrong-length genome.
  - `evolve(...)` gains a `seed_genome=None` keyword.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_evolve.py`:

```python
def test_seeded_population_keeps_the_seed_verbatim():
    """Element 0 is the seed itself, so a run can never score below its starting point."""
    seed_g = [0.5] * ev.GENOME_LEN
    pop = ev.seeded_population(seed_g, size=4, sigma=0.1, rng=random.Random(3))
    assert len(pop) == 4
    assert pop[0] == seed_g
    assert all(g != seed_g for g in pop[1:])          # the rest are mutants


def test_seeded_population_is_deterministic_for_a_seeded_rng():
    """ADR-0005: the same rng seed reproduces the same population exactly."""
    seed_g = [0.5] * ev.GENOME_LEN
    a = ev.seeded_population(seed_g, size=4, sigma=0.1, rng=random.Random(3))
    b = ev.seeded_population(seed_g, size=4, sigma=0.1, rng=random.Random(3))
    assert a == b


def test_evolve_starts_from_the_seed_genome_when_given_one():
    """A seeded run begins at the champion, not at random noise."""
    def rewards(a, b, seed=None):
        return (100.0, 100.0)

    seed_g = [0.5] * ev.GENOME_LEN
    out = ev.evolve(generations=1, pop_size=4, games=2, sigma=0.0, sample_k=1,
                    hof_cap=1, anchor_names=(), seed=1, rewards_fn=rewards,
                    anchor_agents_override=[_tagged("")], seed_genome=seed_g)
    # sigma 0 makes every mutant identical to the seed, so the winner must be it.
    assert out["best_genome"] == seed_g


def test_load_genome_round_trips_a_saved_artifact(tmp_path):
    """A genome written by save_genome loads back identically."""
    p = tmp_path / "g.json"
    g = [0.25] * ev.GENOME_LEN
    ev.save_genome(str(p), g, {"fitness": 0.5})
    assert ev.load_genome(str(p)) == g


def test_load_genome_rejects_a_wrong_length_genome(tmp_path):
    """Fail loudly, never silently fall back to random weights.

    A silent fallback is exactly what shipped a submission running on random
    weights before the Phase 4 fix — the failure must be impossible to miss.
    """
    p = tmp_path / "short.json"
    ev.save_genome(str(p), [0.1, 0.2, 0.3], {})
    with pytest.raises(ValueError, match="length"):
        ev.load_genome(str(p))


def test_load_genome_rejects_a_missing_file(tmp_path):
    """A typo'd path must stop the run, not quietly start from noise."""
    with pytest.raises(ValueError, match="seed genome"):
        ev.load_genome(str(tmp_path / "nope.json"))
```

Add `import pytest` to the test module's imports if it is not already there.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `PYTHONPATH=. .venv/bin/python -m pytest tests/test_evolve.py -k "seeded_population or load_genome or seed_genome" -v`
Expected: FAIL — `AttributeError: module 'harness.evolve' has no attribute 'seeded_population'`

- [ ] **Step 3: Implement both helpers**

Add to `harness/evolve.py` after `initial_population`:

```python
def seeded_population(seed_genome, size, sigma, rng):
    """Population seeded from an existing champion: the seed itself, then mutants.

    A fresh random start throws away everything a previous run learned — the
    evolved champion earns ~20,000 reward where a random genome earns ~1,700, so
    an unseeded run spends its first generations re-deriving the basics (#70).
    Keeping the seed verbatim at index 0 means the run can never end up worse
    than where it began.
    """
    pop = [list(seed_genome)]
    while len(pop) < size:
        pop.append(mutate(seed_genome, sigma, rng))
    return pop[:size]


def load_genome(path):
    """Load a genome artifact for --seed-genome. Raise ValueError if unusable.

    Deliberately loud: a silent fallback to random weights is how a submission
    once shipped running on noise (Phase 4). A bad --seed-genome must stop the run.
    """
    try:
        with open(path) as fh:
            data = json.load(fh)
    except (OSError, ValueError) as exc:
        raise ValueError(f"could not read seed genome {path!r}: {exc}") from exc
    g = data.get("genome") if isinstance(data, dict) else data
    if not isinstance(g, list):
        raise ValueError(f"seed genome {path!r} has no 'genome' list")
    if len(g) != GENOME_LEN:
        raise ValueError(
            f"seed genome {path!r} has length {len(g)}, expected {GENOME_LEN}")
    return [float(w) for w in g]
```

- [ ] **Step 4: Wire `seed_genome` into `evolve()`**

Add `seed_genome=None` to `evolve()`'s keyword arguments, and replace its population
initialization line:

```python
    population = initial_population(pop_size, seed)
```

with:

```python
    population = (seeded_population(seed_genome, pop_size, sigma, rng)
                  if seed_genome is not None else initial_population(pop_size, seed))
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `PYTHONPATH=. .venv/bin/python -m pytest tests/ -q`
Expected: PASS — the whole suite.

- [ ] **Step 6: Wire the CLI flag**

In `main()`:

```python
    ap.add_argument("--seed-genome", default=None,
                    help="start from this genome artifact instead of random init")
```

Before the `evolve(...)` call:

```python
    seed_genome = load_genome(args.seed_genome) if args.seed_genome else None
```

Pass `seed_genome=seed_genome` into `evolve(...)`, and add `"seed_genome": args.seed_genome`
to the `meta` dict in the `save_genome` call.

- [ ] **Step 7: Verify the CLI**

Run: `PYTHONPATH=. .venv/bin/python -m harness.evolve --help`
Expected: `--seed-genome` and `--anchor-weight` both listed.

Run: `PYTHONPATH=. .venv/bin/python -m harness.evolve --seed-genome /nope.json --dry-run`
Expected: exits with a clear `could not read seed genome` message rather than starting a run.

- [ ] **Step 8: Commit**

```bash
git add harness/evolve.py tests/test_evolve.py
git commit -m "feat(evolve): --seed-genome to build on a prior champion (#70)

evolve() re-initialized fresh random weights every run, so each one spent its
early generations re-deriving what the last one already knew — the evolved
champion earns ~20,000 reward where a random genome earns ~1,700. Seed the
population from an existing artifact instead, keeping the seed verbatim at index
0 so a run can never end below its starting point.

A missing or wrong-length seed genome raises rather than falling back to random
weights: the silent version of that fallback is what shipped a submission
running on noise before Phase 4.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 4: Per-generation checkpointing

An interrupted overnight run currently loses everything. Issue #70 calls this out explicitly.

**Files:**
- Modify: `harness/evolve.py` (add `checkpoint_genome`; add a `checkpoint_fn` hook to `evolve`; wire it in `main`)
- Test: `tests/test_evolve.py`

**Interfaces:**
- Consumes: `save_genome`, `load_genome` (Task 3), `evolve` (Task 2).
- Produces:
  - `checkpoint_genome(path, genome, fitness, history) -> bool` — writes atomically; warns and returns `False` on failure instead of raising.
  - `evolve(...)` gains a `checkpoint_fn=None` keyword, called once per generation as `checkpoint_fn(best_genome, best_fitness, history)`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_evolve.py`:

```python
def test_checkpoint_genome_writes_a_loadable_artifact(tmp_path):
    """A checkpoint is a real genome artifact, loadable mid-run."""
    p = tmp_path / "ckpt.json"
    g = [0.25] * ev.GENOME_LEN
    assert ev.checkpoint_genome(str(p), g, 0.42, [{"gen": 0, "best": 0.42}]) is True
    assert ev.load_genome(str(p)) == g


def test_checkpoint_genome_records_progress_in_meta(tmp_path):
    """The checkpoint carries fitness and generations-so-far, so an interrupted
    run is interpretable without the console output."""
    p = tmp_path / "ckpt.json"
    ev.checkpoint_genome(str(p), [0.25] * ev.GENOME_LEN, 0.42,
                         [{"gen": 0, "best": 0.4}, {"gen": 1, "best": 0.42}])
    meta = json.loads(p.read_text())["meta"]
    assert meta["fitness"] == 0.42
    assert meta["generations_completed"] == 2
    assert meta["checkpoint"] is True


def test_checkpoint_genome_survives_a_write_failure(tmp_path):
    """A disk hiccup must not kill an 8-hour run — warn and carry on."""
    blocker = tmp_path / "not_a_dir"
    blocker.write_text("i am a file, not a directory")
    bad = blocker / "sub" / "ckpt.json"
    assert ev.checkpoint_genome(str(bad), [0.25] * ev.GENOME_LEN, 0.1, []) is False


def test_evolve_checkpoints_once_per_generation():
    """Every generation persists the best-so-far, so an interrupt loses at most one."""
    calls = []

    def rewards(a, b, seed=None):
        return (100.0, 100.0)

    ev.evolve(generations=3, pop_size=4, games=2, sigma=0.1, sample_k=1, hof_cap=1,
              anchor_names=(), seed=1, rewards_fn=rewards,
              anchor_agents_override=[_tagged("")],
              checkpoint_fn=lambda g, f, h: calls.append((f, len(h))))
    assert len(calls) == 3
    assert [n for _, n in calls] == [1, 2, 3]
```

Add `import json` to the test module's imports if not already present.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `PYTHONPATH=. .venv/bin/python -m pytest tests/test_evolve.py -k checkpoint -v`
Expected: FAIL — `AttributeError: module 'harness.evolve' has no attribute 'checkpoint_genome'`

- [ ] **Step 3: Implement `checkpoint_genome`**

Add to `harness/evolve.py` after `save_genome`:

```python
def checkpoint_genome(path, genome, fitness, history):
    """Persist the best-so-far genome mid-run. Return True on success.

    Written to a temp file and moved into place with os.replace, so an interrupt
    can never leave a half-written artifact. A write failure warns and returns
    False rather than raising: losing an 8-hour run to a transient disk error
    would be worse than a missing checkpoint (#70).
    """
    tmp = f"{path}.tmp"
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(tmp, "w") as fh:
            json.dump({"genome": list(genome), "meta": {
                "fitness": fitness,
                "generations_completed": len(history),
                "checkpoint": True,
                "history": history,
            }}, fh, indent=2)
            fh.write("\n")
        os.replace(tmp, path)
        return True
    except OSError as exc:
        print(f"warning: checkpoint to {path!r} failed ({exc}); continuing", file=sys.stderr)
        return False
```

- [ ] **Step 4: Add the `checkpoint_fn` hook to `evolve()`**

Add `checkpoint_fn=None` to `evolve()`'s keyword arguments. Inside the generation loop,
immediately after the `if gen_best_f > best_fit:` block and before the `elites = ...` line:

```python
        if checkpoint_fn is not None:
            checkpoint_fn(best_genome, best_fit, list(history))
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `PYTHONPATH=. .venv/bin/python -m pytest tests/ -q`
Expected: PASS — the whole suite.

- [ ] **Step 6: Wire checkpointing into `main()`**

Before the `evolve(...)` call:

```python
    ckpt = None if args.dry_run else (
        lambda g, f, h: checkpoint_genome(args.out, g, f, h))
```

Pass `checkpoint_fn=ckpt` into `evolve(...)`. The final `save_genome` call stays as it is —
it overwrites the last checkpoint with the complete metadata block.

- [ ] **Step 7: Verify end to end with a tiny real run**

Run: `PYTHONPATH=. .venv/bin/python -m harness.evolve --generations 2 --pop 4 --games 1 --sample-k 1 --hof-cap 1 --out /tmp/ckpt_test.json`
Expected: prints two `gen N: best=... mean=...` lines, then `saved champion genome to /tmp/ckpt_test.json`. Takes a few minutes — these are real games.

- [ ] **Step 8: Commit**

```bash
git add harness/evolve.py tests/test_evolve.py
git commit -m "feat(evolve): checkpoint the best genome every generation (#70)

evolve() wrote the champion only at the very end, so an interrupted overnight
run lost everything. Persist the best-so-far each generation via
write-temp-then-os.replace, so an interrupt can never leave a half-written
artifact. A write failure warns and continues rather than raising — losing an
8-hour run to a transient disk error would be the worse outcome.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 5: `harness/genome_bench.py` — the frozen success bar

The agreed acceptance criterion for #70: a reproducible number that makes "0.5833 is a plateau" falsifiable. This is the scratch diagnostic from the brainstorm, promoted to a real tool.

**Files:**
- Create: `harness/genome_bench.py`
- Create: `tests/test_genome_bench.py`

**Interfaces:**
- Consumes: `evolve.load_genome` (Task 3), `evolve.opponent_record` (Task 2), `evolve.genome_agent`, `evolve.DEFAULT_ANCHORS`, `tournament.build_agents`, `tournament.play_rewards` (Task 1).
- Produces: `benchmark_genome(genome, anchor_names=DEFAULT_ANCHORS, games=4, seed_base=0, rewards_fn=None, agents_override=None) -> dict` with keys `"per_opponent"` (list of dicts each carrying `"name"`, `"w"`, `"t"`, `"l"`, `"games"`, `"win_rate"`, `"share"`), `"win_rate"`, `"share"`, `"games"`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_genome_bench.py`:

```python
"""Frozen per-opponent benchmark of one genome (#70)."""
from __future__ import annotations
from harness import genome_bench as gb


def _tagged(tag):
    """Return a stub agent with a tag."""
    def agent(obs):
        return {"farmer": ["PASS"], "hands": [], "market": []}
    agent.tag = tag
    return agent


def _rewards(a, b, seed=None):
    """The agent tagged "strong" scores 300 to the other's 100."""
    if getattr(a, "tag", "") == "strong":
        return (300.0, 100.0)
    if getattr(b, "tag", "") == "strong":
        return (100.0, 300.0)
    return (100.0, 100.0)


def test_benchmark_reports_a_row_per_opponent():
    """The breakdown is per opponent — a single total hid that the champion beat
    exactly one anchor and lost to all five others (#70)."""
    agents = {"weak": _tagged(""), "strong": _tagged("strong")}
    out = gb.benchmark_genome(None, games=2, agents_override=agents,
                              rewards_fn=_rewards)
    names = [r["name"] for r in out["per_opponent"]]
    assert names == ["weak", "strong"]


def test_benchmark_separates_a_beaten_opponent_from_an_unbeaten_one():
    """Losing every game to one opponent and drawing another must be visible
    as two distinct rows, not averaged into one number."""
    agents = {"weak": _tagged(""), "strong": _tagged("strong")}
    out = gb.benchmark_genome(None, games=2, agents_override=agents,
                              rewards_fn=_rewards)
    rows = {r["name"]: r for r in out["per_opponent"]}
    assert rows["weak"]["win_rate"] == 0.5 and rows["weak"]["share"] == 0.5
    assert rows["strong"]["win_rate"] == 0.0 and rows["strong"]["share"] == 0.25


def test_benchmark_totals_average_the_opponents():
    """Overall win-rate and share weight every opponent equally."""
    agents = {"weak": _tagged(""), "strong": _tagged("strong")}
    out = gb.benchmark_genome(None, games=2, agents_override=agents,
                              rewards_fn=_rewards)
    assert out["win_rate"] == 0.25            # (0.5 + 0.0) / 2
    assert out["share"] == 0.375              # (0.5 + 0.25) / 2
    assert out["games"] == 4


def test_benchmark_is_reproducible():
    """ADR-0005: same arguments, same numbers, every time."""
    agents = {"weak": _tagged(""), "strong": _tagged("strong")}
    kw = dict(games=2, agents_override=agents, rewards_fn=_rewards)
    assert gb.benchmark_genome(None, **kw) == gb.benchmark_genome(None, **kw)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `PYTHONPATH=. .venv/bin/python -m pytest tests/test_genome_bench.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'harness.genome_bench'`

- [ ] **Step 3: Create `harness/genome_bench.py`**

```python
"""Frozen benchmark of a single genome against the fixed anchors (#70).

The evolution loop's own fitness is not comparable between runs — its opponent
pool contains a growing Hall-of-Fame and a random population sample, so the
number shifts underneath you. This module plays a genome against the named
anchors ONLY, at fixed seeds, so two runs can actually be compared.

It reports win-rate AND mean score share. Fitness optimizes share, but the
Kaggle ladder scores win/tie only — reporting both makes any divergence between
them visible instead of assumed away.

Usage:
    python -m harness.genome_bench --genome strategies/champion_genome.json --games 4
"""

from __future__ import annotations

import argparse
import sys

from harness.evolve import (DEFAULT_ANCHORS, genome_agent, load_genome,
                            opponent_record)
from harness.tournament import build_agents
from harness.tournament import play_rewards as _play_rewards


def _passer():
    """A do-nothing agent, used when no genome is supplied (tests)."""
    def agent(obs):
        return {"farmer": ["PASS"], "hands": [], "market": []}
    return agent


def benchmark_genome(genome, anchor_names=DEFAULT_ANCHORS, games=4, seed_base=0,
                     rewards_fn=None, agents_override=None):
    """Play `genome` against each anchor and report the per-opponent breakdown.

    No Hall-of-Fame and no population sample: those are what let sibling-beating
    dominate the evolution fitness and saturate it at 0.5833 (#70). Seeds derive
    from the opponent index and game number, so the result reproduces exactly.
    """
    rewards_fn = rewards_fn or _play_rewards
    agents = (agents_override if agents_override is not None
              else build_agents(list(anchor_names)))
    me = genome_agent(genome) if genome is not None else _passer()

    rows = []
    for oi, (name, opp) in enumerate(agents.items()):
        rec = opponent_record(me, opp, games, seed_base + oi * 100000, rewards_fn)
        rows.append({"name": name, **rec})

    n = len(rows)
    return {
        "per_opponent": rows,
        "win_rate": sum(r["win_rate"] for r in rows) / n if n else 0.5,
        "share": sum(r["share"] for r in rows) / n if n else 0.5,
        "games": sum(r["games"] for r in rows),
    }


def main(argv=None):  # pragma: no cover
    ap = argparse.ArgumentParser(description="benchmark one genome vs the fixed anchors (#70)")
    ap.add_argument("--genome", required=True, help="path to a genome artifact")
    ap.add_argument("--games", type=int, default=4)
    ap.add_argument("--seed-base", type=int, default=0)
    ap.add_argument("--anchors", nargs="*", default=list(DEFAULT_ANCHORS))
    args = ap.parse_args(argv)

    out = benchmark_genome(load_genome(args.genome), anchor_names=args.anchors,
                           games=args.games, seed_base=args.seed_base)
    for r in out["per_opponent"]:
        print(f"{r['name']:16s} W{r['w']} T{r['t']} L{r['l']}  "
              f"rate={r['win_rate']:.3f} share={r['share']:.3f}")
    print(f"{'TOTAL':16s} games={out['games']}  "
          f"rate={out['win_rate']:.4f} share={out['share']:.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `PYTHONPATH=. .venv/bin/python -m pytest tests/test_genome_bench.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Reproduce the diagnostic that motivated the issue**

Run: `PYTHONPATH=. .venv/bin/python -m harness.genome_bench --genome strategies/champion_genome.json --games 4`

Expected: the table from the issue — `spoiler` at rate 1.000, the other five at 0.000, TOTAL rate ≈ 0.1667, and shares in the 0.35–0.62 band. Takes ~1 minute (24 real games). **If the win-rates do not match the issue's table, stop and report** — the benchmark is the success criterion, so it has to reproduce the number it is meant to measure.

- [ ] **Step 6: Commit**

```bash
git add harness/genome_bench.py tests/test_genome_bench.py
git commit -m "feat(bench): frozen per-opponent genome benchmark (#70)

The evolution loop's fitness is not comparable between runs — its pool holds a
growing Hall-of-Fame and a random population sample, so the number shifts
underneath you. Benchmark a genome against the named anchors only, at fixed
seeds, reporting win-rate AND mean share so the divergence between the ladder's
win/tie scoring and the shaped fitness stays visible.

This is the agreed success criterion for #70: it makes 'evolution plateaus at
0.5833' a falsifiable claim rather than an artifact of a shifting pool.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 6: Documentation and the full CI gate

**Files:**
- Modify: `CLAUDE.md` (the "Quick reference" list)
- Modify: `docs/adr/0008-neuroevolution-against-a-diverse-pool.md` (a Consequences note)

**Interfaces:**
- Consumes: everything above.
- Produces: no new code interfaces.

- [ ] **Step 1: Add the benchmark to CLAUDE.md's quick reference**

In the `## Quick reference` bullet list, after the `harness.rounds` line, add:

```markdown
- `python -m harness.genome_bench --genome <path> --games 4` — score one genome against the fixed anchors only (no Hall-of-Fame, no population sample). The **comparable** number across evolution runs; `evolve`'s own fitness is not (#70).
```

- [ ] **Step 2: Record the fitness-signal finding in ADR-0008**

ADR-0008 is Accepted and stays Accepted — the diverse-pool decision was right; the
defect was in how the pool was *weighted*. Append to its `## Consequences` section:

```markdown
- **Pool composition must be weighted, not merely diverse (#70, 2026-08-14).** The
  first implementation averaged all opponents equally, so a population sample and
  Hall-of-Fame that were half the pool supplied all the gradient — and saturated,
  pinning fitness at 0.5833 while the agent lost to every real anchor. Fitness is
  now an anchor-dominant blend of shaped score shares. Win/loss alone gives no
  gradient below the finish line.
```

- [ ] **Step 3: Run the full CI gate locally**

`.github/workflows/ci.yml` has exactly two steps — pytest with coverage, then an
explicit two-dimension gate on the JSON report. There is no formatter or linter step
in this repo. Replay both:

```bash
PYTHONPATH=. .venv/bin/python -m pytest -q --cov --cov-branch --cov-report=term-missing --cov-report=json
```

```bash
PYTHONPATH=. .venv/bin/python -c "
import json, sys
t = json.load(open('coverage.json'))['totals']
line = 100.0 * t['covered_lines'] / t['num_statements'] if t['num_statements'] else 100.0
branch = 100.0 * t['covered_branches'] / t['num_branches'] if t['num_branches'] else 100.0
print(f'line {line:.1f}% (gate 85%) / branch {branch:.1f}% (gate 65%)')
sys.exit(line < 85.0 or branch < 65.0)
"
```

Expected: all tests green, and the gate line printing both figures above their floors.

If coverage on `harness/evolve.py` or `harness/genome_bench.py` fell below the gate,
add unit tests for the uncovered pure helpers — do **not** paper over it by widening
`# pragma: no cover`, which is reserved for CLI `main()`s and live-game loops.

- [ ] **Step 4: Confirm the submitted artifact is untouched**

Run: `git diff --stat origin/main...HEAD -- strategies/ kaggisim/ build/`
Expected: **empty**. This work is harness-only; any diff here means something leaked
into the submission path and must be reverted.

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md docs/adr/0008-neuroevolution-against-a-diverse-pool.md
git commit -m "docs: record the fitness-signal finding (#70)

ADR-0008's diverse-pool decision was right; the defect was in how the pool was
weighted. Note that composition must be weighted rather than merely diverse, and
add genome_bench to the quick reference as the comparable cross-run number.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Validation: does the plateau actually move?

Not a task — the experiment the branch exists to enable, run after the tasks land.
Per ADR-0007 the result belongs in issue #70 either way.

Baseline is already recorded: the current champion scores **win-rate 0.1667, share ≈ 0.53**
on `genome_bench --games 4`.

```bash
# Seeded from the current champion, sized to the ~14,000-game overnight budget.
PYTHONPATH=. .venv/bin/python -m harness.evolve \
  --generations 12 --pop 16 --games 2 --sample-k 3 --hof-cap 3 \
  --seed-genome strategies/champion_genome.json \
  --out harness/genomes/champion_genome.json --seed 1
```

That is `12 × 16 × 2 × (6 + 3 + 3) = 4,608` games ≈ 2.5h, comfortably inside budget
and leaving room for a second run at a different `--seed`.

Then compare on the frozen bar:

```bash
PYTHONPATH=. .venv/bin/python -m harness.genome_bench --genome harness/genomes/champion_genome.json --games 4
```

**Hypothesis:** mean share rises above the champion's ≈ 0.53, and at least one anchor
beyond `spoiler` moves off a 0.000 win-rate.

**If share rises but win-rate does not**, that is the margin-vs-wins proxy gap the spec
flagged — report it, and it becomes the argument for #71 (widening the controller)
rather than for more search. **If neither moves**, the substrate is the ceiling after
all and #71 is next. Either outcome is a real result; record it on #70 before deciding
whether to bake a new champion.
