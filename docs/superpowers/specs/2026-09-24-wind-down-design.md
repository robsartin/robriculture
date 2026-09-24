# wind_down — from day 28 buy nothing, keep no feed, hold no fertilizer (#343)

**Declared on #343** under ADR-0007 as amended 2026-09-16, 2026-09-20 and 2026-09-21, corrected 2026-09-17. The issue is the declaration; this spec is the design the plan implements.

## The finding
The farm buys and holds a feed buffer of two wheat per head to the last turn, and buys seed and fertilizer it cannot use before the season ends. From day 28 stopping every buy, keeping no feed reserve (the sweep sells the wheat and no feed is bought) and holding no fertilizer read 16/16 (+2.0K) and 16/16 (+2.1K) on two seed sets, all 32 margins positive. From day 27 it loses: the herd goes unfed two days and escapes before its last yield.

## The change
**Seam** `FieldRivalStrategy.wind_down(self, day) -> None` on the frozen benchmark. In `act`, when the hook returns true: the feed reserve passed to `market_orders` is 0, the fertilizer stock is 0, and the spend floor is `NO_SPEND` (a module constant no farm reaches, so the existing floor blocks land, seed and herd buys; hires and sells go on). `market_orders` does not change. `feed_bench.off_class` gains the stub; twenty-one seams.

**Contender** `strategies/wind_down.py`: `WindDownStrategy(TownMelonStrategy)`, `name = "wind_down"`, `WIND_DOWN_DAY = 28`; `wind_down(day)` returns `True` from that day, `None` before.

**Bench** `harness/winddown_bench.py` — see #343: identity control (twenty-one seams off), mechanism control (no BUY order from day 28 and the champion has some; no WHEAT in the shed at the end of day 28 and the champion has some; first divergence at or after the first action answering day 28), then `rival_bench.decided_row` + anchors + paired externals on seeds 2586–2601. Readings come from `harness.episode_analysis._turns`, which dates each action by the observation it answered.

## Alternatives rejected
On the issue: day 27; the buys or the feed alone; fertilizer alone; a wind-down that also stops watering and hiring.
