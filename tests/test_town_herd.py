"""town_herd (#302): the town's shops pick the kind of the next animal, nothing else."""

from __future__ import annotations

from kaggisim import economy
from strategies import town_herd as th
from strategies.four_at_eight import FourAtEightStrategy


def test_the_tick_count_is_derived_from_the_sims_tables():
    cfg = economy.CONFIG_DEFAULTS
    assert th.SHOP_TICKS_PER_DAY == cfg["turnsPerDay"] // cfg["townShopSellInterval"] == 6
    assert th.KINDS == ("COW", "SHEEP")


def test_shop_drain_counts_instances_doubles_single_product_shops_and_ignores_unknown_names():
    assert th.shop_drain(["BAKERY", "BRUNCH_SPOT"], "MILK") == 0
    assert th.shop_drain(["PIZZA_SHOP"], "MILK") == 6
    assert th.shop_drain(["ICE_CREAM_SHOP", "SMOOTHIE_SHOP", "PIZZA_SHOP"], "MILK") == 18
    assert th.shop_drain(["YARN_STORE"], "WOOL") == 12
    assert th.shop_drain(["YARN_STORE", "YARN_STORE", "PET_CAFE"], "WOOL") == 24
    assert th.shop_drain(["NOT_A_SHOP", None], "MILK") == 0 and th.shop_drain(None, "MILK") == 0


def test_head_supported_is_the_drain_over_one_heads_daily_yield():
    assert th.head_supported(["PIZZA_SHOP"], "COW") == 6 * economy.ANIMALS["COW"]["interval"] == 12
    assert th.head_supported(["YARN_STORE"], "SHEEP") == 12 * economy.ANIMALS["SHEEP"]["interval"] == 36
    assert th.head_supported(["BAKERY"], "COW") == 0


def _tiles(*animals):
    row = [{"animal": a} if a else None for a in animals]
    return [row + ["LOCKED", {"kind": "WEED"}]]


def test_our_head_counts_placed_and_pending_of_one_kind_only():
    assert th.our_head(_tiles("SHEEP", "SHEEP", "COW", None), {"SHEEP": 2, "COW": 5}, "SHEEP") == 4
    assert th.our_head(_tiles("SHEEP", "SHEEP", "COW", None), {"SHEEP": 2, "COW": 5}, "COW") == 6
    assert th.our_head([], None, "COW") == 0


def test_town_kind_follows_the_room_the_town_leaves_and_ties_to_cow():
    assert th.town_kind(["BAKERY", "BRUNCH_SPOT"], 0, 0) is None
    assert th.town_kind([], 0, 0) is None
    assert th.town_kind(["YARN_STORE"], 0, 0) == "SHEEP"
    assert th.town_kind(["PIZZA_SHOP"], 0, 0) == "COW"
    assert th.town_kind(["PIZZA_SHOP", "YARN_STORE"], 0, 0) == "SHEEP"          # 36 > 12
    assert th.town_kind(["PIZZA_SHOP", "YARN_STORE"], 0, 25) == "COW"           # 11 < 12
    assert th.town_kind(["PIZZA_SHOP", "YARN_STORE"], 0, 24) == "COW"           # 12 == 12: tie
    assert th.town_kind(["PIZZA_SHOP"], 12, 0) == "COW"                         # 0 == 0: tie, never SHEEP without demand
    assert th.town_kind(["YARN_STORE"], 0, 40) == "COW"                         # 36-40=-4 < 0-0=0: over-supplied wool


def _obs(shops, *animals, shed=None, rival_sheep=0, player=1):
    rival = [[{"animal": "SHEEP"}] * rival_sheep]
    ours = _tiles(*animals)
    farms = [{"tiles": rival}, {"tiles": ours}] if player == 1 else [{"tiles": ours}, {"tiles": rival}]
    return {"player": player, "farms": farms, "private": {"shed": shed or {}},
            "town": {"unlocked_shops": list(shops)}}


def test_herd_preference_reads_the_town_and_our_farm():
    p = th.TownHerdStrategy()
    assert p.name == "town_herd" and isinstance(p, FourAtEightStrategy) and p.FOURTH_DAY == 8
    assert p.herd_preference(_obs(["YARN_STORE"], "COW", "COW")) == "SHEEP"
    assert p.herd_preference(_obs(["PIZZA_SHOP"], "SHEEP")) == "COW"
    assert p.herd_preference(_obs(["PIZZA_SHOP", "YARN_STORE"], "SHEEP", shed={"SHEEP": 24})) == "COW"   # 36-25 < 12-0
    assert p.owned(_obs([], "COW", "SHEEP", "SHEEP", shed={"COW": 2})) == (3, 2)


def test_herd_preference_falls_through_to_the_inherited_rule_when_the_town_is_silent():
    p = th.TownHerdStrategy()
    assert p.herd_preference(_obs(["BAKERY", "PET_CAFE"], "COW", rival_sheep=0)) is None
    assert p.herd_preference(_obs(["BAKERY", "PET_CAFE"], "COW", rival_sheep=2)) == "COW"   # rival_aware's rule
    assert p.herd_preference(_obs([], rival_sheep=9)) == "COW"
    # the rival's sheep change nothing once the town speaks
    assert p.herd_preference(_obs(["YARN_STORE"], rival_sheep=9)) == "SHEEP"


def test_herd_preference_degrades_to_the_inherited_rule_on_a_malformed_observation():
    p = th.TownHerdStrategy()
    assert p.herd_preference({}) is None
    assert p.herd_preference({"player": 3, "farms": [], "private": None, "town": None}) is None
    assert p.herd_preference({"player": 0, "farms": [{"tiles": None}, "x"], "town": {"unlocked_shops": "YARN_STORE"}}) is None


def test_every_other_seam_is_four_at_eights():
    from harness import sheep_bench as sb
    assert set(th.TownHerdStrategy.__dict__) & set(sb._seam_names()) == {"herd_preference"}
    p, q = th.TownHerdStrategy(), FourAtEightStrategy()
    assert p.livestock_workers(8) == q.livestock_workers(8) and p.CAPS == q.CAPS and p.buy_order() == q.buy_order()


def test_registered():
    from strategies import load
    assert load("town_herd") is th.TownHerdStrategy
