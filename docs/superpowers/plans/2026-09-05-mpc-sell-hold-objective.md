# #172 Stage 1: Sell/Hold Rollout Objective Check — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Measure whether a mirror-opponent, final-money rollout ranks sell-discipline variants of the champion the same way a real-opponent rollout does (Spearman rho), and record PASS/FAIL against the criterion declared in the spec.

**Architecture:** Four small units — a stateless sell-discipline wrapper around any `Strategy`, a state capturer that snapshots our observation from a real game, a rollout-to-end scorer with a pluggable opponent, and a CLI that builds the grid, runs the controls, computes per-state rho and prints the verdict. Nothing edits `strategies/field_rival.py`, `strategies/dense_farm.py` or the champion's decisions.

**Tech Stack:** Python 3.12 (`.venv/bin/python`, symlinked into this worktree), `kaggle_environments` 1.32.7 (pinned, #195), stdlib only otherwise. Tests: `pytest`. Spec: `docs/superpowers/specs/2026-09-05-mpc-sell-hold-objective-design.md`.

## Global Constraints

- Work in the worktree `~/code/rb-172` on branch `172-mpc-sell-hold`. Run everything from there with `.venv/bin/python -m pytest ...` (never bare `python3`, which is 3.9).
- Pure TDD: write the failing test, run it and see it fail for the right reason, then the minimum code, then green, then commit by explicit path (`git add <files>`, never `git add -A`).
- Commit messages end with `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.
- Long-running commands (the full suite, the Stage 1 run) run BLOCKING, not backgrounded.
- Candidate grid is fixed: `min_frac in {0.0, 0.1, ..., 1.0}` (11 values). Criterion is fixed: median Spearman rho over defined states `>= 0.40`. Neither moves after numbers exist.
- New harness modules must NOT expose a module-level `STRATEGY` in `strategies/` unless they are meant to be registered; the wrapper in Task 1 is deliberately unregistered (same pattern as `strategies/ghost.py`).
- Do not use `kaggisim.forward.ROLLOUT_PASS` anywhere in this work.
- Every harness `main()` is `# pragma: no cover`; everything else needs tests (CI gate: line >= 85%, branch >= 65%).

## File Structure

| File | Responsibility |
|---|---|
| `strategies/sell_discipline.py` (create) | `cap_sells(orders, market_inventory, min_frac)` and `SellDiscipline(Strategy)` — the one knob |
| `tests/test_sell_discipline.py` (create) | unit tests for the cap and the wrapper |
| `harness/state_set.py` (create) | `capture_states(agent_a, agent_b, seed, days, hour, episode_steps)` from a real game |
| `tests/test_state_set.py` (create) | capture tests, short episodes |
| `harness/rollout_objective.py` (create) | `final_money(obs, our_agent, opponent_agent, seed, episode_steps)` |
| `tests/test_rollout_objective.py` (create) | the exactness control on a short game |
| `harness/objective_check.py` (create) | grid, per-state scoring, verdict, table, CLI `main()` |
| `tests/test_objective_check.py` (create) | pure-function tests for scoring/verdict/table |

Existing APIs used (do not modify):

- `kaggisim.strategy.Strategy` (`act(obs) -> dict`, attributes `name`, `benchmark`) and `make_agent(strategy) -> agent(obs)`.
- `kaggisim.pricing.sell_quantity(item, inventory, have, min_price) -> int` — how many of `have` sell while each unit still clears `min_price`.
- `kaggisim.economy.MARKET_PARAMS[item]["base"]`, `["I0"]`.
- `kaggisim.forward.rebuild(obs, episode_steps=720, seed=0)` — a `kaggle_environments` env positioned at `obs`.
- `harness.ladder_correlation.spearman(xs, ys) -> float | None` (None when undefined).
- `harness.promotion.gate_opponent() -> str` (reads `harness/champion.json`).
- `strategies.load(name)` -> the `STRATEGY` class; `strategies.REGISTRY`.
- `kaggle_environments.make("kaggriculture", configuration={"episodeSteps": N, "seed": s})`, `env.reset(2)`, `env.step([action0, action1])`, `env.state[i].observation`, `env.steps`, `env.run([agent0, agent1])`.

Observation facts the code relies on: `obs["player"]` is our seat (0/1); `obs["farms"][seat]["money"]`; `obs["market"]["inventory"][item]` and `obs["market"]["prices"][item]`; `obs["day"]`, `obs["hour"]` (24 hours per day, so day *d* hour 0 is step `24*d`); a market order is `["SELL", item, n]`, `["BUY_SEED", ...]`, `["HIRE"]` etc.; the action dict is `{"farmer": [...], "hands": [[...], ...], "market": [[...], ...]}`.

---

### Task 1: The sell-discipline knob

**Files:**
- Create: `strategies/sell_discipline.py`
- Test: `tests/test_sell_discipline.py`

**Interfaces:**
- Consumes: `kaggisim.pricing.sell_quantity`, `kaggisim.economy.MARKET_PARAMS`, `kaggisim.strategy.Strategy`.
- Produces: `cap_sells(orders: list, market_inventory: dict, min_frac: float) -> list` and `class SellDiscipline(Strategy)` with `__init__(self, inner: Strategy, min_frac: float)` and `act(self, obs) -> dict`. `SellDiscipline.name == f"{inner.name}@{min_frac:.1f}"`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_sell_discipline.py
"""The one knob #172 Stage 1 turns: never sell a unit below `min_frac` of its
base price; hold the rest. 0.0 must be the champion unchanged (positive
control), and the wrapper must touch nothing but SELL quantities."""

from __future__ import annotations

from kaggisim.economy import MARKET_PARAMS
from kaggisim.strategy import Strategy
from strategies.sell_discipline import SellDiscipline, cap_sells

I0 = MARKET_PARAMS["STRAWBERRY"]["I0"]


def test_min_frac_zero_is_the_identity():
    orders = [["SELL", "STRAWBERRY", 40], ["HIRE"], ["SELL", "WOOL", 12]]
    inv = {"STRAWBERRY": I0 + 500, "WOOL": I0 + 500}
    assert cap_sells(orders, inv, 0.0) == orders


def test_min_frac_one_sells_nothing_into_a_glutted_market():
    orders = [["SELL", "STRAWBERRY", 40]]
    inv = {"STRAWBERRY": I0 + 50}          # above the anchor: every unit clears below base
    assert cap_sells(orders, inv, 1.0) == []


def test_a_partial_cap_keeps_the_units_that_still_clear_the_floor():
    orders = [["SELL", "STRAWBERRY", 400]]
    inv = {"STRAWBERRY": I0}                # at the anchor: price = base, then falls
    got = cap_sells(orders, inv, 0.5)
    assert len(got) == 1 and got[0][:2] == ["SELL", "STRAWBERRY"]
    assert 0 < got[0][2] < 400


def test_non_sell_orders_and_positions_are_untouched():
    orders = [["BUY_SEED", "WHEAT", 5], ["SELL", "STRAWBERRY", 40], ["HIRE"], ["BUY_LAND", "SE"]]
    inv = {"STRAWBERRY": I0 + 50}
    got = cap_sells(orders, inv, 1.0)
    assert got == [["BUY_SEED", "WHEAT", 5], ["HIRE"], ["BUY_LAND", "SE"]]


def test_two_sells_of_one_item_in_a_turn_share_the_cap():
    # The second order sees the inventory the first one will have pushed up.
    orders = [["SELL", "STRAWBERRY", 400], ["SELL", "STRAWBERRY", 400]]
    inv = {"STRAWBERRY": I0}
    alone = cap_sells(orders[:1], inv, 0.5)[0][2]
    both = cap_sells(orders, inv, 0.5)
    assert sum(o[2] for o in both) == alone


def test_missing_inventory_defaults_to_the_anchor_and_unknown_items_pass_through():
    orders = [["SELL", "STRAWBERRY", 3], ["SELL", "COW", 1]]
    got = cap_sells(orders, {}, 0.99)
    assert got[0] == ["SELL", "STRAWBERRY", 1]     # exactly one unit clears >= 0.99*base at I0
    assert got[1] == ["SELL", "COW", 1]            # not a priced product: left alone


class _Inner(Strategy):
    name = "inner"

    def act(self, obs):
        return {"farmer": ["PLANT", "WHEAT"], "hands": [["WATER"]],
                "market": [["SELL", "STRAWBERRY", 40], ["HIRE"]]}


def test_wrapper_caps_only_the_market_and_names_itself():
    obs = {"market": {"inventory": {"STRAWBERRY": I0 + 50}, "prices": {}}}
    s = SellDiscipline(_Inner(), 1.0)
    got = s.act(obs)
    assert got["farmer"] == ["PLANT", "WHEAT"]
    assert got["hands"] == [["WATER"]]
    assert got["market"] == [["HIRE"]]
    assert s.name == "inner@1.0"
    assert s.benchmark is False
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest -q tests/test_sell_discipline.py`
Expected: collection error `ModuleNotFoundError: No module named 'strategies.sell_discipline'`.

- [ ] **Step 3: Write the minimal implementation**

```python
# strategies/sell_discipline.py
"""Price discipline as a wrapper: never sell a unit below `min_frac` of its base
price; hold the rest in the shed (#172 Stage 1).

The wrapper is the knob the rollout objective is asked to rank. It edits SELL
quantities only, using the sim's own price curve through
`kaggisim.pricing.sell_quantity`, so it works on any strategy and leaves the
frozen benchmark (`field_rival`, #181) and the champion byte-for-byte alone.
`min_frac = 0.0` is the identity — the positive control.

Deliberately NOT registered: no module-level ``STRATEGY``, so the
auto-discovery in ``strategies/__init__.py`` skips this file (the same choice
as ``strategies/ghost.py``). It has no behaviour without an inner strategy.
"""

from __future__ import annotations

from kaggisim.economy import MARKET_PARAMS
from kaggisim.pricing import sell_quantity
from kaggisim.strategy import Strategy


def cap_sells(orders: list, market_inventory: dict, min_frac: float) -> list:
    """`orders` with every SELL capped to the units that still clear
    `min_frac * base`; a SELL capped to zero is dropped (a dead order burns one
    of the ten slots). Non-SELL orders and order positions are untouched.
    Two SELLs of one item in the same turn share the cap: the second is priced
    at the inventory the first will have pushed up."""
    sold: dict = {}
    out = []
    for order in orders:
        if not (order and order[0] == "SELL" and len(order) >= 3 and order[1] in MARKET_PARAMS):
            out.append(order)
            continue
        item, have = order[1], int(order[2])
        params = MARKET_PARAMS[item]
        inventory = market_inventory.get(item, params["I0"]) + sold.get(item, 0)
        n = sell_quantity(item, inventory, have, min_frac * params["base"])
        if n > 0:
            out.append(["SELL", item, n])
            sold[item] = sold.get(item, 0) + n
    return out


class SellDiscipline(Strategy):
    """`inner` with its SELL orders capped by `min_frac` (see `cap_sells`)."""

    benchmark = False

    def __init__(self, inner: Strategy, min_frac: float):
        self.inner = inner
        self.min_frac = float(min_frac)
        self.name = f"{inner.name}@{self.min_frac:.1f}"

    def act(self, obs) -> dict:
        action = self.inner.act(obs)
        inventory = obs.get("market", {}).get("inventory", {})
        return {
            "farmer": action.get("farmer"),
            "hands": action.get("hands", []),
            "market": cap_sells(action.get("market", []), inventory, self.min_frac),
        }
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest -q tests/test_sell_discipline.py`
Expected: `7 passed`. If `test_missing_inventory_defaults_to_the_anchor_and_unknown_items_pass_through` fails on the `1`, check `kaggisim.economy.market_price("STRAWBERRY", I0)` equals the base (120) and `market_price("STRAWBERRY", I0 + 1)` is below `0.99 * 120`; adjust the test's expectation only if the curve says otherwise, and say so in the commit message.

- [ ] **Step 5: Confirm the registry did not pick the wrapper up**

Run: `.venv/bin/python -c "from strategies import REGISTRY; assert 'sell_discipline' not in REGISTRY and not any('@' in k for k in REGISTRY); print(sorted(REGISTRY))"`
Expected: prints the registry, no assertion error.

- [ ] **Step 6: Commit**

```bash
git add strategies/sell_discipline.py tests/test_sell_discipline.py
git commit -m "sell_discipline: cap SELLs at min_frac of base price, 0.0 = identity (#172)

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 2: Capture states from a real game

**Files:**
- Create: `harness/state_set.py`
- Test: `tests/test_state_set.py`

**Interfaces:**
- Consumes: `kaggle_environments.make`.
- Produces: `capture_states(agent_a, agent_b, seed, days, hour=0, episode_steps=720) -> tuple[list[dict], float]` — the list holds one `{"seed": int, "day": int, "hour": int, "step": int, "obs": dict}` per requested day (seat 0's observation, deep-copied, in the order of `days`); the float is seat 0's `farms[0]["money"]` at the end of the game. `agent_a`/`agent_b` are `kaggle_environments` agent callables (`agent(obs) -> action`), e.g. from `kaggisim.strategy.make_agent`. Raises `ValueError` if any requested `(day, hour)` is at or past `episode_steps`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_state_set.py
"""States for the #172 objective check come from a real game, snapshotted at
(day, hour) from our seat, and the same drive must land where `env.run` lands
— otherwise the per-seat observations we hand the agents are not the ones the
runner hands them."""

from __future__ import annotations

import pytest
from kaggle_environments import make

from harness.state_set import capture_states
from kaggisim.strategy import make_agent
from strategies import load

SEED, STEPS = 7, 72          # three days: enough to plant, not enough to bore


def _agents():
    """Two cheap registered strategies, one per seat; both deterministic under
    a seed. `capture_states` drives `env.step` itself, so seats must be
    callables (a built-in name string is only resolved by `env.run`)."""
    return make_agent(load("wheat_hands")()), make_agent(load("hired_hands")())


def test_captures_our_observation_at_the_requested_days():
    a, b = _agents()
    states, final = capture_states(a, b, SEED, days=[1, 2], hour=0, episode_steps=STEPS)
    assert [s["day"] for s in states] == [1, 2]
    assert [s["step"] for s in states] == [24, 48]
    for s in states:
        assert s["seed"] == SEED and s["hour"] == 0
        assert s["obs"]["day"] == s["day"] and s["obs"]["hour"] == 0
        assert s["obs"]["player"] == 0
        assert "private" in s["obs"] and "shed" in s["obs"]["private"]
    assert isinstance(final, float)


def test_snapshots_are_copies_not_views_of_the_live_env():
    a, b = _agents()
    states, _ = capture_states(a, b, SEED, days=[1], hour=0, episode_steps=STEPS)
    money_at_day_1 = states[0]["obs"]["farms"][0]["money"]
    # A second capture of the same game reproduces the value: the first was not
    # mutated by the game continuing to its end.
    again, _ = capture_states(*_agents(), SEED, days=[1], hour=0, episode_steps=STEPS)
    assert again[0]["obs"]["farms"][0]["money"] == money_at_day_1


def test_the_drive_lands_where_env_run_lands():
    # POSITIVE CONTROL for the per-seat observations: stepping the env ourselves
    # with state[i].observation must reach exactly the money env.run reaches.
    a, b = _agents()
    _, final = capture_states(a, b, SEED, days=[1], hour=0, episode_steps=STEPS)
    env = make("kaggriculture", configuration={"episodeSteps": STEPS, "seed": SEED})
    env.run([make_agent(load("wheat_hands")()), make_agent(load("hired_hands")())])
    truth = env.state[0].observation["farms"][0]["money"]
    assert truth > 0, "POSITIVE CONTROL: no money moved, test proves nothing"
    assert final == truth


def test_a_day_past_the_game_is_refused():
    a, b = _agents()
    with pytest.raises(ValueError):
        capture_states(a, b, SEED, days=[3], hour=0, episode_steps=STEPS)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest -q tests/test_state_set.py`
Expected: `ModuleNotFoundError: No module named 'harness.state_set'`.

- [ ] **Step 3: Write the minimal implementation**

```python
# harness/state_set.py
"""Snapshot our observation from a real game at chosen (day, hour) — the state
set for the #172 objective check.

The game is driven step by step (as `tests/test_forward.py` does) so that the
observation each seat acts on is `env.state[i].observation`, the same object
`env.run` hands the agents; `test_state_set.py` pins that the drive lands on
`env.run`'s final money to the value. Observations are deep-copied at capture
because the env mutates them in place as the game continues.
"""

from __future__ import annotations

import copy

TURNS_PER_DAY = 24


def capture_states(agent_a, agent_b, seed, days, hour=0, episode_steps=720):
    """Drive a full game of `agent_a` (seat 0) vs `agent_b` (seat 1) under
    `seed`; return `(states, final_money)` where `states` holds seat 0's
    observation at hour `hour` of each day in `days` (in the order given) and
    `final_money` is seat 0's money when the game ends.

    Both agents are callables `agent(obs) -> action`. A requested (day, hour)
    at or past `episode_steps` is refused up front rather than silently
    missing from the result (#153: a partial set must not look like a set).
    """
    from kaggle_environments import make

    wanted = {int(day) * TURNS_PER_DAY + int(hour): int(day) for day in days}
    too_late = [d for s, d in wanted.items() if s >= episode_steps]
    if too_late:
        raise ValueError(
            f"day(s) {sorted(too_late)} at hour {hour} are at or past the game's "
            f"{episode_steps} steps")

    env = make("kaggriculture", configuration={"episodeSteps": episode_steps, "seed": seed})
    env.reset(2)
    found = {}
    for step in range(episode_steps):
        obs0 = env.state[0].observation
        if step in wanted:
            found[step] = copy.deepcopy(obs0)
        env.step([agent_a(obs0), agent_b(env.state[1].observation)])
    final_money = float(env.state[0].observation["farms"][0]["money"])
    states = []
    for day in days:
        step = int(day) * TURNS_PER_DAY + int(hour)
        states.append({"seed": seed, "day": int(day), "hour": int(hour),
                       "step": step, "obs": found[step]})
    return states, final_money
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest -q tests/test_state_set.py`
Expected: `4 passed` in a few seconds. If `test_the_drive_lands_where_env_run_lands` fails, first print `env.state[1].observation.keys()` after `reset(2)` — if seat 1's observation lacks `farms`/`market`, the interpreter only populates seat 0 and the fix is to hand seat 1 a copy of seat 0's observation with `player` set to 1. Record which it was in the commit message.

- [ ] **Step 5: Commit**

```bash
git add harness/state_set.py tests/test_state_set.py
git commit -m "state_set: snapshot our observation at (day, hour) from a real game (#172)

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 3: Roll to the end and read final money

**Files:**
- Create: `harness/rollout_objective.py`
- Test: `tests/test_rollout_objective.py`

**Interfaces:**
- Consumes: `kaggisim.forward.rebuild`, `harness.state_set.capture_states` (Task 2) in tests.
- Produces: `final_money(obs, our_agent, opponent_agent, seed, episode_steps=720) -> float` — our farm's money at `episode_steps` after rolling from `obs` with `our_agent` on our seat (`obs["player"]`) and `opponent_agent` on the other. Both are callables `agent(obs) -> action`. Also `timed_final_money(...) -> tuple[float, float]` returning `(money, seconds)`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_rollout_objective.py
"""A rollout scored on final money is only a prediction if, with the REAL
opponent on the other farm, it reproduces the real game (#164's exactness,
re-asserted on this code path). The mirror version is the same function with a
different opponent — there is nothing else to test about it."""

from __future__ import annotations

from harness.rollout_objective import final_money, timed_final_money
from harness.state_set import capture_states
from kaggisim.strategy import make_agent
from strategies import load

SEED, STEPS, DAY = 11, 96, 2     # four days; snapshot at day 2, roll the last two


def _ours():
    return make_agent(load("wheat_hands")())


def _theirs():
    return make_agent(load("hired_hands")())


def test_rolling_from_a_state_with_the_real_opponent_reproduces_the_real_game():
    states, truth = capture_states(_ours(), _theirs(), SEED, days=[DAY], hour=0,
                                   episode_steps=STEPS)
    obs = states[0]["obs"]
    assert obs["farms"][0]["money"] != truth, "POSITIVE CONTROL: nothing happened after the snapshot"
    got = final_money(obs, _ours(), _theirs(), SEED, episode_steps=STEPS)
    assert got == truth


def test_a_different_opponent_changes_the_answer():
    # The opponent argument is live: the mirror is not silently the real one.
    states, truth = capture_states(_ours(), _theirs(), SEED, days=[DAY], hour=0,
                                   episode_steps=STEPS)
    obs = states[0]["obs"]
    mirrored = final_money(obs, _ours(), _ours(), SEED, episode_steps=STEPS)
    real = final_money(obs, _ours(), _theirs(), SEED, episode_steps=STEPS)
    assert real == truth
    assert isinstance(mirrored, float)
    # Not asserted unequal: two opponents can tie on a short game. Asserted
    # instead that the mirror ran the full distance:
    assert mirrored > 0


def test_timed_variant_reports_seconds():
    states, _ = capture_states(_ours(), _theirs(), SEED, days=[DAY], hour=0,
                               episode_steps=STEPS)
    money, seconds = timed_final_money(states[0]["obs"], _ours(), _theirs(), SEED,
                                       episode_steps=STEPS)
    assert money == final_money(states[0]["obs"], _ours(), _theirs(), SEED, episode_steps=STEPS)
    assert seconds > 0
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest -q tests/test_rollout_objective.py`
Expected: `ModuleNotFoundError: No module named 'harness.rollout_objective'`.

- [ ] **Step 3: Write the minimal implementation**

```python
# harness/rollout_objective.py
"""Roll a state to the end of the game and read our final money (#172 Stage 1).

This is the only rollout configuration that has ever correlated with real
performance in this repo (#177): both seats ACT, and the score is money at
step 720 rather than any valuation of standing stock (#161's error). The
opponent is an argument so that the prediction (a mirror of the candidate on
the other farm) and the truth (the real gate opponent there) are the same
function called twice. `kaggisim.forward.ROLLOUT_PASS` is deliberately not
used: an idle opponent is a dynamics change, not a bias (#174).

The other farm's private shed is not in our observation, so the opponent
starts a rollout with an empty shed. That is the planner's real information
set at runtime and belongs in the prediction; `tests/test_rollout_objective.py`
shows the truth rollout still reproduces the real game to the value.
"""

from __future__ import annotations

import time

from kaggisim import forward


def final_money(obs, our_agent, opponent_agent, seed, episode_steps=720) -> float:
    """Our farm's money at `episode_steps` after rolling forward from `obs`
    with `our_agent` on seat `obs["player"]` and `opponent_agent` on the other."""
    us = int(obs.get("player", 0))
    env = forward.rebuild(obs, episode_steps=episode_steps, seed=seed)
    agents = [None, None]
    agents[us] = our_agent
    agents[1 - us] = opponent_agent
    while len(env.steps) < episode_steps:
        env.step([agents[i](env.state[i].observation) for i in range(2)])
    return float(env.state[us].observation["farms"][us]["money"])


def timed_final_money(obs, our_agent, opponent_agent, seed, episode_steps=720):
    """`final_money` plus the wall-clock seconds it took — the cost the issue
    says to budget from measurement, not from #159's one-sided numbers."""
    t0 = time.perf_counter()
    money = final_money(obs, our_agent, opponent_agent, seed, episode_steps)
    return money, time.perf_counter() - t0
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest -q tests/test_rollout_objective.py`
Expected: `3 passed`. If the exactness test fails by a small amount, check `len(env.steps)` right after `rebuild` equals `obs["step"] + 1` (the off-by-one #159 documents) before touching anything else; if seat 1's rebuilt observation lacks `player`, set `env.state[i].observation["player"] = i` inside `final_money` after `rebuild` and note it in the commit.

- [ ] **Step 5: Commit**

```bash
git add harness/rollout_objective.py tests/test_rollout_objective.py
git commit -m "rollout_objective: roll a state to game end with a chosen opponent, read final money (#172)

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 4: Grid, per-state rho, verdict, table, CLI

**Files:**
- Create: `harness/objective_check.py`
- Test: `tests/test_objective_check.py`

**Interfaces:**
- Consumes: `harness.ladder_correlation.spearman`, `harness.promotion.gate_opponent`, `harness.state_set.capture_states`, `harness.rollout_objective.timed_final_money`, `strategies.sell_discipline.SellDiscipline`, `strategies.load`, `kaggisim.strategy.make_agent`.
- Produces (pure): `GRID: tuple[float, ...]`, `BAR = 0.40`, `score_state(predicted: dict[float, float], truth: dict[float, float]) -> dict` with keys `rho` (float|None), `predicted_best` (float), `true_best` (float), `n` (int); `verdict(rhos: list[float | None], bar=BAR) -> dict` with keys `passed` (bool), `median` (float|None), `defined` (int), `undefined` (int); `format_table(rows: list[dict]) -> str`; `run_state(state, champion_name, opponent_name, grid=GRID) -> dict` (# pragma: no cover) and `main(argv=None)` (# pragma: no cover).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_objective_check.py
"""The verdict logic for #172 Stage 1, pinned before the numbers exist: the
grid, the per-state rho, undefined states excluded not scored, and the bar."""

from __future__ import annotations

from harness.objective_check import BAR, GRID, format_table, score_state, verdict


def test_the_grid_is_the_declared_eleven_with_the_control_first():
    assert GRID == (0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0)
    assert BAR == 0.40


def test_score_state_ranks_and_names_the_bests():
    predicted = {0.0: 100.0, 0.5: 300.0, 1.0: 200.0}
    truth = {0.0: 10.0, 0.5: 30.0, 1.0: 20.0}
    got = score_state(predicted, truth)
    assert got["rho"] == 1.0
    assert got["predicted_best"] == 0.5 and got["true_best"] == 0.5
    assert got["n"] == 3


def test_score_state_is_undefined_when_truth_has_no_rank_variance():
    predicted = {0.0: 1.0, 0.5: 2.0, 1.0: 3.0}
    truth = {0.0: 7.0, 0.5: 7.0, 1.0: 7.0}
    assert score_state(predicted, truth)["rho"] is None


def test_verdict_passes_at_the_bar_and_fails_just_under_it():
    assert verdict([0.4, 0.4, 0.4])["passed"] is True
    assert verdict([0.39, 0.39, 0.39])["passed"] is False


def test_verdict_uses_the_median_and_excludes_undefined_states():
    got = verdict([None, 0.9, 0.1, 0.5])
    assert got["median"] == 0.5
    assert got["defined"] == 3 and got["undefined"] == 1
    assert got["passed"] is True


def test_verdict_with_nothing_defined_fails_and_says_so():
    got = verdict([None, None])
    assert got["passed"] is False and got["median"] is None and got["defined"] == 0


def test_format_table_has_one_line_per_state_and_prints_undefined():
    rows = [
        {"seed": 0, "day": 3, "n": 11, "rho": 0.5, "predicted_best": 0.2, "true_best": 0.3,
         "seconds_per_rollout": 0.71},
        {"seed": 0, "day": 5, "n": 11, "rho": None, "predicted_best": 0.0, "true_best": 0.0,
         "seconds_per_rollout": 0.60},
    ]
    text = format_table(rows)
    lines = [ln for ln in text.splitlines() if ln.strip()]
    assert len(lines) == 3                      # header + 2 rows
    assert "undefined" in lines[2]
    assert "0.50" in lines[1] and "0.71" in lines[1]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest -q tests/test_objective_check.py`
Expected: `ModuleNotFoundError: No module named 'harness.objective_check'`.

- [ ] **Step 3: Write the implementation**

```python
# harness/objective_check.py
"""#172 Stage 1: does a mirror-opponent, final-money rollout rank sell policies
the way a real-opponent rollout does?

    python -m harness.objective_check                      # dense_farm vs the gate opponent
    python -m harness.objective_check --champion meta_rancher --seeds 0 1 --days 3 5 7 10 15

Declared before code (docs/superpowers/specs/2026-09-05-mpc-sell-hold-objective-design.md):
candidates are the champion behind `strategies.sell_discipline` at each
`min_frac` in GRID; states are hour 0 of each day in --days from a real game of
the bare champion vs the gate opponent on each --seed; prediction = the
candidate mirrored on the other farm, truth = the real opponent there, both
rolled to step 720 from the same state under the same seed; the statistic is
Spearman rho over the grid, one per state; PASS iff the median over DEFINED
states is >= BAR. Controls run first: the truth rollout at min_frac 0.0 must
reproduce the real game's final money to the value, or the run is void.

rho ranks; it does not choose (#177). `predicted_best`/`true_best` are recorded
for that reason and are not part of the verdict.
"""

from __future__ import annotations

import argparse
import statistics

from harness.ladder_correlation import spearman

#: The declared grid; 0.0 is the champion unchanged — the positive control.
GRID = (0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0)
#: The declared bar on the median rho over defined states.
BAR = 0.40
DEFAULT_DAYS = (3, 5, 7, 10, 15)
DEFAULT_SEEDS = (0, 1)
EPISODE_STEPS = 720


def score_state(predicted, truth):
    """Spearman rho of predicted vs true final money over the candidates
    (keys of both dicts, same set), plus which candidate each side ranks
    first. `rho` is None when undefined (no rank variance on a side)."""
    keys = sorted(predicted)
    xs = [predicted[k] for k in keys]
    ys = [truth[k] for k in keys]
    return {
        "rho": spearman(xs, ys),
        "predicted_best": max(keys, key=lambda k: predicted[k]),
        "true_best": max(keys, key=lambda k: truth[k]),
        "n": len(keys),
    }


def verdict(rhos, bar=BAR):
    """PASS iff the median of the DEFINED rhos is >= `bar`. Undefined states
    (None) are counted and excluded, never scored as zero: an all-tied state
    is 'no evidence', not 'no relationship'."""
    defined = [r for r in rhos if r is not None]
    median = statistics.median(defined) if defined else None
    return {
        "passed": median is not None and median >= bar,
        "median": median,
        "defined": len(defined),
        "undefined": len(rhos) - len(defined),
    }


def format_table(rows):
    """One line per state: seed, day, n, rho, predicted best, true best, cost."""
    head = f"{'seed':>4} {'day':>3} {'n':>3} {'rho':>9} {'pred.best':>9} {'true.best':>9} {'s/rollout':>9}"
    lines = [head]
    for r in rows:
        rho = "undefined" if r["rho"] is None else f"{r['rho']:.2f}"
        lines.append(f"{r['seed']:>4} {r['day']:>3} {r['n']:>3} {rho:>9} "
                     f"{r['predicted_best']:>9.1f} {r['true_best']:>9.1f} "
                     f"{r['seconds_per_rollout']:>9.2f}")
    return "\n".join(lines)


def _candidate(champion_cls, min_frac):  # pragma: no cover
    from kaggisim.strategy import make_agent
    from strategies.sell_discipline import SellDiscipline
    return make_agent(SellDiscipline(champion_cls(), min_frac))


def run_state(state, champion_name, opponent_name, grid=GRID):  # pragma: no cover
    """Score one state: every candidate rolled with a mirror and with the
    real opponent. Returns the table row plus the raw per-candidate money."""
    from harness.rollout_objective import timed_final_money
    from kaggisim.strategy import make_agent
    from strategies import load

    champion_cls, opponent_cls = load(champion_name), load(opponent_name)
    predicted, truth, seconds = {}, {}, []
    for f in grid:
        p, t1 = timed_final_money(state["obs"], _candidate(champion_cls, f),
                                  _candidate(champion_cls, f), state["seed"], EPISODE_STEPS)
        t, t2 = timed_final_money(state["obs"], _candidate(champion_cls, f),
                                  make_agent(opponent_cls()), state["seed"], EPISODE_STEPS)
        predicted[f], truth[f] = p, t
        seconds += [t1, t2]
    row = score_state(predicted, truth)
    row.update(seed=state["seed"], day=state["day"],
               seconds_per_rollout=sum(seconds) / len(seconds),
               predicted=predicted, truth=truth)
    return row


def main(argv=None):  # pragma: no cover
    from harness.promotion import gate_opponent
    from harness.state_set import capture_states
    from kaggisim.strategy import make_agent
    from strategies import load

    ap = argparse.ArgumentParser(description="#172 Stage 1 objective check")
    ap.add_argument("--champion", default="dense_farm")
    ap.add_argument("--opponent", default=None, help="default: champion.json gate_opponent")
    ap.add_argument("--seeds", type=int, nargs="+", default=list(DEFAULT_SEEDS))
    ap.add_argument("--days", type=int, nargs="+", default=list(DEFAULT_DAYS))
    args = ap.parse_args(argv)
    opponent = args.opponent or gate_opponent()
    print(f"champion={args.champion} opponent={opponent} seeds={args.seeds} days={args.days} "
          f"grid={GRID} bar={BAR}")

    rows = []
    for seed in args.seeds:
        states, real_final = capture_states(make_agent(load(args.champion)()),
                                            make_agent(load(opponent)()), seed,
                                            args.days, hour=0, episode_steps=EPISODE_STEPS)
        for state in states:
            row = run_state(state, args.champion, opponent)
            control = row["truth"][0.0]
            ok = control == real_final
            print(f"seed {seed} day {state['day']:>2}: control truth@0.0={control:.0f} "
                  f"real={real_final:.0f} {'OK' if ok else 'MISMATCH -- RUN VOID'}")
            if not ok:
                raise SystemExit("positive control failed: the truth rollout does not "
                                 "reproduce the real game; nothing below can be trusted")
            rows.append(row)
            print(format_table([row]).splitlines()[1])

    print()
    print(format_table(rows))
    v = verdict([r["rho"] for r in rows])
    med = "undefined" if v["median"] is None else f"{v['median']:.2f}"
    print(f"\nmedian rho over {v['defined']} defined states ({v['undefined']} undefined): {med}  "
          f"bar {BAR:.2f}  ->  {'PASS' if v['passed'] else 'FAIL'}")
    print("per-candidate money (predicted | truth):")
    for r in rows:
        print(f"  seed {r['seed']} day {r['day']:>2}: " + "  ".join(
            f"{f:.1f}:{r['predicted'][f]:.0f}|{r['truth'][f]:.0f}" for f in GRID))
    return 0 if v["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest -q tests/test_objective_check.py`
Expected: `7 passed`.

- [ ] **Step 5: Smoke the CLI on a tiny configuration (blocking; ~1 minute)**

Run: `.venv/bin/python -m harness.objective_check --seeds 0 --days 3`
Expected: a `control ... OK` line, one table row, a verdict line. If the control prints `MISMATCH`, stop and report — do not proceed to Task 5.

- [ ] **Step 6: Run the whole suite as CI does (blocking)**

Run: `.venv/bin/python -m pytest -q -n auto --cov --cov-branch --cov-report=term-missing --cov-report=json 2>&1 | tail -15`
Expected: all pass; then check the gate the way `.github/workflows/*.yml` does:

```bash
.venv/bin/python - <<'PY'
import json
t = json.load(open("coverage.json"))["totals"]
print("line", 100*t["covered_lines"]/t["num_statements"], "branch", 100*t["covered_branches"]/t["num_branches"])
PY
```
Expected: line >= 85, branch >= 65.

- [ ] **Step 7: Commit**

```bash
git add harness/objective_check.py tests/test_objective_check.py
git commit -m "objective_check: grid, per-state Spearman rho, median verdict and CLI (#172 Stage 1)

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 5: Run Stage 1 and record the result

**Files:**
- No source changes. Output goes to the issue (the lab notebook, ADR-0007) and the PR description.

**Interfaces:**
- Consumes: `python -m harness.objective_check` (Task 4).

- [ ] **Step 1: Run the declared configuration, blocking, capturing the output**

Run from `~/code/rb-172`:

```bash
.venv/bin/python -m harness.objective_check --champion dense_farm --seeds 0 1 --days 3 5 7 10 15 2>&1 | tee /private/tmp/claude-501/-Users-sartin/2195f188-57a5-4834-a6b9-acc4ec519961/scratchpad/objective-check-dense_farm.txt
```

Expected: ten `control ... OK` lines, the table, the verdict. Budget: ~220 rollouts; if a rollout costs 1 s this is under five minutes, if 5 s it is under twenty. Do not background it.

- [ ] **Step 2: Run the same on `meta_rancher` (the `champion.json` submit_default) so the reviewer's one-line objection is already answered**

```bash
.venv/bin/python -m harness.objective_check --champion meta_rancher --seeds 0 1 --days 3 5 7 10 15 2>&1 | tee /private/tmp/claude-501/-Users-sartin/2195f188-57a5-4834-a6b9-acc4ec519961/scratchpad/objective-check-meta_rancher.txt
```

Only the `dense_farm` run is the declared criterion; the `meta_rancher` run is recorded as context.

- [ ] **Step 3: Post the result to issue #172**

Compose the comment with: the verdict line for `dense_farm` (PASS/FAIL against the fixed bar), the full per-state table, the control lines, the measured seconds per rollout from each day, the `meta_rancher` table under a "recorded, not gated" heading, and whether the predicted best equalled the true best per state (rho ranks, does not choose). Then:

```bash
gh issue comment 172 --body-file /private/tmp/claude-501/-Users-sartin/2195f188-57a5-4834-a6b9-acc4ec519961/scratchpad/172-stage1-comment.md
```

The comment must state the numbers as measured and the verdict as the declared criterion gives it. If it FAILS, say Stage 2 is not started. If it PASSES, say Stage 2 is unblocked and stop — Stage 2 is its own spec.

- [ ] **Step 4: Update the draft PR body with the verdict and the table**

```bash
gh pr edit 214 --body-file /private/tmp/claude-501/-Users-sartin/2195f188-57a5-4834-a6b9-acc4ec519961/scratchpad/172-pr-body.md
```

The body keeps the existing summary and adds a "Stage 1 result" section with the verdict, the table, and a note that this PR carries harness/instrument code only and no strategy change (the ADR-0007 salvage shape).

---

## Self-review

- **Spec coverage:** wrapper knob (Task 1), state set with the (seed, day) grid and hour 0 (Task 2, Task 4 defaults), prediction vs truth via one function with a swapped opponent (Task 3), per-state Spearman via `ladder_correlation.spearman`, median verdict with undefined excluded, control-first with a void on mismatch, cost measured and recorded (Task 4), champion as a flag defaulting to `dense_farm` with gate opponent from `champion.json` (Task 4), results to the issue and PR (Task 5). Stage 2 excluded.
- **Placeholders:** none; every step has runnable code or an exact command.
- **Type consistency:** `capture_states` returns `(list[dict], float)` and is consumed that way in Tasks 3 and 4; `timed_final_money` returns `(float, float)` and is consumed that way in Task 4; `score_state`/`verdict`/`format_table` key names match between Task 4's code and tests (`rho`, `predicted_best`, `true_best`, `n`, `seconds_per_rollout`, `passed`, `median`, `defined`, `undefined`).
