# Neuroevolution Harness (Phase 2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `harness/evolve.py` — a neuroevolution loop that evolves `neuropilot`'s genome by win-rate competition against a co-evolving population + fixed anchors, and persists the best genome as an artifact `neuropilot` loads for submission.

**Architecture:** Pure helpers (population, mutation, selection, Hall-of-Fame, fitness) unit-tested with an injected stub `play_fn` (no real games in unit tests) + a thin `evolve()` loop + a CLI. Reuses `neuropilot`'s frozen genome interface, `kaggisim.strategy.make_agent`, and `harness.tournament.play`/`build_agents`.

**Tech Stack:** Python 3.12 (3.11 floor), stdlib (`random`, `json`, `math`), `pytest`, `kaggle_environments` (only in the real CLI/smoke run, never unit tests).

## Global Constraints

- **Stdlib only.** No numpy. Follows the `kaggisim`/`harness` convention.
- **Fitness = win-rate counting ties as half:** `(wins + 0.5*ties) / total_games`, a float in `[0,1]` (the ladder is win/tie-only).
- **Determinism/reproducibility (ADR-0005):** every random draw goes through an injected `random.Random(seed)`; game seeds are derived deterministically; `evolve()` is reproducible under a fixed `seed` + `play_fn`.
- **No real games in unit tests:** all game-touching helpers take an injected `play_fn`; tests pass a deterministic stub. Real games happen only in the CLI and the one manual smoke run.
- **`neuropilot` frozen interface (Phase 1):** `genome_size(n_in,h1,n_out)`, `random_genome(n_in,h1,n_out,seed)`, `MLP.from_genome(genome,n_in,h1,n_out)`, `NeuroPilotStrategy(genome=None)`, `N_FEATURES`, `H1`, `N_KNOBS`, `DEFAULT_GENOME`. A genome is `list[float]` of length `genome_size(N_FEATURES,H1,N_KNOBS)`.
- **Genome → agent:** `from kaggisim.strategy import make_agent`; `make_agent(NeuroPilotStrategy(genome=g))` yields the `agent(obs)` callable `play` expects.
- **Anchors pluggable:** anchor opponents are named strategies resolved via `harness.tournament.build_agents`; the default anchor list is a module constant, overridable, so Phase 3 external agents slot in.
- **Coverage gate:** line ≥85%, branch ≥65% (bare `pytest --cov --cov-branch`). `# pragma: no cover` only on the CLI `main()` and the real-game `play` path, never pure helpers.
- **Run from repo root, venv active** (`source .venv/bin/activate`). Tests pristine.

---

## File Structure

- `harness/evolve.py` — **create.** Population/mutation/selection/HoF/fitness helpers + `evolve()` + CLI.
- `strategies/neuropilot.py` — **modify.** Add `load_champion_genome(path)` and make `DEFAULT_GENOME` load the champion artifact when present (CI-safe fallback to the random default).
- `tests/test_evolve.py` — **create.** Unit tests for the pure + stub-`play_fn` helpers and the loop.
- `tests/test_neuropilot.py` — **modify.** Add tests for `load_champion_genome` + the fallback.
- `harness/genomes/.gitkeep` — **create.** The dir the champion-genome artifact lands in (the artifact itself is written by a real evolution run, not this plan).

---

### Task 1: Population, mutation, selection (pure)

**Files:** Create `harness/evolve.py`; Test `tests/test_evolve.py`.

**Interfaces:**
- Consumes: `neuropilot.genome_size`, `neuropilot.random_genome`, `neuropilot.N_FEATURES/H1/N_KNOBS`.
- Produces: `GENOME_LEN` (= `genome_size(N_FEATURES,H1,N_KNOBS)`); `initial_population(size, seed) -> list[list[float]]`; `mutate(genome, sigma, rng) -> list[float]`; `select_elites(scored, k) -> list[list[float]]` (scored = `list[(genome, fitness)]`); `next_generation(elites, size, sigma, rng) -> list[list[float]]`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_evolve.py
"""Neuroevolution harness (Phase 2, #66)."""
from __future__ import annotations
import random
from harness import evolve as ev


def test_initial_population_shape_and_determinism():
    pop = ev.initial_population(5, seed=1)
    assert len(pop) == 5
    assert all(len(g) == ev.GENOME_LEN for g in pop)
    assert ev.initial_population(5, seed=1) == pop            # deterministic
    assert ev.initial_population(5, seed=2) != pop            # seed matters


def test_mutate_preserves_length_changes_weights_deterministically():
    g = [0.0] * ev.GENOME_LEN
    m1 = ev.mutate(g, sigma=0.1, rng=random.Random(7))
    assert len(m1) == ev.GENOME_LEN and m1 != g
    assert m1 == ev.mutate(g, sigma=0.1, rng=random.Random(7))  # same rng seed => same


def test_mutate_sigma_zero_is_a_noop():
    g = [0.3] * ev.GENOME_LEN
    assert ev.mutate(g, sigma=0.0, rng=random.Random(1)) == g


def test_select_elites_returns_top_k_by_fitness():
    scored = [(["a"], 0.2), (["b"], 0.9), (["c"], 0.5)]
    assert ev.select_elites(scored, 2) == [["b"], ["c"]]


def test_next_generation_keeps_elites_and_refills_to_size():
    elites = [[0.0]*ev.GENOME_LEN, [1.0]*ev.GENOME_LEN]
    gen = ev.next_generation(elites, size=5, sigma=0.1, rng=random.Random(3))
    assert len(gen) == 5
    assert gen[0] in elites and gen[1] in elites               # elitism: elites carried verbatim
```

- [ ] **Step 2: Run to verify fail** — `ROBRICULTURE_STRICT=1 pytest tests/test_evolve.py -v` → ModuleNotFound / undefined.

- [ ] **Step 3: Implement**

```python
# harness/evolve.py
from __future__ import annotations
import random
from strategies import neuropilot as npilot

GENOME_LEN = npilot.genome_size(npilot.N_FEATURES, npilot.H1, npilot.N_KNOBS)

def initial_population(size, seed):
    return [npilot.random_genome(npilot.N_FEATURES, npilot.H1, npilot.N_KNOBS, seed=seed * 1000 + i)
            for i in range(size)]

def mutate(genome, sigma, rng):
    if sigma == 0.0:
        return list(genome)
    return [w + rng.gauss(0.0, sigma) for w in genome]

def select_elites(scored, k):
    ranked = sorted(scored, key=lambda gf: gf[1], reverse=True)
    return [g for g, _ in ranked[:k]]

def next_generation(elites, size, sigma, rng):
    gen = [list(e) for e in elites]                 # elitism: carry survivors verbatim
    while len(gen) < size:
        parent = elites[rng.randrange(len(elites))]
        gen.append(mutate(parent, sigma, rng))
    return gen[:size]
```

- [ ] **Step 4: Run to verify pass** — PASS (5).
- [ ] **Step 5: Commit** — `git add harness/evolve.py tests/test_evolve.py && git commit -m "feat(evolve): population, mutation, truncation selection (#66)"`

---

### Task 2: Fitness evaluation (stub-tested)

**Files:** Modify `harness/evolve.py`; Test `tests/test_evolve.py`.

**Interfaces:**
- Consumes: Task-1 helpers; `neuropilot.NeuroPilotStrategy`; `kaggisim.strategy.make_agent`; `harness.tournament.play` (signature `play(agent_a, agent_b, seed) -> int` in {1,-1,0}).
- Produces: `genome_agent(genome)` (→ the `agent(obs)` callable); `match_winrate(agent, opponents, games, seed_base, play_fn) -> float` (win-rate ties-as-half vs all opponents, sides alternated); `evaluate_population(population, opponents, games, seed_base, play_fn) -> list[(genome, float)]`.

- [ ] **Step 1: Write the failing tests**

```python
def _stub_play(a, b, seed=None):
    # Deterministic: agent tagged "win" beats everything; ties if both tagged "tie".
    if getattr(a, "tag", "") == "win": return 1
    if getattr(b, "tag", "") == "win": return -1
    return 0

def _tagged(tag):
    def agent(obs): return {"farmer": ["PASS"], "hands": [], "market": []}
    agent.tag = tag
    return agent

def test_match_winrate_counts_ties_as_half():
    me = _tagged("")                                  # always ties vs a plain opp
    opp = [_tagged("")]
    assert ev.match_winrate(me, opp, games=4, seed_base=0, play_fn=_stub_play) == 0.5

def test_match_winrate_all_wins_is_one():
    assert ev.match_winrate(_tagged("win"), [_tagged("")], games=2, seed_base=0, play_fn=_stub_play) == 1.0

def test_evaluate_population_returns_genome_fitness_pairs():
    pop = ev.initial_population(3, seed=1)
    scored = ev.evaluate_population(pop, [_tagged("")], games=2, seed_base=0, play_fn=_stub_play)
    assert len(scored) == 3
    assert all(g in pop and 0.0 <= f <= 1.0 for g, f in scored)
```

- [ ] **Step 2: Run to verify fail** — undefined `match_winrate`/`evaluate_population`.

- [ ] **Step 3: Implement**

```python
from kaggisim.strategy import make_agent
from harness.tournament import play as _play

def genome_agent(genome):
    return make_agent(npilot.NeuroPilotStrategy(genome=genome))

def match_winrate(agent, opponents, games, seed_base, play_fn=_play):
    wins = ties = total = 0
    for oi, opp in enumerate(opponents):
        for g in range(games):
            seed = seed_base + oi * 100000 + g
            r = play_fn(agent, opp, seed) if g % 2 == 0 else -play_fn(opp, agent, seed)
            total += 1
            if r > 0: wins += 1
            elif r == 0: ties += 1
    return (wins + 0.5 * ties) / total if total else 0.5

def evaluate_population(population, opponents, games, seed_base, play_fn=_play):
    return [(g, match_winrate(genome_agent(g), opponents, games, seed_base + i, play_fn))
            for i, g in enumerate(population)]
```

- [ ] **Step 4: Run to verify pass** — PASS.
- [ ] **Step 5: Commit** — `git commit -m "feat(evolve): win-rate fitness evaluation (ties-as-half) (#66)"`

---

### Task 3: Opponent pool, Hall-of-Fame, and the evolve() loop

**Files:** Modify `harness/evolve.py`; Test `tests/test_evolve.py`.

**Interfaces:**
- Consumes: Tasks 1-2; `harness.tournament.build_agents`.
- Produces: `DEFAULT_ANCHORS` (tuple of strategy names: `("meta_bot","ranch_hands","market_farmer","ranch_adaptive","wheat_hands","spoiler")`); `anchor_agents(names) -> list` (via `build_agents`, values only); `build_opponents(pop_agents, anchor_agents, hof_agents, sample_k, rng) -> list` (all anchors + all hof + a `sample_k` random sample of `pop_agents`); `update_hof(prev_hof, elites, cap) -> list[genome]` (best-of-run kept, deduped, capped); `evolve(generations, pop_size, games, sigma, sample_k, hof_cap, anchor_names, seed, play_fn) -> dict` returning `{"best_genome","best_fitness","history"}` where history is `list[{"gen","best","mean"}]`.

- [ ] **Step 1: Write the failing tests**

```python
def test_build_opponents_includes_anchors_hof_and_a_pop_sample():
    rng = random.Random(0)
    pop = [_tagged(f"p{i}") for i in range(5)]
    opp = ev.build_opponents(pop, [_tagged("anchor")], [_tagged("hof")], sample_k=2, rng=rng)
    tags = [getattr(a, "tag", "") for a in opp]
    assert "anchor" in tags and "hof" in tags
    assert sum(t.startswith("p") for t in tags) == 2

def test_update_hof_keeps_best_and_caps():
    hof = ev.update_hof([], [[1.0]*ev.GENOME_LEN, [2.0]*ev.GENOME_LEN], cap=1)
    assert len(hof) == 1

def test_evolve_is_deterministic_and_reports_history():
    # Stub: fitness = mean of genome (so mutation toward higher weights wins); no real games.
    def stub(a, b, seed=None):
        return (getattr(a, "_score", 0) > getattr(b, "_score", 0)) - (getattr(a, "_score", 0) < getattr(b, "_score", 0))
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
                       hof_cap=2, anchor_names=[], seed=1, play_fn=stub)
        assert set(out) == {"best_genome", "best_fitness", "history"}
        assert len(out["history"]) == 3
        out2 = E.evolve(generations=3, pop_size=6, games=1, sigma=0.2, sample_k=2,
                        hof_cap=2, anchor_names=[], seed=1, play_fn=stub)
        assert out2["best_fitness"] == out["best_fitness"]     # deterministic
    finally:
        E.genome_agent = orig
```

- [ ] **Step 2: Run to verify fail** — undefined names.

- [ ] **Step 3: Implement**

```python
from harness.tournament import build_agents

DEFAULT_ANCHORS = ("meta_bot", "ranch_hands", "market_farmer", "ranch_adaptive", "wheat_hands", "spoiler")

def anchor_agents(names):
    return list(build_agents(list(names)).values())

def build_opponents(pop_agents, anchor_agents_list, hof_agents, sample_k, rng):
    sample = rng.sample(pop_agents, min(sample_k, len(pop_agents))) if pop_agents else []
    return list(anchor_agents_list) + list(hof_agents) + sample

def update_hof(prev_hof, elites, cap):
    combined = list(prev_hof)
    for e in elites:
        if e not in combined:
            combined.append(e)
    return combined[-cap:] if cap and len(combined) > cap else combined

def evolve(generations, pop_size, games, sigma, sample_k, hof_cap,
           anchor_names=DEFAULT_ANCHORS, seed=0, play_fn=_play):
    rng = random.Random(seed)
    anchors = anchor_agents(anchor_names)
    population = initial_population(pop_size, seed)
    hof_genomes = []
    best_genome, best_fit, history = None, -1.0, []
    for gen in range(generations):
        pop_agents = [genome_agent(g) for g in population]
        hof_agents = [genome_agent(g) for g in hof_genomes]
        scored = []
        for i, g in enumerate(population):
            opp = build_opponents([pa for j, pa in enumerate(pop_agents) if j != i],
                                  anchors, hof_agents, sample_k, rng)
            scored.append((g, match_winrate(pop_agents[i], opp, games, seed + gen * 7919 + i, play_fn)))
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

- [ ] **Step 4: Run to verify pass** — PASS.
- [ ] **Step 5: Commit** — `git commit -m "feat(evolve): opponent pool, Hall-of-Fame, evolve() loop (#66)"`

---

### Task 4: Genome artifact + neuropilot loader

**Files:** Modify `harness/evolve.py`, `strategies/neuropilot.py`; Create `harness/genomes/.gitkeep`; Test `tests/test_evolve.py`, `tests/test_neuropilot.py`.

**Interfaces:**
- Produces: `evolve.save_genome(path, genome, meta) -> None` (writes JSON `{"genome","meta"}`); `evolve.GENOME_ARTIFACT` (= `harness/genomes/champion_genome.json`); `neuropilot.load_champion_genome(path) -> list[float] | None` (returns the genome if the file exists and its length == `genome_size(...)`, else None; never raises). `neuropilot.DEFAULT_GENOME` is the champion genome when the artifact loads, else the seeded random default.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_evolve.py
def test_save_genome_round_trips(tmp_path):
    import json
    p = tmp_path / "g.json"
    ev.save_genome(str(p), [0.1, 0.2], {"fitness": 0.7})
    d = json.loads(p.read_text())
    assert d["genome"] == [0.1, 0.2] and d["meta"]["fitness"] == 0.7
```
```python
# tests/test_neuropilot.py
def test_load_champion_genome_valid_and_invalid(tmp_path):
    import json
    good = tmp_path / "good.json"
    good.write_text(json.dumps({"genome": [0.0]*np.genome_size(np.N_FEATURES, np.H1, np.N_KNOBS), "meta": {}}))
    assert np.load_champion_genome(str(good)) is not None
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"genome": [0.0, 0.0], "meta": {}}))   # wrong length
    assert np.load_champion_genome(str(bad)) is None
    assert np.load_champion_genome(str(tmp_path / "missing.json")) is None
```

- [ ] **Step 2: Run to verify fail** — undefined.

- [ ] **Step 3: Implement**

`harness/evolve.py`:
```python
import json, os
GENOME_ARTIFACT = os.path.join(os.path.dirname(__file__), "genomes", "champion_genome.json")

def save_genome(path, genome, meta):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        json.dump({"genome": list(genome), "meta": meta}, fh, indent=2)
        fh.write("\n")
```
`strategies/neuropilot.py` (add near `DEFAULT_GENOME`):
```python
import json, os
_GENOME_ARTIFACT = os.path.join(os.path.dirname(os.path.dirname(__file__)), "harness", "genomes", "champion_genome.json")

def load_champion_genome(path=_GENOME_ARTIFACT):
    """The evolved champion genome if present and shape-correct, else None (never raises)."""
    try:
        with open(path) as fh:
            g = json.load(fh)["genome"]
        return g if len(g) == genome_size(N_FEATURES, H1, N_KNOBS) else None
    except Exception:
        return None

_loaded = load_champion_genome()
DEFAULT_GENOME = _loaded if _loaded is not None else random_genome(N_FEATURES, H1, N_KNOBS, seed=20260812)
```
Create `harness/genomes/.gitkeep` (empty). Do NOT commit a champion_genome.json — it's written by a real evolution run.

- [ ] **Step 4: Run to verify pass** — both test files PASS. Confirm no artifact exists so `DEFAULT_GENOME` stays the random default in CI.
- [ ] **Step 5: Commit** — `git add harness/evolve.py strategies/neuropilot.py harness/genomes/.gitkeep tests/ && git commit -m "feat(evolve): genome artifact + neuropilot champion-genome loader (#66)"`

---

### Task 5: CLI + smoke evolution + full CI

**Files:** Modify `harness/evolve.py`; run CI.

**Interfaces:** Consumes all prior. Produces `main(argv=None)` (CLI, `# pragma: no cover`).

- [ ] **Step 1: Implement the CLI** (argparse over `evolve()`; flags `--generations --pop --games --sigma --sample-k --hof-cap --seed --anchors --out --dry-run`; prints per-gen `best`/`mean`; on non-dry-run, `save_genome(out, best_genome, {...})`). Mark `main` `# pragma: no cover`. Add `if __name__ == "__main__": sys.exit(main())`.

- [ ] **Step 2: Real smoke evolution (foreground, explicit long timeout)** — a tiny REAL run to prove the loop works end-to-end with real games. Run with Bash `timeout: 480000`:
```bash
ROBRICULTURE_STRICT=1 python -m harness.evolve --generations 3 --pop 6 --games 1 --sigma 0.2 --sample-k 2 --hof-cap 2 --seed 1 --dry-run
```
Confirm it prints 3 generations of best/mean fitness without crashing. Record the per-gen numbers in the report (fitness need not improve in 3 gens — this proves the machinery, not convergence).

- [ ] **Step 3: Full CI gate** — `pytest -q --cov --cov-branch --cov-report=term-missing` (Bash `timeout: 480000`). All PASS; line ≥85%, branch ≥65%. Report numbers. `# pragma: no cover` only on `main`/the real `play` path.

- [ ] **Step 4: Commit** — `git commit -m "feat(evolve): CLI + smoke run; CI gate green (#66)"`

---

## Self-Review

**Spec coverage:** population/mutation/selection → T1; win-rate fitness (ties-as-half) → T2; opponent pool (anchors+pop-sample+HoF) + HoF + evolve loop + artifact/history → T3; genome artifact + neuropilot loader (CI-safe fallback) → T4; CLI + reproducible defaults + smoke → T5. Anchor pluggability (`DEFAULT_ANCHORS`, `--anchors`) → T3/T5. All spec sections covered. ✅

**Placeholder scan:** T1-4 give complete code; T5's CLI is specified by its flags + behavior + the exact smoke command (argparse boilerplate is the implementer's to write against the flag list). No TBD/TODO.

**Type consistency:** a genome is `list[float]` throughout; `scored` is `list[(genome, float)]` in `select_elites`/`evaluate_population`/`evolve`; `play_fn(a,b,seed)->int` consistent; `genome_agent`/`match_winrate`/`evaluate_population`/`build_opponents`/`update_hof`/`evolve` signatures match across tasks. `GENOME_LEN`/`GENOME_ARTIFACT`/`DEFAULT_ANCHORS` defined once. ✅

**Note:** unit tests never run real games (stub `play_fn` + monkeypatched `genome_agent`); the only real games are T5's smoke run + the no-crash gate (which already covers `neuropilot`). Real evolution runs are unattended background jobs after merge.
