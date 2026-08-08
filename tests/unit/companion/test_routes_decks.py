"""Story c3-1: ``GET /api/decks`` and ``GET /api/deck/{deck_id}``, driven end to end.

Every test here builds a **real** ``build_app()`` and drives it through the ``lifespan_client``
seam against a **real** temporary SQLite file — schema created by ``init_database``, card rows and
deck rows seeded through the repositories. Nothing is mocked and no route is test-local, because
what this story mostly does is *consume* seams that already exist (the session dependency, both
``503`` paths, the ``404`` token, the SPA mount ordering) and the only way to prove consumption
rather than reimplementation is to let the real wiring answer.

Writes here are deliberate and confined to the fixtures: ``tests/**`` is not scanned by the
import-boundary guard, which is what lets a test seed the data the read-only routes then read.

**Ordering is deliberately not asserted.** ``DeckRepository.list_decks`` orders by
``created_at DESC, id``, and ``id`` is a UUID — decks seeded back-to-back tie on the clock and
come back in arbitrary UUID order (a pre-existing flake, ledgered twice in ``deferred-work.md``).
Membership is asserted instead; where order matters, the seeds carry distinct ``created_at``
values written directly.
"""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import update

from src.companion.app.main import build_app
from src.data.database import create_engine, create_session_factory, init_database
from src.data.models.card import CardModel
from src.data.models.deck import DeckModel
from src.data.repositories.deck import DeckRepository

# --------------------------------------------------------------------------------------------
# Paths under test. Literals, not built from the router — a test that imported the prefix would
# still pass if the prefix were wrong.
# --------------------------------------------------------------------------------------------

_LIST_PATH = "/api/decks"
_DETAIL_PATH = "/api/deck/{deck_id}"


def _point_at(monkeypatch, path: Path) -> Path:
    """Steer ``src.paths.database_url()`` at *path* via ``CARDS_DATABASE_URL``.

    The ``test_deps.py`` pattern: an explicit ``CARDS_DATABASE_URL`` wins over everything, so the
    resolution cannot be hijacked by a developer's own environment. Note the autouse
    ``isolated_data_dir`` fixture steers ``PLANESWALKER_DATA_DIR`` separately — the database is
    *not* resolved from it.
    """
    monkeypatch.setenv("CARDS_DATABASE_URL", f"sqlite+aiosqlite:///{path.as_posix()}")
    return path


def _card(card_id: str, name: str, *, mana_cost: str | None = None, cmc: float = 1.0) -> CardModel:
    """Build a complete card row. Every non-nullable column, so the insert is realistic.

    **Every card is deliberately distinguishable from every other.** ``mana_cost`` defaults to a
    value derived from ``card_id`` rather than a shared ``"{R}"``: the review of 2026-07-31
    mutation-tested this file with every entry nesting the *same* card and all 28 tests stayed
    green, because the seeded cards were identical on every field the assertions read. Identical
    fixtures cannot catch a mis-paired projection.
    """
    return CardModel(
        id=card_id,
        name=name,
        printed_name=None,
        oracle_id=f"oracle-{card_id}",
        mana_cost=mana_cost if mana_cost is not None else f"{{{card_id[-1].upper()}}}",
        cmc=cmc,
        type_line=f"Instant — {card_id}",
        oracle_text=f"{name} does something.",
        rarity="common",
        set_code="TST",
        set_name="Test Set",
        collector_number="1",
        colors=["R"],
        color_identity=["R"],
        legalities={"standard": "legal", "commander": "legal"},
        games=["paper", "arena", "mtgo"],
    )


async def _ready_database(path: Path) -> None:
    """Create the full schema at *path* and seed one card row.

    ``is_database_initialized`` requires a **populated** ``cards`` table, not merely the file, so a
    schema-only database still reads as ``database_not_initialized``. One row is the minimum that
    makes the routes reachable at all; tests that need decks seed them on top.
    """
    engine = create_engine(f"sqlite+aiosqlite:///{path.as_posix()}")
    try:
        await init_database(engine)
        factory = create_session_factory(engine)
        async with factory() as session:
            session.add(_card("card-anchor", "Anchor Card"))
            await session.commit()
    finally:
        await engine.dispose()


async def _seed(path: Path, seeder) -> None:
    """Open a session against *path* and hand it to *seeder*, then dispose the engine.

    The engine is disposed before the app is built so the fixture never holds a connection the
    routes then contend with.
    """
    engine = create_engine(f"sqlite+aiosqlite:///{path.as_posix()}")
    try:
        factory = create_session_factory(engine)
        async with factory() as session:
            await seeder(session)
    finally:
        await engine.dispose()


async def _stamp_created_at(path: Path, when: dict[str, datetime]) -> None:
    """Force each deck's ``created_at`` to a distinct value, keyed by deck id.

    The repository orders by ``created_at DESC, id``; decks created in the same tick tie and fall
    back to UUID order. A test that wants to assert *order* must therefore break the tie in the
    data rather than hope, which is what this does.
    """

    async def seeder(session):
        for deck_id, value in when.items():
            await session.execute(
                update(DeckModel).where(DeckModel.id == deck_id).values(created_at=value)
            )
        await session.commit()

    await _seed(path, seeder)


@pytest.fixture
async def ready_db(tmp_path, monkeypatch):
    """A real database file with the full schema and one card row, already pointed at.

    The fixture **actually builds the database**, rather than only setting the environment
    variable and trusting each test to remember ``await _ready_database(...)``. A test that forgot
    used to get ``503 database_not_initialized`` — which, for the several tests here that assert
    on 503 or 404 bodies, is a plausible false green rather than a loud failure (review,
    2026-07-31).

    Returns:
        The path, so a test can seed decks into it before building the app.
    """
    path = _point_at(monkeypatch, tmp_path / "cards.db")
    await _ready_database(path)
    return path


# --------------------------------------------------------------------------------------------
# AC 1: the list route
# --------------------------------------------------------------------------------------------


class TestDeckList:
    """AC 1: every saved deck, as a bare array, with an empty database answering ``200 []``."""

    async def test_returns_every_deck_as_a_bare_array(self, ready_db, lifespan_client):
        async def seeder(session):
            repo = DeckRepository(session)
            await repo.create_deck(name="Boros Aggro", format="standard")
            await repo.create_deck(name="Dimir Control", format="modern")

        await _seed(ready_db, seeder)

        async with lifespan_client(build_app()) as client:
            response = await client.get(_LIST_PATH)

        assert response.status_code == 200
        body = response.json()
        # A bare array (AD-16): not {"decks": [...]}, not {"status": ...}, no count field.
        assert isinstance(body, list)
        assert {deck["name"] for deck in body} == {"Boros Aggro", "Dimir Control"}

    async def test_no_decks_is_an_empty_array_not_an_error(self, ready_db, lifespan_client):
        async with lifespan_client(build_app()) as client:
            response = await client.get(_LIST_PATH)

        assert response.status_code == 200
        assert response.json() == []

    async def test_orders_newest_first_when_the_timestamps_differ(self, ready_db, lifespan_client):
        """Order is asserted only against seeds whose ``created_at`` is genuinely distinct.

        Same-tick decks tie on ``created_at`` and fall back to UUID order, which is arbitrary —
        see this module's docstring. Stamping distinct timestamps is what makes the claim testable
        rather than flaky.
        """

        ids: dict[str, str] = {}

        async def seeder(session):
            repo = DeckRepository(session)
            for name in ("Oldest", "Middle", "Newest"):
                ids[name] = (await repo.create_deck(name=name, format="standard")).id

        await _seed(ready_db, seeder)

        base = datetime(2026, 1, 1, tzinfo=UTC).replace(tzinfo=None)
        await _stamp_created_at(
            ready_db,
            {
                ids["Oldest"]: base,
                ids["Middle"]: base + timedelta(days=1),
                ids["Newest"]: base + timedelta(days=2),
            },
        )

        async with lifespan_client(build_app()) as client:
            body = (await client.get(_LIST_PATH)).json()

        assert [deck["name"] for deck in body] == ["Newest", "Middle", "Oldest"]

    async def test_the_list_carries_computed_counts_too(self, ready_db, lifespan_client):
        """The list route projects through the same constructor, so its counts are real as well."""

        async def seeder(session):
            repo = DeckRepository(session)
            session.add(_card("card-a", "Card A"))
            await session.commit()
            deck = await repo.create_deck(name="Counted", format="standard")
            await repo.add_card_to_deck(deck.id, "card-a", quantity=3)

        await _seed(ready_db, seeder)

        async with lifespan_client(build_app()) as client:
            body = (await client.get(_LIST_PATH)).json()

        assert body[0]["mainboard_count"] == 3
        assert body[0]["distinct_cards"] == 1


# --------------------------------------------------------------------------------------------
# AC 2 + AC 3: the detail route, and counts that are computed rather than defaulted
# --------------------------------------------------------------------------------------------


class TestDeckDetail:
    """AC 2, AC 3: the full decklist, with counts proved non-zero and mutually distinct."""

    @pytest.fixture
    async def seeded_deck(self, ready_db):
        """A deck whose three counts are deliberately **different from each other**.

        Non-vacuity (AC 24): if the three counts were equal, a projection that returned the same
        wrong number three times — or the ``0`` defaults — could pass by coincidence. Here:

        * mainboard: 4 + 2 + 1 + 1 = **8**
        * sideboard: 3             = **3**
        * distinct card ids        = **4** (one card sits in both boards and must count once)
        """

        holder: dict[str, str] = {}

        async def seeder(session):
            repo = DeckRepository(session)
            for suffix in ("a", "b", "c", "d"):
                session.add(_card(f"card-{suffix}", f"Card {suffix.upper()}"))
            await session.commit()

            deck = await repo.create_deck(
                name="Seeded", format="standard", strategy="Go wide", tags=["fun", "budget"]
            )
            holder["id"] = deck.id
            await repo.add_card_to_deck(deck.id, "card-a", quantity=4)
            await repo.add_card_to_deck(deck.id, "card-b", quantity=2)
            await repo.add_card_to_deck(deck.id, "card-c", quantity=1, commander=True)
            await repo.add_card_to_deck(deck.id, "card-d", quantity=1)
            # Same card as the mainboard "card-a" entry: distinct_cards must still count it once.
            await repo.add_card_to_deck(deck.id, "card-a", quantity=3, sideboard=True)

        await _seed(ready_db, seeder)
        return holder["id"]

    async def test_returns_the_whole_decklist(self, ready_db, seeded_deck, lifespan_client):
        async with lifespan_client(build_app()) as client:
            response = await client.get(_DETAIL_PATH.format(deck_id=seeded_deck))

        assert response.status_code == 200
        body = response.json()
        assert body["id"] == seeded_deck
        assert body["name"] == "Seeded"
        assert body["format"] == "standard"
        assert body["strategy"] == "Go wide"
        assert body["tags"] == ["fun", "budget"]
        assert len(body["cards"]) == 5

    async def test_counts_are_computed_not_defaulted(self, ready_db, seeded_deck, lifespan_client):
        """AC 3: a populated ``cards[]`` beside ``mainboard_count: 0`` is what this catches."""
        async with lifespan_client(build_app()) as client:
            body = (await client.get(_DETAIL_PATH.format(deck_id=seeded_deck))).json()

        assert body["mainboard_count"] == 8  # 4 + 2 + 1 + 1
        assert body["sideboard_count"] == 3
        assert body["distinct_cards"] == 4  # card-a counted once across both boards

        # Non-vacuity: the three are mutually distinct, so one wrong number repeated three times
        # (or the 0/0/0 defaults) cannot satisfy the assertions above by coincidence.
        counts = {body["mainboard_count"], body["sideboard_count"], body["distinct_cards"]}
        assert len(counts) == 3
        assert 0 not in counts
        assert body["cards"], "counts asserted against an empty deck would prove nothing"

    async def test_sideboard_and_commander_flags_survive_the_projection(
        self, ready_db, seeded_deck, lifespan_client
    ):
        async with lifespan_client(build_app()) as client:
            body = (await client.get(_DETAIL_PATH.format(deck_id=seeded_deck))).json()

        sideboard = [entry for entry in body["cards"] if entry["sideboard"]]
        commanders = [entry for entry in body["cards"] if entry["commander"]]

        assert [entry["card_id"] for entry in sideboard] == ["card-a"]
        assert [entry["card_id"] for entry in commanders] == ["card-c"]
        # Both flags default to False, so the negative half is what proves the True is carried
        # rather than universal.
        assert any(not entry["sideboard"] for entry in body["cards"])
        assert any(not entry["commander"] for entry in body["cards"])

    async def test_each_entry_nests_a_card_summary(self, ready_db, seeded_deck, lifespan_client):
        async with lifespan_client(build_app()) as client:
            body = (await client.get(_DETAIL_PATH.format(deck_id=seeded_deck))).json()

        card = body["cards"][0]["card"]
        assert card["name"].startswith("Card ")
        assert card["set_code"] == "TST"
        # The bounded summary, not the full card: the heavy fields are absent by construction.
        assert "legalities" not in card
        assert "image_uris" not in card
        assert "card_faces" not in card

    async def test_each_entry_nests_its_own_card(self, ready_db, seeded_deck, lifespan_client):
        """The nested card belongs to the entry that carries it — not merely *a* card.

        The review of 2026-07-31 replaced the projection's ``card=`` with a fixed
        ``deck_cards[0].card``, so every entry nested the **wrong** card, and all 28 tests here
        stayed green: nothing tied ``card`` to ``card_id``, and every seeded card was identical
        on the fields being read. This is the assertion that was missing.
        """
        async with lifespan_client(build_app()) as client:
            body = (await client.get(_DETAIL_PATH.format(deck_id=seeded_deck))).json()

        for entry in body["cards"]:
            assert entry["card"]["id"] == entry["card_id"], entry
            # A second, independent link through a field the projection copies separately, so a
            # mutation that fixed only `id` would still be caught.
            assert entry["card"]["type_line"].endswith(entry["card_id"])

        # Non-vacuity: the entries genuinely differ, so a mis-paired projection would be visible
        # at all. (With identical fixtures the loop above passes against any pairing.)
        assert len({entry["card"]["id"] for entry in body["cards"]}) > 1
        assert len({entry["card"]["mana_cost"] for entry in body["cards"]}) > 1

    async def test_a_sideboard_only_deck_has_a_legitimate_zero_mainboard(
        self, ready_db, lifespan_client
    ):
        """The legitimate-zero boundary: ``mainboard_count: 0`` beside a populated ``cards[]``.

        AC 3's non-vacuity seeds structurally exclude this case (``0 not in counts``), so without
        this test the honest zero never crosses the wire at all — and a guard that treated
        0-with-cards as always-wrong would ship unchallenged.
        """

        holder: dict[str, str] = {}

        async def seeder(session):
            repo = DeckRepository(session)
            session.add(_card("card-sb", "Sideboard Only"))
            await session.commit()
            deck = await repo.create_deck(name="Board of One", format="standard")
            holder["id"] = deck.id
            await repo.add_card_to_deck(deck.id, "card-sb", quantity=2, sideboard=True)

        await _seed(ready_db, seeder)

        async with lifespan_client(build_app()) as client:
            body = (await client.get(_DETAIL_PATH.format(deck_id=holder["id"]))).json()

        assert body["mainboard_count"] == 0
        assert body["sideboard_count"] == 2
        assert body["distinct_cards"] == 1
        assert len(body["cards"]) == 1  # the zero sits beside a populated list — that is the point

    async def test_a_cardless_deck_answers_200_with_empty_cards_and_zero_counts(
        self, ready_db, lifespan_client
    ):
        """A deck with no cards is an ordinary answer on the detail route, like the list's."""

        holder: dict[str, str] = {}

        async def seeder(session):
            deck = await DeckRepository(session).create_deck(name="Empty Shell", format="standard")
            holder["id"] = deck.id

        await _seed(ready_db, seeder)

        async with lifespan_client(build_app()) as client:
            response = await client.get(_DETAIL_PATH.format(deck_id=holder["id"]))

        assert response.status_code == 200
        body = response.json()
        assert body["cards"] == []
        assert body["mainboard_count"] == 0
        assert body["sideboard_count"] == 0
        assert body["distinct_cards"] == 0

    async def test_null_strategy_and_empty_tags_cross_the_wire(self, ready_db, lifespan_client):
        """``strategy`` is ``string | null`` in the generated types; prove the ``null`` half is
        real by serving it. Every other seed in this file sets it, so this is the only place that
        nullability is exercised.

        ``format`` is *also* ``string | null`` on the wire, but that half is **unreachable
        through the repository**: ``decks.format`` is a ``NOT NULL`` column, and
        ``create_deck(format=None)`` raises ``IntegrityError`` (measured writing this test,
        review 2026-07-31). The wire type is wider than the data can be — ledgered in
        ``deferred-work.md``, homed at c3-3, whose "no format to check against" answer leans on
        the nullable half.
        """

        holder: dict[str, str] = {}

        async def seeder(session):
            deck = await DeckRepository(session).create_deck(name="Strategyless", format="standard")
            holder["id"] = deck.id

        await _seed(ready_db, seeder)

        async with lifespan_client(build_app()) as client:
            body = (await client.get(_DETAIL_PATH.format(deck_id=holder["id"]))).json()

        assert body["strategy"] is None
        assert body["tags"] == []

    async def test_timestamps_carry_a_utc_offset(self, ready_db, seeded_deck, lifespan_client):
        """The schemas' ``field_serializer`` coerces naive SQLite datetimes to offset-bearing."""
        async with lifespan_client(build_app()) as client:
            body = (await client.get(_DETAIL_PATH.format(deck_id=seeded_deck))).json()

        assert body["created_at"].endswith("+00:00")
        assert body["updated_at"].endswith("+00:00")


# --------------------------------------------------------------------------------------------
# AC 5: the 404 token
# --------------------------------------------------------------------------------------------


class TestUnknownDeck:
    """AC 5: an unknown id answers the token, and only the token."""

    @pytest.mark.parametrize(
        "deck_id",
        ["no-such-deck", "00000000-0000-0000-0000-000000000000", "not a uuid at all"],
        ids=["plain-string", "well-formed-uuid", "free-text"],
    )
    async def test_unknown_id_is_deck_not_found(self, ready_db, lifespan_client, deck_id):
        """A deck id has no declared shape, so every unknown id is simply not found — no 400."""

        async with lifespan_client(build_app()) as client:
            response = await client.get(_DETAIL_PATH.format(deck_id=deck_id))

        assert response.status_code == 404
        assert response.json() == {"reason": "deck_not_found"}

    async def test_the_list_route_has_no_404(self, ready_db, lifespan_client):
        """Non-vacuity for the above: the same empty database answers 200 on the list route."""

        async with lifespan_client(build_app()) as client:
            assert (await client.get(_LIST_PATH)).status_code == 200


# --------------------------------------------------------------------------------------------
# Path spellings that are near-misses of the real routes (review, 2026-07-31)
# --------------------------------------------------------------------------------------------


class TestPathSpellings:
    """Off-by-one-slash and encoded-slash spellings, pinned rather than assumed.

    Two claims lived only in prose before these tests. ``read_deck``'s docstring says an id
    containing an encoded ``/`` "never reaches this handler … routing rejects it as
    ``invalid_request`` first" — asserted, never tested. And the trailing-slash behaviour was
    assumed, not measured: it turns out Starlette's ``redirect_slashes`` **does** fire for a
    slash variant of a route that exists (the redirect partial-match wins before the SPA mount is
    reached), answering ``307`` to the canonical spelling — while a slash spelling that matches
    no route even partially (``/api/deck/``, whose id segment is empty) falls through to the
    reserved-prefix branch instead. These pin both measured outcomes, so a change in either (a
    routing upgrade, a mount change) is a named failure instead of a silent drift.
    """

    @pytest.mark.parametrize(
        ("path", "target"),
        [("/api/decks/", _LIST_PATH), ("/api/deck/some-id/", "/api/deck/some-id")],
        ids=["list-trailing-slash", "detail-trailing-slash"],
    )
    async def test_a_trailing_slash_redirects_to_the_canonical_spelling(
        self, ready_db, lifespan_client, path, target
    ):
        async with lifespan_client(build_app()) as client:
            response = await client.get(path)

        assert response.status_code == 307
        assert response.headers["location"].endswith(target)

    async def test_an_empty_id_segment_is_refused_not_redirected(self, ready_db, lifespan_client):
        """``/api/deck/`` partial-matches nothing (the id segment is empty), so no redirect —
        the reserved-prefix branch answers."""

        async with lifespan_client(build_app()) as client:
            response = await client.get("/api/deck/")

        assert response.status_code == 404
        assert response.json() == {"reason": "invalid_request"}

    async def test_an_encoded_slash_in_the_id_is_rejected_by_routing(
        self, ready_db, lifespan_client
    ):
        """The docstring's claim, measured: ``%2F`` is decoded before matching, so the two-segment
        result matches no route and the handler never runs — ``invalid_request``, not
        ``deck_not_found``."""

        async with lifespan_client(build_app()) as client:
            response = await client.get("/api/deck/a%2Fb")

        assert response.status_code == 404
        assert response.json() == {"reason": "invalid_request"}


# --------------------------------------------------------------------------------------------
# AC 12: both 503 paths, proved through the real routes
# --------------------------------------------------------------------------------------------


class TestDatabaseStates:
    """AC 12: the inherited ``503`` paths answer on both endpoints, with no per-route ceremony."""

    @pytest.fixture(params=[_LIST_PATH, "/api/deck/anything"], ids=["list", "detail"])
    def path(self, request):
        return request.param

    async def test_missing_database_file(self, tmp_path, monkeypatch, lifespan_client, path):
        _point_at(monkeypatch, tmp_path / "absent.db")

        async with lifespan_client(build_app()) as client:
            response = await client.get(path)

        assert response.status_code == 503
        assert response.json() == {"reason": "database_not_initialized"}

    async def test_schema_present_but_no_cards_is_also_not_initialized(
        self, tmp_path, monkeypatch, lifespan_client, path
    ):
        """The readiness probe wants a *populated* ``cards`` table, not merely the file."""
        empty = _point_at(monkeypatch, tmp_path / "empty.db")
        engine = create_engine(f"sqlite+aiosqlite:///{empty.as_posix()}")
        try:
            await init_database(engine)
        finally:
            await engine.dispose()

        async with lifespan_client(build_app()) as client:
            response = await client.get(path)

        assert response.status_code == 503
        assert response.json() == {"reason": "database_not_initialized"}

    async def test_corrupt_database_file(self, tmp_path, monkeypatch, lifespan_client, path):
        """A present-but-unreadable file: ``DatabaseError``, typed app-wide by the middleware."""
        corrupt = _point_at(monkeypatch, tmp_path / "corrupt.db")
        corrupt.write_bytes(b"this is definitely not a sqlite database" * 8)

        async with lifespan_client(build_app()) as client:
            response = await client.get(path)

        assert response.status_code == 503
        assert response.json() == {"reason": "database_unavailable"}

    async def test_a_healthy_database_answers_normally(self, ready_db, lifespan_client, path):
        """Non-vacuity for all three above: the same paths are not permanently 503.

        The expected answer is asserted **exactly** per path rather than as ``200 or 404``. The
        loose form let the detail half reduce to "is not one of two bodies", which a handler that
        404'd unconditionally would also satisfy (review, 2026-07-31).
        """

        async with lifespan_client(build_app()) as client:
            response = await client.get(path)

        if path == _LIST_PATH:
            assert response.status_code == 200
            assert response.json() == []
        else:
            # The detail fixture path names no deck, so reaching the handler means the token.
            assert response.status_code == 404
            assert response.json() == {"reason": "deck_not_found"}


# --------------------------------------------------------------------------------------------
# AC 13: the routes are not shadowed by the SPA mount
# --------------------------------------------------------------------------------------------


class TestNotShadowedBySpa:
    """AC 13: registered above ``install_spa(app)`` — the thing one layer above the routes.

    ``build_app()`` ends with a mount at ``/`` that matches every path, so a router registered
    after it would answer ``200`` with ``index.html`` and the endpoint would never run.

    **Content-type alone proves nothing here, and the review of 2026-07-31 measured why.**
    ``/api`` is in ``spa.py``'s ``_RESERVED_SEED``, so an ``/api`` path with *no* route behind it
    does not fall through to the index either — it is refused by the mount and answered by the
    typed error handler as ``404 application/json {"reason": "invalid_request"}``. That response
    is JSON and contains no doctype, so an assertion that only reads the content-type stays green
    with the router deleted. These tests therefore assert the **status and the body**: only a
    running endpoint produces ``200 []`` or the ``deck_not_found`` token.
    """

    async def test_list_route_is_served_by_the_endpoint_not_the_spa(
        self, ready_db, lifespan_client
    ):
        async with lifespan_client(build_app()) as client:
            response = await client.get(_LIST_PATH)

        assert response.headers["content-type"].startswith("application/json")
        assert "<!doctype html" not in response.text.lower()
        # The teeth: only the endpoint answers 200 with a JSON array. An unregistered router
        # gives 404 invalid_request; a shadowing mount gives 200 text/html.
        assert response.status_code == 200
        assert response.json() == []

    async def test_detail_route_is_served_by_the_endpoint_not_the_spa(
        self, ready_db, lifespan_client
    ):
        async with lifespan_client(build_app()) as client:
            response = await client.get(_DETAIL_PATH.format(deck_id="unknown"))

        assert response.headers["content-type"].startswith("application/json")
        assert "<!doctype html" not in response.text.lower()
        # deck_not_found can only come from the handler. invalid_request would mean no route.
        assert response.status_code == 404
        assert response.json() == {"reason": "deck_not_found"}

    async def test_an_unrouted_api_path_is_refused_rather_than_falling_back(
        self, ready_db, lifespan_client
    ):
        """The non-vacuity pair: prove the assertions above distinguish two *live* outcomes.

        This is what the two tests above would see if the router were missing, measured against a
        path that genuinely has no route. It documents why they assert bodies rather than merely
        content-type, and it fails if the reserved-prefix behaviour ever changes underneath them.
        """

        async with lifespan_client(build_app()) as client:
            response = await client.get("/api/no-such-endpoint")

        assert response.status_code == 404
        assert response.json() == {"reason": "invalid_request"}
        assert response.headers["content-type"].startswith("application/json")

    async def test_the_spa_mount_is_still_the_last_route(self):
        """The mechanism itself, not just its effect: nothing was appended after the mount."""
        routes = build_app().router.routes
        assert getattr(routes[-1], "name", None) == "spa"


# --------------------------------------------------------------------------------------------
# AC 4, AC 6, AC 8: what the committed schema says
# --------------------------------------------------------------------------------------------


class TestCommittedSchema:
    """The generated artifact is the contract the UI is written against, so it is asserted here.

    Read from the **committed** ``ui/src/api/openapi.json`` rather than a live ``app.openapi()``:
    the committed file is what ``npm run gen:types`` consumes and what the drift gates compare, so
    it is the copy whose correctness the frontend actually depends on.
    """

    @pytest.fixture(scope="class")
    def schema(self):
        import json

        path = Path(__file__).resolve().parents[3] / "ui" / "src" / "api" / "openapi.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def test_both_literal_paths_are_present(self, schema):
        """AC 4: plural for the list, **singular** for the detail."""
        assert _LIST_PATH in schema["paths"]
        assert _DETAIL_PATH in schema["paths"]
        # The wrong spelling a reader of deps.py's old docstring would have shipped.
        assert "/api/decks/{deck_id}" not in schema["paths"]
        assert "/api/decks/{id}" not in schema["paths"]

    def test_this_routes_own_shapes_are_described(self, schema):
        """AC 8: the deck shapes this module's routes answer with reach the document.

        **The whole-artifact component pin moved out at c3-4** (Q5, Brad 2026-08-01), to
        ``test_committed_schema.py``. It used to live here *and* in ``test_routes_cards.py`` — one
        fact, two hand-synchronised copies, so every schema-adding story had to edit both. c3-2 and
        then c3-3 each found the second copy by running the suite rather than by reading their
        story, and ``deferred-work.md`` homed the consolidation on c3-4 by name.

        What stays here is what this module is actually about: **the deck shapes**. A
        companion-local mirror of one of them still fails, over there, as an unexpected name in the
        exact set — this asserts the complementary half, that the real ones are present.
        """
        names = set(schema["components"]["schemas"])

        # Non-vacuity first (c3-1 review), and it can genuinely fail: an empty or wrong-shaped
        # parse gives an empty set, which would satisfy any "in" check by accident of ordering.
        assert names, "no component schemas parsed — the fixture is not reading a real document"

        assert {"DeckSummary", "DeckDetail", "DeckCardSummary", "CardSummary"} <= names

    def test_the_detail_route_declares_its_token_and_the_list_route_does_not(self, schema):
        """AC 6: ``deck_not_found`` is declared where it can happen, and only there."""
        detail = schema["paths"][_DETAIL_PATH]["get"]["responses"]
        listing = schema["paths"][_LIST_PATH]["get"]["responses"]

        assert "404" in detail
        assert "deck_not_found" in detail["404"]["description"]
        assert "ErrorResponse" in str(detail["404"])
        assert "404" not in listing

        # Non-vacuity: the app-level declarations are on both, so the difference above is the
        # per-route declaration and not a difference in whether responses exist at all.
        #
        # `413` dropped from both sets at c5-5. These are body-less GETs and could never answer it;
        # they carried it only by inheritance from the shared include set, back when
        # `payload_too_large` had no producer at all. c5-5 built the cap and curated the
        # declaration down to the two operations that can genuinely answer it — so its absence
        # here is the fix landing, not coverage lost.
        assert {"400", "500", "503"} <= set(detail)
        assert {"400", "500", "503"} <= set(listing)
        assert "413" not in detail
        assert "413" not in listing

    def test_the_success_bodies_are_unwrapped(self, schema):
        """AC 1, AC 2: a bare array of ``DeckSummary``, and ``DeckDetail`` itself."""
        listing = schema["paths"][_LIST_PATH]["get"]["responses"]["200"]["content"][
            "application/json"
        ]["schema"]
        assert listing["type"] == "array"
        assert listing["items"]["$ref"].endswith("/DeckSummary")

        detail = schema["paths"][_DETAIL_PATH]["get"]["responses"]["200"]["content"][
            "application/json"
        ]["schema"]
        assert detail["$ref"].endswith("/DeckDetail")
