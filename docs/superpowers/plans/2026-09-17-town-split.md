# town_split (#305) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The `town_split` contender and its declared bench, exactly as `docs/superpowers/specs/2026-09-17-town-split-design.md` and the declaration on #305.

**Architecture:** One strategy file overriding one seam on `four_at_eight`, reusing `town_herd`'s pure helpers; one bench in the shape of `harness/town_bench.py` judged under the amended criterion (`identical=`).

**Tech Stack:** Python 3.12, `.venv/bin/python`, pytest.

## Global Constraints
- Pure TDD: failing tests first, RUN and observe, then the code; the report quotes the red.
- Never edit any existing file.
- `.venv/bin/python` only; every command blocking; do NOT run the full suite (the controller does) — only the targeted tests and the one controls smoke.
- Stage by explicit path; never `git add -A`; never stage `.venv`, `external_agents`, `replays/`.
- Declared values verbatim: `CONTENDER = "town_split"`, `CHAMPION = "four_at_eight"`, `SEEDS = tuple(range(1191, 1223))`, `IDENTITY_SEED = 1191`, `CHAMPION_BAR = 0.60`, `ANCHOR_BAR = 0.90`, `KIND_DAY = 12`, `HEAD_DAY = 14`, `COWS_BAR = 3`, `ARM_B = "even_split"`.
- Commit trailer: `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.

---

### Task 1: The contender and the bench

**Files:**
- Create: `strategies/town_split.py`, `harness/split_bench.py`
- Test: `tests/test_town_split.py`, `tests/test_split_bench.py`

**Interfaces:**
- Consumes: `strategies.four_at_eight.FourAtEightStrategy`; `strategies.town_herd.shop_drain`, `our_head`; `harness.town_bench.town_on_day`; `harness.feed_bench.board_on_day`; `harness.farm_census.animals_placed`; `harness.episode_analysis.decompose`; `harness.four8_bench.escapes`; `harness.sheep_bench._seam_names`; `harness.rival_bench.criterion`, `identical_games`, `format_external`, `format_rows`, `paired_external_rows`; `harness.reserve_bench.MADHUR, PILKWANG, REFERENCE`; `harness.external_pool.EXTERNAL_ANCHORS`; `harness.evolve.DEFAULT_ANCHORS`; `harness.cashflow.play`; `harness.triage.head_to_head_rate`, `_default_agents`; `harness.tournament.play_rewards`; `strategies.field_pace.HERD_RAMP_F`.
- Produces: `town_split.sheep_share`, `split_kind`, `TownSplitStrategy` (with `sheep_share`, `owned`, `herd_preference`), `STRATEGY`; `split_bench.even_share`, `is_split_town`, `reading`, `control_game`, `mechanism_failures`, `off_class`, `arm_b_class`, `main`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_town_split.py
"""town_split (#305): the town's drain sets the herd's sheep share, nothing else."""

from __future__ import annotations

import pytest

from strategies import town_split as ts
from strategies.four_at_eight import FourAtEightStrategy


def test_sheep_share_is_the_wool_drain_over_the_wool_and_milk_drain():
    assert ts.sheep_share(["BAKERY", "BRUNCH_SPOT"]) is None
    assert ts.sheep_share([]) is None and ts.sheep_share(None) is None
    assert ts.sheep_share(["YARN_STORE"]) == 1.0
    assert ts.sheep_share(["PIZZA_SHOP"]) == 0.0
    assert ts.sheep_share(["YARN_STORE", "PIZZA_SHOP"]) == pytest.approx(2 / 3)          # 12 / (12 + 6)
    assert ts.sheep_share(["YARN_STORE", "ICE_CREAM_SHOP", "PIZZA_SHOP", "SMOOTHIE_SHOP"]) == pytest.approx(0.4)
    assert ts.sheep_share(["YARN_STORE", "YARN_STORE", "PIZZA_SHOP"]) == pytest.approx(0.8)


def _buys(share, cows, sheep, n):
    out = []
    for _ in range(n):
        k = ts.split_kind(share, cows, sheep)
        out.append(k[0])
        cows, sheep = (cows + 1, sheep) if k == "COW" else (cows, sheep + 1)
    return "".join(out), (cows, sheep)


def test_split_kind_walks_the_herd_to_its_share_from_the_frozen_day_0_herd():
    assert _buys(1.0, 1, 3, 8) == ("SSSSSSSS", (1, 11))
    assert _buys(0.0, 1, 3, 8) == ("CCCCCCCC", (9, 3))
    assert _buys(2 / 3, 1, 3, 8) == ("SCSSCSSC", (4, 8))
    assert _buys(0.4, 1, 3, 8) == ("CCCSCCSC", (7, 5))
    assert ts.split_kind(0.5, 0, 0) == "SHEEP" and ts.split_kind(0.5, 0, 1) == "COW"


def _tiles(*animals):
    row = [{"animal": a} if a else None for a in animals]
    return [row + ["LOCKED", {"kind": "WEED"}]]


def _obs(shops, *animals, shed=None, rival_sheep=0, player=1):
    rival = [[{"animal": "SHEEP"}] * rival_sheep]
    ours = _tiles(*animals)
    farms = [{"tiles": rival}, {"tiles": ours}] if player == 1 else [{"tiles": ours}, {"tiles": rival}]
    return {"player": player, "farms": farms, "private": {"shed": shed or {}},
            "town": {"unlocked_shops": list(shops)}}


def test_herd_preference_reads_the_town_and_our_farm():
    p = ts.TownSplitStrategy()
    assert p.name == "town_split" and isinstance(p, FourAtEightStrategy) and p.FOURTH_DAY == 8
    assert p.sheep_share(["YARN_STORE", "PIZZA_SHOP"]) == pytest.approx(2 / 3)
    assert p.owned(_obs([], "COW", "SHEEP", "SHEEP", shed={"COW": 2})) == (3, 2)
    assert p.herd_preference(_obs(["YARN_STORE"], "COW", "SHEEP", "SHEEP", "SHEEP")) == "SHEEP"
    assert p.herd_preference(_obs(["PIZZA_SHOP"], "COW", "SHEEP", "SHEEP", "SHEEP")) == "COW"
    assert p.herd_preference(_obs(["YARN_STORE", "PIZZA_SHOP"], "COW", "SHEEP", "SHEEP", "SHEEP")) == "SHEEP"   # 3 < 3.33
    assert p.herd_preference(_obs(["YARN_STORE", "PIZZA_SHOP"], "COW", "SHEEP", "SHEEP", "SHEEP", shed={"SHEEP": 1})) == "COW"  # 4 < 4 is false


def test_herd_preference_falls_through_to_the_inherited_rule_when_the_town_is_silent():
    p = ts.TownSplitStrategy()
    assert p.herd_preference(_obs(["BAKERY", "PET_CAFE"], "COW", rival_sheep=0)) is None
    assert p.herd_preference(_obs(["BAKERY", "PET_CAFE"], "COW", rival_sheep=2)) == "COW"   # rival_aware's rule
    assert p.herd_preference(_obs(["YARN_STORE"], rival_sheep=9)) == "SHEEP"                 # the town outranks the rival


def test_herd_preference_degrades_to_the_inherited_rule_on_a_malformed_observation():
    p = ts.TownSplitStrategy()
    assert p.herd_preference({}) is None
    assert p.herd_preference({"player": 3, "farms": [], "private": None, "town": None}) is None
    assert p.herd_preference({"player": 0, "farms": [{"tiles": None}, "x"], "town": {"unlocked_shops": "YARN_STORE"}}) is None


def test_every_other_seam_is_four_at_eights():
    from harness import sheep_bench as sb
    assert set(ts.TownSplitStrategy.__dict__) & set(sb._seam_names()) == {"herd_preference"}
    p, q = ts.TownSplitStrategy(), FourAtEightStrategy()
    assert p.livestock_workers(8) == q.livestock_workers(8) and p.CAPS == q.CAPS and p.buy_order() == q.buy_order()


def test_registered():
    from strategies import load
    assert load("town_split") is ts.TownSplitStrategy
```

```python
# tests/test_split_bench.py
"""The town_split experiment's declared constants and pure parts (#305)."""

from __future__ import annotations

import pytest

from harness import rival_bench as rb
from harness import split_bench as sb
from strategies import field_pace as fp


def test_the_declared_constants():
    assert sb.CONTENDER == "town_split" and sb.CHAMPION == "four_at_eight" and sb.ARM_B == "even_split"
    assert sb.SEEDS == tuple(range(1191, 1223)) and sb.IDENTITY_SEED == 1191
    assert sb.CHAMPION_BAR == 0.60 and sb.ANCHOR_BAR == 0.90
    assert (sb.KIND_DAY, sb.HEAD_DAY, sb.COWS_BAR) == (12, 14, 3)
    assert sb.LONESPEAR.startswith("lonespear")
    assert sb.criterion is rb.criterion and sb.identical_games is rb.identical_games and rb.MIN_DECIDED == 8


def test_the_seeds_are_fresh_against_every_range_already_spent():
    spent = set(range(100, 116)) | set(range(200, 216)) | set(range(300, 332)) \
        | set(range(400, 416)) | set(range(500, 516)) | set(range(600, 616)) \
        | set(range(700, 704)) | set(range(800, 960)) | set(range(960, 1191))
    assert not spent & set(sb.SEEDS)


def test_even_share_is_half_when_both_drains_exist():
    assert sb.even_share(["YARN_STORE", "PIZZA_SHOP"]) == 0.5
    assert sb.even_share(["YARN_STORE", "YARN_STORE", "PIZZA_SHOP", "SMOOTHIE_SHOP", "ICE_CREAM_SHOP"]) == 0.5
    assert sb.even_share(["YARN_STORE"]) == 1.0 and sb.even_share(["PIZZA_SHOP"]) == 0.0
    assert sb.even_share(["BAKERY"]) is None and sb.even_share([]) is None


def test_is_split_town_needs_both_drains():
    assert sb.is_split_town(0.5) and sb.is_split_town(2 / 3) and sb.is_split_town(0.01)
    assert not sb.is_split_town(1.0) and not sb.is_split_town(0.0) and not sb.is_split_town(None)


def _board(cows, sheep):
    return {"tiles": [[{"animal": "COW"}] * cows + [{"animal": "SHEEP"}] * sheep + [None, "LOCKED"]]}


def test_reading_and_its_failure(monkeypatch):
    monkeypatch.setattr(sb, "town_on_day", lambda steps, seat, day: ["BAKERY", "YARN_STORE", "SMOOTHIE_SHOP", "FARMERS_MARKET"])
    monkeypatch.setattr(sb, "board_on_day", lambda steps, seat, day: _board(4, 8) if day == 14 else None)
    monkeypatch.setattr(sb, "decompose", lambda steps, seat: {"revenue": {"MILK": 9000, "WOOL": 30000}})
    got = sb.reading("s", 0)
    assert got["share_12"] == pytest.approx(2 / 3)
    assert got["shops_12"] == ("BAKERY", "YARN_STORE", "SMOOTHIE_SHOP", "FARMERS_MARKET")
    assert (got["cows_14"], got["sheep_14"], got["milk"], got["wool"]) == (4, 8, 9000, 30000)
    monkeypatch.setattr(sb, "board_on_day", lambda steps, seat, day: None)
    with pytest.raises(ValueError):
        sb.reading("s", 0)
    monkeypatch.setattr(sb, "board_on_day", lambda steps, seat, day: _board(4, 8))
    monkeypatch.setattr(sb, "town_on_day", lambda steps, seat, day: None)
    with pytest.raises(ValueError):
        sb.reading("s", 0)


def test_control_game_is_the_first_seed_with_a_split_town(monkeypatch):
    shares = {1191: 1.0, 1192: None, 1193: 0.4, 1194: 0.5}
    monkeypatch.setattr(sb, "reading", lambda steps, seat: {"share_12": shares[steps]})
    played = []

    def play(contender, champion, seed):
        played.append((contender, champion, seed))
        return seed
    assert sb.control_game((1191, 1192, 1193, 1194), play=play) == (1193, 1193)
    assert played == [("town_split", "four_at_eight", 1191), ("town_split", "four_at_eight", 1192),
                      ("town_split", "four_at_eight", 1193)]
    assert sb.control_game((1191, 1192), play=play) is None


def test_mechanism_failures_name_the_bars():
    champ = {"share_12": 2 / 3, "shops_12": (), "cows_14": 9, "sheep_14": 3, "milk": 40000, "wool": 20000}
    good = {"share_12": 2 / 3, "shops_12": (), "cows_14": 4, "sheep_14": 8, "milk": 15000, "wool": 45000}
    assert sb.mechanism_failures(good, champ) == []
    assert sb.mechanism_failures({**good, "sheep_14": 3}, champ) == ["sheep_14"]
    assert sb.mechanism_failures({**good, "cows_14": 2}, champ) == ["cows_14"]
    assert sb.mechanism_failures({**good, "cows_14": 3}, champ) == []
    assert sb.mechanism_failures({**good, "wool": 20000}, champ) == ["wool"]
    assert sb.mechanism_failures({**good, "sheep_14": 1, "cows_14": 1, "wool": 1}, champ) == ["sheep_14", "cows_14", "wool"]


def test_the_identity_stub_switches_all_sixteen_seams_off_and_survives_a_turn():
    from harness.sheep_bench import _seam_names
    names = _seam_names()
    assert len(names) == 16
    cls = sb.off_class()
    for n in names:
        assert n in cls.__dict__, f"seam {n} not switched off"
    off = cls()
    assert off.herd_preference({"town": {"unlocked_shops": ["YARN_STORE"]}}) is None and off.herd_target(8) is None
    assert off.HERD_RAMP_F == fp.HERD_RAMP_F and off.CAPS == sb.load_reference().CAPS
    from kaggisim.state import parse
    from kaggle_environments import make
    env = make("kaggriculture", configuration={"seed": 1191, "episodeSteps": 3})
    out = off.act(parse(env.reset()[0].observation))
    assert set(out) >= {"farmer", "hands", "market"}


def test_arm_b_uses_the_even_share():
    from strategies import town_split as ts
    cls = sb.arm_b_class()
    assert issubclass(cls, ts.TownSplitStrategy) and cls.__name__ == "EvenSplit"
    b = cls()
    assert b.sheep_share(["YARN_STORE", "PIZZA_SHOP", "PIZZA_SHOP", "PIZZA_SHOP"]) == 0.5
    assert ts.TownSplitStrategy().sheep_share(["YARN_STORE", "PIZZA_SHOP", "PIZZA_SHOP", "PIZZA_SHOP"]) == pytest.approx(0.4)
    from strategies import REGISTRY
    assert "even_split" not in REGISTRY


def test_play_and_the_reference_are_pinned():
    from harness.cashflow import play
    from harness.reserve_bench import MADHUR, PILKWANG, REFERENCE
    assert sb.play is play and sb.REFERENCE == REFERENCE == "dense_farm"
    assert sb.MADHUR == MADHUR and sb.PILKWANG == PILKWANG
```

- [ ] **Step 2: Run the tests and observe them fail**

Run: `.venv/bin/python -m pytest tests/test_town_split.py tests/test_split_bench.py -q 2>&1 | tail -6`
Expected: collection errors — `ImportError: cannot import name 'town_split' from 'strategies'` and `... 'split_bench' from 'harness'`. Quote the lines in the report.

- [ ] **Step 3: Write `strategies/town_split.py`**

```python
"""town_split: four_at_eight with the herd split in proportion to the town's
drain (#305).

#302's switch (`town_herd`) went to eleven sheep and one cow in every
yarn-store town: it won by 26-33K where no milk shop competed and lost by
7-11K where one did, the milk line thrown away and eleven sheep halving their
own price per head. The sign was right and the dose was wrong.

One decision changes: the kind of the next animal. `herd_preference` sets the
herd's sheep share from the town's wool drain over its wool and milk drain
together (`town_herd.shop_drain`, from the sim's own tables) and asks for a
sheep while the sheep are short of that share of the herd including the next
head. A yarn store alone means every head a sheep; a milk shop alone every
head a cow; a yarn store beside a pizza shop eight sheep to four cows at
twelve head. When the town takes neither, the inherited rule runs. The
frozen rule's day-0 herd (three sheep, one cow, before the first shop) is
untouched; everything else is four_at_eight's.

Declared before measurement: the rule, and the controls and criterion in
`harness/split_bench.py` (posted to #305 before any code), judged under
ADR-0007's amendment of 2026-09-16.
"""

from __future__ import annotations

from strategies.four_at_eight import FourAtEightStrategy
from strategies.town_herd import our_head, shop_drain


def sheep_share(shops):
    """The share of the herd that should be sheep: the town's wool drain over
    its wool and milk drain together, or ``None`` when it takes neither."""
    wool, milk = shop_drain(shops, "WOOL"), shop_drain(shops, "MILK")
    if wool + milk == 0:
        return None
    return wool / (wool + milk)


def split_kind(share, cows, sheep):
    """The next head: SHEEP while the sheep are short of `share` of the herd
    that includes it, else COW."""
    return "SHEEP" if sheep < share * (cows + sheep + 1) else "COW"


class TownSplitStrategy(FourAtEightStrategy):
    """`four_at_eight` with the herd split by the town's drain."""

    name = "town_split"
    benchmark = False

    def sheep_share(self, shops):
        """The module's `sheep_share`; arm B overrides it with an even split."""
        return sheep_share(shops)

    def owned(self, obs):
        """(cows, sheep) we have placed or pending."""
        me = obs["farms"][obs["player"]]
        shed = (obs.get("private") or {}).get("shed") or {}
        tiles = me.get("tiles")
        return our_head(tiles, shed, "COW"), our_head(tiles, shed, "SHEEP")

    def herd_preference(self, obs):
        """`split_kind` at the town's share and our head; the inherited rule
        when the town takes neither product or the observation is malformed
        (ADR-0006)."""
        try:
            shops = (obs.get("town") or {}).get("unlocked_shops") or []
            share = self.sheep_share(shops)
            kind = None if share is None else split_kind(share, *self.owned(obs))
        except (LookupError, TypeError, AttributeError):
            kind = None
        return kind if kind is not None else super().herd_preference(obs)


STRATEGY = TownSplitStrategy
```

- [ ] **Step 4: Write `harness/split_bench.py`**

```python
"""The town_split experiment (#305): controls, criterion, arm B -- judged under
ADR-0007's amendment of 2026-09-16 (identical play leaves the denominator).

Declared on #305 before any code. Controls first -- identity (every seam off
is the frozen benchmark to the value) and mechanism, by procedure: the draw
depends on both boards, so the control game is the first seed in SEEDS whose
contender-vs-champion game has a split town on day 12 (both a wool and a milk
drain); on it the contender holds more sheep than the champion at day 14,
keeps at least COWS_BAR cows, and earns more wool. No split town, or a bar
missed, is a VOID run (exit 2). Then rival_bench's criterion with the
identical-play count: >= 60% of the *decided* games vs four_at_eight (VOID if
fewer than MIN_DECIDED are decided), >= 90% vs each anchor, paired external
non-regression. Arm B (`even_split`) is recorded, never gated.

    .venv/bin/python -m harness.split_bench --controls
    .venv/bin/python -m harness.split_bench --criterion
    .venv/bin/python -m harness.split_bench --recorded
"""

from __future__ import annotations

import argparse
import os

from harness.cashflow import play  # noqa: F401  -- pinned by the tests
from harness.episode_analysis import decompose
from harness.evolve import DEFAULT_ANCHORS
from harness.external_pool import EXTERNAL_ANCHORS
from harness.farm_census import animals_placed
from harness.feed_bench import board_on_day
from harness.four8_bench import escapes
from harness.reserve_bench import MADHUR, PILKWANG, REFERENCE  # noqa: F401  -- pinned by the tests
from harness.rival_bench import (  # noqa: F401  -- pinned by the tests to rival_bench's own
    criterion,
    format_external,
    format_rows,
    identical_games,
    paired_external_rows,
)
from harness.sheep_bench import _seam_names
from harness.town_bench import town_on_day
from strategies import field_pace as fp
from strategies import town_split as ts
from strategies.town_herd import shop_drain

CONTENDER = "town_split"
CHAMPION = "four_at_eight"
SEEDS = tuple(range(1191, 1223))
IDENTITY_SEED = 1191
CHAMPION_BAR = 0.60
ANCHOR_BAR = 0.90
KIND_DAY = 12
HEAD_DAY = 14
COWS_BAR = 3
ARM_B = "even_split"
LONESPEAR = EXTERNAL_ANCHORS[1]
assert LONESPEAR.startswith("lonespear"), LONESPEAR  # the pool order is the pin (review)


def load_reference():
    from strategies import load
    return load(REFERENCE)


def even_share(shops):
    """Arm B's share: a half whenever the town takes both wool and milk, one
    or zero when it takes only one, ``None`` when neither."""
    wool, milk = shop_drain(shops, "WOOL"), shop_drain(shops, "MILK")
    if wool + milk == 0:
        return None
    if milk == 0:
        return 1.0
    if wool == 0:
        return 0.0
    return 0.5


def is_split_town(share) -> bool:
    """Both a wool and a milk drain: the share is strictly between 0 and 1."""
    return share is not None and 0 < share < 1


def reading(steps, seat) -> dict:
    """One side's day-12 share and shops, its herd at day 14, and its milk and
    wool revenue."""
    shops = town_on_day(steps, seat, KIND_DAY)
    if shops is None:
        raise ValueError(f"no observation for day {KIND_DAY}: the game ended early")
    board = board_on_day(steps, seat, HEAD_DAY)
    if board is None:
        raise ValueError(f"no board for day {HEAD_DAY}: the game ended early")
    placed = animals_placed(board["tiles"])
    rev = decompose(steps, seat)["revenue"]
    return {"share_12": ts.sheep_share(shops), "shops_12": tuple(shops),
            "cows_14": placed.get("COW", 0), "sheep_14": placed.get("SHEEP", 0),
            "milk": rev.get("MILK", 0), "wool": rev.get("WOOL", 0)}


def control_game(seeds=SEEDS, play=None):
    """The mechanism control's game, by procedure: `(seed, steps)` for the
    first seed whose contender (seat 0) vs champion game has a split town on
    day 12; ``None`` when no seed does."""
    play = play or _default_play()
    for seed in seeds:
        steps = play(CONTENDER, CHAMPION, seed)
        if is_split_town(reading(steps, 0)["share_12"]):
            return seed, steps
    return None


def _default_play():  # pragma: no cover
    from harness.cashflow import play as live_play
    return live_play


def mechanism_failures(contender, champion) -> list:
    """Control 2's bars; the names of the ones that did not hold."""
    failed = []
    if not contender["sheep_14"] > champion["sheep_14"]:
        failed.append("sheep_14")
    if contender["cows_14"] < COWS_BAR:
        failed.append("cows_14")
    if not contender["wool"] > champion["wool"]:
        failed.append("wool")
    return failed


def off_class():
    """Every seam off (sixteen), the reference's caps, and the frozen herd ramp."""
    from strategies import load
    body = {n: (lambda self, *a, **k: None) for n in _seam_names()}
    body["CAPS"] = load_reference().CAPS
    body["HERD_RAMP_F"] = fp.HERD_RAMP_F
    return type("Off", (load(CONTENDER),), body)


def arm_b_class():
    """`town_split` at an even share whenever the town takes both. Never registered."""
    from strategies import load
    return type("EvenSplit", (load(CONTENDER),), {"sheep_share": lambda self, shops: even_share(shops)})


# --- live games -------------------------------------------------------------

def _arm_b_agents(name):  # pragma: no cover
    from harness.triage import _default_agents
    from kaggisim.strategy import make_agent
    arm_b = arm_b_class()
    default_agents = _default_agents()

    def agents(who):
        return make_agent(arm_b()) if who == name else default_agents(who)
    return agents


def run_controls(seed=IDENTITY_SEED):  # pragma: no cover
    os.environ.setdefault("ROBRICULTURE_STRICT", "1")
    from harness.tournament import play_rewards
    from kaggisim.strategy import make_agent
    from strategies import load
    out = {}
    off = off_class()
    base = play_rewards(make_agent(load(REFERENCE)()), make_agent(load(REFERENCE)()), seed)
    got = play_rewards(make_agent(off()), make_agent(load(REFERENCE)()), seed)
    precondition_ok = base[0] > 0
    out["identity"] = {"ok": got == base and precondition_ok, "base": base, "got": got,
                       "precondition_ok": precondition_ok}
    found = control_game()
    if found is None:
        out["mechanism"] = {"ok": False, "failed": ["no_split_town"], "seed": None,
                            "contender": None, "champion": None}
        return out
    control_seed, steps = found
    contender, champion = reading(steps, 0), reading(steps, 1)
    contender["escapes"], champion["escapes"] = escapes(steps, 0), escapes(steps, 1)
    failed = mechanism_failures(contender, champion)
    out["mechanism"] = {"ok": not failed, "failed": failed, "seed": control_seed,
                        "contender": contender, "champion": champion}
    return out


def run_criterion(seeds=SEEDS):  # pragma: no cover
    os.environ.setdefault("ROBRICULTURE_STRICT", "1")
    from harness.triage import head_to_head_rate
    champion_row = head_to_head_rate(CONTENDER, CHAMPION, seeds)
    identical = identical_games(CONTENDER, CHAMPION, seeds)
    anchor_rows = [head_to_head_rate(CONTENDER, a, seeds) for a in DEFAULT_ANCHORS]
    pairs = paired_external_rows(CONTENDER, CHAMPION, seeds)
    return champion_row, identical, anchor_rows, pairs


def run_recorded(seeds=SEEDS):  # pragma: no cover
    os.environ.setdefault("ROBRICULTURE_STRICT", "1")
    from harness.triage import head_to_head_rate
    agents = _arm_b_agents(ARM_B)
    row = head_to_head_rate(ARM_B, CHAMPION, seeds, agents=agents)
    identical = identical_games(ARM_B, CHAMPION, seeds, agents=agents)
    return row, identical


def main(argv=None):  # pragma: no cover
    os.environ.setdefault("ROBRICULTURE_STRICT", "1")
    ap = argparse.ArgumentParser(description="town_split: the herd in proportion to the town's drain")
    ap.add_argument("--controls", action="store_true")
    ap.add_argument("--criterion", action="store_true")
    ap.add_argument("--recorded", action="store_true", help="arm B (recorded, not gated)")
    args = ap.parse_args(argv)

    if args.recorded:
        row, identical = run_recorded()
        print(format_rows([row]))
        decided = row["games"] - identical
        print(f"recorded, not gated: arm B ({ARM_B}: an even share whenever the town takes both) vs {CHAMPION}: "
              f"{row['wins']}/{decided} decided ({identical} identical)")
        return 0

    do_controls = args.controls or not args.criterion
    do_criterion = args.criterion or not args.controls

    if do_controls:
        ctl = run_controls()
        print(f"control identity: {'OK' if ctl['identity']['ok'] else 'FAIL -- RUN VOID'}  {ctl['identity']}")
        m = ctl["mechanism"]
        print(f"control mechanism: {'OK' if m['ok'] else 'FAIL -- RUN VOID'}  seed {m['seed']}  "
              f"(declared: the first seed with a split town on day {KIND_DAY}; sheep at day {HEAD_DAY} > {CHAMPION}'s, "
              f"cows >= {COWS_BAR}, wool > {CHAMPION}'s)  contender {m['contender']}  {CHAMPION} {m['champion']}  "
              f"failed={m['failed'] or 'none'}")
        if not all(r["ok"] for r in ctl.values()):
            print("a control failed: the run is VOID and arm B is NOT scored")
            return 2

    if do_criterion:
        champion_row, identical, anchor_rows, pairs = run_criterion()
        print(format_rows([champion_row] + anchor_rows))
        print(format_external(pairs))
        v = criterion(champion_row, anchor_rows, CHAMPION_BAR, ANCHOR_BAR, external_pairs=pairs, identical=identical)
        verdict = "VOID (under-powered)" if v["void"] else ("PROMOTE" if v["passed"] else "REJECTED")
        print(f"champion {champion_row['wins']}/{v['decided']} decided = {v['champion_rate']:.1%} (bar {CHAMPION_BAR:.0%}; "
              f"{v['identical']} identical of {champion_row['games']}); failing limbs: {v['failing'] or 'none'} -> {verdict}; "
              f"paired rows (contender, champion): madhur {v['external'].get(MADHUR)}, "
              f"pilkwang {v['external'].get(PILKWANG)}, lonespear {v['external'].get(LONESPEAR)}")
        if v["void"]:
            return 2
        return 0 if v["passed"] else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Run the targeted tests and observe them pass**

Run: `.venv/bin/python -m pytest tests/test_town_split.py tests/test_split_bench.py -q 2>&1 | tail -5`
Expected: all pass. If a `split_kind` sequence in the test disagrees with the code, the code is the declared rule (spec §The change); fix the test's arithmetic, not the rule, and say so in the report.

- [ ] **Step 6: Smoke the controls once (blocking; the mechanism control plays seeds in order until it finds a split town, up to a few minutes), then commit**

Run: `.venv/bin/python -m harness.split_bench --controls 2>&1 | grep -v Warning | tail -4`
Expected: `control identity: OK ...` and `control mechanism: OK  seed <N> ...`. Quote both lines in the report. If either says FAIL, do not change the bars: commit anyway and report DONE_WITH_CONCERNS with the lines quoted.

```bash
git add strategies/town_split.py harness/split_bench.py tests/test_town_split.py tests/test_split_bench.py
git commit -m "feat(#305): town_split -- the herd in proportion to the town's drain, with its declared bench

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```
