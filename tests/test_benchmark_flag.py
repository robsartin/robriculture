"""The benchmark flag: opt-in on a Strategy subclass, surfaced by the harness."""

from __future__ import annotations

from harness.tournament import benchmark_names
from kaggisim.strategy import Strategy
from strategies import REGISTRY


def test_strategy_base_defaults_to_not_a_benchmark():
    # Every ordinary strategy is a contender unless it opts in.
    assert Strategy.benchmark is False


def test_a_subclass_can_opt_in_to_benchmark():
    class Frozen(Strategy):
        name = "frozen"
        benchmark = True

    assert Frozen.benchmark is True


def test_benchmark_names_is_a_subset_of_the_registry():
    # benchmark_names() are real, registered strategies.
    assert benchmark_names() <= set(REGISTRY)


def test_existing_strategies_are_not_benchmarks_by_default():
    # Nothing shipped so far is a benchmark (meta_bot arrives in a later task).
    assert "ranch_hands" in REGISTRY
    assert "ranch_hands" not in benchmark_names()
