# Champion Designation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Designate the champion by shaped score-share against the anchor pool instead of head-to-head win-rate, and split the single `champion` field into a `gate_opponent` (benchmarks eligible) and a `submit_default` (benchmarks never).

**Architecture:** `harness/promotion.py` gains a share-based ranking (`pool_share_rank`) and a `designate()` that emits the whole artifact body; `harness/champion.json` grows two role fields; `scripts/submit.py` reads `submit_default` and refuses benchmark-flagged strategies; `harness/rounds.py` delegates designation to the same function so a routine round can no longer silently revert the champion.

**Tech Stack:** Python 3.12 (venv at `.venv`), pytest, stdlib only.

**Spec:** `docs/superpowers/specs/2026-08-16-champion-designation-design.md`
**Issue:** [#76](https://github.com/robsartin/robriculture/issues/76)

## Global Constraints

- **Run every command through the venv:** `PYTHONPATH=. .venv/bin/python -m pytest ...` from the repo root. The system `python3` is 3.9 and will fail; `PYTHONPATH=.` is required for `kaggisim`/`strategies`/`harness` to import.
- **TDD, strictly:** the failing test is written and *observed failing* before the implementation. Red → green → refactor → commit.
- **The suite is green at every commit.** If a signature change breaks an existing test, fixing that test is part of the same task.
- **Stdlib only.** No third-party imports anywhere.
- **Never edit `strategies/__init__.py`** — the registry auto-discovers.
- **Do not modify any strategy under `strategies/`, or `kaggisim/`, or `build/`.** This work is harness + scripts only.
- **Coverage gate:** line ≥ 85%, branch ≥ 65%. CLI `main()` entrypoints and live-game loops get `# pragma: no cover` at the `def`.
- **Test naming:** `test_<expected>_when_<condition>` style, each with a one-line docstring or comment stating intent.
- **No silent fallbacks.** A stale-format `champion.json` must raise, never degrade to the old `champion` field — that would silently re-point the gate at `market_farmer`, the exact bug being fixed.
- **Commit trailer** on every commit:
  ```
  Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
  ```

## File Structure

| file | responsibility | change |
|---|---|---|
| `harness/promotion.py` | the gate, ranking, and the champion artifact | **Modify** — add `pool_share_rank` + `designate`; generalize `top_contender`; rewrite `save_champion`; replace `load_champion`/`current_champion` with two readers |
| `scripts/submit.py` | build + submit a strategy | **Modify** — read `submit_default`; refuse benchmark strategies |
| `harness/rounds.py` | round history + designation | **Modify** — delegate designation; drop the windowed-designation path |
| `harness/champion.json` | the committed decision artifact | **Regenerate** in the new format |
| `tests/test_promotion.py` | promotion unit tests | **Modify** |
| `tests/test_rounds.py` | rounds unit tests | **Modify** |
| `tests/test_submit.py` | submit unit tests | **Modify** |
| `tests/test_champion_excludes_benchmark.py` | the benchmark-exclusion rule | **Rewrite** — exclusion now applies to `submit_default` only |
| `CLAUDE.md`, `README.md`, `docs/adr/0007-*.md` | docs | **Modify** |

---

### Task 1: `pool_share_rank` and a name-based `top_contender`

The share ranking, and the signature change its row shape forces.

**Files:**
- Modify: `harness/promotion.py` (add `pool_share_rank`; change `top_contender`)
- Modify: `harness/rounds.py` (adapt the two `top_contender` call sites)
- Test: `tests/test_promotion.py`, `tests/test_champion_excludes_benchmark.py`

**Interfaces:**
- Consumes: `harness.evolve.match_share(agent, opponents, games, seed_base, rewards_fn)` and `harness.tournament.play_rewards` — both already on `main` from #70.
- Produces:
  - `pool_share_rank(candidates, pool, games=2, seed_base=0, rewards_fn=_play_rewards, benchmarks=None) -> list[dict]` — best-first rows of `{"name": str, "share": float, "benchmark": bool}`. `candidates` and `pool` are both `{name: agent}` maps. A candidate is never its own opponent.
  - `top_contender(names, benchmarks) -> str` — takes best-first **names**, not tuples.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_promotion.py`:

```python
def _named(tag):
    """A stub agent carrying a tag the stub rewards_fn can key off."""
    def agent(obs):
        return {"farmer": ["PASS"], "hands": [], "market": []}
    agent.tag = tag
    return agent


def _stub_rewards(a, b, seed=None):
    """Reward equals the agent's tag length — longer tag scores higher."""
    return (float(len(getattr(a, "tag", ""))), float(len(getattr(b, "tag", ""))))


def test_pool_share_rank_orders_by_share_descending():
    """The strongest agent by score share ranks first."""
    cands = {"aaa": _named("aaa"), "a": _named("a")}
    pool = {"aa": _named("aa")}
    rows = promotion.pool_share_rank(cands, pool, games=2, rewards_fn=_stub_rewards)
    assert [r["name"] for r in rows] == ["aaa", "a"]
    assert rows[0]["share"] > rows[1]["share"]


def test_pool_share_rank_never_plays_a_candidate_against_itself():
    """A candidate that is also in the pool must not be its own opponent —
    a self-match always scores 0.5 and would drag every share toward the mean."""
    seen = []

    def recording_rewards(a, b, seed=None):
        seen.append((getattr(a, "tag", ""), getattr(b, "tag", "")))
        return (100.0, 100.0)

    cands = {"x": _named("x")}
    pool = {"x": _named("x"), "y": _named("y")}
    promotion.pool_share_rank(cands, pool, games=2, rewards_fn=recording_rewards)
    assert all("x" not in (a, b) or a != b for a, b in seen)
    assert all({a, b} != {"x"} for a, b in seen)


def test_pool_share_rank_carries_the_benchmark_flag():
    """The artifact records which rows are external benchmarks."""
    cands = {"aaa": _named("aaa"), "a": _named("a")}
    pool = {"aa": _named("aa")}
    rows = promotion.pool_share_rank(cands, pool, games=2,
                                     rewards_fn=_stub_rewards, benchmarks={"aaa"})
    flags = {r["name"]: r["benchmark"] for r in rows}
    assert flags == {"aaa": True, "a": False}


def test_pool_share_rank_is_deterministic_for_fixed_seeds():
    """ADR-0005: same arguments, same ranking."""
    cands = {"aaa": _named("aaa"), "a": _named("a")}
    pool = {"aa": _named("aa")}
    kw = dict(games=2, rewards_fn=_stub_rewards)
    assert promotion.pool_share_rank(cands, pool, **kw) == promotion.pool_share_rank(cands, pool, **kw)


def test_pool_share_rank_raises_on_an_empty_pool():
    """No opponents means no measurement — fail rather than emit 0.5 for everyone."""
    with pytest.raises(ValueError, match="pool"):
        promotion.pool_share_rank({"a": _named("a")}, {}, games=2, rewards_fn=_stub_rewards)


def test_top_contender_takes_names_and_skips_benchmarks():
    """top_contender now consumes best-first names, not ranking tuples."""
    assert promotion.top_contender(["meta_bot", "ranch_hands"], {"meta_bot"}) == "ranch_hands"
    assert promotion.top_contender(["ranch_hands", "meta_bot"], {"meta_bot"}) == "ranch_hands"


def test_top_contender_raises_when_every_name_is_a_benchmark():
    """There is no valid submit default if everything is external."""
    with pytest.raises(ValueError):
        promotion.top_contender(["meta_bot"], {"meta_bot"})
```

Ensure `tests/test_promotion.py` imports `pytest` and the `promotion` module (it currently imports individual names — add `from harness import promotion` if absent).

- [ ] **Step 2: Run the tests to verify they fail**

Run: `PYTHONPATH=. .venv/bin/python -m pytest tests/test_promotion.py -k "pool_share_rank or top_contender" -v`
Expected: FAIL — `AttributeError: module 'harness.promotion' has no attribute 'pool_share_rank'`

- [ ] **Step 3: Implement in `harness/promotion.py`**

Add near the top, with the other imports:

```python
from harness.evolve import match_share
from harness.tournament import play_rewards as _play_rewards
```

Then add after `round_robin_rank`:

```python
def pool_share_rank(candidates, pool, games=2, seed_base=0,
                    rewards_fn=_play_rewards, benchmarks=None):
    """Rank `candidates` by mean score share against `pool`, best first.

    Share (`me / (me + opp)`, from #70) instead of win-rate, because win/loss
    throws away margin: `market_farmer` won 160/160 head-to-head on margins of
    ~3%, which crowned it champion while it ranked last on the ladder. Share
    puts it within 0.0015 of two other agents — which is the truth.

    A candidate is never its own opponent: a self-match scores 0.5 by
    construction and would pull every share toward the mean.
    """
    if not pool:
        raise ValueError("cannot rank against an empty pool")
    benchmarks = benchmarks or set()
    rows = []
    for name, agent in candidates.items():
        opponents = [a for opp_name, a in pool.items() if opp_name != name]
        rows.append({
            "name": name,
            "share": match_share(agent, opponents, games, seed_base, rewards_fn),
            "benchmark": name in benchmarks,
        })
    rows.sort(key=lambda r: r["share"], reverse=True)
    return rows
```

Then **replace** `top_contender` entirely with:

```python
def top_contender(names, benchmarks):
    """The first name that is not a benchmark opponent.

    Takes best-first *names*. `pool_share_rank` emits dicts, and unpacking those
    as `(label, *rest)` tuples would silently iterate their keys instead of
    raising — so the row shape is names, and callers project explicitly.

    Benchmarks are vendored external agents: they make excellent gate opponents
    but must never be a submit default (ADR-0005 licensing). Raises ValueError
    if every name is a benchmark.
    """
    for name in names:
        if name not in benchmarks:
            return name
    raise ValueError("no non-benchmark contender in ranking")
```

- [ ] **Step 4: Adapt the existing `top_contender` call sites**

`harness/rounds.py` calls `top_contender(ranking, ...)` with tuple rows in two places
(inside `designate_from_history` and `run_and_record`). Project the names at both:

```python
    return top_contender([row[0] for row in ranking], benchmarks or set())
```

```python
    champion = top_contender([row[0] for row in ranking], benchmarks)
```

Task 4 replaces both call sites wholesale; this step only keeps the suite green now.

- [ ] **Step 5: Fix the two pure `top_contender` tests**

In `tests/test_champion_excludes_benchmark.py`, the first two tests pass ranking
tuples. Change them to names:

```python
def test_top_contender_skips_a_leading_benchmark():
    assert promotion.top_contender(["meta_bot", "ranch_hands"], {"meta_bot"}) == "ranch_hands"


def test_top_contender_returns_the_leader_when_no_benchmark_leads():
    assert promotion.top_contender(["ranch_hands", "meta_bot"], {"meta_bot"}) == "ranch_hands"


def test_top_contender_raises_when_every_label_is_a_benchmark():
    with pytest.raises(ValueError):
        promotion.top_contender(["meta_bot"], {"meta_bot"})
```

- [ ] **Step 6: Run the full suite**

Run: `PYTHONPATH=. .venv/bin/python -m pytest tests/ -q`
Expected: PASS — everything green.

- [ ] **Step 7: Commit**

```bash
git add harness/promotion.py harness/rounds.py tests/test_promotion.py tests/test_champion_excludes_benchmark.py
git commit -m "feat(promotion): rank champion candidates by pool share (#76)

Head-to-head win-rate crowned market_farmer 160/160 while it ranked last on the
ladder (476.7). Its margins were ~3%; binary scoring inflated them into an
unbeaten record. By share its 0.5082 sits within 0.0015 of ranch_hands and
ranch_adaptive — indistinguishable, which is the truth.

top_contender now takes best-first names: pool_share_rank emits dicts, and
unpacking those as tuples would iterate their keys rather than raise.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 2: `designate()`, the two-field artifact, and its readers

**Files:**
- Modify: `harness/promotion.py` (`designate`, `save_champion`, `gate_opponent`, `submit_default`, `promotion_test`, CLI `main`)
- Test: `tests/test_promotion.py`

**Interfaces:**
- Consumes: `pool_share_rank`, `top_contender` (Task 1).
- Produces:
  - `designate(candidates, pool, games=2, seed_base=0, rewards_fn=_play_rewards, benchmarks=None) -> dict` — the artifact body: `{"criterion": "pool_share", "gate_opponent": str, "submit_default": str, "games": int, "pool": list[str], "ranking": list[dict]}`.
  - `save_champion(path, body) -> None` — note the signature change from `(path, name, games, ranking)`.
  - `gate_opponent(path=CHAMPION_PATH) -> str`
  - `submit_default(path=CHAMPION_PATH) -> str`
  - `load_champion` and `current_champion` are **removed**.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_promotion.py`:

```python
def test_designate_allows_a_benchmark_as_gate_opponent():
    """The gate is a bar, and a real competitor is the best bar available."""
    cands = {"aaa": _named("aaa"), "a": _named("a")}
    pool = {"aa": _named("aa")}
    body = promotion.designate(cands, pool, games=2, rewards_fn=_stub_rewards,
                               benchmarks={"aaa"})
    assert body["gate_opponent"] == "aaa"


def test_designate_never_puts_a_benchmark_in_submit_default():
    """Submitting a vendored competitor's agent is an ADR-0005 licensing problem."""
    cands = {"aaa": _named("aaa"), "a": _named("a")}
    pool = {"aa": _named("aa")}
    body = promotion.designate(cands, pool, games=2, rewards_fn=_stub_rewards,
                               benchmarks={"aaa"})
    assert body["submit_default"] == "a"


def test_designate_records_the_criterion_and_pool():
    """The artifact says how it was produced, so a future reader can reproduce it."""
    cands = {"aaa": _named("aaa")}
    pool = {"aa": _named("aa")}
    body = promotion.designate(cands, pool, games=2, rewards_fn=_stub_rewards)
    assert body["criterion"] == "pool_share"
    assert body["pool"] == ["aa"]
    assert body["games"] == 2


def test_save_champion_round_trips_both_roles(tmp_path):
    """Both readers return their own field from a saved artifact."""
    p = tmp_path / "champion.json"
    body = {"criterion": "pool_share", "gate_opponent": "meta_bot",
            "submit_default": "meta_rancher", "games": 2, "pool": [], "ranking": []}
    promotion.save_champion(str(p), body)
    assert promotion.gate_opponent(str(p)) == "meta_bot"
    assert promotion.submit_default(str(p)) == "meta_rancher"


def test_gate_opponent_raises_on_an_old_format_artifact(tmp_path):
    """A stale file must fail loudly, never silently fall back to `champion`.

    A silent fallback re-points the gate at market_farmer without anyone
    noticing — the exact bug #76 exists to fix.
    """
    p = tmp_path / "champion.json"
    p.write_text(json.dumps({"champion": "market_farmer", "games": 20, "ranking": []}))
    with pytest.raises(ValueError, match="re-designate"):
        promotion.gate_opponent(str(p))


def test_submit_default_raises_on_an_old_format_artifact(tmp_path):
    """Same loud failure for the submit side."""
    p = tmp_path / "champion.json"
    p.write_text(json.dumps({"champion": "market_farmer", "games": 20, "ranking": []}))
    with pytest.raises(ValueError, match="re-designate"):
        promotion.submit_default(str(p))
```

**Delete** the now-obsolete `test_save_and_load_champion` and
`test_current_champion_reads_the_recorded_file` from `tests/test_promotion.py`,
and update the test near line 182 that asserts `res.champion == current_champion()`
to use `gate_opponent()` instead. Ensure the module imports `json` and `pytest`.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `PYTHONPATH=. .venv/bin/python -m pytest tests/test_promotion.py -k "designate or save_champion or gate_opponent or submit_default" -v`
Expected: FAIL — `AttributeError: module 'harness.promotion' has no attribute 'designate'`

- [ ] **Step 3: Implement in `harness/promotion.py`**

Add after `pool_share_rank`:

```python
CRITERION = "pool_share"


def designate(candidates, pool, games=2, seed_base=0,
              rewards_fn=_play_rewards, benchmarks=None):
    """Rank by pool share and split the result into the champion's two roles.

    `gate_opponent` is the outright leader — benchmarks included, because the
    gate wants the most demanding representative bar available.

    `submit_default` is the leading non-benchmark. `scripts/submit.py` packages
    it with no arguments, so a vendored external agent must never land here:
    submitting a competitor's code is pointless and an ADR-0005 licensing and
    attribution problem. One field cannot answer both questions, which is why
    there are two.
    """
    benchmarks = benchmarks or set()
    ranking = pool_share_rank(candidates, pool, games=games, seed_base=seed_base,
                              rewards_fn=rewards_fn, benchmarks=benchmarks)
    return {
        "criterion": CRITERION,
        "gate_opponent": ranking[0]["name"],
        "submit_default": top_contender([r["name"] for r in ranking], benchmarks),
        "games": games,
        "pool": list(pool),
        "ranking": ranking,
    }
```

**Replace** `save_champion`, `load_champion`, and `current_champion` with:

```python
def save_champion(path, body):
    """Write the designation artifact (a `designate()` body) as JSON."""
    with open(path, "w") as fh:
        json.dump(body, fh, indent=2)
        fh.write("\n")


def _read_role(path, field):
    """Read one role from the artifact, failing loudly on the old single-field format."""
    with open(path) as fh:
        data = json.load(fh)
    if field not in data:
        raise ValueError(
            f"{path!r} has no {field!r} — it predates the two-role split (#76). "
            f"re-designate with: python -m harness.promotion --designate"
        )
    return data[field]


def gate_opponent(path=CHAMPION_PATH):
    """The opponent an ADR-0007 promotion test measures against. May be a benchmark."""
    return _read_role(path, "gate_opponent")


def submit_default(path=CHAMPION_PATH):
    """The strategy `scripts/submit.py` packages by default. Never a benchmark."""
    return _read_role(path, "submit_default")
```

In `promotion_test`, change the default-resolution line from
`champion_name = current_champion()` to:

```python
        champion_name = gate_opponent()
```

- [ ] **Step 4: Update the promotion CLI**

In `main()` (already `# pragma: no cover`), the `--designate` branch currently calls
`designate_champion` and `save_champion(CHAMPION_PATH, champ, args.games, ranking)`.
Replace that branch with:

```python
        from harness.evolve import DEFAULT_ANCHORS
        from harness.tournament import benchmark_names
        from strategies import REGISTRY

        bench = benchmark_names()
        pool = build_agents(list(DEFAULT_ANCHORS))
        candidates = build_agents(list(REGISTRY))
        body = designate(candidates, pool, games=args.games, benchmarks=bench)
        save_champion(CHAMPION_PATH, body)
        for row in body["ranking"]:
            mark = " (benchmark)" if row["benchmark"] else ""
            print(f"  {row['name']:16s} share={row['share']:.4f}{mark}")
        print(f"\ngate_opponent:  {body['gate_opponent']}")
        print(f"submit_default: {body['submit_default']}")
```

Leave `designate_champion` and `round_robin_rank` in place — `round_robin_rank`
still backs `harness/rounds.py`'s round recording, and `designate_champion` is
covered by existing tests. Do not delete them in this task.

- [ ] **Step 5: Point `rounds.py` at the new designation — this closes the revert trap**

Changing `save_champion`'s signature breaks `harness/rounds.py` immediately, and the
fix is the real one, not a shim: if `rounds.py` kept designating from round win-rate,
one ordinary `python -m harness.rounds` would silently overwrite the share-based
champion and re-crown `market_farmer`.

Change its import line from:

```python
from harness.promotion import CHAMPION_PATH, round_robin_rank, save_champion, top_contender
```

to:

```python
from harness import promotion
from harness.promotion import CHAMPION_PATH, round_robin_rank, save_champion
```

Then replace `run_and_record` with:

```python
def run_and_record(names, games=20, rounds_path=ROUNDS_PATH,
                   champion_path=CHAMPION_PATH, play_fn=play, rewards_fn=None,
                   build=build_agents, benchmarks=None, pool=None):
    """Play a round, append it to history, and re-designate by pool share.

    Designation delegates to `promotion.designate` rather than ranking the round
    itself. If this routine kept designating from round win-rate, one ordinary run
    would silently overwrite the share-based champion and re-crown market_farmer
    (#76) — a fix undone invisibly is worse than no fix.
    """
    benchmarks = benchmarks or set()
    rnd = run_round(names, games=games, play_fn=play_fn, build=build)
    append_round(rounds_path, rnd)

    agents = build(names)
    pool_agents = build(list(pool)) if pool is not None else agents
    kw = {"games": games, "benchmarks": benchmarks}
    if rewards_fn is not None:
        kw["rewards_fn"] = rewards_fn
    body = promotion.designate(agents, pool_agents, **kw)
    save_champion(champion_path, body)
    return body["gate_opponent"], body
```

`windowed_ranking` and `designate_from_history` are now unused by production code.
Leave them in place for this task — Task 4 removes them with their tests, so this
task's diff stays reviewable as "the artifact format and its writers".

- [ ] **Step 6: Update the tests that assert the old artifact shape**

In `tests/test_champion_excludes_benchmark.py`, `test_run_and_record_writes_a_non_benchmark_champion`
asserts `json[...]["champion"]`. Replace it with:

```python
def test_run_and_record_writes_a_non_benchmark_submit_default(tmp_path, monkeypatch):
    """A benchmark may be the gate opponent; it must never be the submit default."""
    from harness import rounds

    monkeypatch.setattr(rounds.promotion, "designate", lambda candidates, pool, **kw: {
        "criterion": "pool_share", "gate_opponent": "meta_bot",
        "submit_default": "ranch_hands", "games": 2, "pool": [], "ranking": []})

    champ_path = tmp_path / "champion.json"
    rounds.run_and_record(
        ["meta_bot", "ranch_hands"], games=2,
        rounds_path=str(tmp_path / "rounds.json"), champion_path=str(champ_path),
        play_fn=lambda a, b, seed=None: 1, build=lambda names: {n: n for n in names},
        benchmarks={"meta_bot"},
    )
    saved = json.loads(champ_path.read_text())
    assert saved["gate_opponent"] == "meta_bot"
    assert saved["submit_default"] != "meta_bot"
```

`tests/test_rounds.py` calls `run_and_record` with `window=`/`decay=` in places —
drop those arguments, since the parameters are gone.

- [ ] **Step 7: Confirm green, then commit**

Run: `PYTHONPATH=. .venv/bin/python -m pytest tests/ -q`
Expected: PASS. `tests/test_submit.py` stays green because its fixtures write their
own files; Task 3 migrates `submit.py` before Task 4 regenerates the real artifact.

```bash
git add harness/promotion.py harness/rounds.py tests/test_promotion.py tests/test_rounds.py tests/test_champion_excludes_benchmark.py
git commit -m "feat(promotion): split champion into gate_opponent and submit_default (#76)

The champion field served two incompatible roles: the ADR-0007 gate opponent,
and the default scripts/submit.py packages. The gate wants the most demanding
bar available, including vendored external competitors; the submit default must
never be one, because submitting a competitor's agent is pointless and an
ADR-0005 licensing problem. That conflict is why top_contender excluded
benchmarks at all — undocumented, and correct only for the submit side.

Reading a pre-split artifact raises rather than falling back to the old field: a
silent fallback re-points the gate at market_farmer unnoticed.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 3: `submit.py` reads `submit_default` and refuses benchmarks

**Files:**
- Modify: `scripts/submit.py`
- Test: `tests/test_submit.py`

**Interfaces:**
- Consumes: the `submit_default` field written by `designate` (Task 2).
- Produces: `scripts/submit.py::load_submit_default(path)` replaces `load_champion`; `prepare()` raises on a benchmark-flagged strategy.

- [ ] **Step 1: Write the failing tests**

In `tests/test_submit.py`, replace `test_load_champion_reads_the_champion_field` with:

```python
def test_load_submit_default_reads_the_submit_default_field(tmp_path):
    """submit.py packages the submit default, never the gate opponent."""
    p = tmp_path / "champion.json"
    p.write_text(json.dumps({"gate_opponent": "meta_bot", "submit_default": "mixed_hands"}))
    assert submit.load_submit_default(str(p)) == "mixed_hands"


def test_load_submit_default_raises_on_an_old_format_artifact(tmp_path):
    """A stale artifact must not silently resolve to the old champion field."""
    p = tmp_path / "champion.json"
    p.write_text(json.dumps({"champion": "market_farmer"}))
    with pytest.raises(ValueError, match="re-designate"):
        submit.load_submit_default(str(p))


def test_prepare_refuses_a_benchmark_strategy():
    """Belt and braces: even a hand-edited artifact cannot submit a vendored agent.

    meta_bot is someone else's code, vendored readonly under their license
    (ADR-0005). Packaging it under our name is a licensing problem, not a bad
    score, so the cost of getting this wrong is asymmetric.
    """
    with pytest.raises(SystemExit, match="benchmark"):
        submit.prepare("meta_bot", out=None)
```

Ensure `tests/test_submit.py` imports `json` and `pytest`.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `PYTHONPATH=. .venv/bin/python -m pytest tests/test_submit.py -v`
Expected: FAIL — `AttributeError: module 'submit' has no attribute 'load_submit_default'`

- [ ] **Step 3: Implement in `scripts/submit.py`**

Replace `load_champion` with:

```python
def load_submit_default(path=CHAMPION_PATH):
    """The strategy recorded as the default to submit (never a benchmark, #76)."""
    with open(path) as fh:
        data = json.load(fh)
    if "submit_default" not in data:
        raise ValueError(
            f"{path!r} has no 'submit_default' — it predates the two-role split (#76). "
            f"re-designate with: python -m harness.promotion --designate"
        )
    return data["submit_default"]
```

Replace `prepare` with:

```python
def prepare(strategy=None, out=None, champion_path=CHAMPION_PATH):
    """Resolve the (strategy, tarball-path) to build, defaulting to the submit default.

    Refuses benchmark-flagged strategies outright. They are vendored external
    competitors; packaging one under our name is an ADR-0005 licensing and
    attribution problem, so this guard holds even when the name is given
    explicitly.
    """
    from harness.tournament import benchmark_names

    strategy = strategy or load_submit_default(champion_path)
    if strategy in benchmark_names():
        raise SystemExit(
            f"{strategy!r} is a readonly benchmark opponent (vendored external agent) "
            f"— refusing to package it for submission"
        )
    out = out or os.path.join(DIST_DIR, f"{strategy}.tar.gz")
    return strategy, out
```

Update the `main()` help text for the positional argument from
`"strategy name (default: current champion)"` to
`"strategy name (default: the recorded submit_default)"`.

- [ ] **Step 4: Run the full suite**

Run: `PYTHONPATH=. .venv/bin/python -m pytest tests/ -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/submit.py tests/test_submit.py
git commit -m "feat(submit): package submit_default, never a benchmark (#76)

submit.py with no arguments packaged champion.json's champion. Once a vendored
external competitor can be the champion — which is what makes it a good gate
opponent — that default would submit someone else's agent under our name.

Read submit_default instead, and refuse any benchmark-flagged strategy even when
named explicitly. The cost of getting this wrong is a licensing problem rather
than a bad score, so it gets a guard as well as a correct default.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 4: Remove the dead windowed-designation path

Task 2 rerouted designation. This removes what that left stranded, so no future
reader mistakes `windowed_ranking` for a live selection mechanism.

**Files:**
- Modify: `harness/rounds.py` (delete `windowed_ranking`, `designate_from_history`, `DEFAULT_WINDOW`; update `main`)
- Test: `tests/test_rounds.py`, `tests/test_champion_excludes_benchmark.py`

**Interfaces:**
- Consumes: `run_and_record` and `promotion.designate` as wired in Task 2.
- Produces: no new interfaces. `windowed_ranking`, `designate_from_history`, and `DEFAULT_WINDOW` no longer exist.

- [ ] **Step 1: Write the regression guard for the revert trap**

Add to `tests/test_rounds.py` — this is the test that pins Task 2's fix in place:

```python
def test_run_and_record_designates_by_pool_share_not_round_wins(tmp_path, monkeypatch):
    """The regression guard for #76's revert trap.

    rounds.py used to re-designate from windowed round win-rate. If it ever did
    again, a routine `python -m harness.rounds` would silently overwrite the
    share-based champion and re-crown market_farmer — a fix undone invisibly.
    """
    calls = {}

    def fake_designate(candidates, pool, **kw):
        calls["used"] = True
        return {"criterion": "pool_share", "gate_opponent": "meta_bot",
                "submit_default": "ranch_hands", "games": kw.get("games", 2),
                "pool": list(pool), "ranking": []}

    monkeypatch.setattr(rounds.promotion, "designate", fake_designate)

    champ, body = rounds.run_and_record(
        ["ranch_hands", "meta_bot"], games=2,
        rounds_path=str(tmp_path / "rounds.json"),
        champion_path=str(tmp_path / "champion.json"),
        play_fn=lambda a, b, seed=None: 1 if a == "ranch_hands" else -1,
        build=lambda names: {n: n for n in names},
        benchmarks={"meta_bot"},
    )
    assert calls.get("used") is True
    assert champ == "meta_bot"
    assert body["submit_default"] == "ranch_hands"


def test_run_and_record_still_appends_round_history(tmp_path, monkeypatch):
    """Designation changed; the round history record did not."""
    monkeypatch.setattr(rounds.promotion, "designate", lambda candidates, pool, **kw: {
        "criterion": "pool_share", "gate_opponent": "a", "submit_default": "a",
        "games": 2, "pool": [], "ranking": []})

    rounds_path = tmp_path / "rounds.json"
    rounds.run_and_record(
        ["a", "b"], games=2, rounds_path=str(rounds_path),
        champion_path=str(tmp_path / "champion.json"),
        play_fn=lambda x, y, seed=None: 1, build=lambda names: {n: n for n in names},
    )
    history = json.loads(rounds_path.read_text())
    assert len(history) == 1 and "results" in history[0]
```

Ensure `tests/test_rounds.py` imports `json` and imports `rounds` as a module
(`from harness import rounds`) so `monkeypatch.setattr` can reach
`rounds.promotion`.

- [ ] **Step 2: Run the new tests — they should already PASS**

Run: `PYTHONPATH=. .venv/bin/python -m pytest tests/test_rounds.py -k "designates_by_pool_share or appends_round_history" -v`
Expected: PASS, because Task 2 already rerouted designation.

This is the one place in this plan where a new test is not expected to start red:
it is a **regression guard** for behaviour just landed, not a driver for new
behaviour. If it FAILS, Task 2's delegation is wrong — stop and report rather than
editing the test to match.

- [ ] **Step 3: Delete the dead windowed path**

In `harness/rounds.py`, **delete** `windowed_ranking`, `designate_from_history`, and
the `DEFAULT_WINDOW` constant. Both functions existed to smooth win-rate across
rounds; #77 measured 40 games across 4 pairings with zero outcome flips, so they
smoothed a quantity that barely moves — and designation no longer reads round
history at all.

Round *recording* (`load_rounds`, `append_round`, `run_round`) stays: the history
is still a useful record, and `run_and_record` still writes it.

- [ ] **Step 4: Delete their tests**

In `tests/test_rounds.py`, delete every `windowed_ranking` test and
`test_designate_from_history_picks_the_window_leader`. In
`tests/test_champion_excludes_benchmark.py`, delete
`test_designate_from_history_excludes_benchmark`.

These assert behaviour that no longer exists. The rule they encoded — a benchmark
is never the submit default — is still asserted, by
`test_run_and_record_writes_a_non_benchmark_submit_default` (rewritten in Task 2).
No rule loses its coverage here; only its dead implementation goes.

- [ ] **Step 5: Update the rounds CLI**

In `main()` (already `# pragma: no cover`), drop the `--window` and `--decay`
arguments and their pass-through, and change the reporting block to:

```python
    from harness.evolve import DEFAULT_ANCHORS

    champion, body = run_and_record(
        names, games=args.games, benchmarks=benchmark_names(),
        pool=list(DEFAULT_ANCHORS),
    )
    for row in body["ranking"]:
        mark = " (benchmark)" if row["benchmark"] else ""
        print(f"  {row['name']:16s} share={row['share']:.4f}{mark}")
    print(f"\ngate_opponent:  {body['gate_opponent']}")
    print(f"submit_default: {body['submit_default']}")
```

Also update the module docstring, which currently describes windowed champion
selection, to say designation is by pool share and the history is a record.

- [ ] **Step 6: Run the full suite**

Run: `PYTHONPATH=. .venv/bin/python -m pytest tests/ -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add harness/rounds.py tests/test_rounds.py tests/test_champion_excludes_benchmark.py
git commit -m "feat(rounds): delegate designation, closing the revert trap (#76)

rounds.py re-designated the champion from windowed round win-rate. With
promotion.py switched to pool share, one routine `python -m harness.rounds` would
have silently overwritten the new champion and re-crowned market_farmer. A fix
that an ordinary command undoes invisibly is worse than no fix.

Designation now delegates to promotion.designate. windowed_ranking and
designate_from_history go with it: #12 built them to smooth win-rate across
rounds, and #77 measured zero outcome flips in 40 games, so they smoothed a
quantity that barely moves. Round history recording is unchanged.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 5: Re-designate for real, and update the docs

**Files:**
- Modify: `harness/champion.json` (regenerated)
- Modify: `CLAUDE.md`, `README.md`, `docs/adr/0007-experiment-driven-development-process.md`

**Interfaces:**
- Consumes: everything above.
- Produces: no new code interfaces.

- [ ] **Step 1: Run the real designation**

Run: `PYTHONPATH=. .venv/bin/python -m harness.promotion --designate --games 2`

This plays real 720-turn games across every registered strategy against the six
anchors — roughly 24 candidates x 6 opponents x 2 games. Budget 15-25 minutes and
run it as a single blocking foreground command.

Expected: `gate_opponent: meta_bot` and `submit_default: meta_rancher`, matching
the measurements in the spec (`meta_bot` 0.6325, `meta_rancher` 0.6066).

**If `submit_default` is not `meta_rancher`, stop and report** rather than
committing — the spec's central claim is that share designates differently from
win-rate, and a surprise here means the measurement did not reproduce.

- [ ] **Step 2: Sanity-check the artifact**

Run: `PYTHONPATH=. .venv/bin/python -c "import json; d=json.load(open('harness/champion.json')); print(d['criterion'], d['gate_opponent'], d['submit_default']); print('market_farmer share:', [r for r in d['ranking'] if r['name']=='market_farmer'])"`

Expected: `pool_share meta_bot meta_rancher`, and `market_farmer`'s share around
0.50 rather than a leading position.

- [ ] **Step 3: Update `CLAUDE.md`**

In "Key conventions", replace the bullet that begins **"Beat the *designated*
champion, not an assumption."** with:

```markdown
- **Beat the *designated gate opponent*, not an assumption.** `harness/champion.json` records two roles (#76): `gate_opponent` — what an ADR-0007 experiment is measured against, which **may be a vendored external benchmark** because the gate wants the most demanding representative bar — and `submit_default`, what `scripts/submit.py` packages, which is **never** a benchmark (submitting a vendored competitor's agent is an ADR-0005 licensing problem). Designation is by **pool share**, not head-to-head win-rate: win/loss discards margin, which is how `market_farmer` held a 160/160 record while ranking last on the ladder.
```

In "Quick reference", update the `harness.rounds` line to drop `--window`:

```markdown
- `python -m harness.rounds --games 20` — play a round, append it to `harness/rounds.json`, and re-designate by pool share (#12, #76).
```

- [ ] **Step 4: Update `README.md`**

The submit section says the message defaults to `"<strategy> <sha>"` and the
strategy to the champion. Change "champion" to "recorded `submit_default`" in that
sentence, leaving the rest of the block as is.

- [ ] **Step 5: Record the comparability break in ADR-0007**

Append to ADR-0007's `## Consequences` section:

```markdown
- **The gate opponent changed mid-stream, so promotion results are not comparable
  across it (#76, 2026-08-16).** Until now the gate ran against `market_farmer`,
  designated on a 160/160 head-to-head record that turned out to be ~3% margins
  amplified by binary scoring — its pool share is 0.5082, within 0.0015 of two
  other agents, and it scored 476.7 on the ladder, our worst. Any challenger
  promoted before this date cleared a weaker and unrepresentative bar; do not
  compare those (N, win-rate, p) records with later ones. Designation is now by
  pool share, and the champion's two roles are recorded separately as
  `gate_opponent` and `submit_default`.
```

- [ ] **Step 6: Run the full CI gate**

```bash
PYTHONPATH=. .venv/bin/python -m pytest -q --cov --cov-branch --cov-report=term-missing --cov-report=json
```

```bash
PYTHONPATH=. .venv/bin/python -c "
import json, sys
t = json.load(open('coverage.json'))['totals']
line = 100.0 * t['covered_lines'] / t['num_statements']
branch = 100.0 * t['covered_branches'] / t['num_branches']
print(f'line {line:.1f}% (gate 85%) / branch {branch:.1f}% (gate 65%)')
sys.exit(line < 85.0 or branch < 65.0)
"
```

Expected: all green, both figures above their floors. The ADR-integrity tests
(`tests/test_adr_integrity.py`) must also pass — the ADR edit adds a bullet to an
existing section and changes no status line.

- [ ] **Step 7: Confirm the submission path is untouched**

Run: `git diff --stat origin/main...HEAD -- strategies/ kaggisim/ build/`
Expected: **empty**. This work is harness + scripts only.

- [ ] **Step 8: Commit**

```bash
git add harness/champion.json CLAUDE.md README.md docs/adr/0007-experiment-driven-development-process.md
git commit -m "chore: re-designate the champion by pool share (#76)

market_farmer held the designation on a 160/160 head-to-head record while
scoring 476.7 on the ladder, our worst — the measuring stick for every ADR-0007
experiment pointed at an agent ADR-0008 had already documented as
unrepresentative.

gate_opponent is now meta_bot (share 0.6325), the strongest bar available and a
real competitor rather than one of our own bots. submit_default is meta_rancher
(0.6066), which is also our ladder leader at 556.6 — both signals agree.

ADR-0007 records that the bar changed, so promotion results from before and after
are not comparable.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```
