# ADR-0004: Python-only agent

- **Status:** Accepted
- **Date:** 2026-08-04
- **Deciders:** Rob

## Context

The team's default stack is Java/Spring. However, the competition simulator
(`kaggle_environments`) is Python, and a submission must expose a Python
`agent(obs)` in a `main.py` at the archive root, running self-contained with no
network access on a constrained runtime (1.6 vCPU, 6.5 GB RAM, ≤100 MiB).

## Decision

Write the agent and all supporting code in Python. Do not route agent logic
through the JVM (e.g. via a subprocess or shared library).

## Consequences

- Zero impedance mismatch with the simulator; simplest packaging and lowest
  crash risk at evaluation.
- Team members most comfortable in Java take on a Python context switch; mitigated
  by keeping the code clean, typed where useful, and well-structured.
- We forgo reusing any existing Java tooling for the agent itself.

## Alternatives considered

- **Java core + Python shim.** Rejected: bundling a JVM/native lib within 100 MiB
  with no network, plus per-turn IPC overhead and added failure modes, is not
  worth it for a turn-based agent.
- **Prototype in Java, port to Python.** Rejected: double implementation cost for
  no benefit; develop directly in the submission language.
