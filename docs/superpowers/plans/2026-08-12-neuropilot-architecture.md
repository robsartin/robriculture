# neuropilot — NN-guided Agent Architecture (Phase 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A legal, submittable `Strategy` (`neuropilot`) whose per-turn decisions come from a pure-Python MLP (weights = genome) feeding a fresh knob-driven controller — proving the neuroevolution architecture end-to-end with random weights.

**Architecture:** `strategies/neuropilot.py`: `features(state)→list[float]` → a stdlib MLP (`H1=16`, `N_KNOBS=8`) → `controller(knobs, state)→action_dict`. The controller is self-contained (only low-level `kaggisim` primitives, never other strategies' logic) and supports the full legal action vocabulary. Phase 1 ships a fixed seeded-random `DEFAULT_GENOME`; the genome interface is frozen so Phase 2 can inject evolved weights.

**Tech Stack:** Python 3.12 (3.11 floor), **stdlib only** (`math`, `random` — no numpy), `pytest` (+ `--cov --cov-branch`), `kaggle_environments` kaggriculture sim.

## Global Constraints

- **Stdlib only in the agent** (ADR-0004): the MLP is plain Python (`math.tanh`, a sigmoid); no numpy.
- **Adding a strategy = dropping `strategies/neuropilot.py` + `tests/test_neuropilot.py`.** Do NOT edit `strategies/__init__.py`. `name="neuropilot"`, `benchmark=False`, `STRATEGY=NeuroPilotStrategy`.
- **The controller uses only low-level primitives** — `kaggisim.state` (`my_farm`, `opponent_farm`, `prices`, `tile_at`), `kaggisim.economy` (`CROPS`, `base_price`, `SHOP_DEMAND`), `kaggisim.actions` (the action builders) — and a tiny self-contained navigation helper. **Never import `meta_bot`/`ranch_hands`/other strategy modules.** (The sim *mechanics* — e.g. build-pasture→place→feed order — may be cross-checked against `meta_bot.animal_chore` as a correctness reference, but no strategy code is imported.)
- **Decisions in pure module-level helpers**; `act()` thin. Runs under the existing `make_agent` fail-safe (ADR-0006); develop with `ROBRICULTURE_STRICT=1`.
- **Market cap 10/turn, sells ordered first.**
- **Determinism/reproducibility** (ADR-0005): `DEFAULT_GENOME` from a fixed seed; `features`/`MLP.forward` deterministic; `features` never raises (returns `NEUTRAL_FEATURES` on malformed obs).
- **Coverage gate:** line ≥85%, branch ≥65% (bare `pytest --cov --cov-branch`); `# pragma: no cover` only on integration entrypoints, never pure helpers.
- **Run from repo root, venv active** (`source .venv/bin/activate`, Homebrew python3.12). Tests pristine.
- **Frozen interface names for Phase 2:** `N_FEATURES`, `N_KNOBS`, `H1`, `genome_size(n_in,h1,n_out)`, `random_genome(n_in,h1,n_out,seed)`, `MLP.from_genome(genome,n_in,h1,n_out)`, `MLP.forward(features)`, `features(state)`, `controller(knobs,state)`, `DEFAULT_GENOME`, and `NeuroPilotStrategy(genome=None)` (defaults to `DEFAULT_GENOME`).

---

## File Structure

- `strategies/neuropilot.py` — **create.** The whole agent: features, MLP, knob transforms, controller, strategy class.
- `tests/test_neuropilot.py` — **create.** Pure-helper unit tests for every unit + the frozen-shape checks.

The agent is one focused file (~300-400 lines) with clearly separated helper sections; that matches the repo's one-file-per-strategy convention and keeps the Phase-2-frozen interface in one place.

---

### Task 1: Feature extractor

**Files:** Create `strategies/neuropilot.py` (feature section only); Test `tests/test_neuropilot.py`.

**Interfaces:**
- Produces: `N_FEATURES: int`; `NEUTRAL_FEATURES: list[float]` (length `N_FEATURES`, all `0.5`); `features(state) -> list[float]` (length `N_FEATURES`, each in `[0,1]`, never raises).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_neuropilot.py
"""neuropilot — NN-guided agent (neuroevolution Phase 1, #64)."""
from __future__ import annotations
from strategies import neuropilot as np


def _obs(day=0, hour=0, money=3000, hands=None, tiles=None, shed=None,
         unlocked=("NW",), prices=None, opp_money=3000):
    board = tiles or [[None]*10 for _ in range(10)]
    hands = hands or []
    return {
        "player": 0, "day": day, "hour": hour,
        "farms": [
            {"money": money, "tiles": board, "farmer": [4, 4], "hands": hands,
             "unlocked_quadrants": list(unlocked)},
            {"money": opp_money, "tiles": [[None]*10 for _ in range(10)], "farmer": [4, 4], "hands": []},
        ],
        "market": {"inventory": {}, "prices": prices or {}},
        "town": {"unlocked_shops": []},
        "private": {"shed": shed or {}, "seeds": {}, "inventories": [{} for _ in range(1 + len(hands))]},
    }


def test_features_has_fixed_length_all_in_unit_range():
    f = np.features(_obs())
    assert len(f) == np.N_FEATURES
    assert all(0.0 <= v <= 1.0 for v in f)


def test_features_is_deterministic():
    o = _obs(day=5, money=12000)
    assert np.features(o) == np.features(o)


def test_features_reflects_day_progress():
    # A later day pushes the day-fraction feature higher (feature index 0).
    assert np.features(_obs(day=20))[0] > np.features(_obs(day=1))[0]


def test_features_never_raises_returns_neutral_on_malformed():
    assert np.features({"garbage": True}) == np.NEUTRAL_FEATURES
    assert len(np.NEUTRAL_FEATURES) == np.N_FEATURES
```

- [ ] **Step 2: Run to verify they fail**

Run: `ROBRICULTURE_STRICT=1 pytest tests/test_neuropilot.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'strategies.neuropilot'`.

- [ ] **Step 3: Implement the feature section**

Create `strategies/neuropilot.py` with a module docstring (state it's neuroevolution Phase 1 / ADR-0008 / #64; NN-guided controller, stdlib-only, fresh controller). Then:

```python
from __future__ import annotations
import math, random
from kaggisim import economy
from kaggisim.strategy import Strategy

SEASON_DAYS = 30
TURNS_PER_DAY = 12
MAX_HANDS = 9
N_COW, N_SHEEP = 9, 4

# Ordered feature list — the plan pins this; changing order changes the genome contract.
_PRICE_ITEMS = ("MELON", "WHEAT", "MILK", "WOOL")

def _clamp01(v: float) -> float:
    return 0.0 if v < 0.0 else 1.0 if v > 1.0 else v

def _count_tiles(tiles, pred) -> int:
    return sum(1 for row in tiles for t in row if pred(t))

def features(state) -> list[float]:
    """Fixed-length normalized feature vector (never raises)."""
    try:
        me = state["farms"][state["player"]]
        opp = state["farms"][1 - state["player"]]
        day = state.get("day", 0); hour = state.get("hour", 0)
        tiles = me["tiles"]; money = me.get("money", 0)
        prices = state.get("market", {}).get("prices", {})
        shed = state.get("private", {}).get("shed", {})
        unlocked = me.get("unlocked_quadrants", ["NW"])
        hands = me.get("hands", []) or []
        n_crop = max(1, _count_tiles(tiles, lambda t: t is None) + _count_tiles(
            tiles, lambda t: isinstance(t, dict) and t.get("kind") == "PLANT"))
        f = [
            _clamp01(day / SEASON_DAYS),
            _clamp01(hour / TURNS_PER_DAY),
            _clamp01(1.0 - day / SEASON_DAYS),
            _clamp01(math.log1p(max(0, money)) / 12.0),
            _clamp01(money / (money + opp.get("money", 0) + 1.0)),
        ]
        for item in _PRICE_ITEMS:
            base = economy.base_price(item) or 1.0
            f.append(_clamp01((prices.get(item, base) / base) / 2.0))
        f += [
            _clamp01(_count_tiles(tiles, lambda t: t is None) / n_crop),
            _clamp01(_count_tiles(tiles, lambda t: isinstance(t, dict) and t.get("kind") == "PLANT") / n_crop),
            _clamp01(_count_tiles(tiles, lambda t: isinstance(t, dict) and t.get("kind") == "WEED") / max(1, n_crop)),
            _clamp01(_count_tiles(tiles, lambda t: isinstance(t, dict) and t.get("animal") == "COW") / N_COW),
            _clamp01(_count_tiles(tiles, lambda t: isinstance(t, dict) and t.get("animal") == "SHEEP") / N_SHEEP),
            1.0 if "NE" in unlocked else 0.0,
            1.0 if "SW" in unlocked else 0.0,
            _clamp01(len(hands) / MAX_HANDS),
            _clamp01(shed.get("MELON", 0) / 50.0),
            _clamp01(shed.get("WHEAT", 0) / 50.0),
            _clamp01(shed.get("FERTILIZER", 0) / 20.0),
        ]
        return f
    except Exception:
        return NEUTRAL_FEATURES

N_FEATURES = 18
NEUTRAL_FEATURES = [0.5] * N_FEATURES
```

- [ ] **Step 4: Run to verify pass** — `ROBRICULTURE_STRICT=1 pytest tests/test_neuropilot.py -v` → PASS (4).
  (If `len(features(...))` ≠ 18, fix `N_FEATURES` to the actual count and keep the test `== N_FEATURES`.)

- [ ] **Step 5: Commit**

```bash
git add strategies/neuropilot.py tests/test_neuropilot.py
git commit -m "feat(neuropilot): feature extractor (neuroevolution Phase 1) (#64)"
```

---

### Task 2: Pure-Python MLP (the genome)

**Files:** Modify `strategies/neuropilot.py`; Test `tests/test_neuropilot.py`.

**Interfaces:**
- Consumes: `N_FEATURES`.
- Produces: `H1 = 16`; `N_KNOBS = 8`; `genome_size(n_in, h1, n_out) -> int`; `random_genome(n_in, h1, n_out, seed) -> list[float]`; `class MLP` with `MLP.from_genome(genome, n_in, h1, n_out)` and `forward(features) -> list[float]` (length `n_out`, each in `[0,1]`); `DEFAULT_GENOME: list[float]`.

- [ ] **Step 1: Write the failing tests**

```python
def test_genome_size_matches_layer_shapes():
    # W1 (h1*n_in) + b1 (h1) + W2 (n_out*h1) + b2 (n_out)
    assert np.genome_size(4, 3, 2) == (3*4 + 3) + (2*3 + 2)

def test_forward_outputs_are_in_unit_range_and_right_length():
    g = np.random_genome(np.N_FEATURES, np.H1, np.N_KNOBS, seed=1)
    mlp = np.MLP.from_genome(g, np.N_FEATURES, np.H1, np.N_KNOBS)
    out = mlp.forward([0.5] * np.N_FEATURES)
    assert len(out) == np.N_KNOBS
    assert all(0.0 <= v <= 1.0 for v in out)

def test_forward_is_deterministic():
    g = np.random_genome(np.N_FEATURES, np.H1, np.N_KNOBS, seed=2)
    mlp = np.MLP.from_genome(g, np.N_FEATURES, np.H1, np.N_KNOBS)
    x = [0.3] * np.N_FEATURES
    assert mlp.forward(x) == mlp.forward(x)

def test_tiny_genome_forward_matches_hand_computation():
    # n_in=1, h1=1, n_out=1. genome = [W1, b1, W2, b2] = [1.0, 0.0, 1.0, 0.0].
    mlp = np.MLP.from_genome([1.0, 0.0, 1.0, 0.0], 1, 1, 1)
    h = math.tanh(1.0*0.5 + 0.0)
    expected = 1.0/(1.0+math.exp(-(1.0*h + 0.0)))
    assert abs(mlp.forward([0.5])[0] - expected) < 1e-9

def test_default_genome_has_the_right_length():
    assert len(np.DEFAULT_GENOME) == np.genome_size(np.N_FEATURES, np.H1, np.N_KNOBS)
```
(add `import math` at the top of the test file.)

- [ ] **Step 2: Run to verify fail** — Expected: `AttributeError` (`genome_size`/`MLP`/… undefined).

- [ ] **Step 3: Implement**

```python
H1 = 16
N_KNOBS = 8

def _sigmoid(z: float) -> float:
    if z < 0:
        e = math.exp(z); return e / (1.0 + e)
    return 1.0 / (1.0 + math.exp(-z))

def genome_size(n_in: int, h1: int, n_out: int) -> int:
    return (h1 * n_in + h1) + (n_out * h1 + n_out)

def random_genome(n_in: int, h1: int, n_out: int, seed: int) -> list[float]:
    r = random.Random(seed)
    return [r.uniform(-1.0, 1.0) for _ in range(genome_size(n_in, h1, n_out))]

class MLP:
    def __init__(self, w1, b1, w2, b2):
        self.w1, self.b1, self.w2, self.b2 = w1, b1, w2, b2

    @classmethod
    def from_genome(cls, genome, n_in, h1, n_out):
        i = 0
        w1 = [genome[i + j*n_in : i + (j+1)*n_in] for j in range(h1)]; i += h1*n_in
        b1 = genome[i:i+h1]; i += h1
        w2 = [genome[i + j*h1 : i + (j+1)*h1] for j in range(n_out)]; i += n_out*h1
        b2 = genome[i:i+n_out]
        return cls(w1, b1, w2, b2)

    def forward(self, features):
        h = [math.tanh(sum(w*x for w, x in zip(row, features)) + b)
             for row, b in zip(self.w1, self.b1)]
        return [_sigmoid(sum(w*x for w, x in zip(row, h)) + b)
                for row, b in zip(self.w2, self.b2)]

DEFAULT_GENOME = random_genome(N_FEATURES, H1, N_KNOBS, seed=20260812)
```

- [ ] **Step 4: Run to verify pass** — PASS (5 new).
- [ ] **Step 5: Commit** — `git commit -m "feat(neuropilot): stdlib MLP + genome interface (#64)"`

---

### Task 3: Knob transforms + minimal controller → a playable agent

Deliver a legal, playable `neuropilot` that farms crops, hires, and sells under NN control (livestock added in Task 4). This proves the full pipeline end-to-end (the Phase-1 goal).

**Files:** Modify `strategies/neuropilot.py`; Test `tests/test_neuropilot.py`.

**Interfaces:**
- Consumes: `features`, `MLP`, `DEFAULT_GENOME`, `N_KNOBS`.
- Produces: `Knobs` (a small dataclass or namedtuple with fields `sell_throttle, hire_target, livestock_pace, livestock_labor_share, herd_target_scale, fertilize_pref, capital_reserve, crop_mix`, all floats in [0,1]); `decode_knobs(raw: list[float]) -> Knobs`; `_step_toward(pos, target) -> list` (one MOVE toward target, or `["PASS"]` if there); `controller(knobs, state) -> dict` (a legal `{"farmer","hands","market"}`, ≤10 market orders, sells first); `class NeuroPilotStrategy(Strategy)` (`name="neuropilot"`, `benchmark=False`, `__init__(self, genome=None)` using `DEFAULT_GENOME` when None) with `act(state)`; `STRATEGY = NeuroPilotStrategy`.

- [ ] **Step 1: Write the failing tests**

```python
def test_decode_knobs_maps_all_eight_fields_into_unit_range():
    k = np.decode_knobs([0.0, 0.25, 0.5, 0.75, 1.0, 0.1, 0.9, 0.4])
    assert 0.0 <= k.sell_throttle <= 1.0 and 0.0 <= k.crop_mix <= 1.0
    assert k.hire_target == 0.25

def test_step_toward_moves_and_passes():
    from kaggisim.actions import MOVES
    assert np._step_toward([4, 4], [4, 4]) == ["PASS"]
    assert np._step_toward([0, 4], [4, 4])[0] in MOVES

def test_controller_returns_a_legal_shape():
    k = np.decode_knobs([0.5]*np.N_KNOBS)
    a = np.controller(k, _obs(hour=0))
    assert isinstance(a["farmer"], list) and a["farmer"]
    assert isinstance(a["hands"], list)
    assert len(a["market"]) <= 10

def test_controller_sells_lead_the_market_list():
    k = np.decode_knobs([0.0] + [0.5]*(np.N_KNOBS-1))  # sell_throttle low => sell freely
    a = np.controller(k, _obs(hour=0, shed={"MELON": 10}))
    sells = [i for i, o in enumerate(a["market"]) if o[0] == "SELL"]
    non_sells = [i for i, o in enumerate(a["market"]) if o[0] != "SELL"]
    assert not non_sells or (not sells) or max(sells) < min(non_sells)

def test_hire_target_scales_the_hire_count():
    low = np.controller(np.decode_knobs([0.5, 0.0] + [0.5]*6), _obs(hour=0))
    high = np.controller(np.decode_knobs([0.5, 1.0] + [0.5]*6), _obs(hour=0))
    assert sum(o[0] == "HIRE" for o in high["market"]) >= sum(o[0] == "HIRE" for o in low["market"])

def test_act_runs_and_returns_legal_shape():
    a = np.NeuroPilotStrategy().act(_obs(hour=0))
    assert set(a) == {"farmer", "hands", "market"} and len(a["market"]) <= 10

def test_strategy_registered_as_contender():
    assert np.STRATEGY.benchmark is False and np.STRATEGY.name == "neuropilot"
```

- [ ] **Step 2: Run to verify fail** — Expected: `decode_knobs`/`controller`/`NeuroPilotStrategy` undefined.

- [ ] **Step 3: Implement knob decode + minimal controller + strategy**

Add a `Knobs = collections.namedtuple(...)` with the 8 fields; `decode_knobs(raw)` maps the raw sigmoid list positionally into `Knobs` (identity for [0,1] fields; `hire_target`/`herd_target_scale`/`labor_share` interpreted by the controller). Implement `_step_toward(pos, target)` using `kaggisim.actions.MOVES` (compare x then y, return the appropriate `["NORTH"|"SOUTH"|"EAST"|"WEST"]`, `["PASS"]` if on target — mirror the sim's coordinate convention: tiles indexed `[y][x]`, farmer pos `[x, y]`). Implement `controller(knobs, state)`:
- **Crop plots:** a fixed NW crew list `CROP_PLOTS = [(x, y) for y in range(...) for x in range(...)]` covering the always-unlocked NW block (reuse the same 10-tile NW layout constant meta_bot uses *by value*, re-declared here — do not import it). Assign farmer + hands to plots by index; a crop worker on its plot runs a minimal loop: `DIG` a weed; `PLANT` the crop (melon if `crop_mix` favors melon and plantable, else wheat) on an empty plot when seed is held; `WATER` a live unwatered plant; `HARVEST` a mature plant; else `PASS`. Off-plot → `_step_toward`.
- **Market (sells first):** `SELL` each sellable shed product, but skip melon when its `price/base < sell_throttle`; then `HIRE` up to `round(hire_target * MAX_HANDS)` at `hour==0`; then `BUY_SEED` to cover empty active plots (bounded by money and remaining slots). Clamp `market[:10]`.
- `NeuroPilotStrategy.__init__(self, genome=None)` stores `MLP.from_genome(genome or DEFAULT_GENOME, N_FEATURES, H1, N_KNOBS)`; `act(state)` = `controller(decode_knobs(self.mlp.forward(features(state))), state)`.
Provide `STRATEGY = NeuroPilotStrategy` at module end.

- [ ] **Step 4: Run helper tests** — PASS. Then the **no-crash gate**: `ROBRICULTURE_STRICT=1 pytest tests/test_no_crash.py -q` (foreground; ~3 min) → neuropilot survives full games under strict mode with the random default genome.

- [ ] **Step 5: Commit** — `git commit -m "feat(neuropilot): knob controller + playable crop/hire/sell agent (#64)"`

---

### Task 4: Complete the action vocabulary — livestock + fertilizer

Extend `controller` so knobs can also drive land purchase, pasture building, animal placement, feeding/harvest/collect, and fertilizer — so evolution can reach the winning comp. Written fresh; the sim mechanics (build→place→feed order; `COLLECT_FERTILIZER`; `FERTILIZE` is crop-only) are cross-checked against `meta_bot.animal_chore` as a correctness reference (no import).

**Files:** Modify `strategies/neuropilot.py`; Test `tests/test_neuropilot.py`.

**Interfaces:**
- Consumes: everything from Task 3 + `kaggisim.actions` builders.
- Produces: `ANIMAL_TILES` (the NE-cows/SW-sheep layout, re-declared by value); pure helpers `_animal_chore(tile_pos, kind, pos, tiles, inv, shed, unlocked) -> list | None` and `_livestock_market_orders(knobs, state, market_len) -> list` (BUY_LAND paced by `livestock_pace`; BUY_ANIMAL toward `round(herd_target_scale*(N_COW+N_SHEEP))`, cows before sheep, gated on land + a `capital_reserve`-scaled money floor; lowest market priority). `controller` now assigns the last `round(livestock_labor_share*len(workers))` workers to livestock beats and appends livestock market orders after crops/sells/hire, still `market[:10]` with sells first.

- [ ] **Step 1: Write the failing tests**

```python
def test_animal_chore_builds_pasture_on_empty_unlocked_tile():
    tiles = [[None]*10 for _ in range(10)]
    a = np._animal_chore((5, 0), "COW", [5, 0], tiles, {}, {}, ["NW", "NE"])
    assert a == ["BUILD_PASTURE"]

def test_animal_chore_none_when_land_locked():
    tiles = [[None]*10 for _ in range(10)]
    assert np._animal_chore((5, 0), "COW", [5, 0], tiles, {}, {}, ["NW"]) is None

def test_livestock_orders_buy_land_before_animals_when_pace_high():
    k = np.decode_knobs([0.5, 0.5, 1.0, 0.5, 1.0, 0.5, 0.0, 0.5])  # pace high, reserve low
    orders = np._livestock_market_orders(k, _obs(money=100000, unlocked=("NW",)), 0)
    assert ["BUY_LAND"] in orders

def test_controller_still_sells_first_with_livestock_active():
    k = np.decode_knobs([0.0, 0.5, 1.0, 1.0, 1.0, 0.5, 0.0, 0.5])
    a = np.controller(k, _obs(hour=0, money=100000, shed={"MELON": 8}, unlocked=("NW", "NE", "SW")))
    sells = [i for i, o in enumerate(a["market"]) if o[0] == "SELL"]
    non = [i for i, o in enumerate(a["market"]) if o[0] != "SELL"]
    assert not non or not sells or max(sells) < min(non)
```

- [ ] **Step 2: Run to verify fail** — `_animal_chore`/`_livestock_market_orders` undefined.

- [ ] **Step 3: Implement** the livestock helpers (fresh; cite the sim mechanics reference in comments) and wire them into `controller` per the Interfaces block. Keep all decisions in the pure helpers; `controller` stays a thin assembler.

- [ ] **Step 4: Verify** — helper tests PASS; **no-crash gate** green in the foreground (`ROBRICULTURE_STRICT=1 pytest tests/test_no_crash.py -q`) — neuropilot stands up under full games with livestock reachable.

- [ ] **Step 5: Commit** — `git commit -m "feat(neuropilot): livestock + fertilizer vocabulary in the controller (#64)"`

---

### Task 5: Full CI gate + coverage

**Files:** possibly Modify `strategies/neuropilot.py` (a single `# pragma: no cover` only if a genuine integration entrypoint is the gap); Test `tests/test_neuropilot.py` (fill any helper coverage gap).

- [ ] **Step 1: Run the full CI gate** — from repo root, venv active:
```bash
pytest -q --cov --cov-branch --cov-report=term-missing
```
Expected: all PASS; line ≥85%, branch ≥65%. Report numbers verbatim.
- [ ] **Step 2:** If a pure helper is under-covered, add a focused unit test for the missing branch (never `# pragma` a helper). Only an integration entrypoint (`act`'s live-loop wiring, if any) may take `# pragma: no cover` at the `def`.
- [ ] **Step 3: Commit** any coverage additions — `git commit -m "test(neuropilot): cover controller/helper branches to CI gate (#64)"`

---

## Self-Review

**Spec coverage:**
- `features(state)->list[float]`, fixed length, normalized, never-raises → Task 1. ✅
- Pure-Python MLP, genome interface (`genome_size`/`random_genome`/`MLP.from_genome`/`forward`/`DEFAULT_GENOME`) → Task 2. ✅
- Fresh knob controller, low-level primitives only, full legal vocabulary, sells-first, market[:10] → Tasks 3 (crop/hire/sell) + 4 (livestock/fertilizer). ✅
- `act()` under fail-safe; `NeuroPilotStrategy(genome=None)` frozen interface → Task 3. ✅
- No `__init__.py` edit; `benchmark=False`; stdlib-only → Global Constraints + Task 3 test `test_strategy_registered_as_contender`. ✅
- No-crash gate + full CI (line≥85/branch≥65) → Tasks 3/4 (no-crash) + Task 5 (coverage). ✅
- Phase-2-frozen names → listed in Global Constraints, produced across Tasks 1-3. ✅

**Placeholder scan:** Tasks 1-2 give complete code. Tasks 3-4 give complete tests + full interface signatures + concrete per-branch controller logic described imperatively with the exact primitives to call; the controller bodies are specified at the helper level (each helper's inputs/outputs/behavior are pinned by its tests) rather than transcribed line-by-line, because the controller is new code whose exact assembly the implementer writes against the tests — this is the intended "build to the tests + interface" shape, not a vague placeholder. `N_FEATURES=18` is provisional and self-correcting (Task 1 Step 4 pins it to the real count).

**Type consistency:** `features→list[float]` feeds `MLP.forward(features)->list[float]` (len `N_KNOBS`) feeds `decode_knobs->Knobs` feeds `controller(knobs,state)->dict`. `genome_size`/`random_genome`/`from_genome` share `(n_in,h1,n_out)` ordering. `DEFAULT_GENOME` length = `genome_size(N_FEATURES,H1,N_KNOBS)`. Consistent.

**Note (Phase-1 scope):** random-weight `neuropilot` is expected to play *weakly but legally*. Strength is Phase 2 (evolution). Do not tune the controller for strength.
