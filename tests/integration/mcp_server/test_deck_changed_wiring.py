"""Every deck-mutation tool emits ``deck_changed`` after its commit — and nothing else does (c7-2).

Two halves, one file.

**The behavioural half** drives the five mutation tools — ``create_deck`` / ``delete_deck`` /
``add_card_to_deck`` / ``import_decklist`` / ``remove_card_from_deck`` — through an in-process MCP
client against a real file-backed database, with a recording stub monkeypatched at **server.py's
own import seam** (``server._notify_deck_changed``). Patching there rather than on the leaf is the
same reasoning ``test_companion_tool.py`` documents: the property under test is that *this* module
reaches the notifier through the name it imported. What is proven:

* every persisted write emits exactly once, carrying that deck's id — including a multi-line
  import, whose helper delegates per line and commits N times but must sound like one change;
* the emit happens **after the commit is visible**: the stub opens its own session from the same
  factory at notify time and sees the created row present / the deleted row gone — the "the view
  can never show something the database doesn't have" guarantee, made mechanical;
* every no-write outcome (``invalid`` / ``exists`` / ``not_in_deck`` / ``*_not_found`` /
  ``ambiguous`` / ``error`` / ``database_not_initialized`` / an import landing zero lines) emits
  nothing;
* a failure ``PushOutcome`` leaves the tool's structured result byte-identical — the notification
  outcome never becomes a status, a field or a changed message;
* with no companion anywhere (``PLANESWALKER_DATA_DIR`` repointed at an empty directory, the
  **real** client on the path), a mutation still returns ``ok`` — the notifier degrades to a
  cheap ``app_not_running`` that the tool result never mentions.

**The enumeration half** is the guard the epic asked for: a future mutation tool cannot be
forgotten silently. It *derives* the set of mutating tools rather than trusting a hand-kept list —
sweeping every module under ``src/mcp_server/tools/`` (recursively, ``__init__.py`` included) for
references to the pinned deck-write repository methods (``_REPO_WRITE_METHODS``, imported from
``test_import_boundary.py`` where ``TestRepositorySurfaceIsPinned`` cross-checks it against the
live repositories), then closing over delegation in every call shape a repo module can legally
write: from-imported names (aliased, absolute or **relative** — ``deck_import``'s
``_add_card_to_deck`` is the absolute-alias case that demands resolution, and the project's import
convention permits the relative twin), same-module names, and attribute calls through
module-object bindings (``import ... as dm; dm.helper(...)``). The derived set, mapped through
``server.py``'s own imports to the wrappers that call them, must equal the five wired tool names;
a sixth deck-write surface fails here **by name** until it is wired. Sibling guards pin the
wiring's shape: server.py itself never touches a repository write method (the inline-mutation
bypass), only the five wrappers reference the emit path, no emit reference sits inside an ``async
with`` session block (the connection-held-across-HTTP hazard ``companion.py:181-186`` documents),
and every reference in ``server.py`` sits under a plain ``await`` — the local half of the
detached-task ban (``create_task``/``ensure_future``/``TaskGroup``/``gather``), which
``test_ws.py`` enforces for ``src/companion`` and this file enforces for the new sites without
extending that package sweep.

Despite living under ``tests/integration/``, these run in the ordinary ``-m "not integration"``
set: a directory is not a marker (AD-10), and nothing here opens a socket — the degradation test
finds no discovery file before any HTTP could begin.
"""

import ast
from collections.abc import AsyncGenerator, Awaitable, Callable
from pathlib import Path

import pytest
from mcp.shared.memory import create_connected_server_and_client_session
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.companion.client import PUSH_OUTCOMES, PushOutcome
from src.companion.discovery import COMPANION_FILENAME, read_discovery
from src.data.database import create_engine, create_session_factory, init_database
from src.data.models.card import CardModel
from src.data.repositories.deck import DeckRepository
from src.mcp_server import server as server_module
from src.mcp_server.server import build_server
from tests.unit.companion.test_import_boundary import (
    _REPO_WRITE_METHODS,
    package_for,
    repo_relative,
    resolve_import,
)

# ---------------------------------------------------------------------------------------------
# Repository layout — resolved from __file__, never from the runner's working directory.
# ---------------------------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[3]
_TOOLS_DIR = _REPO_ROOT / "src" / "mcp_server" / "tools"
_SERVER_PATH = _REPO_ROOT / "src" / "mcp_server" / "server.py"
_TOOLS_PACKAGE = "src.mcp_server.tools"

_MUTATION_TOOLS = frozenset(
    {"create_deck", "delete_deck", "add_card_to_deck", "import_decklist", "remove_card_from_deck"}
)
"""The five wired tools. The enumeration guard *derives* its own set from the write methods the
tools actually reach and asserts equality with this one — so the constant is an expectation to
diff against, never the source of truth about what mutates."""

_EMIT_NAMES = frozenset({"_emit_deck_changed", "_notify_deck_changed"})
"""Both names on the emit path in server.py: the wrapper-facing helper and the leaf notifier it
delegates to. The guards treat a reference to either as a reference to the path."""


def _card(card_id: str, name: str) -> CardModel:
    return CardModel(
        id=card_id,
        name=name,
        printed_name=None,
        oracle_id=f"oracle-{card_id}",
        mana_cost="{R}",
        cmc=1.0,
        type_line="Instant",
        oracle_text="Deals 3 damage.",
        rarity="common",
        set_code="TST",
        set_name="Test Set",
        collector_number="1",
        colors=["R"],
        color_identity=["R"],
        legalities={"standard": "legal"},
    )


@pytest.fixture
async def deck_db(tmp_path: Path) -> AsyncGenerator[async_sessionmaker[AsyncSession], None]:
    """A file-backed, initialised database seeded with two cards sharing the substring "bolt".

    Two rather than one so the ``ambiguous`` no-write path is drivable; file-backed rather than
    in-memory so the after-commit observer's *separate* session genuinely re-reads storage.
    """
    engine = create_engine(f"sqlite+aiosqlite:///{(tmp_path / 'cards.db').as_posix()}")
    await init_database(engine)
    session_factory = create_session_factory(engine)
    async with session_factory() as session:
        session.add(_card("card-bolt", "Lightning Bolt"))
        session.add(_card("card-thunderbolt", "Thunderbolt"))
        await session.commit()
    yield session_factory
    await engine.dispose()


@pytest.fixture
async def uninitialized_db(
    tmp_path: Path,
) -> AsyncGenerator[async_sessionmaker[AsyncSession], None]:
    """A schema that exists but holds no cards — ``database_not_initialized`` territory."""
    engine = create_engine(f"sqlite+aiosqlite:///{(tmp_path / 'empty.db').as_posix()}")
    await init_database(engine)
    yield create_session_factory(engine)
    await engine.dispose()


class _RecordingNotifier:
    """Stands in for c7-1's notifier at server.py's import seam, recording every emit.

    Recording the deck ids rather than a call count is deliberate: "nothing was emitted" and "the
    wrong deck was announced" are different failures, and only a recorded argument list tells them
    apart. The optional ``observer`` runs *at notify time* — the after-commit proofs use it to
    read the database through their own session while the emit is in flight.
    """

    def __init__(
        self,
        outcome: PushOutcome | None = None,
        observer: Callable[[str | None], Awaitable[object]] | None = None,
    ) -> None:
        if outcome is None:
            outcome = PushOutcome(outcome="displayed", clients=1)
        self.outcome = outcome
        self.observer = observer
        self.deck_ids: list[str | None] = []
        self.observations: list[object] = []

    async def __call__(self, deck_id: str | None = None, *, timeout: object = None) -> PushOutcome:
        self.deck_ids.append(deck_id)
        if self.observer is not None:
            self.observations.append(await self.observer(deck_id))
        return self.outcome


@pytest.fixture
def notifier(monkeypatch: pytest.MonkeyPatch):
    """Yield a factory installing a :class:`_RecordingNotifier` as ``server._notify_deck_changed``.

    The wrappers close over the module-level ``_emit_deck_changed``, which resolves
    ``_notify_deck_changed`` as a module global at call time — so patching the server module's
    binding intercepts every emit without touching the leaf client.
    """

    def install(
        outcome: PushOutcome | None = None,
        observer: Callable[[str | None], Awaitable[object]] | None = None,
    ) -> _RecordingNotifier:
        stub = _RecordingNotifier(outcome=outcome, observer=observer)
        monkeypatch.setattr(server_module, "_notify_deck_changed", stub)
        return stub

    return install


class TestEachPersistedWriteEmitsExactlyOnce:
    """The matrix's write rows: one emit, the right id, after the commit is visible."""

    async def test_create_deck_emits_the_new_id_and_the_row_is_already_visible(
        self, deck_db, notifier
    ):
        """The after-commit proof for creation: a *separate* session sees the row at notify time.

        An emit fired inside the transaction would announce a deck a refetching UI cannot load
        yet; the observer reading through its own connection is what makes "after the commit"
        a measured fact rather than a description of where the call sits in the source.
        """

        async def row_exists(deck_id: str | None) -> bool:
            assert deck_id is not None
            async with deck_db() as session:
                return await DeckRepository(session).get_deck(deck_id) is not None

        stub = notifier(observer=row_exists)
        server = build_server(session_factory=deck_db)
        async with create_connected_server_and_client_session(server) as client:
            created = await client.call_tool("create_deck", {"name": "Burn"})

        assert created.isError is False
        assert created.structuredContent is not None
        assert created.structuredContent["status"] == "ok"
        deck_id = created.structuredContent["deck"]["id"]
        assert stub.deck_ids == [deck_id], "exactly one emit, carrying the new deck's id"
        assert stub.observations == [True], "the created row was visible at notify time"

    async def test_delete_deck_emits_the_now_absent_id_after_the_row_is_gone(
        self, deck_db, notifier
    ):
        """Deletion emits too (the UI's refetch 404s and clears, by design) — after the row is
        gone, so a refetch racing the emit can never resurrect the deck."""

        async def row_exists(deck_id: str | None) -> bool:
            assert deck_id is not None
            async with deck_db() as session:
                return await DeckRepository(session).get_deck(deck_id) is not None

        stub = notifier(observer=row_exists)
        server = build_server(session_factory=deck_db)
        async with create_connected_server_and_client_session(server) as client:
            created = await client.call_tool("create_deck", {"name": "Doomed"})
            deck_id = created.structuredContent["deck"]["id"]
            deleted = await client.call_tool("delete_deck", {"deck_id": deck_id})

        assert deleted.structuredContent["status"] == "ok"
        assert stub.deck_ids == [deck_id, deck_id], "the create emitted, then the delete emitted"
        assert stub.observations == [True, False], (
            "at the delete's notify time the row was already gone"
        )

    async def test_add_card_emits_the_deck_id_once(self, deck_db, notifier):
        stub = notifier()
        server = build_server(session_factory=deck_db)
        async with create_connected_server_and_client_session(server) as client:
            created = await client.call_tool("create_deck", {"name": "Burn"})
            deck_id = created.structuredContent["deck"]["id"]
            added = await client.call_tool(
                "add_card_to_deck", {"deck_id": deck_id, "card_id": "card-bolt", "quantity": 4}
            )

        assert added.structuredContent["status"] == "ok"
        assert stub.deck_ids == [deck_id, deck_id], "one for the create, one for the add"

    async def test_remove_card_emits_the_deck_id_once(self, deck_db, notifier):
        stub = notifier()
        server = build_server(session_factory=deck_db)
        async with create_connected_server_and_client_session(server) as client:
            created = await client.call_tool("create_deck", {"name": "Burn"})
            deck_id = created.structuredContent["deck"]["id"]
            await client.call_tool("add_card_to_deck", {"deck_id": deck_id, "card_id": "card-bolt"})
            removed = await client.call_tool(
                "remove_card_from_deck", {"deck_id": deck_id, "card_id": "card-bolt"}
            )

        assert removed.structuredContent["status"] == "ok"
        assert stub.deck_ids == [deck_id] * 3, "create, add, remove — one emit each"

    async def test_a_multi_line_import_emits_exactly_once(self, deck_db, notifier):
        """The helper delegates per line and commits N times; the glass hears one change.

        Per-line emits are precisely what wrapper-level wiring exists to prevent — this is the
        assertion that fails if the emit ever migrates into ``deck_import.py``'s loop.
        """
        stub = notifier()
        server = build_server(session_factory=deck_db)
        export = "Deck\n2 Lightning Bolt (TST) 1\n1 Thunderbolt (TST) 2\n1 Counterspell (TST) 3"
        async with create_connected_server_and_client_session(server) as client:
            created = await client.call_tool("create_deck", {"name": "Imported"})
            deck_id = created.structuredContent["deck"]["id"]
            imported = await client.call_tool(
                "import_decklist", {"deck_id": deck_id, "arena_export": export}
            )

        sc = imported.structuredContent
        assert sc["status"] == "partial", "two lines land, the unseeded Counterspell does not"
        assert sc["imported_lines"] == 2, "a real multi-line import, or the count proves nothing"
        assert stub.deck_ids == [deck_id, deck_id], (
            "the create emitted once and the whole import emitted once — never once per line"
        )


class TestANoWriteOutcomeEmitsNothing:
    """The matrix's zero-emit rows: every status that persisted nothing announces nothing."""

    async def test_every_drivable_no_write_status_is_silent(self, deck_db, notifier):
        """One server, every no-write status the tool surface can produce, zero new emits.

        Each case asserts its expected status first — a case that drifted into ``ok`` would be a
        write, and the final count would be measuring the wrong thing.
        """
        stub = notifier()
        server = build_server(session_factory=deck_db)
        async with create_connected_server_and_client_session(server) as client:
            created = await client.call_tool("create_deck", {"name": "Quiet"})
            deck_id = created.structuredContent["deck"]["id"]
            baseline = len(stub.deck_ids)

            cases = [
                ("create_deck", {"name": "   "}, "invalid"),
                ("delete_deck", {"deck_id": "no-such-deck"}, "not_found"),
                (
                    "add_card_to_deck",
                    {"deck_id": "no-such-deck", "card_id": "card-bolt"},
                    "deck_not_found",
                ),
                (
                    "add_card_to_deck",
                    {"deck_id": deck_id, "name": "No Such Card"},
                    "card_not_found",
                ),
                ("add_card_to_deck", {"deck_id": deck_id, "name": "bolt"}, "ambiguous"),
                ("add_card_to_deck", {"deck_id": deck_id}, "invalid"),
                (
                    "remove_card_from_deck",
                    {"deck_id": deck_id, "card_id": "card-bolt"},
                    "not_in_deck",
                ),
                ("import_decklist", {"deck_id": deck_id, "arena_export": "   "}, "invalid"),
                (
                    # Every line parses, no line lands: `partial` with imported_lines == 0 — the
                    # one import status the emit predicate must read past the status to refuse.
                    "import_decklist",
                    {"deck_id": deck_id, "arena_export": "Deck\n1 No Such Card (TST) 9"},
                    "partial",
                ),
            ]
            for tool, args, expected in cases:
                result = await client.call_tool(tool, args)
                assert result.structuredContent["status"] == expected, (tool, args)
                if tool == "import_decklist" and expected == "partial":
                    assert result.structuredContent["imported_lines"] == 0

        assert len(stub.deck_ids) == baseline, (
            f"a no-write outcome emitted: {stub.deck_ids[baseline:]}"
        )

    async def test_an_exists_answer_is_not_a_write(self, deck_db, notifier):
        """The near-miss case: the same call that just emitted, repeated, must not emit again."""
        stub = notifier()
        server = build_server(session_factory=deck_db)
        async with create_connected_server_and_client_session(server) as client:
            created = await client.call_tool("create_deck", {"name": "Burn"})
            deck_id = created.structuredContent["deck"]["id"]
            first = await client.call_tool(
                "add_card_to_deck", {"deck_id": deck_id, "card_id": "card-bolt"}
            )
            emits_after_first = len(stub.deck_ids)
            second = await client.call_tool(
                "add_card_to_deck", {"deck_id": deck_id, "card_id": "card-bolt"}
            )

        assert first.structuredContent["status"] == "ok"
        assert second.structuredContent["status"] == "exists"
        assert emits_after_first == 2, "the non-vacuity twin: the first add really did emit"
        assert len(stub.deck_ids) == 2, "the exists answer added nothing and announced nothing"

    async def test_an_uninitialized_database_is_silent(self, uninitialized_db, notifier):
        stub = notifier()
        server = build_server(session_factory=uninitialized_db)
        async with create_connected_server_and_client_session(server) as client:
            result = await client.call_tool("create_deck", {"name": "Too Early"})

        assert result.structuredContent["status"] == "database_not_initialized"
        assert stub.deck_ids == []

    async def test_a_database_error_mid_write_is_silent(self, deck_db, notifier, monkeypatch):
        """``status="error"`` means nothing persisted — the rolled-back mutation emits nothing."""
        from sqlalchemy.exc import DatabaseError

        stub = notifier()
        server = build_server(session_factory=deck_db)
        async with create_connected_server_and_client_session(server) as client:
            created = await client.call_tool("create_deck", {"name": "Sturdy"})
            deck_id = created.structuredContent["deck"]["id"]

            async def boom(self, deck_id: str) -> bool:
                raise DatabaseError("delete", {}, Exception("disk I/O error"))

            monkeypatch.setattr(DeckRepository, "delete_deck", boom)
            result = await client.call_tool("delete_deck", {"deck_id": deck_id})

        assert result.structuredContent["status"] == "error"
        assert stub.deck_ids == [deck_id], "only the create emitted; the failed delete was silent"


class TestANotifyOutcomeNeverTouchesTheResult:
    """The matrix's failure row: the emit is an aside, never a participant in the result."""

    @pytest.mark.parametrize("outcome", [o for o in PUSH_OUTCOMES if o != "displayed"])
    async def test_the_structured_result_is_identical_across_outcome_tokens(
        self, deck_db, notifier, outcome
    ):
        """The same mutation under a success outcome and under *outcome* answers byte-identically.

        Byte-identical, not merely both ``ok``: a wrapper that leaked the outcome into a message,
        a count or a new field would still pass a status-only assertion. Nothing raises either —
        the real client guarantees that; here the guarantee is that the wrapper adds no seam
        where an outcome could become an error.
        """
        stub = notifier(PushOutcome(outcome="displayed", clients=1))
        server = build_server(session_factory=deck_db)
        async with create_connected_server_and_client_session(server) as client:
            created = await client.call_tool("create_deck", {"name": "Steady"})
            deck_id = created.structuredContent["deck"]["id"]
            baseline = await client.call_tool(
                "add_card_to_deck", {"deck_id": deck_id, "card_id": "card-bolt"}
            )
            assert baseline.structuredContent["status"] == "ok"

            await client.call_tool(
                "remove_card_from_deck", {"deck_id": deck_id, "card_id": "card-bolt"}
            )
            stub.outcome = PushOutcome(outcome=outcome)
            again = await client.call_tool(
                "add_card_to_deck", {"deck_id": deck_id, "card_id": "card-bolt"}
            )

        assert again.isError is False
        assert again.structuredContent == baseline.structuredContent, (
            f"a {outcome!r} notify outcome altered the mutation's own result"
        )


class TestAClosedCompanionCostsTheMutationNothing:
    """The degradation row, with the real client on the path and no companion anywhere."""

    async def test_a_mutation_still_persists_and_reports_ok(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, deck_db
    ):
        """No stub: the emit reaches the real ``notify_deck_changed``, which finds no discovery
        file and returns ``app_not_running`` cheaply. The tool result neither fails nor mentions
        the companion — SC-3's promise carried into the mutation tools."""
        data_dir = tmp_path / "no-companion-here"
        data_dir.mkdir()
        monkeypatch.setenv("PLANESWALKER_DATA_DIR", str(data_dir))
        assert not (data_dir / COMPANION_FILENAME).exists()
        assert read_discovery() is None, (
            "something published a discovery record into the isolated data dir — this would be "
            "measuring a live companion instead of a closed one"
        )

        server = build_server(session_factory=deck_db)
        async with create_connected_server_and_client_session(server) as client:
            created = await client.call_tool("create_deck", {"name": "Offline"})
            assert created.isError is False
            assert created.structuredContent["status"] == "ok"
            deck_id = created.structuredContent["deck"]["id"]

            added = await client.call_tool(
                "add_card_to_deck", {"deck_id": deck_id, "card_id": "card-bolt"}
            )

        assert added.isError is False
        sc = added.structuredContent
        assert sc["status"] == "ok"
        assert "companion" not in sc["message"].lower(), (
            "the mutation's own message must not surface the notification's fate"
        )


# ---------------------------------------------------------------------------------------------
# The enumeration half: AST guards over the real tree. Pure helpers first, thin tests below.
# ---------------------------------------------------------------------------------------------


def _parse(path: Path) -> ast.Module:
    """Parse *path* without importing it (``utf-8-sig`` so a BOM never reads as a SyntaxError)."""
    return ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))


def _functions(tree: ast.Module) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
    """Top-level function definitions of *tree*."""
    return [n for n in tree.body if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)]


def _names_used(fn: ast.AST) -> set[str]:
    """Every bare identifier referenced anywhere inside *fn*."""
    return {n.id for n in ast.walk(fn) if isinstance(n, ast.Name)}


def _tool_modules() -> dict[str, tuple[Path, ast.Module]]:
    """Parse every module under the tools package — recursively, ``__init__.py`` included.

    Keyed by the module's dotted path relative to the package (``deck_management``; ``sub.mod``
    for a future subpackage; ``__init__`` for a package initializer), so a helper hiding in an
    initializer or a future subpackage is swept like any other module.
    """
    files = sorted(_TOOLS_DIR.rglob("*.py"))
    assert files, f"no tool modules found under {_TOOLS_DIR} — the sweep would pass vacuously"
    modules: dict[str, tuple[Path, ast.Module]] = {}
    for path in files:
        parts = path.relative_to(_TOOLS_DIR).with_suffix("").parts
        modules[".".join(parts)] = (path, _parse(path))
    return modules


def _module_key_for(base: str) -> str | None:
    """Turn an absolute dotted import target into a tools-package module key, or ``None``."""
    if base == _TOOLS_PACKAGE:
        return "__init__"
    if base.startswith(f"{_TOOLS_PACKAGE}."):
        return base[len(_TOOLS_PACKAGE) + 1 :]
    return None


def _imported_name_edges(path: Path, tree: ast.Module) -> dict[str, tuple[str, str]]:
    """Map each name a file from-imports out of the tools package to its ``(module_key, name)``.

    Covers ``from src.mcp_server.tools.X import y [as z]`` — the alias form ``deck_import`` uses
    for ``add_card_to_deck`` — **and its relative twin** ``from .X import y``, which the repo's
    import convention explicitly permits within a package. Relative levels are resolved through
    the importing file's own package (``resolve_import``, shared with the AD-2/AD-3 guards), so a
    delegation cannot hide behind a leading dot.
    """
    package = package_for(repo_relative(path))
    edges: dict[str, tuple[str, str]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        key = _module_key_for(resolve_import(node.module, node.level, package))
        if key is None:
            continue
        for alias in node.names:
            edges[alias.asname or alias.name] = (key, alias.name)
    return edges


def _module_bindings(path: Path, tree: ast.Module) -> dict[str, str]:
    """Map each module-object binding of a tools module to its module key.

    Covers ``import src.mcp_server.tools.X [as y]`` and ``from src.mcp_server.tools import X``
    (absolute or relative): delegation then looks like ``y.helper(...)`` — an *attribute* call
    the name-edge map structurally cannot see, so the closure needs this second map.
    """
    package = package_for(repo_relative(path))
    bindings: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                key = _module_key_for(alias.name)
                if key is not None:
                    # Without an asname the usable binding is the full dotted chain, which is
                    # exactly what an attribute reference unparses to.
                    bindings[alias.asname or alias.name] = key
        elif isinstance(node, ast.ImportFrom):
            key = _module_key_for(resolve_import(node.module, node.level, package))
            if key is None:
                continue
            for alias in node.names:
                # `from ..tools import deck_management [as dm]` binds a *submodule* object;
                # non-module names bound this way resolve to no module key and simply miss.
                sub = alias.name if key == "__init__" else f"{key}.{alias.name}"
                bindings[alias.asname or alias.name] = sub
    return bindings


def _edge_hits(target: tuple[str, str], mutating: set[tuple[str, str]]) -> bool:
    """True when *target* names a mutating function — directly or via a package initializer."""
    key, name = target
    return (key, name) in mutating or (f"{key}.__init__", name) in mutating


def _delegates_to_mutating(
    fn: ast.AST,
    *,
    module_key: str | None,
    local_functions: set[str],
    name_edges: dict[str, tuple[str, str]],
    module_bindings: dict[str, str],
    mutating: set[tuple[str, str]],
) -> bool:
    """True when *fn* reaches a mutating function through any of the three call shapes.

    The shapes: a from-imported name (aliased, absolute or relative); a same-module name; an
    attribute call through a module-object binding (``dm.add_card_to_deck(...)``).
    """
    for name in _names_used(fn):
        if name in name_edges and _edge_hits(name_edges[name], mutating):
            return True
        if module_key is not None and name in local_functions and (module_key, name) in mutating:
            return True
    for node in ast.walk(fn):
        if isinstance(node, ast.Attribute):
            prefix, _, attr = ast.unparse(node).rpartition(".")
            if prefix in module_bindings and _edge_hits((module_bindings[prefix], attr), mutating):
                return True
    return False


def _mutating_helpers(modules: dict[str, tuple[Path, ast.Module]]) -> set[tuple[str, str]]:
    """Derive every ``(module_key, function)`` in the tools package that can write deck tables.

    Seed: functions holding an attribute reference to a pinned repository write method. Closure:
    functions that reach a mutating function through any shape :func:`_delegates_to_mutating`
    resolves join the set, to a fixpoint — a future helper that writes through three layers of
    delegation is still found, as long as each hop is an ordinary call.
    """
    mutating = {
        (key, fn.name)
        for key, (_, tree) in modules.items()
        for fn in _functions(tree)
        if any(
            isinstance(node, ast.Attribute) and node.attr in _REPO_WRITE_METHODS
            for node in ast.walk(fn)
        )
    }
    changed = True
    while changed:
        changed = False
        for key, (path, tree) in modules.items():
            name_edges = _imported_name_edges(path, tree)
            bindings = _module_bindings(path, tree)
            local = {fn.name for fn in _functions(tree)}
            for fn in _functions(tree):
                if (key, fn.name) in mutating:
                    continue
                if _delegates_to_mutating(
                    fn,
                    module_key=key,
                    local_functions=local,
                    name_edges=name_edges,
                    module_bindings=bindings,
                    mutating=mutating,
                ):
                    mutating.add((key, fn.name))
                    changed = True
    return mutating


def _server_wrappers(tree: ast.Module) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
    """The tool wrappers: the function definitions nested directly in ``build_server``."""
    build = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name == "build_server"
    )
    wrappers = [n for n in build.body if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)]
    assert len(wrappers) >= 15, (
        f"only {len(wrappers)} wrappers found inside build_server — the scan shape is wrong"
    )
    return wrappers


class TestEveryMutationToolIsWiredAndNoOtherToolIs:
    """The enumeration guard: derived writers == wired emitters, by name, forever."""

    def test_the_derived_mutating_tools_are_exactly_the_five_wired_ones(self):
        """A sixth deck-write surface fails here naming the unwired tool.

        The derivation starts from ``_REPO_WRITE_METHODS`` — the same pinned vocabulary the AD-2
        write guard bans and ``TestRepositorySurfaceIsPinned`` cross-checks against the live
        repository classes — so a brand-new write method cannot slip past this sweep without
        first failing that pin.
        """
        assert _REPO_WRITE_METHODS, "the pinned write vocabulary is empty — nothing to derive from"
        modules = _tool_modules()
        assert "__init__" in modules, (
            "the recursive sweep no longer sees the package initializer — a helper could hide "
            "in tools/__init__.py unseen"
        )
        mutating = _mutating_helpers(modules)

        # Non-vacuity, both derivation legs: the direct-reference seed found the plain writers,
        # and the fixpoint resolved the aliased cross-module delegation that demands it.
        assert ("deck_management", "add_card_to_deck") in mutating
        assert ("deck_import", "import_decklist") in mutating, (
            "the aliased-delegation case (_add_card_to_deck) was not resolved — the closure leg "
            "of the derivation is broken, and a delegating future tool would go unseen"
        )

        tree = _parse(_SERVER_PATH)
        name_edges = _imported_name_edges(_SERVER_PATH, tree)
        bindings = _module_bindings(_SERVER_PATH, tree)
        wired = {
            wrapper.name
            for wrapper in _server_wrappers(tree)
            if _delegates_to_mutating(
                wrapper,
                module_key=None,
                local_functions=set(),
                name_edges=name_edges,
                module_bindings=bindings,
                mutating=mutating,
            )
        }
        assert wired == set(_MUTATION_TOOLS), (
            "the tools that reach a deck-write repository method and the five wired emitters "
            f"disagree — wire (or unwire) the difference: {sorted(wired ^ set(_MUTATION_TOOLS))}"
        )

    def test_server_py_reaches_no_repository_write_method_directly(self):
        """The inline-mutation hole, closed cheaply: server.py itself never touches a writer.

        The derivation sweeps the tools package, so a mutation coded directly in ``server.py``
        against a repository would bypass it entirely — and would be a sixth write surface with
        no helper for the enumeration to find. This pin makes that shape fail by name: any
        attribute reference to a pinned write method inside ``server.py`` is a breach, whatever
        the receiver.
        """
        assert _REPO_WRITE_METHODS, "the pinned write vocabulary is empty — nothing to pin against"
        offenders = [
            f"server.py:{node.lineno} — {ast.unparse(node)}"
            for node in ast.walk(_parse(_SERVER_PATH))
            if isinstance(node, ast.Attribute) and node.attr in _REPO_WRITE_METHODS
        ]
        assert not offenders, (
            "server.py references a repository write method directly — deck writes belong in a "
            f"tools helper, where the enumeration guard can see them: {offenders}"
        )

    def test_no_emit_reference_sits_inside_a_session_block(self):
        """The Always-constraint "emit outside the session block, never inside it", structural.

        The after-commit observers cannot catch this regression — the repositories commit
        internally, so the row is visible to a second session either way. What an inline emit
        *does* cost is a pooled connection held open across the up-to-~1 s notify window, the
        exact hazard ``companion.py:181-186`` documents and the wrapper restructure exists to
        avoid structurally. So the guard is structural too: within a mutation wrapper, no
        emit-path name may sit anywhere under an ``async with`` block.
        """
        wrappers = _server_wrappers(_parse(_SERVER_PATH))
        mutating_wrappers = [w for w in wrappers if w.name in _MUTATION_TOOLS]
        assert {w.name for w in mutating_wrappers} == set(_MUTATION_TOOLS), (
            "the wrapper scan no longer finds all five mutation tools — the scan shape is wrong"
        )

        offenders = []
        for wrapper in mutating_wrappers:
            session_blocks = [n for n in ast.walk(wrapper) if isinstance(n, ast.AsyncWith)]
            assert session_blocks, (
                f"{wrapper.name} holds no async-with block at all — the wrapper shape changed "
                "and this guard can no longer see the session boundary; rewrite it, don't skip it"
            )
            for block in session_blocks:
                offenders.extend(
                    f"{wrapper.name}:{node.lineno} — {node.id} inside the session block"
                    for node in ast.walk(block)
                    if isinstance(node, ast.Name) and node.id in _EMIT_NAMES
                )
        assert not offenders, (
            "emit reference(s) inside an `async with` session block — the emit must run after "
            f"the block exits, with the pooled connection released: {offenders}"
        )

    def test_exactly_the_five_mutating_wrappers_reference_the_emit_path(self):
        """Each of the five awaits the emit; no other wrapper touches either name.

        Set equality, so both failure directions name themselves: an emit deleted from a wrapper
        (the planted red) and an emit creeping into a read-only tool.
        """
        wrappers = _server_wrappers(_parse(_SERVER_PATH))
        emitting = {w.name for w in wrappers if _names_used(w) & _EMIT_NAMES}
        assert emitting == set(_MUTATION_TOOLS), (
            f"emit-path references disagree with the five mutation tools: "
            f"{sorted(emitting ^ set(_MUTATION_TOOLS))}"
        )
        raw = {w.name for w in wrappers if "_notify_deck_changed" in _names_used(w)}
        assert raw == set(), (
            f"wrapper(s) bypass _emit_deck_changed and call the leaf notifier directly: "
            f"{sorted(raw)} — the emit helper is the one place the outcome gets logged"
        )

    def test_every_emit_reference_in_server_py_is_a_plain_awaited_call(self):
        """The local detached-task ban: no ``create_task``/``ensure_future``/``TaskGroup``/
        ``gather`` can hold the emit, because nothing but ``await <name>(...)`` may reference it.

        The structural form of the c7-1 rule: a detached task can be torn down before it runs,
        silently losing the event. ``test_ws.py`` sweeps ``src/companion`` for the four names;
        this covers the new ``src/mcp_server`` sites without widening that package sweep.
        """
        tree = _parse(_SERVER_PATH)
        parents: dict[ast.AST, ast.AST] = {
            child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)
        }
        references = [
            node for node in ast.walk(tree) if isinstance(node, ast.Name) and node.id in _EMIT_NAMES
        ]
        assert len(references) >= 6, (
            f"only {len(references)} emit-path references found — five wrapper awaits plus the "
            "notifier call inside _emit_deck_changed are expected; the scan shape is wrong"
        )

        offenders = []
        for name in references:
            call = parents.get(name)
            awaited = (
                isinstance(call, ast.Call)
                and call.func is name
                and isinstance(parents.get(call), ast.Await)
            )
            if not awaited:
                offenders.append(f"server.py:{name.lineno} — {name.id}")
        assert not offenders, (
            "emit-path reference(s) not of the form `await <name>(...)` — a detached or indirect "
            f"use of the notify path: {offenders}"
        )
