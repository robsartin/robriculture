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
from kaggisim.economy import base_price, market_price

CROPS = economy.CROPS
ANIMALS = economy.ANIMALS
LAND_COSTS = economy.LAND_COSTS


def _fib(n: int) -> int:
    """The sim's own hire ladder, indexed so _fib(0)=1, _fib(1)=1, _fib(2)=2."""
    a, b = 1, 1
    for _ in range(n):
        a, b = b, a + b
    return a


def buy_product_cost(item, units, prices=None, inventory=None):
    """Cost of buying `units` of `item` off the market, walked like the sim.

    A BUY drains market inventory, which moves the quote *up* against the buyer
    -- the mirror image of a big sell. The sim quotes each unit at the
    post-buy inventory (`market_price(item, inv - 1)`), so a buy/sell
    round-trip against an unchanged market nets zero.

    Estimated, not exact: the sim aborts the rest of an order the moment money
    or shed space runs out, and this cannot see either. It is therefore an
    upper bound on a truncated order -- which is the honest direction, because
    the alternative already cost us a 55%-of-final-money residual that read as
    a sell-side mystery.
    """
    price = (prices or {}).get(item)
    inv = (inventory or {}).get(item)
    if inv is None:
        return units * int(price) if price else 0
    total = 0
    inv = int(inv)
    for _ in range(units):
        total += market_price(item, inv - 1)
        inv -= 1
    return total


def order_spend(orders, hires_before, quadrants, prices=None, inventory=None):
    """Exact cost of one turn's market orders.

    Seed cost, animal cost, the quadrant ladder and the n-th hire of the day at
    ``fib(n)`` are listed prices and exact. ``BUY_PRODUCT`` is not: it walks the
    market curve and the sim truncates it on money or shed space, so it is
    estimated the same way sell revenue is. The residual in `decompose`
    therefore covers both sides of the ledger -- which is what it was already
    doing silently, since dropping BUY_PRODUCT entirely booked a -19,000
    residual on a 35,000 game as a sell-side mystery (#146).
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
        elif op == "BUY_PRODUCT" and len(order) >= 3:
            spend += buy_product_cost(order[1], int(order[2]), prices, inventory)
    return spend


def spend_by_category(orders, hires_before, quadrants, prices=None, inventory=None):
    """`order_spend` split into named buckets, for the write-up."""
    out = {"seed": 0, "hire": 0, "land": 0, "animal": 0, "product": 0}
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
        elif op == "BUY_PRODUCT" and len(order) >= 3:
            out["product"] += buy_product_cost(order[1], int(order[2]),
                                               prices, inventory)
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


def unit_prices(orders, prices, shed, banked=None, inventory=None):
    """Realised price of each unit sold this turn, per item, in commit order.

    The walk `sell_revenue` performs, exposed rather than summed away. Revenue
    answers "how much did we make"; only the per-unit sequence answers "what is
    a unit still worth after we have sold N of them" -- the question in #146.

    Same two conservatisms as `sell_revenue`, because it is the same walk: an
    order is capped at the stock that actually exists, and an item with no
    quoted price contributes nothing.
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
        seq = out.setdefault(item, [])
        inv = (inventory or {}).get(item)
        if inv is None:
            seq.extend([int(price)] * units)
            continue
        # Walk the curve, as the sim does: each unit is quoted against the
        # inventory the previous units have already added to. Measured on a real
        # episode, 96 melon quoted at 244 realised 190/unit -- pricing the whole
        # order at the opening quote overstates it by 28%.
        inv = int(inv)
        for _ in range(units):
            unit_price = market_price(item, inv)
            seq.append(unit_price)
            if unit_price > 1:      # sales at the floor add no market supply
                inv += 1
    return out


def sell_revenue(orders, prices, shed, banked=None, inventory=None):
    """Estimated proceeds per item from one turn's SELL orders.

    Exactly `unit_prices` summed per item -- one walk, so the two can never
    disagree.

    Two deliberate conservatisms, both of which would otherwise invent money:
    an order is capped at the stock that actually exists (the sim partially
    fills), and an item with no quoted price contributes nothing -- livestock
    and anything else the market does not bid on.

    ``banked`` is what this turn's DROPs add to the shed. The interpreter runs
    every unit action before the market, so a crew that banks its harvest and
    sells it in the same turn is the normal case; capping at the observed
    pre-DROP shed erased almost all real revenue.
    """
    return {item: sum(seq)
            for item, seq in unit_prices(orders, prices, shed, banked, inventory).items()}


#: Share of a season's units treated as "end of season" when reporting the
#: realised price a market has decayed to (#146). A quarter is enough units to
#: average out the per-unit sawtooth without reaching back to opening prices.
LATE_WINDOW = 0.25


def summarize_prices(seq, item):
    """Summary of one item's season-long sequence of realised unit prices.

    ``pct_of_base`` is the whole season's average; ``late_pct_of_base`` is the
    last ``LATE_WINDOW`` of units -- what a unit was still worth once the season
    had done its selling, which is the number #146 asks about. A season that
    opens at base and closes at the $1 floor averages to something reassuring;
    only the late window shows the floor.
    """
    seq = list(seq)
    base = base_price(item)
    if not seq:
        return {"units": 0, "revenue": 0, "mean_price": 0.0, "base": base,
                "pct_of_base": 0.0, "late_units": 0, "late_mean_price": 0.0,
                "late_pct_of_base": 0.0, "last_unit_price": 0}
    revenue = sum(seq)
    mean = revenue / len(seq)
    late_n = max(1, int(round(len(seq) * LATE_WINDOW)))
    late = seq[-late_n:]
    late_mean = sum(late) / len(late)
    return {
        "units": len(seq),
        "revenue": revenue,
        "mean_price": mean,
        "base": base,
        "pct_of_base": (mean / base) if base else 0.0,
        "late_units": len(late),
        "late_mean_price": late_mean,
        "late_pct_of_base": (late_mean / base) if base else 0.0,
        "last_unit_price": seq[-1],
    }


def price_realisation(steps, player):
    """Realised price per unit, per product, across one side of one season.

    ``items`` is `summarize_prices` per product actually sold. ``final_quotes``
    is the market's own closing quote, read straight off the last observation
    rather than reconstructed -- the positive control on the walk: if our
    reconstruction says we crashed a market and the recorded quote disagrees,
    the instrument is what is broken.
    """
    seqs: dict = {}
    for turn in _turns(steps, player):
        for item, seq in unit_prices(turn["orders"], turn["prices"], turn["shed"],
                                     turn["banked"], turn["inv_levels"]).items():
            seqs.setdefault(item, []).extend(seq)
    last = _slot(steps, len(steps) - 1, player) if steps else None
    quotes = (((last or {}).get("observation") or {}).get("market") or {}).get("prices") or {}
    return {
        "items": {item: summarize_prices(seq, item) for item, seq in seqs.items()},
        "final_quotes": dict(quotes),
        "unit_prices": seqs,
    }


def _slot(steps, t, player):
    """One player's slot at step `t`, or None."""
    step = steps[t] if t < len(steps) else None
    if not step or player >= len(step):
        return None
    return step[player]


def _turns(steps, player):
    """One dict per turn, pairing each action with the state it was chosen from.

    The action recorded at index t was chosen from -- and applied to -- the
    observation at index t-1. Verified on a real episode: the SELL of 96 melon
    sits at index 289 while the shed holding those melon is index 288, and the
    money moves across that pair. Reading an order against the observation at
    its own index prices it against the state it already produced, which scored
    the champion's whole season at 994 against an actual 48,144.

    Shared by `decompose` and `price_realisation` so the two can never drift
    apart on which observation an order is priced against.
    """
    for t in range(len(steps)):
        slot = _slot(steps, t, player)
        if slot is None:
            continue
        prior = _slot(steps, t - 1, player) if t else None
        obs = (prior or {}).get("observation") or {}
        farms = obs.get("farms")
        if farms:
            me = farms[obs.get("player", player)] if len(farms) > 1 else farms[0]
            quadrants = len(me.get("unlocked_quadrants") or ["NW"])
            sheds = (obs.get("private") or {}).get("shed") or {}
            prices = (obs.get("market") or {}).get("prices") or {}
            inv_levels = (obs.get("market") or {}).get("inventory") or None
        else:
            quadrants, sheds, prices, inv_levels = 1, {}, {}, None

        action = slot.get("action")
        if not isinstance(action, dict):
            continue
        yield {
            "slot": slot,
            "day": obs.get("day"),
            "quadrants": quadrants,
            "shed": sheds,
            "prices": prices,
            "inv_levels": inv_levels,
            "action": action,
            "orders": action.get("market") or [],
            "banked": banked_this_turn(
                action, (obs.get("private") or {}).get("inventories") or []),
        }


def decompose(steps, player):
    """Decompose one side of one episode.

    Returns revenue by item, spend by category, an action tally, and the
    ``residual`` -- the money the replay ends with, minus the money this
    reconstruction accounts for. Read the residual first: a large one means the
    rest of the numbers are not to be trusted.
    """
    revenue: dict = {}
    spend = {"seed": 0, "hire": 0, "land": 0, "animal": 0, "product": 0}
    actions: dict = {}
    start_money = None
    final_money = 0.0
    hires_today = 0
    last_day = None

    for t in range(len(steps)):
        slot = _slot(steps, t, player)
        if slot is None:
            continue
        money_obs = (slot.get("observation") or {})
        money_farms = money_obs.get("farms")
        if money_farms:
            me_now = (money_farms[money_obs.get("player", player)]
                      if len(money_farms) > 1 else money_farms[0])
            if start_money is None:
                start_money = float(me_now.get("money", 0))
            final_money = float(me_now.get("money", 0))

    for turn in _turns(steps, player):
        if turn["day"] != last_day:
            hires_today = 0              # the sim clears the crew nightly
            last_day = turn["day"]

        for act in [turn["action"].get("farmer")] + list(turn["action"].get("hands") or []):
            if isinstance(act, list) and act:
                actions[act[0]] = actions.get(act[0], 0) + 1

        orders = turn["orders"]
        for item, amount in sell_revenue(orders, turn["prices"], turn["shed"],
                                         turn["banked"], turn["inv_levels"]).items():
            revenue[item] = revenue.get(item, 0) + amount
        for bucket, amount in spend_by_category(orders, hires_today,
                                                turn["quadrants"], turn["prices"],
                                                turn["inv_levels"]).items():
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
