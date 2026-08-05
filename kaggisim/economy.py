"""Game economics: the numbers that drive every decision.

These tables are transcribed from the competition's "How to Play" spec. They are
the ground truth our ROI models build on. Verify them against the installed sim
source (kaggle_environments/envs/kaggriculture/kaggriculture.py) before trusting
them for tuning — see ADR-0002.
"""

from __future__ import annotations

# --- Simulation configuration defaults (env.configuration knobs) ---
CONFIG_DEFAULTS = {
    "episodeSteps": 720,          # 24 turns/day * 30 days
    "boardSize": 10,             # four 5x5 quadrants
    "startingMoney": 3000,
    "maxMarketOrdersPerTurn": 10,
    "turnsPerDay": 24,
    "shedCapacity": 100,          # non-seed items; overflow discarded
    "weedSpawnChance": 0.005,
    "townShopUnlockInterval": 3,  # days between shop unlocks
    "townShopSellInterval": 4,    # turns between shop consumption ticks
    "townCenterSellInterval": 12,
}

LAND_COSTS = [1000, 2000, 4000]   # cost of each successive quadrant

# --- Crops ---
# seed_cost, base_price, first_yield_day, max_yield_day, ongoing?, max_yield
#   (max_yield is the fertilized cap; unfertilized cap in comment where different)
CROPS = {
    "WHEAT":      {"seed": 10,  "base": 25,  "first": 2,  "max_day": 4,  "ongoing": False, "max_yield": 6},   # 4 unfert
    "CARROT":     {"seed": 20,  "base": 35,  "first": 2,  "max_day": 3,  "ongoing": False, "max_yield": 4},   # 3 unfert
    "TOMATO":     {"seed": 50,  "base": 60,  "first": 8,  "max_day": 11, "ongoing": True,  "max_yield": 4},   # 4 scheduled
    "STRAWBERRY": {"seed": 100, "base": 120, "first": 10, "max_day": 16, "ongoing": True,  "max_yield": 4},
    "MELON":      {"seed": 80,  "base": 250, "first": 10, "max_day": 10, "ongoing": False, "max_yield": 6},
}

# --- Animals ---
# cost, product, product_base_price, first_yield_day, yield_interval_days,
#   max_held, structure needed
ANIMALS = {
    "GOOSE": {"cost": 300, "product": "EGG",  "base": 50,  "first": 4, "interval": 1, "max_held": 4, "structure": "COOP"},
    "COW":   {"cost": 400, "product": "MILK", "base": 160, "first": 8, "interval": 2, "max_held": 6, "structure": "PASTURE"},
    "SHEEP": {"cost": 500, "product": "WOOL", "base": 200, "first": 6, "interval": 3, "max_held": 6, "structure": "PASTURE"},
}

# --- Market price curve parameters ---
# price(inv) = base + sign * amp * f(|inv - I0|); floored at $1.
# base, I0, T (throughput anchor), below_func/target, above_func/target
MARKET_PARAMS = {
    "WHEAT":      {"base": 25,  "I0": 10000, "T": 400, "below_func": "sqrt",   "below_target": 0.80, "above_func": "log",    "above_target": 0.20},
    "CARROT":     {"base": 35,  "I0": 10000, "T": 450, "below_func": "log",    "below_target": 0.20, "above_func": "sqrt",   "above_target": 0.70},
    "TOMATO":     {"base": 60,  "I0": 10000, "T": 200, "below_func": "linear", "below_target": 0.40, "above_func": "sqrt",   "above_target": 0.60},
    "STRAWBERRY": {"base": 120, "I0": 10000, "T": 100, "below_func": "sqrt",   "below_target": 0.70, "above_func": "linear", "above_target": 1.60},
    "MELON":      {"base": 250, "I0": 10000, "T": 300, "below_func": "log",    "below_target": 0.20, "above_func": "sq",     "above_target": 3.60},
    "EGG":        {"base": 50,  "I0": 10000, "T": 332, "below_func": "linear", "below_target": 0.40, "above_func": "log",    "above_target": 0.20},
    "MILK":       {"base": 160, "I0": 10000, "T": 122, "below_func": "sqrt",   "below_target": 0.60, "above_func": "linear", "above_target": 1.60},
    "WOOL":       {"base": 200, "I0": 10000, "T": 105, "below_func": "log",    "below_target": 0.20, "above_func": "sq",     "above_target": 3.20},
    "FERTILIZER": {"base": 100, "I0": 10000, "T": 200, "below_func": "linear", "below_target": 0.40, "above_func": "linear", "above_target": 0.40},
}

# Town shops and what they demand (drives which products stay profitable).
SHOP_DEMAND = {
    "BAKERY":         ["EGG", "WHEAT"],
    "PIZZA_SHOP":     ["MILK", "TOMATO", "WHEAT"],
    "BRUNCH_SPOT":    ["EGG", "WHEAT", "STRAWBERRY"],
    "YARN_STORE":     ["WOOL"],            # 2x
    "ICE_CREAM_SHOP": ["STRAWBERRY", "MILK", "WHEAT"],
    "PET_CAFE":       ["CARROT"],          # 2x
    "SMOOTHIE_SHOP":  ["STRAWBERRY", "MILK"],
    "FARMERS_MARKET": ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY"],
}


def base_price(item: str) -> int:
    p = MARKET_PARAMS.get(item)
    return p["base"] if p else 0


def naive_crop_roi(crop: str) -> float:
    """Very rough profit-per-tile-per-day at base prices, no fertilizer.

    Placeholder to be replaced by a proper model that accounts for the price
    curve, watering schedule, labor cost, and town demand (ADR-0002). Do not
    tune against this number yet.
    """
    c = CROPS[crop]
    # crude: (max_yield * base_price - seed_cost) / days_occupied
    days = max(c["max_day"], 1)
    return (c["max_yield"] * c["base"] - c["seed"]) / days
