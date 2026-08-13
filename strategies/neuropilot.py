"""neuropilot — NN-guided agent (neuroevolution Phase 1, ADR-0008, #64).

A small pure-Python MLP → knob controller; stdlib-only, fresh controller.
"""
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
