"""What one farm is actually made of, read off a single observation (#234).

`harness.milk_trace` already counts cows (`count_cows`) because #228 was a
question about one product. #232 and #234 ask a wider one -- how much pasture a
farm builds, how much of it stands empty, how much head waits in the shed
because there is nowhere to put it, and how the tiles are split between crops --
for *either* seat, ours or an opponent's. These are the pure readings behind
that, kept out of the live drives so they unit-test without a 720-turn game.

Tile shapes are the sim's own (`_new_farm`, `_new_plant`, `_new_animal`): a
locked tile is the bare string ``"LOCKED"``, an empty unlocked tile is ``None``,
and everything else is a dict whose ``kind`` is ``PLANT``, ``PASTURE``,
``COOP`` or ``WEED``. An animal is a structure dict carrying an ``animal`` key,
so a pasture with no such key is capacity rather than livestock -- the
distinction #232 is about.
"""

from __future__ import annotations

from kaggisim.economy import ANIMALS

#: The two structures an animal can stand on, always reported even at zero:
#: "no pasture built" and "not measured" must not read the same.
STRUCTURES = ("PASTURE", "COOP")


def _tiles(tiles):
    """Every tile dict on the board, locked and empty tiles skipped."""
    for row in tiles or []:
        for tile in row:
            if isinstance(tile, dict):
                yield tile


def planted_by_crop(tiles):
    """``{crop: tiles}`` for every crop standing on the farm."""
    out: dict = {}
    for tile in _tiles(tiles):
        if tile.get("kind") == "PLANT" and tile.get("crop"):
            crop = tile["crop"]
            out[crop] = out.get(crop, 0) + 1
    return out


def animals_placed(tiles):
    """``{animal: head}`` standing on the farm's structures."""
    out: dict = {}
    for tile in _tiles(tiles):
        animal = tile.get("animal")
        if animal:
            out[animal] = out.get(animal, 0) + 1
    return out


def structure_counts(tiles):
    """Per structure, how many tiles exist and how many stand empty.

    ``free`` is the headroom #232 asks about: head bought past it can never be
    placed, however many herder turns are spent walking it.
    """
    out = {k: {"total": 0, "free": 0} for k in STRUCTURES}
    for tile in _tiles(tiles):
        kind = tile.get("kind")
        if kind in out:
            out[kind]["total"] += 1
            if not tile.get("animal"):
                out[kind]["free"] += 1
    return out


def animals_held(shed):
    """``{animal: head}`` bought but not yet placed, from the private shed.

    Only the sim's animal items count: the shed also holds produce, and a
    count that swept it all up would report milk as livestock.
    """
    return {k: int(n) for k, n in (shed or {}).items()
            if k in ANIMALS and int(n or 0) > 0}


def census(farm, private):
    """One farm's whole shape at one instant.

    ``private`` is optional because only our own side has one: an opponent's
    shed is not in our observation, and the honest reading there is zero held
    head rather than an absent key.
    """
    tiles = (farm or {}).get("tiles")
    placed = animals_placed(tiles)
    held = animals_held(((private or {}).get("shed")) or {})
    planted = planted_by_crop(tiles)
    return {
        "money": float((farm or {}).get("money", 0)),
        "quadrants": list((farm or {}).get("unlocked_quadrants") or []),
        "hands": len((farm or {}).get("hands") or []),
        "planted": planted,
        "planted_tiles": sum(planted.values()),
        "animals_placed": placed,
        "head_placed": sum(placed.values()),
        "animals_held": held,
        "head_held": sum(held.values()),
        "structures": structure_counts(tiles),
        "weeds": sum(1 for t in _tiles(tiles) if t.get("kind") == "WEED"),
        "empty": sum(1 for row in tiles or [] for t in row if t is None),
    }


def aggregate(turns):
    """What a whole game's censuses say about placement (#237).

    `turns` is ``[(day, census), ...]`` in order, one entry per turn the side
    actually acted on -- the shape `census_series` below records. Two of these
    readings are #237's declared mechanism-fired check: the first day pasture
    reaches a threshold (read off `pasture_series` with
    `harness.rival_bench.first_day_at_or_above`, which already answers exactly
    that question) and how many turns head sat unplaced in the shed.

    A turn counts as waiting when ANY head is held: one animal stuck in the
    shed is a turn of waiting whether or not a second is stuck beside it.
    """
    series = [(day, c["structures"]["PASTURE"]["total"]) for day, c in turns]
    return {
        "turns": len(turns),
        "turns_with_head_in_shed": sum(1 for _, c in turns if c["head_held"] > 0),
        "pasture_series": series,
        "max_pasture": max((n for _, n in series), default=0),
        "max_head_placed": max((c["head_placed"] for _, c in turns), default=0),
    }


def census_series(agent_a, agent_b, seed, episode_steps=720):  # pragma: no cover
    """Drive one seeded game and census BOTH farms every turn.

    Each side is read off the observation it actually acted on, so each census
    sees its own private shed -- an opponent's held head is not in our
    observation at all, and reading both boards from one seat would report the
    rival's waiting head as zero.

    `episode_steps` configures the total state count, which is the reset state
    plus ``episode_steps - 1`` `env.step()` calls (`harness.state_set`); calling
    step() `episode_steps` times overruns an already-done env.

    Returns ``(ours, theirs)``, each ``[(day, census), ...]``.
    """
    from kaggle_environments import make
    env = make("kaggriculture", configuration={"episodeSteps": episode_steps, "seed": seed})
    env.reset(2)
    ours, theirs = [], []
    for _ in range(episode_steps - 1):
        obs0 = env.state[0].observation
        obs1 = env.state[1].observation
        ours.append((obs0.get("day", 0), census(obs0["farms"][obs0["player"]], obs0["private"])))
        theirs.append((obs1.get("day", 0), census(obs1["farms"][obs1["player"]], obs1["private"])))
        env.step([agent_a(obs0), agent_b(obs1)])
    return ours, theirs
