"""neuropilot — NN-guided agent (neuroevolution Phase 1, ADR-0008, #64).

A small pure-Python MLP → knob controller; stdlib-only, fresh controller.
"""
from __future__ import annotations
import collections, json, math, os, random
from kaggisim import actions as acts
from kaggisim import economy
from kaggisim.strategy import Strategy

TURNS_PER_DAY = economy.CONFIG_DEFAULTS["turnsPerDay"]
SEASON_DAYS = economy.CONFIG_DEFAULTS["episodeSteps"] // TURNS_PER_DAY
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


#: The evolved champion genome ships INSIDE the strategies package so it travels in
#: the submission tarball — build/package.py copies strategies/ (and kaggisim/), NOT
#: harness/. Without this, a submitted neuropilot would find no genome at eval time
#: and silently fall back to random weights. The harness path below is where the
#: evolution loop writes during dev; promoting a champion = copy it to _LOCAL_GENOME.
_LOCAL_GENOME = os.path.join(os.path.dirname(__file__), "champion_genome.json")
_GENOME_ARTIFACT = os.path.join(os.path.dirname(os.path.dirname(__file__)), "harness", "genomes", "champion_genome.json")


def load_champion_genome(path=_GENOME_ARTIFACT):
    """The evolved champion genome if present and shape-correct, else None (never raises)."""
    try:
        with open(path) as fh:
            g = json.load(fh)["genome"]
        return g if len(g) == genome_size(N_FEATURES, H1, N_KNOBS) else None
    except Exception:
        return None


# Prefer the package-local champion (travels in the tarball); fall back to the
# harness artifact (in-repo dev), then to the seeded-random default.
_loaded = load_champion_genome(_LOCAL_GENOME) or load_champion_genome()
DEFAULT_GENOME = _loaded if _loaded is not None else random_genome(N_FEATURES, H1, N_KNOBS, seed=20260812)


# --- Knob decode (Task 3, #64) -----------------------------------------------
#
# `Knobs` names the MLP's 8 raw sigmoid outputs positionally; `decode_knobs` is
# an identity mapping (every output is already in [0,1]) — the *meaning* of
# each knob (e.g. hire_target as a fraction of MAX_HANDS) is interpreted by the
# controller below, not here. `livestock_pace`, `livestock_labor_share`,
# `herd_target_scale`, `capital_reserve` and `fertilize_pref` drive the
# livestock + fertilizer vocabulary (Task 4, below).

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


# --- Livestock + fertilizer (Task 4, #64) ------------------------------------
#
# Fresh code, built only from kaggisim.actions / economy / this module's own
# helpers (no strategy imports, per ADR-0008). The sim mechanics below (unlock
# order, build->place->feed order, COLLECT_FERTILIZER, FERTILIZE being
# crop-only) are cross-checked against `meta_bot.animal_chore` /
# `meta_bot.livestock_action` (read for reference, never imported) and against
# the installed sim source (kaggle_environments/envs/kaggriculture/kaggriculture.py).

#: The reachable comp's layout: a compact NE 3x3 cow block and an SW 4-tile
#: sheep row — re-declared BY VALUE from `meta_bot.ANIMAL_TILES` (ADR-0008
#: forbids importing another strategy module).
ANIMAL_TILES: list = [
    ((5, 0), "COW"), ((6, 0), "COW"), ((7, 0), "COW"),
    ((5, 1), "COW"), ((6, 1), "COW"), ((7, 1), "COW"),
    ((5, 2), "COW"), ((6, 2), "COW"), ((7, 2), "COW"),
    ((0, 5), "SHEEP"), ((1, 5), "SHEEP"), ((2, 5), "SHEEP"), ((3, 5), "SHEEP"),
]
assert sum(1 for _, k in ANIMAL_TILES if k == "COW") == N_COW
assert sum(1 for _, k in ANIMAL_TILES if k == "SHEEP") == N_SHEEP

#: The one shed-access tile the crop crew also occupies (CROP_PLOTS[0]) — the
#: only corner every worker can reach a PICKUP/DROP from.
SHED_TILE = (4, 4)

#: A knob-scaled money floor for livestock spend, sized against the season's
#: starting capital (mirrors `meta_bot.MELON_RESERVE`'s role, but dialed by
#: `capital_reserve` instead of fixed).
_MONEY_FLOOR_BASE = economy.CONFIG_DEFAULTS["startingMoney"]  # 3000


def _needs_quadrant(kind: str) -> str:
    """The land quadrant an animal of `kind` is placed in (cows NE, sheep SW)."""
    return "NE" if kind == "COW" else "SW"


def _is_animal(tile) -> bool:
    return isinstance(tile, dict) and "animal" in tile


def _animal_chore(tile_pos, kind: str, pos, tiles, inv: dict, shed: dict, unlocked):
    """This turn's chore for ONE animal tile, or `None` when it wants nothing.

    A pure state machine over one tile: build the pasture, fetch the bought
    animal from the shed and place it, then keep it fed / harvested /
    collected / cared. Feed leads maintenance — an animal escapes after two
    unfed days, so it is checked before harvest/collect/care. Mirrors
    `meta_bot.animal_chore` (the correctness reference for this state
    machine's shape; not imported).
    """
    if _needs_quadrant(kind) not in unlocked:
        return None  # its land isn't bought yet — nothing buildable here.
    tile = _tile_at(tiles, tile_pos)
    on = _on(pos, tile_pos)

    # --- Setup: pasture -> animal in hand -> placed. ---
    if not _is_animal(tile):
        if inv.get(kind, 0) > 0:
            return acts.place(kind) if on else _step_toward(pos, tile_pos)
        if tile is None:
            return acts.build_pasture() if on else _step_toward(pos, tile_pos)
        if shed.get(kind, 0) > 0:  # empty pasture; fetch the bought animal.
            return acts.pickup(kind, 1) if _on(pos, SHED_TILE) else _step_toward(pos, SHED_TILE)
        return None  # not bought yet; the market will buy it.

    # --- Maintain the placed animal. ---
    if not tile.get("fed_today", False) and inv.get("WHEAT", 0) > 0:
        return acts.feed() if on else _step_toward(pos, tile_pos)
    if tile.get("yield_units", 0) > 0:
        return acts.harvest() if on else _step_toward(pos, tile_pos)
    if tile.get("fertilizer_available", False):
        return acts.collect_fertilizer() if on else _step_toward(pos, tile_pos)
    if not tile.get("cared_today", False) and on:
        return acts.care()
    return None


def _assign_beats(n_livestock: int) -> list:
    """Split `ANIMAL_TILES` into `n_livestock` contiguous beats, as even as
    possible — `[]` when no worker is on livestock duty this turn."""
    if n_livestock <= 0:
        return []
    n = len(ANIMAL_TILES)
    base, rem = divmod(n, n_livestock)
    beats, idx = [], 0
    for i in range(n_livestock):
        size = base + (1 if i < rem else 0)
        beats.append(ANIMAL_TILES[idx: idx + size])
        idx += size
    return beats


def _livestock_worker_action(pos, beat: list, tiles, inv: dict, shed: dict, unlocked) -> list:
    """One livestock worker's action this turn (never `None`).

    Feed leads (survival-critical): fetch WHEAT from the shed for a hungry
    animal in the beat before anything else, then fall through to the first
    tile with an outstanding chore (`_animal_chore`); idle toward the beat
    when nothing else applies.
    """
    hungry = [tp for tp, _ in beat if _is_animal(_tile_at(tiles, tp))
              and not _tile_at(tiles, tp).get("fed_today", False)]
    if hungry:
        if inv.get("WHEAT", 0) > 0:
            tp = hungry[0]
            return acts.feed() if _on(pos, tp) else _step_toward(pos, tp)
        if shed.get("WHEAT", 0) > 0:
            if _on(pos, SHED_TILE):
                return acts.pickup("WHEAT", min(shed["WHEAT"], len(hungry)))
            return _step_toward(pos, SHED_TILE)
    for tile_pos, kind in beat:
        chore = _animal_chore(tile_pos, kind, pos, tiles, inv, shed, unlocked)
        if chore is not None:
            return chore
    if beat:
        return _step_toward(pos, beat[0][0])
    return acts.pass_()


def _land_order(unlocked, money: float, pace: float) -> list:
    """At most one `BUY_LAND` this turn, paced by `livestock_pace`.

    Below a pace of 0.5, land is never pursued; above it, the required money
    buffer above the price shrinks toward 0 as pace climbs to 1 (buy as soon
    as affordable). Follows the sim's fixed NE -> SW unlock order
    (`kaggisim.economy.LAND_COSTS`), capped at those two extra quadrants —
    no `ANIMAL_TILES` tile lives in the $4000 SE quadrant, so it's never
    worth buying (mirrors `meta_bot.land_orders`' `n_extra >= 2` guard,
    by value, not import). `[]` once NE and SW are both owned.
    """
    n_extra = len(unlocked) - 1  # NW is always unlocked; 0 => only NW owned
    if n_extra < 0 or n_extra >= 2 or pace < 0.5:
        return []  # already own NE and SW — never reach for the $4000 SE
    price = economy.LAND_COSTS[n_extra]
    buffer = (1.0 - pace) * price * 4
    if money >= price + buffer:
        return [["BUY_LAND"]]
    return []


def _herd_targets(knobs: Knobs) -> tuple:
    """(cow_target, sheep_target) toward `herd_target_scale` of the full
    13-animal comp, cows filled first, each capped at its species maximum."""
    total = max(0, round(knobs.herd_target_scale * (N_COW + N_SHEEP)))
    cow = min(N_COW, total)
    sheep = min(N_SHEEP, max(0, total - N_COW))
    return cow, sheep


def _count_existing(kind: str, tiles, shed: dict, inventories: list) -> int:
    """How many animals of `kind` are already accounted for — placed on a
    tile, waiting in the shed, or held in a worker's inventory."""
    placed = sum(
        1 for row in tiles for t in row
        if isinstance(t, dict) and t.get("animal") == kind
    )
    in_shed = shed.get(kind, 0)
    in_inv = sum(inv.get(kind, 0) for inv in inventories)
    return placed + in_shed + in_inv


def _animal_orders(knobs: Knobs, tiles, shed: dict, inventories: list,
                    money: float, unlocked, cap: int) -> list:
    """`BUY_ANIMAL` orders toward the herd targets, cows before sheep.

    Gated on the animal's land quadrant being unlocked and on money staying
    above a `capital_reserve`-scaled floor per unit; capped at `cap` orders
    (the caller passes the remaining market slots) so these lowest-priority
    orders never displace a sell. Mirrors `meta_bot.animal_buy_orders`.
    """
    cow_target, sheep_target = _herd_targets(knobs)
    floor = knobs.capital_reserve * _MONEY_FLOOR_BASE
    orders: list = []
    budget = money
    for kind, target in (("COW", cow_target), ("SHEEP", sheep_target)):
        if _needs_quadrant(kind) not in unlocked:
            continue
        have = _count_existing(kind, tiles, shed, inventories)
        for _ in range(max(0, target - have)):
            if len(orders) >= cap:
                return orders
            cost = economy.ANIMALS[kind]["cost"]
            if budget < cost + floor:
                break
            orders.append(["BUY_ANIMAL", kind, 1])
            budget -= cost
    return orders


def _wants_fertilizer(tile, day: int) -> bool:
    """True when `tile` is a live plant not already fertilizer-covered for
    `day` (a fresh unit would otherwise be wasted). FERTILIZE is crop-only —
    this mirrors the sim's own `kind == "PLANT"` gate."""
    if not _is_live_plant(tile):
        return False
    return tile.get("fertilized_until_day", -1) < day


def _fertilize_or_fetch(tile, day: int, inv: dict, shed: dict):
    """The fertilizer action for the shed-adjacent farmer plot (CROP_PLOTS[0],
    which doubles as a shed-access tile), or `None`.

    Applies straight from inventory when a unit is held; otherwise `PICKUP`
    one from the shed (legal here only because this plot is shed-adjacent).
    Mirrors `fertilized_hands.fertilize_or_fetch`.
    """
    if not _wants_fertilizer(tile, day):
        return None
    if inv.get("FERTILIZER", 0) > 0:
        return acts.fertilize()
    if shed.get("FERTILIZER", 0) > 0:
        return acts.pickup("FERTILIZER", 1)
    return None


def _fertilizer_buy_order(knobs: Knobs, state, cap: int) -> list:
    """A single fallback `BUY_PRODUCT FERTILIZER` for the farmer's crop plot,
    or `[]`.

    Gated on `fertilize_pref` and fires only when the plot's crop actually
    wants fertilizer *and* neither the shed nor the farmer's own inventory
    already holds a free unit — the herd's `COLLECT_FERTILIZER` byproduct is
    always preferred over spending money. Mirrors `meta_bot.fertilizer_orders`
    / `fertilized_hands.should_buy_fertilizer`.
    """
    if cap <= 0 or knobs.fertilize_pref < 0.5:
        return []
    player = state.get("player", 0)
    me = state["farms"][player]
    private = state.get("private", {})
    day = state.get("day", 0)
    tiles = me["tiles"]
    shed = private.get("shed", {})
    inventories = private.get("inventories", [])
    farmer_inv = inventories[0] if inventories else {}
    tile = _tile_at(tiles, CROP_PLOTS[0])
    if not _wants_fertilizer(tile, day):
        return []
    if shed.get("FERTILIZER", 0) > 0 or farmer_inv.get("FERTILIZER", 0) > 0:
        return []
    price = economy.base_price("FERTILIZER") or 1.0
    if me.get("money", 0) < price:
        return []
    return [["BUY_PRODUCT", "FERTILIZER", 1]]


def _livestock_market_orders(knobs: Knobs, state, market_len: int) -> list:
    """Livestock + fertilizer market orders, lowest priority.

    `BUY_LAND` (paced by `livestock_pace`), then `BUY_ANIMAL` toward
    `round(herd_target_scale * (N_COW + N_SHEEP))` (cows before sheep), then a
    fallback fertilizer buy — capped at the market slots the caller has left
    (`10 - market_len`) so these never displace a sell, hire or seed order.
    """
    cap = max(0, 10 - market_len)
    if cap <= 0:
        return []
    player = state.get("player", 0)
    me = state["farms"][player]
    private = state.get("private", {})
    money = me.get("money", 0)
    tiles = me["tiles"]
    unlocked = me.get("unlocked_quadrants", ["NW"])
    shed = private.get("shed", {})
    inventories = private.get("inventories", [])

    orders: list = _land_order(unlocked, money, knobs.livestock_pace)[:cap]
    if len(orders) < cap:
        orders += _animal_orders(
            knobs, tiles, shed, inventories, money, unlocked, cap - len(orders)
        )
    if len(orders) < cap:
        orders += _fertilizer_buy_order(knobs, state, cap - len(orders))
    return orders[:cap]


def controller(knobs: Knobs, state) -> dict:
    """A legal `{"farmer", "hands", "market"}` turn from decoded knobs + state.

    Worker roles: the last `round(livestock_labor_share * len(workers))`
    workers (farmer counted first, so it's the last hands that peel off) tend
    the herd in `ANIMAL_TILES` beats; the rest farm `CROP_PLOTS`, navigating to
    their plot and running the dig/plant/water/fertilize/harvest loop there.
    Market: sells lead (never displaced by the 10-order cap), then hires up to
    `hire_target * MAX_HANDS` new hands (mornings only), then restocks seed for
    empty active crop plots, then livestock/fertilizer market orders (lowest
    priority) fill whatever slots remain.
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
    unlocked = me.get("unlocked_quadrants", ["NW"])
    inventories = private.get("inventories", [])

    crop = _crop_for(knobs, day)

    # --- Worker roles: the last `livestock_labor_share` fraction of workers
    # (farmer first, then hands) tend the herd; the rest farm crops. ---
    positions = [me["farmer"], *hands]
    n_workers = len(positions)
    n_livestock = min(n_workers, max(0, round(knobs.livestock_labor_share * n_workers)))
    n_crop = n_workers - n_livestock
    beats = _assign_beats(n_livestock)

    # --- One action per worker: navigate to its plot/beat, then work it. ---
    planted_this_turn: dict = {}
    actions = []
    for i, pos in enumerate(positions):
        inv = inventories[i] if i < len(inventories) else {}
        if i < n_crop:
            plot = CROP_PLOTS[i] if i < len(CROP_PLOTS) else CROP_PLOTS[-1]
            if not _on(pos, plot):
                actions.append(_step_toward(pos, plot))
                continue
            tile = _tile_at(tiles, plot)
            action = None
            if i == 0 and knobs.fertilize_pref >= 0.5:
                # Only the shed-adjacent farmer plot (CROP_PLOTS[0]) can
                # PICKUP + FERTILIZE without leaving its tile.
                action = _fertilize_or_fetch(tile, day, inv, shed)
            if action is None:
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
        else:
            beat = beats[i - n_crop] if (i - n_crop) < len(beats) else []
            actions.append(_livestock_worker_action(pos, beat, tiles, inv, shed, unlocked))

    farmer_action = actions[0]
    hand_actions = actions[1:]

    # --- Market: sells first, then hire, then seed, then livestock/fertilizer
    # (lowest priority) — sells are never truncated by the 10-order cap. ---
    market: list = _sell_orders(shed, prices, knobs.sell_throttle)

    if hour == 0:
        n_hire = max(0, round(knobs.hire_target * MAX_HANDS))
        market.extend([["HIRE"]] * n_hire)

    if crop is not None and len(market) < 10:
        active_plots = min(n_crop, len(CROP_PLOTS))
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

    if len(market) < 10:
        market.extend(_livestock_market_orders(knobs, state, len(market)))

    return {"farmer": farmer_action, "hands": hand_actions, "market": market[:10]}


class NeuroPilotStrategy(Strategy):
    """The NN-driven agent: MLP -> knobs -> controller. Full legal vocabulary —
    crop farming, selling, hiring, livestock (land/pasture/place/feed/harvest/
    collect) and fertilizer (#64) — weak by design (random default weights),
    but legal and crash-free under `ROBRICULTURE_STRICT=1` (the Phase-1
    milestone)."""

    name = "neuropilot"
    benchmark = False

    def __init__(self, genome=None):
        g = genome if genome is not None else DEFAULT_GENOME
        self.mlp = MLP.from_genome(g, N_FEATURES, H1, N_KNOBS)

    def act(self, state) -> dict:
        knobs = decode_knobs(self.mlp.forward(features(state)))
        return controller(knobs, state)


STRATEGY = NeuroPilotStrategy
