"""Assess and compare wire bytes are identical across two interpreters with different hash seeds.

The in-process byte-determinism tests in ``tests/integration/test_mcp_tools.py`` compare two calls
made in one interpreter. Both calls share one ``PYTHONHASHSEED``, so a set of names iterated
without sorting comes out in the same order both times and those tests cannot see it. Here the
parent builds one fixture database with two decks, then runs
:mod:`tests.fixtures.assessment_wire_dump` in two child processes under ``PYTHONHASHSEED=1`` and
``=2`` and compares their stdout byte for byte. Deck B carries eight confirmed Game Changers that
deck A lacks, so both ``flags.game_changers`` and ``game_changers_added`` are long enough for an
unsorted set to come out in a different order under the two seeds.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

from src.data.database import create_engine, create_session_factory, init_database
from tests.fixtures.assessment_db import assessment_card, assessment_core_cards, make_deck
from tests.fixtures.combo_snapshot import seed_snapshot, snapshot_variant

_REPO_ROOT = Path(__file__).resolve().parents[3]

#: Six Game Changers beyond the two in the core seed, so deck B holds eight.
_EXTRA_GAME_CHANGERS: tuple[tuple[str, str], ...] = (
    ("card-gc-rhystic", "Rhystic Study"),
    ("card-gc-smothering", "Smothering Tithe"),
    ("card-gc-cradle", "Gaea's Cradle"),
    ("card-gc-orcish", "Orcish Bowmasters"),
    ("card-gc-jeskas", "Jeska's Will"),
    ("card-gc-thassa", "Thassa's Oracle"),
)


async def _build_fixture_db(db_path: Path) -> tuple[str, str]:
    """Seed the fixture database, create decks A and B, and return their ids."""
    engine = create_engine(f"sqlite+aiosqlite:///{db_path.as_posix()}")
    await init_database(engine)
    try:
        async with create_session_factory(engine)() as session:
            session.add_all(assessment_core_cards("card-"))
            session.add_all(
                assessment_card(card_id, name, type_line="Artifact", game_changer=True)
                for card_id, name in _EXTRA_GAME_CHANGERS
            )
            await session.commit()
            await seed_snapshot(
                session, [snapshot_variant("1-1", ["Krenko, Mob Boss", "Zada, Hedron Grinder"])]
            )
            base: list[tuple[str, int, bool, bool]] = [
                ("card-krenko", 1, False, True),
                ("card-zada", 1, False, False),
                ("card-goblin-guide", 4, False, False),
                ("card-mountain", 20, False, False),
            ]
            game_changers = [
                ("card-gc-bolas", 1, False, False),
                ("card-gc-aura", 1, False, False),
                *((card_id, 1, False, False) for card_id, _ in _EXTRA_GAME_CHANGERS),
            ]
            deck_a = await make_deck(session, base, name="Seedless A")
            deck_b = await make_deck(session, [*base, *game_changers], name="Seedless B")
    finally:
        await engine.dispose()
    return deck_a, deck_b


def _run_child(hash_seed: str, db_path: Path, deck_a: str, deck_b: str) -> bytes:
    """Run the wire dump under ``hash_seed`` and return its stdout; fail on a non-zero exit."""
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "tests.fixtures.assessment_wire_dump",
            str(db_path),
            deck_a,
            deck_b,
        ],
        cwd=_REPO_ROOT,
        env={**os.environ, "PYTHONHASHSEED": hash_seed},
        capture_output=True,
        timeout=180,
        check=False,
    )
    assert completed.returncode == 0, (
        f"wire dump under PYTHONHASHSEED={hash_seed} exited {completed.returncode}:\n"
        f"{completed.stderr.decode('utf-8', errors='replace')}"
    )
    return completed.stdout


def _split_wire_texts(stdout: bytes) -> list[dict[str, object]]:
    """Parse the child's two concatenated JSON documents."""
    text = stdout.decode("utf-8")
    decoder = json.JSONDecoder()
    documents: list[dict[str, object]] = []
    index = 0
    while text[index:].strip():
        while text[index].isspace():
            index += 1
        document, index = decoder.raw_decode(text, index)
        documents.append(document)
    return documents


async def test_wire_bytes_identical_across_hash_seeds(tmp_path: Path) -> None:
    """Assess and compare emit the same bytes under ``PYTHONHASHSEED`` 1 and 2 (AD-8)."""
    db_path = tmp_path / "wire-determinism.db"
    deck_a, deck_b = await _build_fixture_db(db_path)

    first = _run_child("1", db_path, deck_a, deck_b)
    second = _run_child("2", db_path, deck_a, deck_b)

    # Guard against a vacuous match: both calls answered ok and the payload carries the
    # eight names whose order the hash seed would scramble.
    assess, compare = _split_wire_texts(first)
    assert assess["status"] == "ok", assess
    assert compare["status"] == "ok", compare
    assessment = assess["assessment"]
    assert isinstance(assessment, dict)
    assert len(assessment["flags"]["game_changers"]) == 8
    comparison = compare["comparison"]
    assert isinstance(comparison, dict)
    assert len(comparison["game_changers_added"]) == 8

    assert first == second, "assess/compare wire text differs between PYTHONHASHSEED 1 and 2"
