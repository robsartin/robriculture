"""Every fetched pool entry must bank money against `starter` (#346).

A pool entry that ends every game on $0 still imports, still returns legal
actions and still finishes DONE -- nothing in `external_pool` notices. It is a
dead measurement voice: any agent that sells anything beats it, so a win over
it says nothing. `driw0x_kaggriculture_chi7` was one for weeks: upstream
chi.py-chi7.py never emit SELL at all (selling arrives in chi8.py), and reward
is final money with no end-of-game liquidation.

Seat 0, seed 1, one game each against the env's own `starter` (~3.5K). The
bar is `> 0`, not "beats starter": a weak-but-alive voice is still a voice.
Entries not fetched to `external_agents/` are skipped, so a clean clone and
CI stay green; the check bites on the machine that actually runs the pool.
"""

import os

import pytest
from kaggle_environments import make

from harness import external_pool
from scripts import fetch_external_agents as fea


def _entries():
    return [pytest.param(e, id=e["name"]) for e in fea.load_manifest()]


@pytest.mark.parametrize("entry", _entries())
def test_banks_money_against_starter_when_a_pool_entry_is_fetched(entry):
    path = fea.dest_path(entry, external_pool.DEFAULT_DIR)
    if not os.path.isfile(path):
        pytest.skip(f"{entry['name']} not fetched to {external_pool.DEFAULT_DIR}")
    agent = external_pool.load_external_agent(path)
    final = make("kaggriculture", configuration={"seed": 1}).run([agent, "starter"])[-1]
    assert final[0].status == "DONE"
    assert final[0].reward > 0, (
        f"{entry['name']} banked {final[0].reward} against starter "
        f"({final[1].reward}): a dead pool voice"
    )
