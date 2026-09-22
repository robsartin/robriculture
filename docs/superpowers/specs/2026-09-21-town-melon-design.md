# town_melon — melon from day 9 while the town has no strawberry shop (#337)

**Declared on #337** under ADR-0007 as amended 2026-09-16, 2026-09-20 and 2026-09-21 (PR #338), corrected 2026-09-17. The issue is the declaration; this spec is the design the plan implements.

## The finding
Five of `fert_sixteen`'s fourteen ladder losses, and none of its wins, were towns with no shop that takes strawberry (BRUNCH_SPOT, ICE_CREAM_SHOP, SMOOTHIE_SHOP, FARMERS_MARKET). Shops unlock on days 3, 6, 9, … drawn with replacement from eight kinds; 12% of ladder towns have no strawberry shop at day 9. In those towns the champion holds a full strawberry field the town never buys.

Scratch probes (2026-09-21, seeds 1687–2358 spent): from day 9, while no unlocked shop takes strawberry, plant melon instead of strawberry (window 9–18, melon cap 24, strawberry cap 0), reverting the turn a strawberry shop unlocks. On `second_melon` vs `second_melon`, dead-at-9 seeds screened by champion self-play: 16/16 (+11.9K) and 15/16 (+11.3K). Day 12 is a null (field full), day 6 loses on false positives, latching is one game worse, a larger cap never binds.

## The change
**Seam** `FieldRivalStrategy.crop_plan(self, obs)` on the frozen benchmark: returns `None` (frozen) or a `(caps, windows)` pair that `act` uses for this turn in place of `self.CAPS` and `self.melon_windows()`, for the crop workers' `crop_for_plot` and `market_orders`' seed buying alike. The benchmark returns `None`; `feed_bench.off_class` gains the stub; the seam count is eighteen.

**Contender** `strategies/town_melon.py`: `TownMelonStrategy(SecondMelonStrategy)`, `name = "town_melon"`; `DEAD_DAY = 9`, `LAST_MELON_DAY = 18`, `DEAD_WINDOWS = ((9, 18),)`, `DEAD_CAPS = {**free_straw.CAPS_S, "MELON": 24, "STRAWBERRY": 0}`; `straw_dead(shops)`; `crop_plan(obs)` → `(DEAD_CAPS, DEAD_WINDOWS)` when `day >= DEAD_DAY and straw_dead(shops)`, else `None`.

**Bench** `harness/deadtown_bench.py` — see the declaration on #337 for constants, the screen, the three controls and the criterion. The screen (`scan`) plays the champion against itself from `SCAN_FROM` in seed order and keeps the first `SEED_COUNT` seeds whose day-9 town is dead; `LIVE_SEED` is the first seed whose day-9 town is not. The screen's pure part (`screen`) takes an injected reader so it is unit-tested without games.

## Alternatives rejected
On the issue: day-12 and day-6 decisions, latching, a larger cap, melon from day 9 in every town.
