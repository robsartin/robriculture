# even_split (#310) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The `even_split` contender and its declared bench, exactly as `docs/superpowers/specs/2026-09-18-even-split-design.md` and the declaration on #310.

**Architecture:** One strategy file overriding one method on `town_split`; one bench in the shape of `harness/split_bench.py`, judged with `rival_bench.decided_row`.

**Tech Stack:** Python 3.12, `.venv/bin/python`, pytest.

## Global Constraints
- Pure TDD: failing tests first, RUN and observe, then the code; the report quotes the red.
- Never edit any existing file.
- `.venv/bin/python` only; every command blocking; do NOT run the full suite (the controller does) — only the targeted tests and the one controls smoke.
- Stage by explicit path; never `git add -A`; never stage `.venv`, `external_agents`, `replays/`.
- Declared values verbatim: `CONTENDER = "even_split"`, `CHAMPION = "town_split"`, `SEEDS = tuple(range(1223, 1271))`, `IDENTITY_SEED = 1223`, `CHAMPION_BAR = 0.60`, `ANCHOR_BAR = 0.90`, `KIND_DAY = 12`, `HEAD_DAY = 14`, `BALANCE_BAR = 2`, `ARM_B = "half_always"`.
- Commit trailer: `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.

---

### Task 1: The contender and the bench

**Files:**
- Create: `strategies/even_split.py`, `harness/even_bench.py`
- Test: `tests/test_even_split.py`, `tests/test_even_bench.py`

**Interfaces:**
- Consumes: `strategies.town_split.TownSplitStrategy`, `sheep_share`; `strategies.town_herd.shop_drain`; `harness.town_bench.town_on_day`; `harness.feed_bench.board_on_day`; `harness.farm_census.animals_placed`; `harness.episode_analysis.decompose`; `harness.four8_bench.escapes`; `harness.sheep_bench._seam_names`; `harness.rival_bench.criterion`, `decided_row`, `format_external`, `format_rows`, `paired_external_rows`; `harness.reserve_bench.MADHUR, PILKWANG, REFERENCE`; `harness.external_pool.EXTERNAL_ANCHORS`; `harness.evolve.DEFAULT_ANCHORS`; `harness.cashflow.play`; `harness.triage.head_to_head_rate`, `_default_agents`; `harness.tournament.play_rewards`; `strategies.field_pace.HERD_RAMP_F`.
- Produces: `even_split.even_share`, `EvenSplitStrategy`, `STRATEGY`; `even_bench.half_share`, `is_uneven_town`, `reading`, `control_game`, `mechanism_failures`, `off_class`, `arm_b_class`, `main`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_even_split.py
"""even_split (#310): a half share whenever the town takes both, nothing else."""

from __future__ import annotations

from strategies import even_split as es
from strategies.town_split import TownSplitStrategy


def test_even_share_is_a_half_whenever_the_town_takes_both():
    assert es.even_share(["BAKERY", "BRUNCH_SPOT"]) is None and es.even_share([]) is None and es.even_share(None) is None
    assert es.even_share(["YARN_STORE"]) == 1.0 and es.even_share(["YARN_STORE", "YARN_STORE"]) == 1.0
    assert es.even_share(["PIZZA_SHOP"]) == 0.0 and es.even_share(["SMOOTHIE_SHOP", "ICE_CREAM_SHOP"]) == 0.0
    assert es.even_share(["YARN_STORE", "PIZZA_SHOP"]) == 0.5
    assert es.even_share(["YARN_STORE", "YARN_STORE", "PIZZA_SHOP", "SMOOTHIE_SHOP", "ICE_CREAM_SHOP"]) == 0.5


def _tiles(*animals):
    row = [{"animal": a} if a else None for a in animals]
    return [row + ["LOCKED", {"kind": "WEED"}]]


def _obs(shops, *animals, shed=None, rival_sheep=0, player=1):
    rival = [[{"animal": "SHEEP"}] * rival_sheep]
    ours = _tiles(*animals)
    farms = [{"tiles": rival}, {"tiles": ours}] if player == 1 else [{"tiles": ours}, {"tiles": rival}]
    return {"player": player, "farms": farms, "private": {"shed": shed or {}},
            "town": {"unlocked_shops": list(shops)}}


def _walk(p, shops, cows, sheep, n):
    out = []
    for _ in range(n):
        k = p.herd_preference(_obs(shops, *(["COW"] * cows + ["SHEEP"] * sheep)))
        out.append(k[0])
        cows, sheep = (cows + 1, sheep) if k == "COW" else (cows, sheep + 1)
    return "".join(out), (cows, sheep)


def test_herd_preference_walks_the_day_0_herd_to_even_and_to_all_sheep():
    p = es.EvenSplitStrategy()
    assert p.name == "even_split" and isinstance(p, TownSplitStrategy) and p.FOURTH_DAY == 8
    assert p.sheep_share(["YARN_STORE", "PIZZA_SHOP", "PIZZA_SHOP", "PIZZA_SHOP"]) == 0.5
    assert _walk(p, ["YARN_STORE", "PIZZA_SHOP"], 1, 3, 8) == ("CCCSCSCS", (6, 6))
    assert _walk(p, ["YARN_STORE"], 1, 3, 8) == ("SSSSSSSS", (1, 11))
    assert _walk(p, ["PIZZA_SHOP"], 1, 3, 8) == ("CCCCCCCC", (9, 3))


def test_herd_preference_falls_through_to_the_inherited_rule():
    p = es.EvenSplitStrategy()
    assert p.herd_preference(_obs(["BAKERY", "PET_CAFE"], "COW", rival_sheep=0)) is None
    assert p.herd_preference(_obs(["BAKERY", "PET_CAFE"], "COW", rival_sheep=2)) == "COW"   # rival_aware's rule
    assert p.herd_preference({}) is None
    assert p.herd_preference({"player": 3, "farms": [], "private": None, "town": None}) is None


def test_the_class_defines_no_seam_of_its_own():
    from harness import sheep_bench as sb
    assert set(es.EvenSplitStrategy.__dict__) & set(sb._seam_names()) == set()
    assert set(es.EvenSplitStrategy.__dict__) >= {"sheep_share", "name"}
    p, q = es.EvenSplitStrategy(), TownSplitStrategy()
    assert p.livestock_workers(8) == q.livestock_workers(8) and p.CAPS == q.CAPS and p.buy_order() == q.buy_order()


def test_registered():
    from strategies import load
    assert load("even_split") is es.EvenSplitStrategy
```

```python
# tests/test_even_bench.py
"""The even_split experiment's declared constants and pure parts (#310)."""

from __future__ import annotations

import pytest

from harness import even_bench as eb
from harness import rival_bench as rb
from strategies import field_pace as fp


def test_the_declared_constants():
    assert eb.CONTENDER == "even_split" and eb.CHAMPION == "town_split" and eb.ARM_B == "half_always"
    assert eb.SEEDS == tuple(range(1223, 1271)) and eb.IDENTITY_SEED == 1223
    assert eb.CHAMPION_BAR == 0.60 and eb.ANCHOR_BAR == 0.90
    assert (eb.KIND_DAY, eb.HEAD_DAY, eb.BALANCE_BAR) == (12, 14, 2)
    assert eb.LONESPEAR.startswith("lonespear")
    assert eb.criterion is rb.criterion and eb.decided_row is rb.decided_row and rb.MIN_DECIDED == 8


def test_the_seeds_are_fresh_against_every_range_already_spent():
    spent = set(range(100, 116)) | set(range(200, 216)) | set(range(300, 332)) \
        | set(range(400, 416)) | set(range(500, 516)) | set(range(600, 616)) \
        | set(range(700, 704)) | set(range(800, 960)) | set(range(960, 1223))
    assert not spent & set(eb.SEEDS)


def test_half_share_is_a_half_whenever_there_is_a_yarn_store():
    assert eb.half_share(["YARN_STORE"]) == 0.5 and eb.half_share(["YARN_STORE", "PIZZA_SHOP"]) == 0.5
    assert eb.half_share(["PIZZA_SHOP"]) == 0.0
    assert eb.half_share(["BAKERY"]) is None and eb.half_share([]) is None


def test_is_uneven_town_needs_both_drains_and_an_unequal_share():
    assert eb.is_uneven_town(2 / 3) and eb.is_uneven_town(0.4) and eb.is_uneven_town(0.8)
    assert not eb.is_uneven_town(0.5) and not eb.is_uneven_town(1.0) and not eb.is_uneven_town(0.0)
    assert not eb.is_uneven_town(None)


def _board(cows, sheep):
    return {"tiles": [[{"animal": "COW"}] * cows + [{"animal": "SHEEP"}] * sheep + [None, "LOCKED"]]}


def test_reading_and_its_failure(monkeypatch):
    monkeypatch.setattr(eb, "town_on_day", lambda steps, seat, day: ["YARN_STORE", "SMOOTHIE_SHOP", "SMOOTHIE_SHOP", "ICE_CREAM_SHOP"])
    monkeypatch.setattr(eb, "board_on_day", lambda steps, seat, day: _board(6, 6) if day == 14 else None)
    monkeypatch.setattr(eb, "decompose", lambda steps, seat: {"revenue": {"MILK": 30000, "WOOL": 35000}})
    got = eb.reading("s", 0)
    assert got["share_12"] == pytest.approx(0.4) and got["even_12"] == 0.5
    assert got["shops_12"] == ("YARN_STORE", "SMOOTHIE_SHOP", "SMOOTHIE_SHOP", "ICE_CREAM_SHOP")
    assert (got["cows_14"], got["sheep_14"], got["balance_14"], got["milk"], got["wool"]) == (6, 6, 0, 30000, 35000)
    monkeypatch.setattr(eb, "board_on_day", lambda steps, seat, day: _board(9, 3))
    assert eb.reading("s", 0)["balance_14"] == 6
    monkeypatch.setattr(eb, "board_on_day", lambda steps, seat, day: None)
    with pytest.raises(ValueError):
        eb.reading("s", 0)
    monkeypatch.setattr(eb, "board_on_day", lambda steps, seat, day: _board(6, 6))
    monkeypatch.setattr(eb, "town_on_day", lambda steps, seat, day: None)
    with pytest.raises(ValueError):
        eb.reading("s", 0)


def test_control_game_is_the_first_seed_with_an_uneven_town(monkeypatch):
    shares = {1223: 1.0, 1224: 0.5, 1225: None, 1226: 0.4, 1227: 2 / 3}
    monkeypatch.setattr(eb, "reading", lambda steps, seat: {"share_12": shares[steps]})
    played = []

    def play(contender, champion, seed):
        played.append((contender, champion, seed))
        return seed
    assert eb.control_game((1223, 1224, 1225, 1226, 1227), play=play) == (1226, 1226)
    assert played == [("even_split", "town_split", s) for s in (1223, 1224, 1225, 1226)]
    assert eb.control_game((1223, 1224, 1225), play=play) is None


def test_mechanism_failures_name_the_bars():
    champ = {"share_12": 0.4, "even_12": 0.5, "shops_12": (), "cows_14": 7, "sheep_14": 5, "balance_14": 2, "milk": 1, "wool": 1}
    good = {**champ, "cows_14": 6, "sheep_14": 6, "balance_14": 0}
    assert eb.mechanism_failures(good, champ) == []
    assert eb.mechanism_failures({**good, "balance_14": 1}, champ) == []
    assert eb.mechanism_failures({**good, "balance_14": 2}, champ) == ["balance_vs_champion"]
    assert eb.mechanism_failures({**good, "balance_14": 3}, {**champ, "balance_14": 6}) == ["balance"]
    assert eb.mechanism_failures({**good, "balance_14": 4}, {**champ, "balance_14": 2}) == ["balance", "balance_vs_champion"]


def test_the_identity_stub_switches_all_sixteen_seams_off_and_survives_a_turn():
    from harness.sheep_bench import _seam_names
    names = _seam_names()
    assert len(names) == 16
    cls = eb.off_class()
    for n in names:
        assert n in cls.__dict__, f"seam {n} not switched off"
    off = cls()
    assert off.herd_preference({"town": {"unlocked_shops": ["YARN_STORE", "PIZZA_SHOP"]}}) is None and off.herd_target(8) is None
    assert off.HERD_RAMP_F == fp.HERD_RAMP_F and off.CAPS == eb.load_reference().CAPS
    from kaggisim.state import parse
    from kaggle_environments import make
    env = make("kaggriculture", configuration={"seed": 1223, "episodeSteps": 3})
    out = off.act(parse(env.reset()[0].observation))
    assert set(out) >= {"farmer", "hands", "market"}


def test_arm_b_uses_half_share():
    from strategies import even_split as es
    cls = eb.arm_b_class()
    assert issubclass(cls, es.EvenSplitStrategy) and cls.__name__ == "HalfAlways"
    b = cls()
    assert b.sheep_share(["YARN_STORE"]) == 0.5 and es.EvenSplitStrategy().sheep_share(["YARN_STORE"]) == 1.0
    assert b.sheep_share(["PIZZA_SHOP"]) == 0.0 and b.sheep_share(["BAKERY"]) is None
    from strategies import REGISTRY
    assert "half_always" not in REGISTRY


def test_play_and_the_reference_are_pinned():
    from harness.cashflow import play
    from harness.reserve_bench import MADHUR, PILKWANG, REFERENCE
    assert eb.play is play and eb.REFERENCE == REFERENCE == "dense_farm"
    assert eb.MADHUR == MADHUR and eb.PILKWANG == PILKWANG
```

- [ ] **Step 2: Run the tests and observe them fail**

Run: `.venv/bin/python -m pytest tests/test_even_split.py tests/test_even_bench.py -q 2>&1 | tail -6`
Expected: collection errors — `ImportError: cannot import name 'even_split' from 'strategies'` and `... 'even_bench' from 'harness'`. Quote the lines in the report.

- [ ] **Step 3: Write `strategies/even_split.py`**

```python
"""even_split: town_split with an even herd whenever the town takes both
wool and milk (#310).

#305's recorded arm B -- exactly this rule -- went 16/16 decided against
four_at_eight where the proportional split went 13/16. The proportional
split's three losses were the towns where a yarn store sat among two or
three milk shops and its weight still tipped the herd to nine sheep; the
yarn store's double drain does not translate into double revenue once nine
sheep sit on it.

One method changes: the share. A half whenever the town drains both
products, all sheep when only wool, all cows when only milk, the inherited
rule when neither. `split_kind`, `owned` and `herd_preference` are
town_split's; the frozen day-0 herd is untouched.

Declared before measurement: the rule, and the controls and criterion in
`harness/even_bench.py` (posted to #310 before any code), judged under
ADR-0007's amendment of 2026-09-16 as corrected 2026-09-17.
"""

from __future__ import annotations

from strategies.town_herd import shop_drain
from strategies.town_split import TownSplitStrategy


def even_share(shops):
    """A half whenever the town takes both wool and milk; one when only wool,
    zero when only milk, ``None`` when neither."""
    wool, milk = shop_drain(shops, "WOOL"), shop_drain(shops, "MILK")
    if wool + milk == 0:
        return None
    if milk == 0:
        return 1.0
    if wool == 0:
        return 0.0
    return 0.5


class EvenSplitStrategy(TownSplitStrategy):
    """`town_split` at a half share whenever the town takes both."""

    name = "even_split"
    benchmark = False

    def sheep_share(self, shops):
        """The module's `even_share`; arm B overrides it with `half_share`."""
        return even_share(shops)


STRATEGY = EvenSplitStrategy
```

- [ ] **Step 4: Write `harness/even_bench.py`**

```python
"""The even_split experiment (#310): controls, criterion, arm B -- judged under
ADR-0007's amendment of 2026-09-16 as corrected 2026-09-17 (`decided_row`).

Declared on #310 before any code. Controls first -- identity (every seam off
is the frozen benchmark to the value) and mechanism, by procedure: the draw
depends on both boards, so the control game is the first seed in SEEDS whose
contender-vs-champion game has an uneven town on day 12 (both drains, and
the proportional share not a half); on it the contender's herd is within
BALANCE_BAR of even and closer to even than the champion's. No uneven town,
or a bar missed, is a VOID run (exit 2). Then rival_bench's criterion on the
decided row: >= 60% of the decided games vs town_split (VOID if fewer than
MIN_DECIDED are decided), >= 90% vs each anchor, paired external
non-regression. Arm B (`half_always`) is recorded, never gated.

    .venv/bin/python -m harness.even_bench --controls
    .venv/bin/python -m harness.even_bench --criterion
    .venv/bin/python -m harness.even_bench --recorded
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
    decided_row,
    format_external,
    format_rows,
    paired_external_rows,
)
from harness.sheep_bench import _seam_names
from harness.town_bench import town_on_day
from strategies import even_split as es
from strategies import field_pace as fp
from strategies import town_split as ts
from strategies.town_herd import shop_drain

CONTENDER = "even_split"
CHAMPION = "town_split"
SEEDS = tuple(range(1223, 1271))
IDENTITY_SEED = 1223
CHAMPION_BAR = 0.60
ANCHOR_BAR = 0.90
KIND_DAY = 12
HEAD_DAY = 14
BALANCE_BAR = 2
ARM_B = "half_always"
LONESPEAR = EXTERNAL_ANCHORS[1]
assert LONESPEAR.startswith("lonespear"), LONESPEAR  # the pool order is the pin (review)


def load_reference():
    from strategies import load
    return load(REFERENCE)


def half_share(shops):
    """Arm B's share: a half whenever the town takes any wool, milk shops or
    not; zero when it takes only milk; ``None`` when neither."""
    wool, milk = shop_drain(shops, "WOOL"), shop_drain(shops, "MILK")
    if wool + milk == 0:
        return None
    if wool == 0:
        return 0.0
    return 0.5


def is_uneven_town(share) -> bool:
    """Both drains present and the proportional share not a half: the one
    kind of town where the two rules disagree."""
    return share is not None and 0 < share < 1 and share != 0.5


def reading(steps, seat) -> dict:
    """One side's day-12 shares and shops, its herd and balance at day 14, and
    its milk and wool revenue."""
    shops = town_on_day(steps, seat, KIND_DAY)
    if shops is None:
        raise ValueError(f"no observation for day {KIND_DAY}: the game ended early")
    board = board_on_day(steps, seat, HEAD_DAY)
    if board is None:
        raise ValueError(f"no board for day {HEAD_DAY}: the game ended early")
    placed = animals_placed(board["tiles"])
    rev = decompose(steps, seat)["revenue"]
    cows, sheep = placed.get("COW", 0), placed.get("SHEEP", 0)
    return {"share_12": ts.sheep_share(shops), "even_12": es.even_share(shops), "shops_12": tuple(shops),
            "cows_14": cows, "sheep_14": sheep, "balance_14": abs(cows - sheep),
            "milk": rev.get("MILK", 0), "wool": rev.get("WOOL", 0)}


def control_game(seeds=SEEDS, play=None):
    """The mechanism control's game, by procedure: `(seed, steps)` for the
    first seed whose contender (seat 0) vs champion game has an uneven town
    on day 12; ``None`` when no seed does."""
    play = play or _default_play()
    for seed in seeds:
        steps = play(CONTENDER, CHAMPION, seed)
        if is_uneven_town(reading(steps, 0)["share_12"]):
            return seed, steps
    return None


def _default_play():  # pragma: no cover
    from harness.cashflow import play as live_play
    return live_play


def mechanism_failures(contender, champion) -> list:
    """Control 2's bars; the names of the ones that did not hold."""
    failed = []
    if contender["balance_14"] > BALANCE_BAR:
        failed.append("balance")
    if not contender["balance_14"] < champion["balance_14"]:
        failed.append("balance_vs_champion")
    return failed


def off_class():
    """Every seam off (sixteen), the reference's caps, and the frozen herd ramp."""
    from strategies import load
    body = {n: (lambda self, *a, **k: None) for n in _seam_names()}
    body["CAPS"] = load_reference().CAPS
    body["HERD_RAMP_F"] = fp.HERD_RAMP_F
    return type("Off", (load(CONTENDER),), body)


def arm_b_class():
    """`even_split` at a half share whenever the town takes any wool. Never registered."""
    from strategies import load
    return type("HalfAlways", (load(CONTENDER),), {"sheep_share": lambda self, shops: half_share(shops)})


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
        out["mechanism"] = {"ok": False, "failed": ["no_uneven_town"], "seed": None,
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
    champion_row = decided_row(CONTENDER, CHAMPION, seeds)
    anchor_rows = [head_to_head_rate(CONTENDER, a, seeds) for a in DEFAULT_ANCHORS]
    pairs = paired_external_rows(CONTENDER, CHAMPION, seeds)
    return champion_row, anchor_rows, pairs


def run_recorded(seeds=SEEDS):  # pragma: no cover
    os.environ.setdefault("ROBRICULTURE_STRICT", "1")
    return decided_row(ARM_B, CHAMPION, seeds, agents=_arm_b_agents(ARM_B))


def main(argv=None):  # pragma: no cover
    os.environ.setdefault("ROBRICULTURE_STRICT", "1")
    ap = argparse.ArgumentParser(description="even_split: an even herd whenever the town takes both")
    ap.add_argument("--controls", action="store_true")
    ap.add_argument("--criterion", action="store_true")
    ap.add_argument("--recorded", action="store_true", help="arm B (recorded, not gated)")
    args = ap.parse_args(argv)

    if args.recorded:
        row = run_recorded()
        print(format_rows([row]))
        decided = row["games"] - row["identical"]
        print(f"recorded, not gated: arm B ({ARM_B}: a half share whenever the town takes any wool) vs {CHAMPION}: "
              f"{row['wins']}W {row['ties']}T {row['losses']}L over {decided} decided ({row['identical']} identical)")
        return 0

    do_controls = args.controls or not args.criterion
    do_criterion = args.criterion or not args.controls

    if do_controls:
        ctl = run_controls()
        print(f"control identity: {'OK' if ctl['identity']['ok'] else 'FAIL -- RUN VOID'}  {ctl['identity']}")
        m = ctl["mechanism"]
        print(f"control mechanism: {'OK' if m['ok'] else 'FAIL -- RUN VOID'}  seed {m['seed']}  "
              f"(declared: the first seed with an uneven town on day {KIND_DAY}; herd balance at day {HEAD_DAY} "
              f"<= {BALANCE_BAR} and < {CHAMPION}'s)  contender {m['contender']}  {CHAMPION} {m['champion']}  "
              f"failed={m['failed'] or 'none'}")
        if not all(r["ok"] for r in ctl.values()):
            print("a control failed: the run is VOID and arm B is NOT scored")
            return 2

    if do_criterion:
        champion_row, anchor_rows, pairs = run_criterion()
        print(format_rows([champion_row] + anchor_rows))
        print(format_external(pairs))
        v = criterion(champion_row, anchor_rows, CHAMPION_BAR, ANCHOR_BAR, external_pairs=pairs,
                      identical=champion_row["identical"])
        verdict = "VOID (under-powered)" if v["void"] else ("PROMOTE" if v["passed"] else "REJECTED")
        print(f"champion {champion_row['wins']}W {champion_row['ties']}T {champion_row['losses']}L over {v['decided']} decided "
              f"= {v['champion_rate']:.1%} (bar {CHAMPION_BAR:.0%}; {v['identical']} identical of {champion_row['games']}); "
              f"failing limbs: {v['failing'] or 'none'} -> {verdict}; "
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

Run: `.venv/bin/python -m pytest tests/test_even_split.py tests/test_even_bench.py -q 2>&1 | tail -5`
Expected: all pass. If a walk sequence in the test disagrees with the code, the code is the declared rule (spec §The change); fix the test's arithmetic, not the rule, and say so in the report.

- [ ] **Step 6: Smoke the controls once (blocking; the mechanism control plays seeds in order until it finds an uneven town, allow up to 10 minutes), then commit**

Run: `.venv/bin/python -m harness.even_bench --controls 2>&1 | grep -v Warning | tail -4`
Expected: `control identity: OK ...` and `control mechanism: OK  seed <N> ...`. Quote both lines in the report. If either says FAIL, do not change the bars: commit anyway and report DONE_WITH_CONCERNS with the lines quoted.

```bash
git add strategies/even_split.py harness/even_bench.py tests/test_even_split.py tests/test_even_bench.py
git commit -m "feat(#310): even_split -- an even herd whenever the town takes both, with its declared bench

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```
