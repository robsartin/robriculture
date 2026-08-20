"""Per-game production/throughput report (#95).

#95 found a ~9:1 score gap driven by *throughput*, not policy quality: our
champion peaks at 8 planted tiles on a 10x10 (four 5x5 quadrant) board while
the external competitor `pilkwang` reaches 51. This module turns the throwaway
diagnostic that found that (`production_diag.py` / `land_check.py`, both
session scratch, folded in here) into a repeatable tool, the way
`harness/genome_bench.py` made the fitness gap visible on demand (#70).

It answers, per agent per game: how many tiles/animals/hired hands it ever ran,
which quadrants it unlocked and when, when it bought land and at what money
level, what it sold and how much, and whether cash sat idle instead of being
reinvested.

Land purchases are reported as two distinct fields, deliberately not merged:
`land_purchases` (confirmed -- derived from `unlocked_quadrants` growing) and
`land_purchase_attempts` (every turn a `BUY_LAND` verb appears in the
returned action). The sim's `_do_buy_land` silently no-ops a purchase when
money is insufficient, so the verb alone is only an attempt; keeping the two
counts separate makes a rejected attempt visible instead of being counted as
a success.

Design mirrors `harness/genome_bench.py` and `harness/rounds.py`: the pure
aggregation (`summarize`) is unit-tested against synthetic logs, and every
real-game/registry/filesystem touch (`play_and_record`'s `play_fn`,
`resolve_agent`'s `discover_fn`/`build`) is an injectable seam so the wiring is
testable without spinning up `kaggle_environments`.

Usage:
    python -m harness.production_report meta_rancher wheat_hands
    python -m harness.production_report strategies/champion_genome.json pilkwang
    python -m harness.production_report meta_rancher pilkwang --seed 3
"""

from __future__ import annotations

import argparse
import collections
import inspect
import os
import sys

from harness import external_pool
from harness.evolve import genome_agent, load_genome
from harness.tournament import build_agents
from kaggisim import economy
from strategies import REGISTRY

#: One in-game day (CONFIG_DEFAULTS["turnsPerDay"]) -- the idle-money-streak
#: threshold below. Shorter flat spells are just "between purchases".
IDLE_STREAK_TURNS = economy.CONFIG_DEFAULTS["turnsPerDay"]

#: The least a flat cash pile could have bought -- the cheapest quadrant
#: (LAND_COSTS[0]). Money flat below this floor isn't "idle capital", there
#: was nothing to spend it on yet.
IDLE_MONEY_FLOOR = economy.LAND_COSTS[0]

#: Always unlocked, never bought -- see `_confirmed_land_purchases`.
FREE_QUADRANT = "NW"


# --- snapshot_turn / recorder: pure per-turn extraction, then the wrapping seam ---

def _call(fn, obs):
    """Call an agent with whatever arity it declares: `agent(obs)` (our
    `make_agent` wrapper) or `agent(obs, config)` (kaggle_environments' own
    convention, which external agents follow)."""
    try:
        n = len(inspect.signature(fn).parameters)
    except (TypeError, ValueError):
        n = 1
    return fn(obs) if n <= 1 else fn(obs, None)


def snapshot_turn(obs, action):
    """Pure: turn one (raw obs, returned action) pair into one log row.

    `obs` is the raw kaggle_environments observation for one player --
    `kaggisim.state.parse` is presently an identity transform (see
    `kaggisim/state.py`), so reading it directly here matches what a strategy
    actually sees. Never raises: a malformed obs/action is recorded as
    `{"error": ...}` instead, so instrumentation can never take down a
    benchmark game (mirrors `harness/external_pool.py`'s import-failure skip).
    """
    try:
        me = obs["farms"][obs["player"]]
        shed = obs.get("private", {}).get("shed", {}) or {}
        tiles = me.get("tiles", [])
        plants = sum(1 for row in tiles for t in row
                     if isinstance(t, dict) and t.get("kind") == "PLANT")
        animals = sum(1 for row in tiles for t in row
                      if isinstance(t, dict) and t.get("animal"))

        verbs = collections.Counter()
        sells = collections.Counter()
        farmer_verb = ((action or {}).get("farmer") or [None])[0]
        if farmer_verb:
            verbs[farmer_verb] += 1
        for h in (action or {}).get("hands", []) or []:
            if h:
                verbs[h[0]] += 1
        for order in (action or {}).get("market", []) or []:
            if order:
                verbs[order[0]] += 1
                if order[0] == "SELL":
                    sells[order[1]] += order[2]

        return {
            "day": obs.get("day", 0),
            "money": me.get("money", 0),
            "plants": plants,
            "animals": animals,
            "hands": len(me.get("hands", []) or []),
            "unlocked": tuple(me.get("unlocked_quadrants", ["NW"]) or ["NW"]),
            "shed": {k: v for k, v in shed.items() if v},
            "sells": dict(sells),
            "verbs": dict(verbs),
        }
    except Exception as exc:  # instrumentation must never crash the game
        return {"error": repr(exc)}


def recorder(inner, log, call=_call):
    """Wrap an agent, appending one `snapshot_turn` row to `log` per call."""
    def wrapper(obs, config=None):
        act = call(inner, obs)
        log.append(snapshot_turn(obs, act))
        return act
    return wrapper


# --- play_and_record: wires both sides through recorder; game-play is injected ---

def _play_rewards(agent_a, agent_b, seed=None):  # pragma: no cover
    from kaggle_environments import make
    config = {"episodeSteps": economy.CONFIG_DEFAULTS["episodeSteps"]}
    if seed is not None:
        config["seed"] = seed
    env = make("kaggriculture", configuration=config)
    env.run([agent_a, agent_b])
    ra, rb = (s.reward for s in env.steps[-1])
    return (ra or 0), (rb or 0)


def play_and_record(agent_a, agent_b, seed=None, play_fn=None):
    """Play one game with both sides wrapped by `recorder`.

    Returns `(log_a, log_b, reward_a, reward_b)`. `play_fn(wrapped_a,
    wrapped_b, seed) -> (reward_a, reward_b)` is the real-game seam (mirrors
    `harness.tournament.play_rewards` / `genome_bench`'s `rewards_fn`); tests
    inject a stub so the wrapping/logging wiring is verified without a real
    `kaggle_environments` game.
    """
    play_fn = play_fn or _play_rewards
    log_a, log_b = [], []
    wrapped_a = recorder(agent_a, log_a)
    wrapped_b = recorder(agent_b, log_b)
    reward_a, reward_b = play_fn(wrapped_a, wrapped_b, seed)
    return log_a, log_b, reward_a, reward_b


# --- summarize: pure aggregation over one side's recorder log ---

def longest_idle_money_streak(money_series):
    """Longest run of consecutive turns where money was flat (unchanged) at or
    above `IDLE_MONEY_FLOOR` -- cash sitting on hand, affordable to spend,
    that wasn't. A flat streak below the floor isn't idle capital; there was
    nothing to buy with it yet.
    """
    longest = streak = 0
    prev = None
    for m in money_series:
        if prev is not None and m == prev and m >= IDLE_MONEY_FLOOR:
            streak += 1
        else:
            streak = 1 if m >= IDLE_MONEY_FLOOR else 0
        longest = max(longest, streak)
        prev = m
    return longest


def _confirmed_land_purchases(rows):
    """Confirmed land purchases, derived from `unlocked_quadrants` actually
    growing -- never from the `BUY_LAND` verb alone. The sim's
    `_do_buy_land` (kaggriculture.py:689-698) silently no-ops a purchase
    attempt when money is insufficient, so a `BUY_LAND` verb in the returned
    action proves only an *attempt*, never a completed purchase. State (the
    quadrant set growing) is the source of truth here, independent of
    whether an attempt verb was even captured on some earlier row -- see
    `_attempted_land_purchases` for that separate, verb-based count.
    """
    purchases = []
    seen = set()
    for r in rows:
        for q in r.get("unlocked", ()):
            if q not in seen:
                seen.add(q)
                if q != FREE_QUADRANT:
                    purchases.append({"quadrant": q, "day": r["day"], "money": r["money"]})
    return purchases


def _attempted_land_purchases(rows):
    """Turns where a `BUY_LAND` verb appears in the returned action.

    An attempt, not proof of purchase -- see `_confirmed_land_purchases`.
    Kept as its own field so a policy that tries to buy land it can't afford
    is visible as a divergence between the two counts, not hidden inside a
    single number.
    """
    return [{"day": r["day"], "money": r["money"]}
            for r in rows if r.get("verbs", {}).get("BUY_LAND")]


def summarize(log, reward, label=""):
    """Pure: turn a recorder log + final reward into a per-agent report dict.

    No I/O, no `kaggle_environments` -- unit-tested directly against synthetic
    logs, the same split `genome_bench.benchmark_genome` uses for its
    `rewards_fn` seam.
    """
    rows = [r for r in log if "error" not in r]
    plants = [r["plants"] for r in rows]
    animals = [r["animals"] for r in rows]
    hands = [r["hands"] for r in rows]
    money = [r["money"] for r in rows]

    quadrants_unlocked = {}
    for r in rows:
        for q in r.get("unlocked", ()):
            quadrants_unlocked.setdefault(q, r["day"])

    land_purchases = _confirmed_land_purchases(rows)
    land_purchase_attempts = _attempted_land_purchases(rows)

    sold = collections.Counter()
    for r in rows:
        for item, n in (r.get("sells") or {}).items():
            sold[item] += n

    idle_streak = longest_idle_money_streak(money)

    return {
        "label": label,
        "reward": reward,
        "turns": len(rows),
        "turns_with_errors": len(log) - len(rows),
        "plants_peak": max(plants, default=0),
        "plants_mean": (sum(plants) / len(plants)) if plants else 0.0,
        "animals_peak": max(animals, default=0),
        "hands_peak": max(hands, default=0),
        "quadrants_unlocked": quadrants_unlocked,
        "land_purchases": land_purchases,
        "land_purchase_attempts": land_purchase_attempts,
        "units_sold": dict(sold),
        "units_sold_total": sum(sold.values()),
        "distinct_products_sold": sum(1 for n in sold.values() if n > 0),
        "money_peak": max(money, default=0),
        "money_final": money[-1] if money else 0,
        "money_idle_streak": idle_streak,
        "money_sat_idle": idle_streak >= IDLE_STREAK_TURNS,
    }


def report_game(label_a, agent_a, label_b, agent_b, seed=0, play_fn=None):
    """Play one game and return `(summary_a, summary_b)`."""
    log_a, log_b, reward_a, reward_b = play_and_record(agent_a, agent_b, seed=seed, play_fn=play_fn)
    return (summarize(log_a, reward_a, label_a), summarize(log_b, reward_b, label_b))


# --- resolve_agent: CLI spec -> (label, agent) for a strategy, genome, or external agent ---

def resolve_agent(spec, discover_fn=None, build=build_agents):
    """Resolve a CLI-supplied agent spec to `(label, agent_callable)`.

    `spec` is, in resolution order:
      1. a path to a genome JSON artifact (`{"genome": [...]}`, e.g.
         `strategies/champion_genome.json`) -- loaded via
         `harness.evolve.load_genome`/`genome_agent`, the same pair
         `genome_bench` uses;
      2. a registered strategy name (`strategies.REGISTRY`), built the normal
         tournament way;
      3. a locally-fetched external agent (#78) -- matched by exact filename
         stem or, failing that, a unique substring (so `pilkwang` finds
         `pilkwang_structured_economic_policy` without the full name).

    `discover_fn` and `build` are injectable so tests never touch the registry,
    the filesystem-backed `external_agents/` directory, or the network.
    """
    if os.path.isfile(spec) and spec.endswith(".json"):
        label = os.path.splitext(os.path.basename(spec))[0]
        return label, genome_agent(load_genome(spec))

    if spec in REGISTRY:
        return spec, build([spec])[spec]

    discover_fn = discover_fn or external_pool.discover_external_agents
    external = discover_fn()
    if spec in external:
        return spec, external[spec]

    matches = [n for n in external if spec in n]
    if len(matches) == 1:
        return matches[0], external[matches[0]]
    if len(matches) > 1:
        raise ValueError(f"ambiguous agent spec {spec!r}: matches {matches}")

    raise ValueError(f"unknown agent spec: {spec!r}")


# --- CLI ---

def _print_report(rep):  # pragma: no cover
    print(f"\n=== {rep['label']} ===  reward={rep['reward']:,.0f}  "
          f"turns={rep['turns']} (errors={rep['turns_with_errors']})")
    print(f"plants: peak={rep['plants_peak']}  mean={rep['plants_mean']:.1f}   "
          f"animals: peak={rep['animals_peak']}   hands: peak={rep['hands_peak']}")
    print(f"quadrants unlocked (first day seen): {rep['quadrants_unlocked']}")
    print(f"land purchases confirmed (quadrant, day, money): {rep['land_purchases']}")
    print(f"land purchase attempts (day, money): {rep['land_purchase_attempts']}")
    print(f"units sold: {rep['units_sold']}")
    print(f"  total={rep['units_sold_total']}  distinct products={rep['distinct_products_sold']}")
    print(f"money: peak={rep['money_peak']:,.0f}  final={rep['money_final']:,.0f}  "
          f"idle_streak={rep['money_idle_streak']} turns  sat_idle={rep['money_sat_idle']}")


def main(argv=None):  # pragma: no cover
    ap = argparse.ArgumentParser(description="per-game production/throughput report (#95)")
    ap.add_argument("agent", help="registered strategy name, genome JSON path, "
                                   "or external agent name/fragment")
    ap.add_argument("opponent", nargs="?", default="wheat_hands")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args(argv)

    label_a, agent_a = resolve_agent(args.agent)
    label_b, agent_b = resolve_agent(args.opponent)
    report_a, report_b = report_game(label_a, agent_a, label_b, agent_b, seed=args.seed)
    _print_report(report_a)
    _print_report(report_b)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
