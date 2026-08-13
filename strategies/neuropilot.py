"""neuropilot — NN-guided agent (neuroevolution Phase 1, ADR-0008, #64).

A small pure-Python MLP → knob controller; stdlib-only, fresh controller.
"""
from __future__ import annotations
import collections, math, random
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

N_FEATURES = 20
NEUTRAL_FEATURES = [0.5] * N_FEATURES

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


# --- Knob decode (Task 3, #64) -----------------------------------------------
#
# `Knobs` names the MLP's 8 raw sigmoid outputs positionally; `decode_knobs` is
# an identity mapping (every output is already in [0,1]) — the *meaning* of
# each knob (e.g. hire_target as a fraction of MAX_HANDS) is interpreted by the
# controller below, not here. `livestock_pace`, `livestock_labor_share`,
# `herd_target_scale` and `fertilize_pref` are unused until Task 4 (livestock).

Knobs = collections.namedtuple(
    "Knobs",
    [
        "sell_throttle", "hire_target", "livestock_pace", "livestock_labor_share",
        "herd_target_scale", "fertilize_pref", "capital_reserve", "crop_mix",
    ],
)


def decode_knobs(raw: list[float]) -> Knobs:
    """Map the MLP's raw output vector positionally onto named, unit-range knobs."""
    vals = [_clamp01(v) for v in raw]
    if len(vals) < N_KNOBS:
        vals += [0.5] * (N_KNOBS - len(vals))
    return Knobs(*vals[:N_KNOBS])


# --- Minimal controller: crop farming + selling + hiring + seed (Task 3) ----
#
# Independent of every other strategy module (ADR-0008) — built only from
# kaggisim.state / kaggisim.economy / kaggisim.actions primitives, plus this
# module's own tiny helpers. Constants that mirror another strategy's layout
# (e.g. the NW crop-plot crew) are re-declared here BY VALUE, not imported.

#: The champion's 10-tile NW crew (all x,y <= 4, always-unlocked land), nearest
#: tiles first. Re-declared by value from `wide_hands.PLOTS` / `meta_bot.MELON_PLOTS`
#: per ADR-0008 — neuropilot must not import another strategy module.
CROP_PLOTS = [
    (4, 4),                  # worker 0 (farmer, shed-adjacent)
    (3, 4), (4, 3),
    (2, 4), (3, 3), (4, 2),
    (1, 4), (2, 3), (3, 2), (4, 1),
]

#: A crop must reach first yield with at least this many days to spare before
#: the final day, or planting it just strands the tile (and its seed cost).
SELL_MARGIN_DAYS = 1

#: Everything the market will actually buy from us.
_SELLABLE = frozenset(economy.MARKET_PARAMS)

#: The two crops the crop crew grows: melon (high value, slow) or wheat (cheap,
#: fast), chosen per-turn by `_crop_for` from the `crop_mix` knob.
_MELON, _WHEAT = "MELON", "WHEAT"


def _step_toward(pos, target) -> list:
    """One MOVE (x first, then y) stepping `pos` toward `target`, else PASS.

    Mirrors the sim's coordinate convention: tiles are `tiles[y][x]`; farmer /
    hand positions are `[x, y]`; EAST/WEST move x, NORTH/SOUTH move y (NORTH
    decreases y, SOUTH increases it).
    """
    px, py = pos[0], pos[1]
    tx, ty = target[0], target[1]
    if px < tx:
        return ["EAST"]
    if px > tx:
        return ["WEST"]
    if py < ty:
        return ["SOUTH"]
    if py > ty:
        return ["NORTH"]
    return ["PASS"]


def _on(pos, target) -> bool:
    return pos[0] == target[0] and pos[1] == target[1]


def _tile_at(tiles, plot):
    x, y = plot
    return tiles[y][x]


def _is_live_plant(tile) -> bool:
    return isinstance(tile, dict) and tile.get("kind") == "PLANT"


def _plantable(crop: str, day: int, season_days: int = SEASON_DAYS) -> bool:
    """Can `crop`, planted on `day`, reach first yield with a day to sell before
    the season ends?"""
    c = economy.CROPS[crop]
    final_day = season_days - 1
    return day + c["first"] + SELL_MARGIN_DAYS <= final_day


def _harvest_ready(tile, day: int) -> bool:
    """True when a standing plant holds yield and has reached first-yield age."""
    crop = tile.get("crop")
    c = economy.CROPS.get(crop)
    if not c or tile.get("yield_units", 0) <= 0:
        return False
    return day - tile.get("planted_day", day) >= c["first"]


def _crop_for(knobs: Knobs, day: int):
    """The crop to grow this turn: melon when `crop_mix` favors it and it can
    still mature; otherwise wheat; `None` once neither can mature (tail end of
    the season)."""
    if knobs.crop_mix >= 0.5 and _plantable(_MELON, day):
        return _MELON
    if _plantable(_WHEAT, day):
        return _WHEAT
    return None


def _plot_action(tile, day: int, crop):
    """The action for a worker standing on its plot: dig a weed; plant `crop` on
    an empty plot; water an unwatered live plant; harvest a mature one; else
    pass. Seed-availability is enforced by the caller (`controller`)."""
    if isinstance(tile, dict) and tile.get("kind") == "WEED":
        return ["DIG"]
    if tile is None:
        return ["PLANT", crop] if crop is not None else ["PASS"]
    if _is_live_plant(tile):
        if _harvest_ready(tile, day):
            return ["HARVEST"]
        if not tile.get("watered_today", False):
            return ["WATER"]
    return ["PASS"]


def _sell_orders(shed: dict, prices: dict, sell_throttle: float) -> list:
    """SELL orders liquidating the shed, deterministic (sorted by item).

    Melon is held back when its price has slumped below `sell_throttle` of its
    base price (a low `sell_throttle` sells freely; a high one waits for a
    better price) — every other sellable product clears in full.
    """
    orders = []
    for item in sorted(shed):
        n = shed.get(item, 0)
        if item not in _SELLABLE or n <= 0:
            continue
        if item == _MELON:
            base = economy.base_price(_MELON) or 1.0
            ratio = prices.get(_MELON, base) / base
            if ratio < sell_throttle:
                continue
        orders.append(["SELL", item, n])
    return orders


def controller(knobs: Knobs, state) -> dict:
    """A legal `{"farmer", "hands", "market"}` turn from decoded knobs + state.

    Crop crew: one worker per `CROP_PLOTS` tile (farmer first, then hands),
    navigating to its plot and running the dig/plant/water/harvest loop there.
    Market: sells lead (never displaced by the 10-order cap), then hires up to
    `hire_target * MAX_HANDS` new hands (mornings only), then restocks seed for
    empty active plots, bounded by money and the remaining order slots.
    """
    player = state.get("player", 0)
    me = state["farms"][player]
    private = state.get("private", {})
    day = state.get("day", 0)
    hour = state.get("hour", 0)
    money = me.get("money", 0)
    tiles = me["tiles"]
    hands = me.get("hands", []) or []
    seeds = private.get("seeds", {})
    shed = private.get("shed", {})
    prices = state.get("market", {}).get("prices", {})

    crop = _crop_for(knobs, day)

    # --- One action per worker: navigate to its crop plot, then farm it. ---
    positions = [me["farmer"], *hands]
    planted_this_turn: dict = {}
    actions = []
    for i, pos in enumerate(positions):
        plot = CROP_PLOTS[i] if i < len(CROP_PLOTS) else CROP_PLOTS[-1]
        if not _on(pos, plot):
            actions.append(_step_toward(pos, plot))
            continue
        tile = _tile_at(tiles, plot)
        action = _plot_action(tile, day, crop)
        if action[0] == "PLANT":
            # Only plant as many of `crop` this turn as we hold seed for, or the
            # sim's atomic-plant rule voids every plant of the crop at once.
            planted_crop = action[1]
            if planted_this_turn.get(planted_crop, 0) < seeds.get(planted_crop, 0):
                planted_this_turn[planted_crop] = planted_this_turn.get(planted_crop, 0) + 1
            else:
                action = ["WATER"] if _is_live_plant(tile) else ["PASS"]
        actions.append(action)

    farmer_action = actions[0]
    hand_actions = actions[1:]

    # --- Market: sells first, then hire, then seed — sells are never truncated
    # by the 10-order cap. ---
    market: list = _sell_orders(shed, prices, knobs.sell_throttle)

    if hour == 0:
        n_hire = max(0, round(knobs.hire_target * MAX_HANDS))
        market.extend([["HIRE"]] * n_hire)

    if crop is not None and len(market) < 10:
        active_plots = min(len(CROP_PLOTS), len(positions))
        empty_active = sum(
            1 for plot in CROP_PLOTS[:active_plots] if _tile_at(tiles, plot) is None
        )
        want_seed = max(0, empty_active - seeds.get(crop, 0))
        if want_seed > 0:
            seed_cost = economy.CROPS[crop]["seed"]
            affordable = int(money // seed_cost) if seed_cost > 0 else want_seed
            buy = min(want_seed, affordable, 10 - len(market))
            if buy > 0:
                market.append(["BUY_SEED", crop, buy])

    return {"farmer": farmer_action, "hands": hand_actions, "market": market[:10]}


class NeuroPilotStrategy(Strategy):
    """The NN-driven agent: MLP -> knobs -> controller. Crop/sell/hire/seed only
    (livestock is Task 4) — weak by design (random default weights), but legal
    and crash-free under `ROBRICULTURE_STRICT=1` (the Phase-1 milestone, #64)."""

    name = "neuropilot"
    benchmark = False

    def __init__(self, genome=None):
        self.mlp = MLP.from_genome(genome or DEFAULT_GENOME, N_FEATURES, H1, N_KNOBS)

    def act(self, state) -> dict:
        knobs = decode_knobs(self.mlp.forward(features(state)))
        return controller(knobs, state)


STRATEGY = NeuroPilotStrategy
