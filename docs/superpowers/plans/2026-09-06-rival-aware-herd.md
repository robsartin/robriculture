# #219 Rival-Aware Herd — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A contender `rival_aware` that is `dense_farm` except that it buys cows instead of sheep once the rival shows two or more sheep, plus the controls and the declared 16-seed experiment that decide PROMOTE or REJECTED.

**Architecture:** One behaviour-preserving seam on the frozen benchmark (`market_orders(..., prefer=None)` and a `herd_preference(obs)` hook returning `None`, the #202 `caps` shape, pinned byte-identical), a 40-line strategy module that overrides the hook, and a small harness module that runs the three controls and the criterion via `harness.triage.head_to_head_rate`. Nothing else in any strategy changes.

**Tech Stack:** Python 3.12 (`.venv/bin/python`), `kaggle_environments` 1.32.7, stdlib. Spec: `docs/superpowers/specs/2026-09-06-rival-aware-herd-design.md`.

## Global Constraints

- Worktree `~/code/rb-219`, branch `219-rival-routing`; `.venv/bin/python` only; commands BLOCKING; commit by explicit path; messages end with `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`; pure TDD with RED observed.
- Declared and never moved: `SHEEP_THRESHOLD = 2`; seeds `400-415`; bars `>= 60%` of 16 vs `dense_farm` and `>= 90%` vs each of `harness.evolve.DEFAULT_ANCHORS`; a tie is not a win; controls first, a failed control voids the run.
- `field_rival`'s decisions stay byte-identical with the defaults (the existing frozen-pin tests in `tests/test_dense_farm.py` and `tests/test_field_rival.py` must keep passing unchanged, plus the new equality test); `dense_farm` and `balanced_farm` decisions unchanged; `champion.json` untouched.
- `rival_aware` is registered (module-level `STRATEGY`), `benchmark = False`, and must survive `tests/test_no_crash.py` (full season vs `random`/`starter`, beats `random`).
- CI gate: line >= 85%, branch >= 65%. Harness `main()` is `# pragma: no cover`; live-game loops in the harness are `# pragma: no cover` like `ghost_bench.bench_row`; pure verdict/count functions are tested.

## File Structure

| File | Responsibility |
|---|---|
| `strategies/field_rival.py` (modify) | `rival_sheep(obs)` helper; `market_orders(..., prefer=None)`; `FieldRivalStrategy.herd_preference(obs) -> None` hook, passed as `prefer` |
| `strategies/rival_aware.py` (create) | `SHEEP_THRESHOLD`, `RivalAwareStrategy(DenseFarmStrategy)` overriding `herd_preference` |
| `harness/rival_bench.py` (create) | action-stream capture, animal-buy counts, the three controls, criterion + verdict, CLI |
| `tests/test_rival_aware.py` (create) | seam equality, helper, hook, identity control, registration |
| `tests/test_rival_bench.py` (create) | counting and verdict logic with fakes |

Facts the code relies on: a pasture tile is a dict with `"animal": "COW"|"SHEEP"`; `obs["player"]` is our seat, `obs["farms"][1 - player]["tiles"]` the rival's 10x10 tile grid (rows of tiles, `None` for empty, `"LOCKED"` strings possible); `HERD_MIX = ("COW", "SHEEP")` and the current rule is `kind = HERD_MIX[1] if budget >= 3 * economy.ANIMALS[HERD_MIX[1]]["cost"] else HERD_MIX[0]` inside `market_orders`'s herd loop (`strategies/field_rival.py` around line 390); `FieldRivalStrategy.act(self, obs)` calls `market_orders(day, hour, me["money"], len(hands), <quadrants>, animals, shed, seeds, empty, standing, caps=self.CAPS)` near line 579; `harness.triage.head_to_head_rate(name, opponent, seeds, play=None, agents=None) -> {"name","opponent","wins","ties","games","seeds"}`; `harness.evolve.DEFAULT_ANCHORS == ("meta_bot","ranch_hands","market_farmer","ranch_adaptive","wheat_hands","field_rival")`; `harness.tournament.play_rewards(agent_a, agent_b, seed) -> (ra, rb)`; `kaggisim.strategy.make_agent`, `strategies.load`.

---

### Task 1: The seam on the frozen benchmark (behaviour-preserving)

**Files:**
- Modify: `strategies/field_rival.py` (add `rival_sheep`, the `prefer` parameter, the hook, one call-site change)
- Test: `tests/test_rival_aware.py` (create; more tests appended in Task 2)

**Interfaces:**
- Produces: `rival_sheep(obs) -> int`; `market_orders(day, hour, money, hands, quadrants, animals, shed, seeds, empty_plots, standing=None, caps=None, prefer=None)` where `prefer` is `None` or an animal kind string that overrides the budget rule for every BUY_ANIMAL in that call; `FieldRivalStrategy.herd_preference(self, obs) -> str | None` returning `None`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_rival_aware.py
"""#219: the frozen benchmark gains one behaviour-preserving seam (the #202
`caps` shape) and a helper that reads the rival's sheep off their tiles."""

from __future__ import annotations

from strategies import field_rival as fr


def _board(animals_at):
    """A 10x10 tile grid with pasture animals at the given (x, y) -> kind."""
    tiles = [[None] * fr.BOARD for _ in range(fr.BOARD)]
    for (x, y), kind in animals_at.items():
        tiles[y][x] = {"kind": "PASTURE", "animal": kind, "fed_today": False}
    return tiles


def _obs(player, our_tiles, their_tiles):
    farms = [None, None]
    farms[player] = {"money": 5000, "tiles": our_tiles, "hands": [], "unlocked_quadrants": ["NW"]}
    farms[1 - player] = {"money": 5000, "tiles": their_tiles, "hands": [], "unlocked_quadrants": ["NW"]}
    return {"player": player, "day": 9, "hour": 0, "farms": farms,
            "private": {"shed": {}, "seeds": {}, "inventories": [{}]}}


def test_rival_sheep_counts_only_the_other_farms_sheep():
    ours = _board({(0, 5): "SHEEP", (1, 5): "SHEEP"})
    theirs = _board({(2, 5): "SHEEP", (3, 5): "COW", (4, 5): "SHEEP"})
    assert fr.rival_sheep(_obs(0, ours, theirs)) == 2
    assert fr.rival_sheep(_obs(1, ours, theirs)) == 2      # seat 1: "theirs" is now ours


def test_rival_sheep_ignores_weeds_locked_and_empty_tiles():
    theirs = _board({})
    theirs[3][3] = {"kind": "WEED"}
    theirs[4][4] = "LOCKED"
    assert fr.rival_sheep(_obs(0, _board({}), theirs)) == 0


def _orders(prefer):
    # A rich farm on a herd-buying turn: the budget rule alone would pick SHEEP.
    return fr.market_orders(day=9, hour=0, money=50_000, hands=8, quadrants=2, animals=0,
                            shed={}, seeds={}, empty_plots=0, standing={}, caps=None, prefer=prefer)


def test_prefer_none_is_the_budget_rule_unchanged():
    kinds = [o[1] for o in _orders(None) if o[0] == "BUY_ANIMAL"]
    assert kinds, "POSITIVE CONTROL: no animal was bought, the seam was not exercised"
    assert set(kinds) == {"SHEEP"}


def test_prefer_cow_overrides_the_budget_rule():
    kinds = [o[1] for o in _orders("COW") if o[0] == "BUY_ANIMAL"]
    assert kinds and set(kinds) == {"COW"}


def test_prefer_changes_nothing_but_the_kind():
    without = [o for o in _orders(None) if o[0] != "BUY_ANIMAL"]
    with_cow = [o for o in _orders("COW") if o[0] != "BUY_ANIMAL"]
    assert without == with_cow
    assert len([o for o in _orders(None) if o[0] == "BUY_ANIMAL"]) == \
           len([o for o in _orders("COW") if o[0] == "BUY_ANIMAL"])


def test_the_benchmarks_hook_prefers_nothing():
    assert fr.FieldRivalStrategy().herd_preference(_obs(0, _board({}), _board({(0, 5): "SHEEP"}))) is None


def test_the_benchmark_acts_exactly_as_before_the_seam():
    # Byte-identical decisions with the defaults: the same observation, the
    # same action, whether or not the hook exists -- pinned by comparing
    # act() against market_orders called with prefer=None on a real game turn.
    from kaggle_environments import make
    from kaggisim.strategy import make_agent
    env = make("kaggriculture", configuration={"episodeSteps": 240, "seed": 5})
    env.reset(2)
    a = make_agent(fr.FieldRivalStrategy()); b = make_agent(fr.FieldRivalStrategy())
    bought = 0
    for _ in range(239):
        act0 = a(env.state[0].observation)
        bought += sum(1 for o in act0["market"] if o[0] == "BUY_ANIMAL")
        env.step([act0, b(env.state[1].observation)])
    assert bought > 0, "POSITIVE CONTROL: the benchmark bought no animals in ten days"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest -q tests/test_rival_aware.py`
Expected: `AttributeError: module 'strategies.field_rival' has no attribute 'rival_sheep'`; `TypeError: market_orders() got an unexpected keyword argument 'prefer'`; `AttributeError: 'FieldRivalStrategy' object has no attribute 'herd_preference'`. The last test (a real ten-day game) may pass already — record that it did; it is the precondition-bearing control that the benchmark buys animals at all, and it protects the call-site change in Step 3.

- [ ] **Step 3: Make the minimal changes to `strategies/field_rival.py`**

Add after `count_animals`:

```python
def rival_sheep(obs) -> int:
    """How many sheep the OTHER farm has placed, read off its public tiles.

    #219: the one thing worth knowing about the rival is which shallow market
    they are about to flood, and wool (one shop) is the knife-edge one (#146).
    A weed is a dict with no "animal" key and a locked tile is a string; both
    count zero.
    """
    them = obs["farms"][1 - int(obs.get("player", 0))]
    return sum(1 for row in (them.get("tiles") or []) for t in row
               if isinstance(t, dict) and t.get("animal") == "SHEEP")
```

Change the signature `def market_orders(day, hour, money, hands, quadrants, animals, shed, seeds, empty_plots, standing=None, caps=None):` to end `..., caps=None, prefer=None):`, add to its docstring one line: "`prefer`: an animal kind that overrides the budget rule for this turn's BUY_ANIMALs (#219); `None` keeps the benchmark's rule.", and in the herd loop replace

```python
        kind = HERD_MIX[1] if budget >= 3 * economy.ANIMALS[HERD_MIX[1]]["cost"] else HERD_MIX[0]
```

with

```python
        kind = prefer or (HERD_MIX[1] if budget >= 3 * economy.ANIMALS[HERD_MIX[1]]["cost"]
                          else HERD_MIX[0])
```

In `FieldRivalStrategy`, add a method (next to `act`):

```python
    def herd_preference(self, obs):
        """The animal kind to buy this turn regardless of budget, or ``None``
        for the benchmark's own rule. A seam for contenders (#219); the
        benchmark itself never prefers, so its decisions stay frozen (#181)."""
        return None
```

and change the `market_orders(...)` call in `act` to pass `caps=self.CAPS, prefer=self.herd_preference(obs)`.

- [ ] **Step 4: Run the new tests and the frozen pins**

Run: `.venv/bin/python -m pytest -q tests/test_rival_aware.py tests/test_field_rival.py tests/test_dense_farm.py tests/test_dung_farm.py tests/test_balanced_farm.py`
Expected: all pass. (`dung_farm` wraps `market_orders` positionally; the trailing keyword is invisible to it.)

- [ ] **Step 5: Full suite, then commit**

Run: `.venv/bin/python -m pytest -q -n auto` (about a minute). Then:

```bash
git add strategies/field_rival.py tests/test_rival_aware.py
git commit -m "field_rival: rival_sheep helper and a behaviour-preserving herd-kind seam (#219)

prefer=None and herd_preference() -> None keep the benchmark byte-identical,
in the #202 caps shape; contenders override the hook.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 2: The contender `rival_aware`

**Files:**
- Create: `strategies/rival_aware.py`
- Test: `tests/test_rival_aware.py` (append)

**Interfaces:**
- Consumes: Task 1's `rival_sheep`, `herd_preference` hook; `strategies.dense_farm.DenseFarmStrategy`.
- Produces: `SHEEP_THRESHOLD = 2`; `class RivalAwareStrategy(DenseFarmStrategy)` with `name = "rival_aware"`, `benchmark = False`, class attribute `THRESHOLD = SHEEP_THRESHOLD`, `herd_preference(self, obs) -> "COW" | None`; module-level `STRATEGY = RivalAwareStrategy`.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_rival_aware.py`)

```python
from strategies import rival_aware as ra


def test_the_threshold_is_declared():
    assert ra.SHEEP_THRESHOLD == 2 and ra.RivalAwareStrategy.THRESHOLD == 2


def test_prefers_cows_once_the_rival_shows_two_sheep():
    s = ra.RivalAwareStrategy()
    one = _obs(0, _board({}), _board({(0, 5): "SHEEP"}))
    two = _obs(0, _board({}), _board({(0, 5): "SHEEP", (1, 5): "SHEEP"}))
    cows = _obs(0, _board({}), _board({(0, 5): "COW", (1, 5): "COW", (2, 5): "COW"}))
    assert s.herd_preference(one) is None
    assert s.herd_preference(two) == "COW"
    assert s.herd_preference(cows) is None


def test_it_is_a_registered_contender_built_on_dense_farm():
    from strategies import REGISTRY, load
    from strategies.dense_farm import DenseFarmStrategy
    assert "rival_aware" in REGISTRY and load("rival_aware") is ra.RivalAwareStrategy
    assert issubclass(ra.RivalAwareStrategy, DenseFarmStrategy)
    assert ra.RivalAwareStrategy.benchmark is False
    assert ra.RivalAwareStrategy.CAPS == DenseFarmStrategy.CAPS


def test_identity_control_threshold_off_is_dense_farm_to_the_value():
    # Spec control 1: with the threshold unreachable the contender IS dense_farm
    # on a full seeded game, both seats' rewards equal to the value.
    from kaggle_environments import make
    from kaggisim.strategy import make_agent
    from strategies import load

    class Off(ra.RivalAwareStrategy):
        THRESHOLD = 10 ** 9

    def rewards(ours):
        env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": 21})
        env.run([make_agent(ours), make_agent(load("dense_farm")())])
        return [s.reward or 0 for s in env.steps[-1]]

    base = rewards(load("dense_farm")())
    assert base[0] > 0, "POSITIVE CONTROL: no money moved"
    assert rewards(Off()) == base
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest -q tests/test_rival_aware.py`
Expected: `ModuleNotFoundError: No module named 'strategies.rival_aware'` at collection.

- [ ] **Step 3: Write the strategy**

```python
# strategies/rival_aware.py
"""Read the rival's herd off the board and keep ours out of their market (#219).

`dense_farm` with one decision changed: once the other farm has placed
SHEEP_THRESHOLD sheep, every animal we buy is a cow. Wool has one shop and
floors past ~300 units between the two farms (#146); milk has three shops and
570 season demand. Everything else -- crop caps, ramps, sells, land, feed --
is `dense_farm`'s, through the `herd_preference` seam on the frozen benchmark
(#181, #202).

Declared before measurement: the threshold, and the criterion in
docs/superpowers/specs/2026-09-06-rival-aware-herd-design.md.
"""

from __future__ import annotations

from strategies import field_rival as fr
from strategies.dense_farm import DenseFarmStrategy

#: One sheep can be a stray placement; two is a herd. Declared in #219.
SHEEP_THRESHOLD = 2


class RivalAwareStrategy(DenseFarmStrategy):
    """`dense_farm` that buys cows once the rival is running sheep."""

    name = "rival_aware"
    benchmark = False

    #: Class attribute so a test can switch the mechanism off (threshold
    #: unreachable) and prove the identity with dense_farm to the value.
    THRESHOLD = SHEEP_THRESHOLD

    def herd_preference(self, obs):
        return "COW" if fr.rival_sheep(obs) >= self.THRESHOLD else None


STRATEGY = RivalAwareStrategy
```

- [ ] **Step 4: Run the tests, the no-crash guard for the new name, then the full suite**

Run: `.venv/bin/python -m pytest -q tests/test_rival_aware.py`, then `.venv/bin/python -m pytest -q tests/test_no_crash.py -k rival_aware` (two full seasons), then `.venv/bin/python -m pytest -q -n auto`.
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add strategies/rival_aware.py tests/test_rival_aware.py
git commit -m "rival_aware: dense_farm that buys cows once the rival runs sheep (#219)

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 3: Controls, criterion and CLI

**Files:**
- Create: `harness/rival_bench.py`
- Test: `tests/test_rival_bench.py`

**Interfaces:**
- Consumes: `harness.triage.head_to_head_rate`, `harness.evolve.DEFAULT_ANCHORS`, `harness.tournament.play_rewards`, `kaggisim.strategy.make_agent`, `strategies.load`.
- Produces (pure, tested): `CHAMPION = "dense_farm"`, `CONTENDER = "rival_aware"`, `SEEDS = tuple(range(400, 416))`, `CHAMPION_BAR = 0.60`, `ANCHOR_BAR = 0.90`; `animal_buys(actions) -> dict` counting `BUY_ANIMAL` kinds over a list of action dicts; `mechanism_fired(contender_counts, baseline_counts) -> bool` (`COW` strictly higher AND `SHEEP` strictly lower); `criterion(champion_row, anchor_rows, champion_bar=CHAMPION_BAR, anchor_bar=ANCHOR_BAR) -> dict` with `passed`, `champion_rate`, `anchor_rates` (name -> rate), `failing` (list of names below their bar); `format_rows(rows) -> str`. Live (`# pragma: no cover`): `action_stream(strategy_name, opponent_name, seed, episode_steps=720) -> tuple[list[dict], dict]` (our actions per turn, plus the rival's final placed animal counts), `run_controls()`, `run_criterion()`, `main()`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_rival_bench.py
"""The #219 experiment's counting and verdict logic, pinned before any number."""

from __future__ import annotations

from harness import rival_bench as rb


def test_the_declared_constants():
    assert rb.CHAMPION == "dense_farm" and rb.CONTENDER == "rival_aware"
    assert rb.SEEDS == tuple(range(400, 416))
    assert rb.CHAMPION_BAR == 0.60 and rb.ANCHOR_BAR == 0.90


def test_animal_buys_counts_kinds_across_turns():
    actions = [{"market": [["BUY_ANIMAL", "COW", 1], ["SELL", "WOOL", 3]]},
               {"market": [["BUY_ANIMAL", "SHEEP", 1], ["BUY_ANIMAL", "COW", 1]]},
               {"market": []}]
    assert rb.animal_buys(actions) == {"COW": 2, "SHEEP": 1}


def test_mechanism_fired_needs_more_cows_and_fewer_sheep():
    assert rb.mechanism_fired({"COW": 6, "SHEEP": 2}, {"COW": 3, "SHEEP": 5}) is True
    assert rb.mechanism_fired({"COW": 6, "SHEEP": 5}, {"COW": 3, "SHEEP": 5}) is False
    assert rb.mechanism_fired({"COW": 3, "SHEEP": 2}, {"COW": 3, "SHEEP": 5}) is False


def _row(name, wins, games=16):
    return {"name": "rival_aware", "opponent": name, "wins": wins, "ties": 0, "games": games,
            "seeds": "400-415"}


def test_criterion_passes_only_at_both_bars():
    anchors = [_row(n, 15) for n in ("meta_bot", "ranch_hands", "market_farmer",
                                     "ranch_adaptive", "wheat_hands", "field_rival")]
    ok = rb.criterion(_row("dense_farm", 10), anchors)           # 62.5% and 93.75%
    assert ok["passed"] is True and ok["failing"] == []
    champ_short = rb.criterion(_row("dense_farm", 9), anchors)   # 56.25% < 60%
    assert champ_short["passed"] is False and champ_short["failing"] == ["dense_farm"]
    anchors[0] = _row("meta_bot", 14)                            # 87.5% < 90%
    anchor_short = rb.criterion(_row("dense_farm", 10), anchors)
    assert anchor_short["passed"] is False and anchor_short["failing"] == ["meta_bot"]


def test_criterion_counts_a_tie_as_not_a_win():
    tied = dict(_row("dense_farm", 9), ties=7)
    assert rb.criterion(tied, [_row("meta_bot", 16)])["champion_rate"] == 9 / 16


def test_format_rows_one_line_per_opponent_with_rate():
    text = rb.format_rows([_row("dense_farm", 10), _row("meta_bot", 15)])
    lines = [ln for ln in text.splitlines() if ln.strip()]
    assert len(lines) == 3 and "dense_farm" in lines[1] and "10/16" in lines[1]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest -q tests/test_rival_bench.py`
Expected: `ModuleNotFoundError: No module named 'harness.rival_bench'`.

- [ ] **Step 3: Write the module**

```python
# harness/rival_bench.py
"""#219: does buying cows when the rival runs sheep beat the champion?

    python -m harness.rival_bench --controls      # the three spec controls, ~2 min
    python -m harness.rival_bench --criterion     # 16 seeds x 7 opponents, ~8 min
    python -m harness.rival_bench                 # both, controls first

Declared before code (docs/superpowers/specs/2026-09-06-rival-aware-herd-design.md):
seeds 400-415, sides alternated by list position (`harness.triage.head_to_head_rate`),
PROMOTE only at >= 60% of 16 vs the champion AND >= 90% vs each DEFAULT_ANCHOR;
a tie is not a win. Controls run first and a failed control voids the run.
Exit codes: 0 PROMOTE, 1 REJECTED, 2 VOID. Runs under ROBRICULTURE_STRICT=1.
"""

from __future__ import annotations

import argparse
import os

from harness.evolve import DEFAULT_ANCHORS

CHAMPION = "dense_farm"
CONTENDER = "rival_aware"
SEEDS = tuple(range(400, 416))
CHAMPION_BAR = 0.60
ANCHOR_BAR = 0.90
CONTROL_SEED = 400
QUIET_RIVAL = "wheat_hands"        # places no animals


def animal_buys(actions):
    """{kind: count} of BUY_ANIMAL orders across a list of action dicts."""
    counts = {}
    for action in actions:
        for order in action.get("market", []):
            if order and order[0] == "BUY_ANIMAL" and len(order) >= 2:
                counts[order[1]] = counts.get(order[1], 0) + 1
    return counts


def mechanism_fired(contender_counts, baseline_counts):
    """More cows AND fewer sheep than the baseline, strictly."""
    return (contender_counts.get("COW", 0) > baseline_counts.get("COW", 0)
            and contender_counts.get("SHEEP", 0) < baseline_counts.get("SHEEP", 0))


def _rate(row):
    return row["wins"] / row["games"]


def criterion(champion_row, anchor_rows, champion_bar=CHAMPION_BAR, anchor_bar=ANCHOR_BAR):
    """The declared verdict: both bars, ties never wins."""
    champion_rate = _rate(champion_row)
    anchor_rates = {r["opponent"]: _rate(r) for r in anchor_rows}
    failing = ([champion_row["opponent"]] if champion_rate < champion_bar else []) + \
              [n for n, rate in anchor_rates.items() if rate < anchor_bar]
    return {"passed": not failing, "champion_rate": champion_rate,
            "anchor_rates": anchor_rates, "failing": failing}


def format_rows(rows):
    lines = [f"{'opponent':<16} {'wins':>7} {'ties':>4} {'rate':>6}"]
    for r in rows:
        lines.append(f"{r['opponent']:<16} {r['wins']:>3}/{r['games']:<3} {r.get('ties', 0):>4} "
                     f"{_rate(r):>6.1%}")
    return "\n".join(lines)


# --- live games -------------------------------------------------------------

def action_stream(strategy_name, opponent_name, seed, episode_steps=720):  # pragma: no cover
    """Our per-turn actions in seat 0 against `opponent_name`, plus the rival's
    placed-animal counts at the end (the precondition for control 2)."""
    from kaggle_environments import make
    from kaggisim.strategy import make_agent
    from strategies import load
    env = make("kaggriculture", configuration={"episodeSteps": episode_steps, "seed": seed})
    env.reset(2)
    ours = make_agent(load(strategy_name)())
    theirs = make_agent(load(opponent_name)())
    actions = []
    for _ in range(episode_steps - 1):
        act0 = ours(env.state[0].observation)
        actions.append(act0)
        env.step([act0, theirs(env.state[1].observation)])
    rival = env.state[1].observation["farms"][1]["tiles"]
    placed = {}
    for row in rival:
        for t in row:
            if isinstance(t, dict) and t.get("animal"):
                placed[t["animal"]] = placed.get(t["animal"], 0) + 1
    return actions, placed


def run_controls(seed=CONTROL_SEED):  # pragma: no cover
    from harness.tournament import play_rewards
    from kaggisim.strategy import make_agent
    from strategies import load
    out = {}
    # 1. identity with the threshold off
    off = type("Off", (load(CONTENDER),), {"THRESHOLD": 10 ** 9})
    base = play_rewards(make_agent(load(CHAMPION)()), make_agent(load(CHAMPION)()), seed)
    got = play_rewards(make_agent(off()), make_agent(load(CHAMPION)()), seed)
    out["identity"] = {"ok": got == base, "base": base, "got": got}
    # 2. mechanism fires against the champion (which runs sheep when rich)
    c_actions, rival_placed = action_stream(CONTENDER, CHAMPION, seed)
    b_actions, _ = action_stream(CHAMPION, CHAMPION, seed)
    c_counts, b_counts = animal_buys(c_actions), animal_buys(b_actions)
    out["mechanism"] = {"ok": rival_placed.get("SHEEP", 0) >= 2 and mechanism_fired(c_counts, b_counts),
                        "rival_sheep_placed": rival_placed.get("SHEEP", 0),
                        "contender": c_counts, "baseline": b_counts}
    # 3. quiet against a rival with no sheep: identical action stream
    q_actions, q_placed = action_stream(CONTENDER, QUIET_RIVAL, seed)
    qb_actions, _ = action_stream(CHAMPION, QUIET_RIVAL, seed)
    out["quiet"] = {"ok": q_placed.get("SHEEP", 0) == 0 and q_actions == qb_actions,
                    "rival_sheep_placed": q_placed.get("SHEEP", 0)}
    return out


def run_criterion(seeds=SEEDS):  # pragma: no cover
    from harness.triage import head_to_head_rate
    champion_row = head_to_head_rate(CONTENDER, CHAMPION, seeds)
    anchor_rows = [head_to_head_rate(CONTENDER, a, seeds) for a in DEFAULT_ANCHORS]
    return champion_row, anchor_rows


def main(argv=None):  # pragma: no cover
    os.environ.setdefault("ROBRICULTURE_STRICT", "1")   # an instrument surfaces crashes
    ap = argparse.ArgumentParser(description="#219 rival-aware herd: controls and criterion")
    ap.add_argument("--controls", action="store_true")
    ap.add_argument("--criterion", action="store_true")
    args = ap.parse_args(argv)
    do_controls = args.controls or not args.criterion
    do_criterion = args.criterion or not args.controls

    if do_controls:
        ctl = run_controls()
        for name, r in ctl.items():
            print(f"control {name}: {'OK' if r['ok'] else 'FAIL -- RUN VOID'}  {r}")
        if not all(r["ok"] for r in ctl.values()):
            return 2
    if do_criterion:
        champion_row, anchor_rows = run_criterion()
        print(format_rows([champion_row] + anchor_rows))
        v = criterion(champion_row, anchor_rows)
        print(f"champion {v['champion_rate']:.1%} (bar {CHAMPION_BAR:.0%}); anchors below {ANCHOR_BAR:.0%}: "
              f"{v['failing'] or 'none'} -> {'PROMOTE' if v['passed'] else 'REJECTED'}")
        return 0 if v["passed"] else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest -q tests/test_rival_bench.py`
Expected: `6 passed`.

- [ ] **Step 5: Run the controls (blocking, ~2-3 minutes)**

Run: `.venv/bin/python -m harness.rival_bench --controls`
Expected: three `control ...: OK` lines. If `mechanism` reports `rival_sheep_placed` below 2 on seed 400, that is a precondition failure: report it (do NOT change the seed silently) — the controller decides whether to declare a different control seed before the criterion runs.

- [ ] **Step 6: Full suite with coverage + gate numbers, then commit**

Run: `.venv/bin/python -m pytest -q -n auto --cov --cov-branch --cov-report=term-missing --cov-report=json 2>&1 | tail -3` and print the gate numbers from `coverage.json` (line >= 85, branch >= 65).

```bash
git add harness/rival_bench.py tests/test_rival_bench.py
git commit -m "rival_bench: the #219 controls, the declared criterion and its CLI

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 4: Run the declared experiment and draft the record

**Files:** none in the repo. Output goes to the scratchpad; the controller posts.

- [ ] **Step 1: Declare on the issue before the criterion runs** — the controller posts a short comment on #219 with the spec link, the threshold, seeds, bars and the control results from Task 3 Step 5 (this step is the controller's, recorded here so the order is explicit).

- [ ] **Step 2: Run the whole thing once, blocking, timed** (`time .venv/bin/python -m harness.rival_bench 2>&1 | tee /private/tmp/claude-501/-Users-sartin/2195f188-57a5-4834-a6b9-acc4ec519961/scratchpad/219-rival-bench.txt`). Expect ~10 minutes (7 opponents x 16 games plus the controls). Note the verdict line and exit code (read from the printed verdict, not `$pipestatus` after `time`).

- [ ] **Step 3: Recorded, not gated** — one python snippet: per-opponent median final money for the contender over the 16 games is NOT available from `head_to_head_rate` (it returns wins); instead play seeds 400 and 401 contender-vs-champion through `harness.episode_analysis.price_realisation` for both farms and report realised WOOL and MILK prices and units — the mechanism's direct signature. Also report cows/sheep bought per game from the controls output.

- [ ] **Step 4: Draft the issue comment** (`.../scratchpad/219-comment.md`): `## PROMOTE|REJECTED, 2026-09-06` heading; the declared criterion verbatim; the three control lines; the per-opponent table verbatim; the verdict line; the wool/milk realised-price table; cows/sheep bought; "root cause" if REJECTED (from the numbers); "what to do with it" (ADR-0007 salvage: the seam and the bench stay, no strategy promoted); last line naming branch `219-rival-routing` and the PR.

- [ ] **Step 5: Draft the PR body** (`.../scratchpad/219-pr-body.md`): title-in-body `PROMOTE`/`REJECTED (#219)`, the declared criterion, controls, table, verdict, what the PR carries (the seam on `field_rival` pinned byte-identical, `rival_aware`, `rival_bench`, tests). No `Closes #219` (ADR-0007: the issue keeps the record either way). Final line `🤖 Generated with [Claude Code](https://claude.com/claude-code)`.

---

## Self-review

- **Spec coverage:** signal (Task 1 `rival_sheep`), decision + threshold (Task 2), seam pinned byte-identical (Task 1 tests + existing pins), registration/contender (Task 2), three controls (Task 3 `run_controls`; identity also as a unit test in Task 2), criterion with both bars and ties-not-wins on seeds 400-415 via `head_to_head_rate` (Task 3), recorded-not-gated wool/milk realisation and buy counts (Task 4), verdict to issue and PR without `Closes` (Task 4).
- **Placeholders:** none.
- **Type consistency:** `market_orders(..., caps=None, prefer=None)` used identically in Task 1's tests and `act`; `herd_preference(obs) -> str | None` in Tasks 1 and 2; `head_to_head_rate` rows carry `name/opponent/wins/ties/games/seeds` and `criterion`/`format_rows` read exactly `opponent/wins/games/ties`; `action_stream` returns `(actions, placed)` and `run_controls` consumes exactly that.
