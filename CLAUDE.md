# CLAUDE.md

Conventions and AI-specific workflow for **robriculture**, our agent for the
Kaggriculture (Kaggle × Google) farming-economy competition. For the human-facing
overview and setup, see [README.md](README.md); for the *why* behind each rule,
see the ADRs in [docs/adr/](docs/adr/).

## Quick reference

- `pytest -q` — full suite: pure-helper unit tests, the no-crash gate (ADR-0006), and the ADR-honesty checks (#3). A bare `pytest` works from the repo root (root `conftest.py` puts packages on the path).
- `pytest -q --cov --cov-branch --cov-report=term-missing` — with coverage. CI gates **line ≥ 85% and branch ≥ 65%** (#10).
- `ROBRICULTURE_STRICT=1 pytest -q` — let strategy exceptions propagate instead of degrading to the fail-safe PASS. **Use this while developing a strategy** — otherwise a bug hides as a silent PASS.
- `python -m harness.tournament --games 20` — local round-robin (all registered strategies + built-in bots).
- `python -m harness.promotion <challenger> --champion <name> --games 200` — the ADR-0007 strategy gate (seeded; reports win-rate + binomial p + PROMOTE/REJECT).
- `python -m harness.promotion --designate` — re-designate the champion from a seeded round-robin.
- `python -m harness.rounds --games 20 --window 3` — play a round, append it to `harness/rounds.json`, re-pick the champion over the recent window (#12).
- `python -m harness.genome_bench --genome <path> --games 4` — score one genome against the fixed anchors only (no Hall-of-Fame, no population sample). The **comparable** number across evolution runs; `evolve`'s own fitness is not (#70).
- `python -m build.package <strategy>` — build a submittable tarball (runs a post-build smoke test).

## The experiment loop (ADR-0007) — the defining workflow

**The unit of work is an experiment: one GitHub issue, label `experiment`, with the hypothesis stated up front.** Two kinds of change flow through the repo and are validated differently:

- **Engine / correctness** (economy, state parsing, action legality, harness, packaging). "Does the code do what we said?" is a boolean — validated by **green tests + the no-crash gate**. Merges via a normal green PR.
- **Strategy** (a new or tuned agent). "Is this agent actually *better*?" is a statistical question no unit test can answer. It must additionally pass the **promotion test**: a fixed set of **seeded** games (default **200**) against the current champion — promote only if **win-rate ≥ 55% AND a binomial test rejects the 50% null at p < 0.05**. Record N / win-rate / p in the issue.

**Always TDD** the code (red → green → refactor, stay green). Work on a branch per experiment; nothing lands on `main` directly; PRs are reviewed, not auto-merged.

**Execute plans via subagent-driven-development** — a fresh implementer subagent per task, a spec + code-quality review after each task, and a whole-branch review before the PR. This is the standing default: go straight to it once a plan is committed; do **not** pause to offer an execution-mode menu.

**Outcomes:**
- **Hypothesis supported** → PR to `main`, reviewed, merged; the issue is closed by the merge and records the numbers.
- **Hypothesis rejected** → **do not merge.** Record the result *and the root-cause lesson* as a comment on the issue, close it `not_planned`, and **discard the files** so `main` stays clean (see #24, #31 for the format). Salvage any genuinely reusable engine/harness/infra into its own small green-test PR *first*.

**The issue is the lab notebook** — every hypothesis and result lives there; it's the raw material for the ADR-0005 reproducible writeup.

## Layout

```
kaggisim/    shared library bundled into every submission — state.parse, economy tables,
             the Strategy interface, actions. Depends only on stdlib + the sim.
strategies/  swappable agents behind one interface. Auto-discovered (see below).
harness/     local tournament / promotion / rounds — our fitness signal.
             champion.json + rounds.json are committed decision artifacts.
build/       package.py: turn one strategy into a submittable tarball (+ smoke test).
tests/       pure-helper unit tests + the no-crash regression guard.
docs/adr/    architecture decision records (append-only; index in docs/adr/README.md).
```

## Key conventions

- **Adding a strategy = dropping two files.** `strategies/<name>.py` exposing a module-level `STRATEGY` (a `Strategy` subclass with a unique `name`) plus `tests/test_<name>.py`. The registry **auto-discovers** it — **never edit `strategies/__init__.py`**. That auto-discovery is deliberate: it's what lets parallel experiments land without ever colliding on the registry.
- **The Strategy interface** ([`kaggisim/strategy.py`](kaggisim/strategy.py)): implement `act(obs) -> {"farmer": [ACTION, *args], "hands": [[...], ...], "market": [[ORDER, ITEM, N], ...]}`. `obs` is the parsed state (`kaggisim.state.parse`). Keep decisions in **pure module-level helpers** so the technique unit-tests without spinning up a full 720-turn game.
- **Fail-safe, never crash (ADR-0006).** A crash during evaluation is an auto-loss, so `make_agent` wraps `act` in try/except → a safe PASS. That safety net also *hides bugs*, so develop with `ROBRICULTURE_STRICT=1`. The no-crash gate ([`tests/test_no_crash.py`](tests/test_no_crash.py)) runs every registered strategy through full games vs the built-ins under strict mode.
- **Economy is the ground truth, reconciled to the sim (ADR-0002).** [`kaggisim/economy.py`](kaggisim/economy.py) is validated field-for-field against the installed `kaggle_environments` kaggriculture source; [`tests/test_economy_matches_sim.py`](tests/test_economy_matches_sim.py) is the claim-check. When intuition and `economy.py` disagree, fix your intuition; when `economy.py` and the sim disagree, fix `economy.py` (and the test).
- **Beat the *designated* champion, not an assumption.** `harness/champion.json` records the current champion (windowed over recent rounds, #12). An experiment is measured against exactly that agent.
- **Respect the market-order cap.** At most `maxMarketOrdersPerTurn` (**10**) market orders per turn; order them so the ones that matter (sells) are never the ones truncated.
- **Reproducibility (ADR-0005).** Seeds are fixed everywhere so a result re-runs to the same number. Record every experiment's (N, win-rate, p) in its issue.

## Tests & style

- **pytest**, plain `snake_case` test names that read as `test_<expected>_when_<condition>`, each with a one-line docstring or comment stating intent (see [`tests/test_hired_hands.py`](tests/test_hired_hands.py) as the model). Unit-test the pure helpers; let the no-crash gate cover full games.
- **Coverage gate:** line ≥ 85%, branch ≥ 65% (CI). Mark genuine integration entrypoints — the CLI `main()`s, the live-game loops, the subprocess smoke test — `# pragma: no cover` at the `def`; everything else is expected to be covered.
- **No enforced formatter/linter.** Follow PEP 8 and match the surrounding code: small pure helpers, docstrings that say *why*, type hints where they aid reading.
- **Python 3.11 recommended** (Kaggle's runtime); CI runs 3.12; 3.10+ works locally.
