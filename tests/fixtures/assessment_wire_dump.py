"""Child entry point that prints the assess and compare wire text for two decks.

Run as ``python -m tests.fixtures.assessment_wire_dump <db_path> <deck_id_a> <deck_id_b>``.
It opens the database through ``create_engine``, calls ``assess_deck_power`` on deck B and
``compare_deck_power`` on (A, B) through ``build_server`` and an in-memory MCP client, and writes
each call's ``content[0].text`` to stdout as UTF-8, each followed by a newline (the texts are
indented JSON, so a reader splits them with ``json.JSONDecoder.raw_decode``).

``tests/integration/mcp_server/test_assessment_wire_determinism.py`` runs this under two
``PYTHONHASHSEED`` values. Two calls in one interpreter share one hash seed, so a set iterated
without sorting gives the same order both times; two interpreters with different seeds do not.
"""

import asyncio
import sys

from mcp.shared.memory import create_connected_server_and_client_session
from mcp.types import TextContent

from src.data.database import create_engine, create_session_factory
from src.mcp_server.server import build_server


async def _dump(db_path: str, deck_id_a: str, deck_id_b: str) -> list[str]:
    """Return the wire text of the assess (deck B) and compare (A, B) calls, in that order."""
    engine = create_engine(f"sqlite+aiosqlite:///{db_path}")
    try:
        server = build_server(session_factory=create_session_factory(engine))
        async with create_connected_server_and_client_session(server) as client:
            assess = await client.call_tool("assess_deck_power", {"deck_id": deck_id_b})
            compare = await client.call_tool(
                "compare_deck_power", {"deck_id_a": deck_id_a, "deck_id_b": deck_id_b}
            )
    finally:
        await engine.dispose()
    texts: list[str] = []
    for result in (assess, compare):
        block = result.content[0]
        if result.isError or not isinstance(block, TextContent):
            raise RuntimeError(f"tool call did not return wire text: {result!r}")
        texts.append(block.text)
    return texts


def main(argv: list[str]) -> int:
    """Write the two wire texts to stdout; exit 2 on a usage error."""
    if len(argv) != 3:
        print("usage: assessment_wire_dump <db_path> <deck_id_a> <deck_id_b>", file=sys.stderr)
        return 2
    texts = asyncio.run(_dump(*argv))
    for text in texts:
        sys.stdout.buffer.write(text.encode("utf-8") + b"\n")
    sys.stdout.buffer.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
