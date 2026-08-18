"""Frozen per-opponent benchmark of one genome (#70)."""
from __future__ import annotations
from harness import genome_bench as gb


def _tagged(tag):
    """Return a stub agent with a tag."""
    def agent(obs):
        return {"farmer": ["PASS"], "hands": [], "market": []}
    agent.tag = tag
    return agent


def _rewards(a, b, seed=None):
    """The agent tagged "strong" scores 300 to the other's 100."""
    if getattr(a, "tag", "") == "strong":
        return (300.0, 100.0)
    if getattr(b, "tag", "") == "strong":
        return (100.0, 300.0)
    return (100.0, 100.0)


def test_benchmark_reports_a_row_per_opponent():
    """The breakdown is per opponent — a single total hid that the champion beat
    exactly one anchor and lost to all five others (#70)."""
    agents = {"weak": _tagged(""), "strong": _tagged("strong")}
    out = gb.benchmark_genome(_tagged("me"), games=2, agents_override=agents,
                              rewards_fn=_rewards)
    names = [r["name"] for r in out["per_opponent"]]
    assert names == ["weak", "strong"]


def test_benchmark_separates_a_beaten_opponent_from_an_unbeaten_one():
    """Losing every game to one opponent and drawing another must be visible
    as two distinct rows, not averaged into one number."""
    agents = {"weak": _tagged(""), "strong": _tagged("strong")}
    out = gb.benchmark_genome(_tagged("me"), games=2, agents_override=agents,
                              rewards_fn=_rewards)
    rows = {r["name"]: r for r in out["per_opponent"]}
    assert rows["weak"]["win_rate"] == 0.5 and rows["weak"]["share"] == 0.5
    assert rows["strong"]["win_rate"] == 0.0 and rows["strong"]["share"] == 0.25


def test_benchmark_totals_average_the_opponents():
    """Overall win-rate and share weight every opponent equally."""
    agents = {"weak": _tagged(""), "strong": _tagged("strong")}
    out = gb.benchmark_genome(_tagged("me"), games=2, agents_override=agents,
                              rewards_fn=_rewards)
    assert out["win_rate"] == 0.25            # (0.5 + 0.0) / 2
    assert out["share"] == 0.375              # (0.5 + 0.25) / 2
    assert out["games"] == 4


def test_benchmark_is_reproducible():
    """ADR-0005: same arguments, same numbers, every time."""
    agents = {"weak": _tagged(""), "strong": _tagged("strong")}
    kw = dict(games=2, agents_override=agents, rewards_fn=_rewards)
    assert gb.benchmark_genome(_tagged("me"), **kw) == gb.benchmark_genome(_tagged("me"), **kw)


# --- build_bench_agents: --include-external opt-in (#78) ---

def test_build_bench_agents_default_excludes_external_and_never_calls_discover():
    """The frozen comparability bar (CLAUDE.md) must not depend on what a
    gitignored, un-fetched directory happens to contain — default OFF."""
    calls = []

    def fake_discover():
        calls.append(True)
        return {"external_x": _tagged("x")}

    agents = gb.build_bench_agents(
        ["meta_bot"], include_external=False, discover_fn=fake_discover,
        build=lambda names: {n: _tagged(n) for n in names},
    )
    assert "external_x" not in agents
    assert calls == []  # discovery is never even attempted on the default path


def test_build_bench_agents_include_external_merges_discovered_agents():
    def fake_discover():
        return {"external_x": _tagged("x")}

    agents = gb.build_bench_agents(
        ["meta_bot"], include_external=True, discover_fn=fake_discover,
        build=lambda names: {n: _tagged(n) for n in names},
    )
    assert set(agents) == {"meta_bot", "external_x"}
