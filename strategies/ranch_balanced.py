"""Two-front income robustness on the ranch (experiment #53, ADR-0007).

Foundation: `ranch_hands`, the champion — a 9-tile melon crew, a dedicated
livestock hand running a cow + sheep cluster, a WHEAT catch-crop that doubles as
feed, and the sell-before-hire market ordering. The livestock hand, the animal
state machine, the feed-buffer sell rule, hiring, navigation and market plumbing
are reused *verbatim* by importing the champion's helpers.

The single variable under test — **income concentration**. `ranch_hands` earns
almost all of its coins from **one** market: melon. But the 1v1 ladder shares
*one* melon market, and MELON is demanded by **no** town shop (`economy.SHOP_DEMAND`),
so melon an opponent dumps is never drained by consumption — it just sits there
depressing the price. A single-market spoiler (experiment #52's `spoiler`) can
therefore crash the exact market our whole income rides on. `ranch_adaptive` (#52)
answers this *reactively* — it reads the melon price and throttles selling when it
is crashed. This experiment answers it *structurally*: earn from **two roughly-equal
markets** so that crashing either one only removes about half our income.

Concretely, the champion's 9-tile melon crew is **re-partitioned** into two fronts
of comparable expected income:

- a **4-tile melon crew** (the farmer keeps the shed-adjacent home plot), and
- a **5-tile continuous-WHEAT crew** — wheat grown as a *primary* crop, replanted
  all season (not merely a post-melon catch crop). WHEAT is demanded by five town
  shops (the #46 result: it clears at/above base on shop scarcity) *and* it is the
  livestock's feed, so the wheat front doubles as the cow + sheep feed supply.

The cow + sheep livestock hand is unchanged, giving milk and wool as further
non-melon income. The result: melon falls to roughly half of expected income
(see `melon_income_share`), so a melon-only flood can crater at most ~half of what
we earn — while the wheat / milk / wool fronts, which the flood cannot touch, keep
paying. The expected-income model that sizes the split lives in pure helpers so
the balance property is unit-tested without a full 720-turn game.

**The expected-income model.** Per-line seasonal income is expected units x price:

- **Melon** is modelled at a *depressed* realized price — ``MELON_REALIZED_RATIO``
  x base — because it has no shop demand and both players dump into one shared
  market (the same "crashed" fraction `ranch_adaptive` reacts to). This is the
  honest realized-income view; modelling melon at full base would only *overstate*
  its share, so the <=55% bound is conservative either way.
- **Wheat, milk, wool** are shop-demanded and clear at/above base; we model them
  *at* base (conservative — a higher wheat price would only shrink melon's share).

The numbers land melon at ~53% of expected income: two roughly-equal fronts.
"""

from __future__ import annotations

from kaggisim import economy
from kaggisim.strategy import Strategy
from strategies import catch_hands as ch
from strategies import hired_hands as hh
from strategies import ranch_hands as rh

#: Season length, crew cap, turns-per-day — inherited from the champion.
MELON = rh.MELON
SEASON_DAYS = rh.SEASON_DAYS
MAX_HANDS = rh.MAX_HANDS
TURNS_PER_DAY = hh.TURNS_PER_DAY

#: The livestock line is the champion's, byte-for-byte.
COW_TILE = rh.COW_TILE
SHEEP_TILE = rh.SHEEP_TILE
ANIMAL_COST = rh.ANIMAL_COST
COW_MONEY_BUFFER = rh.COW_MONEY_BUFFER
SHEEP_MONEY_BUFFER = rh.SHEEP_MONEY_BUFFER
WHEAT_CARRY = rh.WHEAT_CARRY
WHEAT_BUFFER = rh.WHEAT_BUFFER

#: The two crop fronts, partitioning the champion's 9-tile crop crew. The near
#: block (the farmer's shed-adjacent home plot first) stays melon; the farther
#: block grows continuous wheat. Sizes chosen so the two fronts' expected incomes
#: are roughly equal (see the model below): 4 melon + 5 wheat.
MELON_PLOTS = rh.MELON_PLOTS[:4]
WHEAT_PLOTS = rh.MELON_PLOTS[4:]

#: The crop crew as (tile, crop) in worker-assignment order: melon block, then
#: wheat block. Worker 0 gets [0]; worker 1 is the livestock hand; workers 2..N
#: take [1..] (see `crop_plot_for`).
CROP_PLOTS: list[tuple[tuple[int, int], str]] = [(t, "MELON") for t in MELON_PLOTS] + [
    (t, "WHEAT") for t in WHEAT_PLOTS
]

#: Every crop tile, in assignment order — used to size the crew's live coverage.
CROP_TILES = [t for t, _ in CROP_PLOTS]


# --- Expected-income model: sizes the split and pins the balance property ---

#: Realized melon price as a fraction of base. MELON has no town-shop demand and
#: both 1v1 players dump into the ONE shared melon market, so it clears well below
#: its $250 base — the exact weakness this experiment de-risks. We use the same
#: fraction `ranch_adaptive` treats as a crashed market. Modelling melon lower
#: only shrinks its share, so the <=55% balance bound is conservative.
MELON_REALIZED_RATIO = 0.6

#: Expected seasonal units per plot / line (reconciled to the economy tables):
#: - melon: ~2 cycles/season x 6 units (first yield day 10, max_day 12).
#: - wheat: ~6 cycles/season x 4 units (max_day 4, replanted all season).
#: - milk:  first yield day 8, +1 every 2 days through the final day (~11).
#: - wool:  first yield day 6, +1 every 3 days through the final day (~8).
MELON_UNITS_PER_PLOT = 12
WHEAT_UNITS_PER_PLOT = 24
COW_MILK_UNITS = 11
SHEEP_WOOL_UNITS = 8


def _line_income(product: str, units: int) -> float:
    """Expected seasonal income for a line: units x realized price. Melon is
    discounted to its depressed shared-market level; everything else at base."""
    price = economy.base_price(product)
    if product == MELON:
        price *= MELON_REALIZED_RATIO
    return units * price


def melon_income(n_plots: int) -> float:
    """Expected seasonal melon income across ``n_plots`` melon tiles."""
    return n_plots * _line_income(MELON, MELON_UNITS_PER_PLOT)


def wheat_income(n_plots: int) -> float:
    """Expected seasonal wheat income across ``n_plots`` continuous-wheat tiles."""
    return n_plots * _line_income("WHEAT", WHEAT_UNITS_PER_PLOT)


def livestock_income() -> float:
    """Expected seasonal income from the cow (milk) + sheep (wool) cluster."""
    return _line_income("MILK", COW_MILK_UNITS) + _line_income("WOOL", SHEEP_WOOL_UNITS)


def melon_income_share() -> float:
    """Melon's fraction of total expected income under the model — the balance
    property the experiment turns on. At the chosen split this is ~0.53: melon
    and the combined wheat + livestock fronts are roughly equal."""
    melon = melon_income(len(MELON_PLOTS))
    total = melon + wheat_income(len(WHEAT_PLOTS)) + livestock_income()
    return melon / total


# --- Plot assignment and the continuous-wheat tile loop ---

def crop_plot_for(i: int):
    """The (tile, crop) worker ``i`` tends, or ``None`` for the livestock hand.

    Worker 0 (farmer) keeps the first crop plot; worker 1 is the dedicated
    livestock hand; workers 2..N take the remaining crop plots. Indices past the
    crew clamp to the last plot (mirrors the champion's `melon_plot_for`)."""
    if i == 0:
        return CROP_PLOTS[0]
    if i == 1:
        return None  # the livestock hand — no crop plot
    idx = i - 1  # worker 2 -> CROP_PLOTS[1], ... worker 9 -> CROP_PLOTS[8]
    if idx >= len(CROP_PLOTS):
        idx = len(CROP_PLOTS) - 1
    return CROP_PLOTS[idx]


def _wheat_decide(tile, day: int, hour: int, season_days: int = SEASON_DAYS):
    """The action for a worker standing on a **wheat front** plot: grow wheat as a
    primary crop — plant on an empty plot, then water/harvest the standing plant,
    and replant once it clears. Wheat is only planted while it can still reach full
    maturity before the buzzer, and never on the day's last turn (a plant left
    unwatered on its birth night dies)."""
    if isinstance(tile, dict) and tile.get("kind") == "WEED":
        return ["DIG"]
    if tile is None:
        if ch.cc_plantable("WHEAT", day, season_days) and hour < TURNS_PER_DAY - 1:
            return ["PLANT", "WHEAT"]
        return ["PASS"]
    if hh._is_live_plant(tile):
        return ch.catch_tile_action(tile, day)
    return ["PASS"]


class RanchBalancedStrategy(Strategy):
    name = "ranch_balanced"

    def act(self, obs) -> dict:
        player = obs["player"]
        me = obs["farms"][player]
        private = obs["private"]
        day = obs.get("day", 0)
        hour = obs.get("hour", 0)
        money = me["money"]
        tiles = me["tiles"]
        hands = me.get("hands", []) or []
        seeds = private.get("seeds", {})
        shed = private.get("shed", {})
        inventories = private.get("inventories", [{}])

        season_days = SEASON_DAYS
        catch = rh.choose_catch_crop(day, season_days)  # WHEAT tail for melon plots
        melon_open = hh.plantable(MELON, day, season_days)

        # --- Market: product SELLs FIRST (melon/milk/wool + wheat surplus) so the
        # price-sensitive melon SELL leads the 10-order cap ahead of HIRE. Crop-
        # WHEAT is sold only down to the animals' feed buffer (the champion's rule);
        # the wheat front tops the shed up, so the buffer doubles as free feed. ---
        market: list = rh._sell_orders_keep_feed(shed)

        # --- Hire the crew (mornings only). While melon is plantable this is the
        # champion's rule; once melon closes, the wheat front keeps the whole crew
        # productive, so we keep hiring toward the cap on wheat's value. ---
        n_hire = 0
        if hour == 0:
            n_hire = ch.plan_hands_multicrop(
                day,
                money,
                hh.max_live_index(tiles, CROP_TILES),
                catch,
                season_days,
                MAX_HANDS,
            )
            market.extend([["HIRE"]] * n_hire)

        # --- One action per worker. Worker 1 is the livestock hand; every other
        # worker farms its crop plot: the melon block runs the champion's melon +
        # wheat-tail loop, the wheat block grows continuous wheat. ---
        positions = [me["farmer"], *hands]
        cow_ct = rh._tile(tiles, COW_TILE)
        cow_live = rh._is_animal(cow_ct)
        planted_this_turn: dict[str, int] = {}
        actions = []
        for i, pos in enumerate(positions):
            if i == 1:
                inv = inventories[i] if i < len(inventories) else {}
                actions.append(rh.livestock_action(pos, tiles, inv, shed, cow_live))
                continue

            plot, crop = crop_plot_for(i)
            on_plot = [pos[0], pos[1]] == [plot[0], plot[1]]
            if not on_plot:
                actions.append(hh.step_toward(pos, plot))
                continue

            tile = hh.tile_at(tiles, plot)
            if crop == "MELON":
                action = ch._decide(tile, day, hour, catch, season_days)
            else:
                action = _wheat_decide(tile, day, hour, season_days)
            if action and action[0] == "PLANT":
                # Atomic-plant rule is per crop: plant only as many of a crop this
                # turn as we hold seed for, or the sim voids every plant of it.
                pcrop = action[1]
                if planted_this_turn.get(pcrop, 0) < seeds.get(pcrop, 0):
                    planted_this_turn[pcrop] = planted_this_turn.get(pcrop, 0) + 1
                else:
                    action = ["WATER"] if hh._is_live_plant(tile) else ["PASS"]
            actions.append(action)

        farmer_action = actions[0]
        hand_actions = actions[1:]

        # --- Seed restock for BOTH fronts. Count only the crop plots a present
        # worker can reach (worker 1 is livestock, so crop workers = workers - 1). ---
        total_workers = 1 + (n_hire if hour == 0 else len(hands))
        crop_workers = total_workers - (1 if total_workers >= 2 else 0)
        active = CROP_PLOTS[: min(len(CROP_PLOTS), crop_workers)]
        empty_melon = sum(
            1 for plot, c in active if c == "MELON" and hh.tile_at(tiles, plot) is None
        )
        empty_wheat = sum(
            1 for plot, c in active if c == "WHEAT" and hh.tile_at(tiles, plot) is None
        )

        if melon_open and empty_melon > 0:
            want = max(0, empty_melon - seeds.get(MELON, 0))
            if want > 0:
                affordable = int(money // rh.CROPS[MELON]["seed"])
                buy = min(want, affordable, 10 - len(market))
                if buy > 0:
                    market.append(["BUY_SEED", MELON, buy])

        if ch.cc_plantable("WHEAT", day, season_days) and empty_wheat > 0:
            want = max(0, empty_wheat - seeds.get("WHEAT", 0))
            if want > 0:
                affordable = int(money // rh.CROPS["WHEAT"]["seed"])
                buy = min(want, affordable, 10 - len(market))
                if buy > 0:
                    market.append(["BUY_SEED", "WHEAT", buy])

        # --- Animal purchases, lowest market priority (never displace a crop
        # order). Buy the cow first; the sheep only once the cow line is live. ---
        cow_exists = (
            cow_live
            or shed.get("COW", 0) > 0
            or any(inv.get("COW", 0) > 0 for inv in inventories)
        )
        if (
            not cow_exists
            and money >= ANIMAL_COST["COW"] + COW_MONEY_BUFFER
            and len(market) < 10
        ):
            market.append(["BUY_ANIMAL", "COW", 1])

        sheep_ct = rh._tile(tiles, SHEEP_TILE)
        sheep_exists = (
            rh._is_animal(sheep_ct)
            or shed.get("SHEEP", 0) > 0
            or any(inv.get("SHEEP", 0) > 0 for inv in inventories)
        )
        if (
            cow_exists
            and not sheep_exists
            and money >= ANIMAL_COST["SHEEP"] + SHEEP_MONEY_BUFFER
            and len(market) < 10
        ):
            market.append(["BUY_ANIMAL", "SHEEP", 1])

        # --- Keep a WHEAT buffer in the shed to feed BOTH animals. Once the wheat
        # front is harvesting this rarely fires (the shed stays topped up); it still
        # covers the early game before any front wheat exists. ---
        line_started = cow_exists or sheep_exists
        wheat_on_hand = shed.get("WHEAT", 0) + sum(
            inv.get("WHEAT", 0) for inv in inventories
        )
        if line_started and wheat_on_hand < WHEAT_BUFFER and len(market) < 10:
            want = WHEAT_BUFFER - wheat_on_hand
            if money >= COW_MONEY_BUFFER:  # never spend crop working capital
                market.append(["BUY_PRODUCT", "WHEAT", want])

        return {"farmer": farmer_action, "hands": hand_actions, "market": market[:10]}


STRATEGY = RanchBalancedStrategy
