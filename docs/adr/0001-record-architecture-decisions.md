# ADR-0001: Record architecture decisions

- **Status:** Accepted
- **Date:** 2026-08-04
- **Deciders:** Rob

## Context

This project explores several genuinely different agent strategies over an
~8-week competition window, and design decisions made early (architecture,
packaging, licensing) have long tails. We want the reasoning behind those
choices preserved so we — or teammates who join before the Sept 23 merger
deadline — don't relitigate settled questions or lose the "why".

## Decision

Use Architecture Decision Records (Michael Nygard format) stored in
`docs/adr/`, one file per decision, append-only. Decisions already made during
initial planning are backfilled as ADR-0002 through ADR-0005. New decisions get
new ADRs as they arise during development.

## Consequences

- Cheap, durable record of intent that lives with the code and is reviewable in
  PRs.
- Small ongoing discipline cost: significant decisions should be written up
  rather than living only in chat or memory.

## Alternatives considered

- **A single running design doc.** Rejected: mutable, so the historical "why"
  gets overwritten.
- **No formal record.** Rejected: with multiple strategies and a possible team,
  the context loss is expensive.
