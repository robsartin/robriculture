# Per-day cash flow of one side of one game (#260)

**Issue:** #260 — measurement before the feed-floor contender
**Branch:** `260-cashflow`
**Decided with Rob, 2026-09-10:** measure the cash flow of pilkwang and our three
schedule contenders on a spent seed before declaring a fourth arm.

## Context

Three contenders on the field's schedule starved three different lines — field_pace (#252)
the herd, herd_first (#254) the crew, dusk_floor (#258) land and seed — each for a reason a
one-turn trace would have shown. `harness/episode_analysis.decompose` already prices every
order against the state it was chosen from and reports a residual against the game's final
money; it reports season totals. A local game's `env.steps` has the same shape as a
downloaded replay (per-step lists of per-player `{action, observation}`), so the same
decomposition runs on our own games. What the design needs is the same numbers per day.

## The tool: `harness/cashflow.py`

- `CATEGORIES = ("hire", "land", "seed", "animal", "product")` — `decompose`'s buckets.
- `daily_cashflow(steps, player) -> {day: {"spend": {category: amount}, "revenue": {item: amount}, "close": money}}`
  built on `episode_analysis._turns` (one dict per turn, the action paired with the state it
  was chosen from), `sell_revenue` and `spend_by_category`, with the hire ladder reset at each
  new day exactly as `decompose` resets it; `close` is the money in the last observation
  recorded for that day (the day's closing board). Days with no turns are absent.
- `season_totals(table) -> {"spend": {...}, "revenue": {...}}` — the positive control's
  subject: summed over every day it must equal `decompose(steps, player)["spend"]` and
  `["revenue"]`, so the daily view cannot drift from the season view.
- `format_cashflow(table, days=range(0, 13)) -> str` — one line per day in `days`: close,
  the five spend columns, revenue by item in a fixed order (`WHEAT, MELON, STRAWBERRY, MILK,
  WOOL, FERTILIZER`, then any other item), then a `cumulative` line for those days and a
  `season` line for every day in the table.
- Live (`# pragma: no cover`): `play(name, opponent, seed)` — `name` is a registry strategy or
  a pinned external (`external_pool.external_anchor_agents([name])`, fresh per game) in seat
  0, `opponent` a registry strategy in seat 1, `kaggle_environments.make("kaggriculture",
  configuration={"seed": seed}).run(...)`; returns `env.steps`. `main` takes `--seed`,
  `--agents` (several), `--opponent` (default `third_herder`), `--days` (default 13) and prints,
  per agent, the table and one line with `decompose`'s `final_money` and `residual` — the
  honesty check beside every table.

## The run

Seed 944 (spent: #258's control seed), agents `pilkwang_structured_economic_policy`,
`field_pace`, `herd_first`, `dusk_floor`, opponent `third_herder`, days 0-12. Four games. The
four tables and the residual lines are posted on #260. No contender code, no fresh seeds.

## Testing

Pure TDD on fabricated steps (the `_step` helper shape `tests/test_episode_analysis.py`
uses, with a `day`): a two-day game where day 0 sells and buys seed and day 1 hires twice and
sells — the daily split, the hire ladder resetting on day 1 (1 + 1, not 2 + 3), closing money
per day, revenue keyed by item; `season_totals` equals `decompose`'s two dicts on the same
steps; `format_cashflow` prints one line per requested day plus `cumulative` and `season`,
and a day absent from the table prints as absent, not zero. Full gate and preflight before
push.

## Outcome

A harness PR (engine/infra: green tests, normal merge). The tables on #260 are the input to
the feed-floor brainstorm; #260 closes when that contender is declared.
