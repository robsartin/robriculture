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


def _product_unit_prices(item, units, prices=None, inventory=None):
    """Per-unit BUY_PRODUCT price, walked like the sim, one unit at a time.

    A BUY drains market inventory, which moves the quote *up* against the buyer
    -- the mirror image of a big sell. The sim quotes each unit at the
    post-buy inventory (`market_price(item, inv - 1)`), so a buy/sell
    round-trip against an unchanged market nets zero. Falls back to the flat
    quoted price, `units` times, when inventory is unknown -- degrade rather
    than disappear.
    """
    price = (prices or {}).get(item)
    inv = (inventory or {}).get(item)
    if inv is None:
        if price:
            for _ in range(units):
                yield int(price)
        return
    inv = int(inv)
    for _ in range(units):
        yield market_price(item, inv - 1)
        inv -= 1


def buy_product_cost(item, units, prices=None, inventory=None):
    """Cost of buying `units` of `item` off the market, walked like the sim.

    Sums `_product_unit_prices`, the per-unit walk `spend_by_category` also
    pays unit by unit, so the two can never disagree.

    Estimated, not exact: the sim aborts the rest of an order the moment money
    or shed space runs out, and this cannot see shed space. It is therefore an
    upper bound on a truncated order -- which is the honest direction, because
    the alternative already cost us a 55%-of-final-money residual that read as
    a sell-side mystery. `spend_by_category`'s `money` argument corrects the
    money side of that truncation; this function stays the uncapped upper
    bound for callers that do not have `money` to give it.
    """
    return sum(_product_unit_prices(item, units, prices, inventory))


def order_spend(orders, hires_before, quadrants, prices=None, inventory=None, money=None):
    """Exact cost of one turn's market orders.

    Seed cost, animal cost, the quadrant ladder and the n-th hire of the day at
    ``fib(n)`` are listed prices and exact. ``BUY_PRODUCT`` is not: it walks the
    market curve and the sim truncates it on money or shed space, so it is
    estimated the same way sell revenue is. The residual in `decompose`
    therefore covers both sides of the ledger -- which is what it was already
    doing silently, since dropping BUY_PRODUCT entirely booked a -19,000
    residual on a 35,000 game as a sell-side mystery (#146).

    One walker with `spend_by_category` -- this is simply that function's
    buckets summed, so the two can never drift apart. See `spend_by_category`
    for what `money` does.
    """
    return sum(spend_by_category(orders, hires_before, quadrants, prices, inventory, money).values())


def spend_by_category(orders, hires_before, quadrants, prices=None, inventory=None, money=None):
    """`order_spend` split into named buckets, for the write-up.

    `money` is what the farm held when it chose these orders plus this turn's
    sell revenue; with it, an order is booked only as far as the sim would
    have paid it (the sim drops the rest unit by unit -- `kaggriculture.py`
    checks `farm["money"] < price` before every buy). Without it the old
    upper bound stands, for replays read without money.
    """
    out = {"seed": 0, "hire": 0, "land": 0, "animal": 0, "product": 0}
    hires = hires_before
    owned = quadrants
    budget = None if money is None else float(money)

    def pay(cost):
        """Pays `cost` out of the walking budget, unit by unit. Returns
        `(amount_booked, paid)`; with no budget, every cost is paid."""
        nonlocal budget
        if budget is None or budget >= cost:
            if budget is not None:
                budget -= cost
            return cost, True
        return 0, False

    for order in orders:
        if not isinstance(order, list) or not order:
            continue
        op = order[0]
        if op == "HIRE":
            spent, _ = pay(_fib(hires))
            out["hire"] += spent
            hires += 1
        elif op == "BUY_LAND":
            if owned - 1 < len(LAND_COSTS):
                spent, _ = pay(LAND_COSTS[owned - 1])
                out["land"] += spent
                owned += 1
        elif op == "BUY_SEED" and len(order) >= 3 and order[1] in CROPS:
            unit_cost = CROPS[order[1]]["seed"]
            for _ in range(int(order[2])):
                spent, paid = pay(unit_cost)
                out["seed"] += spent
                if not paid:
                    break
        elif op == "BUY_ANIMAL" and len(order) >= 2 and order[1] in ANIMALS:
            n = int(order[2]) if len(order) >= 3 else 1
            unit_cost = ANIMALS[order[1]]["cost"]
            for _ in range(n):
                spent, paid = pay(unit_cost)
                out["animal"] += spent
                if not paid:
                    break
        elif op == "BUY_PRODUCT" and len(order) >= 3:
            for unit_cost in _product_unit_prices(order[1], int(order[2]), prices, inventory):
                spent, paid = pay(unit_cost)
                out["product"] += spent
                if not paid:
                    break
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
            money = float(me.get("money", 0))
        else:
            quadrants, sheds, prices, inv_levels, money = 1, {}, {}, None, None

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
            "money": money,
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
        revenue_this_turn = sell_revenue(orders, turn["prices"], turn["shed"],
                                         turn["banked"], turn["inv_levels"])
        for item, amount in revenue_this_turn.items():
            revenue[item] = revenue.get(item, 0) + amount
        # Sells settle before buys except at dawn (the reset slot, `money`
        # None); the dawn case is the upper-bound direction and is left as is.
        money = (turn["money"] + sum(revenue_this_turn.values())
                 if turn["money"] is not None else None)
        for bucket, amount in spend_by_category(orders, hires_today,
                                                turn["quadrants"], turn["prices"],
                                                turn["inv_levels"], money=money).items():
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
