# External agents fresh per game on the evolve path (#247) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** An external competitor agent handed out by `harness.external_pool.resolve_opponents` (the evolve / genome_bench path) starts every game with a fresh module, as the gate path already does.

**Architecture:** `discover_external_agents` wraps each loaded external in a small `FreshPerGame` callable that re-imports the file on every step-0 observation. The `{name: agent}` contract of `discover_external_agents` / `resolve_opponents` is unchanged, so `harness.evolve` and `harness.genome_bench` need no edit. `_source_of` reads the wrapper's `__external_source__` so pin verification (#152) still sees the real file. Injected test stubs are not wrapped (they never pass through discovery).

**Tech Stack:** Python 3.12 in `.venv` (`.venv/bin/python`, never a bare python3), pytest with `-n auto`.

## Global Constraints

- Pure TDD: write the failing tests, **run them and quote the failure**, then the minimal code, run green, commit. One of the three new tests pins a property the fix must preserve and is expected green before the change — say so in the report.
- The build stays green: `.venv/bin/python -m pytest -q -n auto` before the commit.
- No change to `harness/evolve.py`, `harness/genome_bench.py`, `load_external_agent`, `external_anchor_agents`, or any existing assertion in `tests/test_external_pool.py`.
- Test names read `test_<the fact>`, each with a docstring or comment saying why (house style).
- Stage by explicit path; never `git add -A`; never stage `.venv` or `external_agents` (symlinks in this worktree).
- Commit messages end with a blank line and `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.

---

### Task 1: `FreshPerGame` in discovery, and `_source_of` reading through it

**Files:**
- Modify: `harness/external_pool.py` — add class `FreshPerGame` above `discover_external_agents` (line ~192); change one line in `discover_external_agents`; add the first branch in `_source_of` (line ~146).
- Test: `tests/test_external_pool.py` (append at the end).

**Interfaces:**
- Consumes: `load_external_agent(path)` (unchanged; returns a fresh callable per call), `_source_of(agent)`, `mismatched_sources(agents, pins)`, and the test module's existing helpers `_stub(name)`, `_write_manifest(tmp_path, stems)`, `_GOOD`, `_sha(text)`.
- Produces: `FreshPerGame(path, agent)` — callable `(obs, *args, **kwargs)`; attribute `__external_source__` = the file path; `discover_external_agents` returns `{name: FreshPerGame}`; `_source_of(FreshPerGame(...))` returns the path.

- [ ] **Step 1: Write the failing tests** — append to `tests/test_external_pool.py`:

```python
# --- #247: the evolve path plays one callable across games; it must reload per game ---

_COUNTER = (
    "CALLS = 0\n"
    "def agent(obs, config=None):\n"
    "    global CALLS\n"
    "    CALLS += 1\n"
    "    return CALLS\n"
)


def test_a_discovered_external_reloads_its_module_on_every_games_first_step(tmp_path):
    """The positive control for #247: a stranger's agent that counts its own calls
    in a module global reads 1 on the first turn of EVERY game. Before the fix
    the second game opened at 4."""
    (tmp_path / "counter.py").write_text(_COUNTER)
    opp = external_pool.discover_external_agents(str(tmp_path))["counter"]
    assert [opp({"step": 0}), opp({"step": 1}), opp({"step": 2})] == [1, 2, 3]
    assert [opp({"step": 0}), opp({"step": 1})] == [1, 2]


def test_resolve_opponents_hands_the_evolve_path_the_reloading_external(tmp_path):
    """The path #247 names: `resolve_opponents(include_external=True)` with real
    discovery. The one callable evolve keeps for the whole run is the reloading one."""
    (tmp_path / "counter.py").write_text(_COUNTER)
    manifest_path = _write_manifest(tmp_path, ["counter"])
    agents = external_pool.resolve_opponents(
        ["meta_bot"], include_external=True,
        build=lambda names: {n: _stub(n) for n in names},
        manifest_path=manifest_path, directory=str(tmp_path), warn=lambda message: None)
    opp = agents["counter"]
    assert opp({"step": 0}) == 1 and opp({"step": 1}) == 2
    assert opp({"step": 0}) == 1


def test_the_reloading_wrapper_still_reports_the_file_it_came_from(tmp_path):
    """Pin verification reads the source off the callable (#152); the wrapper must
    not hide it behind external_pool.py's own namespace. Green before the fix
    (discovery returned the raw function) and it must stay green after."""
    (tmp_path / "x.py").write_text(_GOOD)
    opp = external_pool.discover_external_agents(str(tmp_path))["x"]
    assert external_pool._source_of(opp) == str(tmp_path / "x.py")
    assert external_pool.mismatched_sources({"x": opp}, {"x": _sha(_GOOD)}) == []
```

- [ ] **Step 2: Run them and quote the failure**

Run: `.venv/bin/python -m pytest -q tests/test_external_pool.py -k "reloads_its_module or hands_the_evolve_path or still_reports_the_file"`
Expected: 2 failed, 1 passed. The two failures are `AssertionError` on the second-game line — `assert [4, 5] == [1, 2]` and `assert 3 == 1` — because the shared callable keeps counting; `test_the_reloading_wrapper_still_reports_the_file_it_came_from` passes already (it pins the property the fix must preserve).

- [ ] **Step 3: Minimal implementation** in `harness/external_pool.py`:

Add above `discover_external_agents`:

```python
class FreshPerGame:
    """A discovered external that re-imports its module on every game's first step (#247).

    The gate (`external_anchor_agents`) imports a fresh module per game; the
    evolve / genome_bench path (`resolve_opponents`) hands out one callable per
    run and plays it across every game, so an external that keeps module-level
    state -- day counters, cached plans, memoised prices -- started its second
    game with its first game's memory, and the gate and the ranking measured
    different opponents under one name. Reloading on the step-0 observation
    restores the gate's semantics without changing the ``{name: agent}``
    contract every consumer holds. `_source_of` reads the file off
    `__external_source__`, so pin verification (#152) still sees the real file.
    """

    def __init__(self, path, agent):
        self.__external_source__ = path
        self._agent = agent          # the module discovery already imported
        self._used = False

    def __call__(self, obs, *args, **kwargs):
        step = obs.get("step") if isinstance(obs, dict) else getattr(obs, "step", None)
        if step == 0 and self._used:
            self._agent = load_external_agent(self.__external_source__)
        self._used = True
        return self._agent(obs, *args, **kwargs)
```

In `discover_external_agents`, replace `agents[name] = load_external_agent(path)` with
`agents[name] = FreshPerGame(path, load_external_agent(path))`, and add one sentence to its
docstring: "Each agent is a `FreshPerGame` wrapper, so a consumer that keeps the callable for
a whole run still plays a fresh module per game (#247)."

In `_source_of`, directly after the `while isinstance(agent, functools.partial)` loop, add:

```python
    source = getattr(agent, "__external_source__", None)        # a FreshPerGame wrapper (#247)
    if source is not None:
        return source
```

- [ ] **Step 4: Run green**

Run: `.venv/bin/python -m pytest -q -n auto`
Expected: all pass (the existing discovery tests call the wrapper with `{}`, `None` and `({}, {})` observations; `test_resolve_opponents_verifies_the_file_each_discovered_agent_came_from` still raises on the tampered file because `_source_of` reads through the wrapper).

- [ ] **Step 5: Commit**

```bash
git add harness/external_pool.py tests/test_external_pool.py
git commit -m "external_pool: a discovered external re-imports its module on every game's first step (#247)

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

## Self-review

- **Coverage of #247:** the evolve path (`resolve_opponents` with real discovery) now hands out a callable that reloads per game — the issue's test ("reads 1 on the first turn of every game") is the first new test. `verify_pins` / `mismatched_sources` unchanged; the third test proves verification sees through the wrapper.
- **Placeholders:** none.
- **Type consistency:** `FreshPerGame(path, agent)` is what `discover_external_agents` constructs; `__external_source__` is the attribute `_source_of` reads; `_write_manifest`, `_stub`, `_GOOD`, `_sha` exist in the test module today.
