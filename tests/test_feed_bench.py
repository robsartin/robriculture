"""The lean_feed experiment's declared constants and the pure parts it adds.

The verdict is `rival_bench`'s; the cash-flow reading is `cashflow`'s; new
here: boards read off a game's own steps by the day-boundary rule cashflow
established, the three feed/head bars, and a buffer-only arm B.
"""

from __future__ import annotations

from harness import feed_bench as fdb
from harness import cashflow as cf
from harness import reserve_bench as rsb
from harness import rival_bench as rb


def test_the_declared_constants():
    # Declared on #262 before any code; not to be tuned.
    assert fdb.CONTENDER == "lean_feed" and fdb.CHAMPION == "third_herder" and fdb.BASELINE == "herd_first"
    assert fdb.SEEDS == tuple(range(960, 976)) and fdb.CONTROL_SEED == 960
    assert fdb.CHAMPION_BAR == 0.60 and fdb.ANCHOR_BAR == 0.90 and fdb.ARM_B == "lean_buffer"
    assert fdb.FEED_DAY0_BAR == 250 and list(fdb.FEED_DAYS) == [1, 2, 3, 4, 5] and fdb.FEED_DAYS_BAR == 1200
    assert (fdb.HEAD_DAY, fdb.HEAD_BAR, fdb.CROP_DAY, fdb.PLANTED_GAP_BAR) == (8, 8, 12, 12)


def test_the_seeds_are_fresh_against_every_range_already_spent():
    # 944 was #258's control seed; 929-943 and 945-959 were declared and never played, not reused.
    spent = set(range(100, 116)) | set(range(200, 216)) | set(range(300, 332)) \
        | set(range(400, 416)) | set(range(500, 516)) | set(range(600, 616)) \
        | set(range(700, 704)) | set(range(800, 960))
    assert not spent & set(fdb.SEEDS)


def test_the_readers_and_the_verdict_are_imported_not_copied():
    assert fdb.daily_cashflow is cf.daily_cashflow and fdb.play is cf.play
    assert fdb.criterion is rb.criterion and fdb.paired_external_rows is rb.paired_external_rows
    assert fdb.MADHUR == rsb.MADHUR and fdb.PILKWANG == rsb.PILKWANG and fdb.REFERENCE == rsb.REFERENCE


def _step(money, day, tiles=None, hands=0, market=None):
    farm = {"money": money, "tiles": tiles or [], "hands": [[0, 0]] * hands, "unlocked_quadrants": ["NW"]}
    return {"action": {"farmer": ["PASS"], "hands": [], "market": market or []},
            "observation": {"day": day, "hour": 0, "player": 0, "farms": [farm],
                            "market": {"prices": {"WHEAT": 25}, "inventory": {}},
                            "private": {"shed": {}, "seeds": {}, "inventories": []}}}


def _cow(): return {"kind": "PASTURE", "animal": "COW", "yield_units": 0, "fed_today": False, "cared_today": False}
def _melon(): return {"kind": "PLANT", "crop": "MELON"}


def test_board_on_day_is_the_state_the_days_last_turn_produced():
    """The sim stamps the state after a day's last turn with the next day; the
    board for day D is the observation whose prior observation is day D (last
    wins) -- the rule cashflow's close column uses."""
    steps = [[_step(3000, 0)], [_step(2900, 0, tiles=[[_cow()]], hands=2)],
             [_step(2800, 1, tiles=[[_cow(), _cow()]], hands=3)],      # produced by day 0's last turn
             [_step(2700, 1, tiles=[[_cow(), _cow(), _melon()]], hands=4)],
             [_step(2600, 2, tiles=[[_cow()]], hands=1)]]               # produced by day 1's last turn
    day0, day1 = fdb.board_on_day(steps, 0, 0), fdb.board_on_day(steps, 0, 1)
    assert len(day0["hands"]) == 3 and sum(1 for t in day0["tiles"][0] if "animal" in t) == 2
    assert len(day1["hands"]) == 1
    assert fdb.board_on_day(steps, 0, 7) is None


def test_the_crew_is_read_off_the_last_observation_labelled_the_day_not_the_boundary_board():
    """Hands are cleared at the rollover, so the board a day's last turn produces
    shows none; the crew that worked the day is on the last observation labelled
    the day. Head and planted tiles persist across the rollover and stay on the
    boundary board."""
    steps = [[_step(3000, 0)], [_step(2900, 0, tiles=[[_cow()]], hands=2)],
             [_step(2800, 1, tiles=[[_cow(), _cow()]], hands=0)],
             [_step(2700, 1, tiles=[[_cow(), _cow(), _melon()]], hands=4)],
             [_step(2600, 2, tiles=[[_cow()]], hands=0)]]
    assert fdb.hands_on_day(steps, 0, 0) == 2 and fdb.hands_on_day(steps, 0, 1) == 4
    assert fdb.hands_on_day(steps, 0, 7) is None


def _reading(feed0=100, feed15=600, head=8, planted=40):
    return {"feed_day0": feed0, "feed_days_1_5": feed15, "head_placed_8": head, "hands_8": 2, "planted_12": planted}


def test_each_mechanism_bar_can_fail_alone_and_names_itself():
    assert fdb.mechanism_failures(_reading()) == []
    assert fdb.mechanism_failures(_reading(feed0=251)) == ["feed_day0"]
    assert fdb.mechanism_failures(_reading(feed15=1201)) == ["feed_days_1_5"]
    assert fdb.mechanism_failures(_reading(head=7)) == ["head_placed_8"]
    assert fdb.mechanism_failures(_reading(feed0=664, feed15=2467, head=6)) == ["feed_day0", "feed_days_1_5", "head_placed_8"]


def test_the_crop_line_is_paired_within_the_gap():
    assert fdb.crop_line_ok(_reading(planted=36), _reading(planted=48)) is True
    assert fdb.crop_line_ok(_reading(planted=35), _reading(planted=48)) is False


def test_feed_reading_takes_the_product_column_and_the_boards():
    """feed_day0 is day 0's product spend, feed_days_1_5 the sum over days 1-5,
    head/planted come off the boards of days 8 and 12, and hands_8 is taken
    through directly -- the crew is read off the day it worked, not the
    post-rollover boundary board, so the board no longer carries it."""
    table = {0: {"spend": {"product": 120}}, 1: {"spend": {"product": 100}}, 2: {"spend": {"product": 100}},
             3: {"spend": {"product": 100}}, 4: {"spend": {"product": 100}}, 5: {"spend": {"product": 100}},
             6: {"spend": {"product": 999}}}
    boards = {8: {"tiles": [[_cow()] * 9]}, 12: {"tiles": [[_melon()] * 40], "hands": []}}
    r = fdb.feed_reading_from(table, boards, 5)
    assert r == {"feed_day0": 120, "feed_days_1_5": 500, "head_placed_8": 9, "hands_8": 5, "planted_12": 40}


def test_the_identity_stub_switches_every_seam_off_and_survives_a_turn():
    """Thirteen hooks off, the two feed seams among them, at their current arity."""
    from kaggle_environments import make
    off = fdb.off_class()()
    assert off.feed_carry(4, 3) is None and off.feed_stock(4) is None and off.spend_floor() is None
    assert off.buy_order() is None and off.layout() is None and off.capital_reserve(8, 4) is None
    obs = make("kaggriculture", configuration={"seed": 1}).state[0].observation
    assert set(off.act(obs)) == {"farmer", "hands", "market"}


def test_arm_b_sizes_the_stock_only_and_is_not_registered():
    from strategies import REGISTRY
    from strategies.herd_first import HerdFirstStrategy
    from strategies.lean_feed import stock_for
    cls = fdb.arm_b_class()
    assert issubclass(cls, HerdFirstStrategy)
    arm = cls()
    assert arm.feed_stock(4) == stock_for(4) == 4 and arm.feed_carry(4, 3) is None
    assert arm.buy_order() == ("hires", "herd", "land", "seed")
    assert fdb.ARM_B not in REGISTRY and fdb.CONTENDER in REGISTRY
