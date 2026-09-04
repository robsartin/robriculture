"""Decompose a real ladder replay into where the money came from (issue #157).

We have played 76 rated matches and the downloaded replays carry BOTH players'
actions and observations, so an opponent can be decomposed exactly as we can.

The sim has exactly one money inflow: ``farm["money"] += price`` on a SELL
commit. Town shops drain market *inventory*, which lifts prices, but they never
pay a farm. So a farm's whole income is market sell revenue, and its final
reward is its final cash.

Sell revenue can only be *estimated* here -- price moves within an order and the
two players commit unit-by-unit in lockstep -- so every decomposition carries a
``residual``: the gap between the reconstruction and the money the replay
actually records. A decomposition with a large residual says so, instead of
looking plausible. That check is the point of the module.
"""

from __future__ import annotations

from kaggisim import economy

CROPS = economy.CROPS
ANIMALS = economy.ANIMALS
LAND_COSTS = economy.LAND_COSTS


def _fib(n: int) -> int:
    """The sim's own hire ladder, indexed so _fib(0)=1, _fib(1)=1, _fib(2)=2."""
    a, b = 1, 1
    for _ in range(n):
        a, b = b, a + b
    return a


def order_spend(orders, hires_before, quadrants):
    """Exact cost of one turn's market orders.

    Every outflow in the sim is a listed price -- seed cost, animal cost, the
    quadrant ladder, and the n-th hire of the day at ``fib(n)``. Nothing here is
    estimated, which is why the residual in `decompose` is attributable to the
    sell side alone.
    """
    spend = 0
    hires = hires_before
    owned = quadrants
    for order in orders:
        if not isinstance(order, list) or not order:
            continue
        op = order[0]
        if op == "HIRE":
            spend += _fib(hires)
            hires += 1
        elif op == "BUY_LAND":
            if owned - 1 < len(LAND_COSTS):
                spend += LAND_COSTS[owned - 1]
                owned += 1
        elif op == "BUY_SEED" and len(order) >= 3 and order[1] in CROPS:
            spend += CROPS[order[1]]["seed"] * int(order[2])
        elif op == "BUY_ANIMAL" and len(order) >= 2 and order[1] in ANIMALS:
            n = int(order[2]) if len(order) >= 3 else 1
            spend += ANIMALS[order[1]]["cost"] * n
    return spend


def spend_by_category(orders, hires_before, quadrants):
    """`order_spend` split into named buckets, for the write-up."""
    out = {"seed": 0, "hire": 0, "land": 0, "animal": 0}
    hires = hires_before
    owned = quadrants
    for order in orders:
        if not isinstance(order, list) or not order:
            continue
        op = order[0]
        if op == "HIRE":
            out["hire"] += _fib(hires)
            hires += 1
        elif op == "BUY_LAND":
            if owned - 1 < len(LAND_COSTS):
                out["land"] += LAND_COSTS[owned - 1]
                owned += 1
        elif op == "BUY_SEED" and len(order) >= 3 and order[1] in CROPS:
            out["seed"] += CROPS[order[1]]["seed"] * int(order[2])
        elif op == "BUY_ANIMAL" and len(order) >= 2 and order[1] in ANIMALS:
            n = int(order[2]) if len(order) >= 3 else 1
            out["animal"] += ANIMALS[order[1]]["cost"] * n
    return out


def sell_revenue(orders, prices, shed):
    """Estimated proceeds per item from one turn's SELL orders.

    Two deliberate conservatisms, both of which would otherwise invent money:
    an order is capped at what the shed actually holds (the sim partially fills),
    and an item with no quoted price contributes nothing -- livestock and
    anything else the market does not bid on.
    """
    out: dict = {}
    for order in orders:
        if not isinstance(order, list) or len(order) < 3 or order[0] != "SELL":
            continue
        item = order[1]
        price = (prices or {}).get(item)
        if not price:
            continue
        units = min(int(order[2]), int((shed or {}).get(item, 0)))
        if units > 0:
            out[item] = out.get(item, 0) + units * int(price)
    return out


def _slot(steps, t, player):
    """One player's slot at step `t`, or None."""
    step = steps[t] if t < len(steps) else None
    if not step or player >= len(step):
        return None
    return step[player]


def decompose(steps, player):
    """Decompose one side of one episode.

    Returns revenue by item, spend by category, an action tally, and the
    ``residual`` -- the money the replay ends with, minus the money this
    reconstruction accounts for. Read the residual first: a large one means the
    rest of the numbers are not to be trusted.
    """
    revenue: dict = {}
    spend = {"seed": 0, "hire": 0, "land": 0, "animal": 0}
    actions: dict = {}
    start_money = None
    final_money = 0.0
    hires_today = 0
    last_day = None

    for t in range(len(steps)):
        slot = _slot(steps, t, player)
        if slot is None:
            continue
        obs = slot.get("observation") or {}
        farms = obs.get("farms")
        if farms:
            me = farms[obs.get("player", player)] if len(farms) > 1 else farms[0]
            if start_money is None:
                start_money = float(me.get("money", 0))
            final_money = float(me.get("money", 0))
            day = obs.get("day")
            if day != last_day:
                hires_today = 0          # the sim clears the crew nightly
                last_day = day
            quadrants = len(me.get("unlocked_quadrants") or ["NW"])
            sheds = (obs.get("private") or {}).get("shed") or {}
            prices = (obs.get("market") or {}).get("prices") or {}
        else:
            quadrants, sheds, prices = 1, {}, {}

        action = slot.get("action")
        if not isinstance(action, dict):
            continue

        for act in [action.get("farmer")] + list(action.get("hands") or []):
            if isinstance(act, list) and act:
                actions[act[0]] = actions.get(act[0], 0) + 1

        orders = action.get("market") or []
        for item, amount in sell_revenue(orders, prices, sheds).items():
            revenue[item] = revenue.get(item, 0) + amount
        for bucket, amount in spend_by_category(orders, hires_today, quadrants).items():
            spend[bucket] += amount
        hires_today += sum(1 for o in orders
                           if isinstance(o, list) and o and o[0] == "HIRE")

    accounted = (start_money or 0) + sum(revenue.values()) - sum(spend.values())
    return {
        "revenue": revenue,
        "spend": spend,
        "actions": actions,
        "final_money": final_money,
        "residual": final_money - accounted,
    }
