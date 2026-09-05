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
from kaggisim.economy import market_price

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


def banked_this_turn(action, inventories):
    """Items every DROPping worker puts into the shed this turn.

    The interpreter applies unit actions before it processes market orders, so
    these units are sellable in the very same turn. DROP banks a worker's whole
    inventory.
    """
    out: dict = {}
    if not isinstance(action, dict):
        return out
    units = [action.get("farmer")] + list(action.get("hands") or [])
    for idx, act in enumerate(units):
        if not (isinstance(act, list) and act and act[0] == "DROP"):
            continue
        inv = inventories[idx] if idx < len(inventories) else {}
        for item, n in (inv or {}).items():
            if n:
                out[item] = out.get(item, 0) + int(n)
    return out


def sell_revenue(orders, prices, shed, banked=None, inventory=None):
    """Estimated proceeds per item from one turn's SELL orders.

    Two deliberate conservatisms, both of which would otherwise invent money:
    an order is capped at the stock that actually exists (the sim partially
    fills), and an item with no quoted price contributes nothing -- livestock
    and anything else the market does not bid on.

    ``banked`` is what this turn's DROPs add to the shed. The interpreter runs
    every unit action before the market, so a crew that banks its harvest and
    sells it in the same turn is the normal case; capping at the observed
    pre-DROP shed erased almost all real revenue.
    """
    out: dict = {}
    for order in orders:
        if not isinstance(order, list) or len(order) < 3 or order[0] != "SELL":
            continue
        item = order[1]
        price = (prices or {}).get(item)
        if not price:
            continue
        available = int((shed or {}).get(item, 0)) + int((banked or {}).get(item, 0))
        units = min(int(order[2]), available)
        if units <= 0:
            continue
        inv = (inventory or {}).get(item)
        if inv is None:
            out[item] = out.get(item, 0) + units * int(price)
            continue
        # Walk the curve, as the sim does: each unit is quoted against the
        # inventory the previous units have already added to. Measured on a real
        # episode, 96 melon quoted at 244 realised 190/unit -- pricing the whole
        # order at the opening quote overstates it by 28%.
        total = 0
        inv = int(inv)
        for _ in range(units):
            unit_price = market_price(item, inv)
            total += unit_price
            if unit_price > 1:      # sales at the floor add no market supply
                inv += 1
        out[item] = out.get(item, 0) + total
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

    # The action recorded at index t was chosen from -- and applied to -- the
    # observation at index t-1. Verified on a real episode: the SELL of 96 melon
    # sits at index 289 while the shed holding those melon is index 288, and the
    # money moves across that pair. Reading an order against the observation at
    # its own index prices it against the state it already produced, which
    # scored the champion's whole season at 994 against an actual 48,144.
    for t in range(len(steps)):
        slot = _slot(steps, t, player)
        prior = _slot(steps, t - 1, player) if t else None
        if slot is None:
            continue
        obs = (prior or {}).get("observation") or {}
        money_obs = (slot.get("observation") or {})
        money_farms = money_obs.get("farms")
        if money_farms:
            me_now = (money_farms[money_obs.get("player", player)]
                      if len(money_farms) > 1 else money_farms[0])
            if start_money is None:
                start_money = float(me_now.get("money", 0))
            final_money = float(me_now.get("money", 0))

        farms = obs.get("farms")
        if farms:
            me = farms[obs.get("player", player)] if len(farms) > 1 else farms[0]
            day = obs.get("day")
            if day != last_day:
                hires_today = 0          # the sim clears the crew nightly
                last_day = day
            quadrants = len(me.get("unlocked_quadrants") or ["NW"])
            sheds = (obs.get("private") or {}).get("shed") or {}
            prices = (obs.get("market") or {}).get("prices") or {}
            inv_levels = (obs.get("market") or {}).get("inventory") or None
        else:
            quadrants, sheds, prices, inv_levels = 1, {}, {}, None

        action = slot.get("action")
        if not isinstance(action, dict):
            continue

        for act in [action.get("farmer")] + list(action.get("hands") or []):
            if isinstance(act, list) and act:
                actions[act[0]] = actions.get(act[0], 0) + 1

        orders = action.get("market") or []
        banked = banked_this_turn(action, (obs.get("private") or {}).get("inventories") or [])
        for item, amount in sell_revenue(orders, prices, sheds, banked, inv_levels).items():
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


def _sold_units(orders, item, shed, banked):
    """Units of `item` one turn's SELL orders can actually fill.

    Same conservatism as `sell_revenue`: an order is capped at the stock that
    exists, counting what this turn's DROPs bank, because the interpreter runs
    unit actions before the market.
    """
    available = int((shed or {}).get(item, 0)) + int((banked or {}).get(item, 0))
    units = 0
    for order in orders:
        if not isinstance(order, list) or len(order) < 3 or order[0] != "SELL":
            continue
        if order[1] != item:
            continue
        fill = min(int(order[2]), available - units)
        if fill > 0:
            units += fill
    return units


def _sells_item(slot, item):
    """True when this slot's action carries a SELL order for `item`."""
    action = (slot or {}).get("action")
    if not isinstance(action, dict):
        return False
    return any(isinstance(o, list) and len(o) >= 3 and o[0] == "SELL" and o[1] == item
               for o in (action.get("market") or []))


def first_sale(steps, player, item):
    """The first turn `player` actually sells `item`, decomposed (#205).

    ``None`` when the item never reaches the market. Otherwise the `day` and
    `hour` the order was chosen on, the `units` it filled, the estimated
    `revenue`, the realised `price` per unit, the market `inventory` the sale
    opened against, and `contested`.

    Read `contested` before the price. Both players commit unit-by-unit against
    the same pre-commit inventory, so on a turn the opponent also sells into,
    this side's own walk down the curve is an *overestimate* -- the interleaved
    units pushed the real fills further down it.

    An order that cannot fill is not a sale: a SELL against an empty shed costs
    nothing and moves nothing, and reporting it would date the sale to a turn
    where no melon changed hands.
    """
    for t in range(len(steps)):
        slot = _slot(steps, t, player)
        prior = _slot(steps, t - 1, player) if t else None
        if slot is None or prior is None:
            continue
        if not _sells_item(slot, item):
            continue
        obs = prior.get("observation") or {}
        action = slot.get("action")
        orders = action.get("market") or []
        shed = (obs.get("private") or {}).get("shed") or {}
        banked = banked_this_turn(action, (obs.get("private") or {}).get("inventories") or [])
        units = _sold_units(orders, item, shed, banked)
        if units <= 0:
            continue
        market = obs.get("market") or {}
        revenue = sell_revenue(orders, market.get("prices") or {}, shed, banked,
                               market.get("inventory") or None).get(item, 0)
        return {
            "day": obs.get("day"),
            "hour": obs.get("hour"),
            "units": units,
            "revenue": revenue,
            "price": revenue / units,
            "inventory": (market.get("inventory") or {}).get(item),
            "quoted": (market.get("prices") or {}).get(item),
            "contested": _sells_item(_slot(steps, t, 1 - player), item),
        }
    return None
