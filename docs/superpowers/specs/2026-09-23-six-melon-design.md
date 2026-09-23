# six_melon — water a melon before cutting it, carry eighteen (#341)

**Declared on #341** under ADR-0007 as amended 2026-09-16, 2026-09-20 and 2026-09-21, corrected 2026-09-17. The issue is the declaration; this spec is the design the plan implements.

## The finding
Melon yield rises by one per WATER between ages 6 and 12 (the sim's WATER op: `(max_yield_day + 1) // 2` to `max_yield_day`). Our plot rule harvests before it waters, so the first wave is cut at five units on day 10; opponents water first and cut six. Water-first alone loses: at yield six a worker fills its carry of six on one tile instead of two, halves its harvests, and the tiles it never reaches die after two dry days. With the carry raised to eighteen (the sim has no per-worker cap; six is our own constant) the probes read 13/16 (+2.0K) and 12/16 (+1.0K); the carry alone is a null.

## The change
**Seams** on the frozen benchmark, off by default:
- `plot_action(tile, crop, day, hour, water_first=False)`: with `water_first`, a live, harvest-ready, non-ongoing plant not watered today whose `yield_units < max_yield` and whose age ≤ `max_yield_day` gets WATER; the next turn's visit harvests. Frozen otherwise.
- `crop_worker_action(..., carry=CARRY_LIMIT, water_first=False)`: `carry` replaces the module constant in the bank check; `water_first` is passed to `plot_action`.
- Hooks `FieldRivalStrategy.carry_limit(self) -> None` and `water_first(self) -> None`; `act` passes `carry=CARRY_LIMIT if the hook is None else its value` and `water_first=bool(self.water_first())` to `crop_worker_action`. `feed_bench.off_class` gains both stubs; the seam count is twenty.

**Contender** `strategies/six_melon.py`: `SixMelonStrategy(TownMelonStrategy)`, `name = "six_melon"`, `CARRY = 18`; `carry_limit()` returns `CARRY`, `water_first()` returns `True`.

**Bench** `harness/sixmelon_bench.py` — see #341: identity control (twenty seams off), mechanism control (melon units sold by the end of day `EARLY_DAY = 13` ≥ `EARLY_BAR = 60` and > the champion's; melon units over the game > the champion's; strawberry units printed), then `rival_bench.decided_row` + anchors + paired externals on seeds 2522–2537.

## Alternatives rejected
On the issue: water first at carry six, a cluster-wide order, the carry alone, carry 24, fertilizing the first wave.
