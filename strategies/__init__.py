"""Strategy registry.

Every strategy module exposes a module-level `STRATEGY` (a Strategy subclass).
The registry lets the harness and the build script refer to strategies by a
short name. Add new strategies here.
"""

REGISTRY = {
    "lean": "strategies.lean",
    "greedy": "strategies.greedy",
    "planner": "strategies.planner",
    "capital_rush": "strategies.capital_rush",
    "market_timer": "strategies.market_timer",
}


def load(name):
    """Import a strategy module by short name and return its STRATEGY class."""
    import importlib
    if name not in REGISTRY:
        raise KeyError(f"unknown strategy {name!r}; known: {sorted(REGISTRY)}")
    mod = importlib.import_module(REGISTRY[name])
    return mod.STRATEGY
