"""Story c3-3: ``GET /api/deck/{deck_id}/format-check``, driven end to end.

Same seam as ``test_routes_decks.py``: a **real** ``build_app()`` through ``lifespan_client``
against a **real** temporary SQLite file, schema created by ``init_database`` and rows seeded
through the repositories. Nothing is mocked, because what this story mostly does is *consume*
seams that already exist — the session dependency, both ``503`` paths, the ``404`` token, the SPA
mount ordering — and only the shipped wiring can prove consumption rather than reimplementation.

**Every legality fixture here is synthetic, and that is a measurement, not a preference.** All 40
real saved decks contain zero banned and zero restricted cards, so a fixture seeded from real
data would let the banned assertions pass by finding nothing (story landmine 15).

The row projection itself is unit-tested in ``tests/unit/logic/test_format_check.py``, where it
lives. What is tested *here* is the route: that it loads the deck the right way, that its counts
are real, that the tokens and statuses are the inherited ones, and that no deck-construction rule
followed the response out into ``src/companion``.
"""

import json
from pathlib import Path

import pytest

from src.companion.app.main import build_app
from src.data.database import create_engine, create_session_factory, init_database
from src.data.models.card import CardModel
from src.data.repositories.deck import DeckRepository
from src.logic.deck_validator import CHECK_ORDER

# --------------------------------------------------------------------------------------------
# Paths under test. Literals, not built from the router — a test that imported the prefix would
# still pass if the prefix were wrong (the c3-1 convention).
# --------------------------------------------------------------------------------------------

_PATH = "/api/deck/{deck_id}/format-check"
_DETAIL_PATH = "/api/deck/{deck_id}"

REPO_ROOT = Path(__file__).resolve().parents[3]


def _point_at(monkeypatch, path: Path) -> Path:
    """Steer ``src.paths.database_url()`` at *path* via ``CARDS_DATABASE_URL``."""
    monkeypatch.setenv("CARDS_DATABASE_URL", f"sqlite+aiosqlite:///{path.as_posix()}")
    return path


def _card(
    card_id: str,
    name: str,
    *,
    legalities: dict[str, str] | None = None,
    type_line: str | None = None,
) -> CardModel:
    """Build a complete card row whose legalities are the fixture's whole point.

    Every field an assertion might read is derived from *card_id*, so no two cards in one deck
    are interchangeable — c3-1's review R3 found a projection nesting the wrong card entirely
    while every test stayed green, because the seeds were identical on the asserted fields.
    """
    return CardModel(
        id=card_id,
        name=name,
        printed_name=None,
        oracle_id=f"oracle-{card_id}",
        mana_cost=f"{{{card_id[-1].upper()}}}",
        cmc=0.0 if type_line else 1.0,
        type_line=type_line or f"Instant — {card_id}",
        oracle_text=f"{name} does something.",
        rarity="common",
        set_code="TST",
        set_name="Test Set",
        collector_number="1",
        colors=["R"],
        color_identity=["R"],
        legalities=legalities if legalities is not None else {"standard": "legal"},
        games=["paper", "arena", "mtgo"],
    )


def _basic(card_id: str, name: str, *, legalities: dict[str, str] | None = None) -> CardModel:
    """A basic land: copy-limit exempt, so a deck can reach 60 cards on one entry."""
    return _card(card_id, name, legalities=legalities, type_line="Basic Land — Mountain")


async def _ready_database(path: Path) -> None:
    """Create the full schema at *path* and seed one card row.

    ``is_database_initialized`` wants a *populated* ``cards`` table, not merely the file.
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
    """Open a session against *path*, hand it to *seeder*, then dispose the engine."""
    engine = create_engine(f"sqlite+aiosqlite:///{path.as_posix()}")
    try:
        factory = create_session_factory(engine)
        async with factory() as session:
            await seeder(session)
    finally:
        await engine.dispose()


@pytest.fixture
async def ready_db(tmp_path, monkeypatch):
    """A real database file with the full schema and one card row, already pointed at."""
    path = _point_at(monkeypatch, tmp_path / "cards.db")
    await _ready_database(path)
    return path


def _deck_seeder(cards, entries, *, name="Checked", format="standard"):
    """Return a seeder adding *cards* and building one deck from *entries*.

    Args:
        cards: ``CardModel`` rows to insert.
        entries: ``(card_id, quantity)`` or ``(card_id, quantity, sideboard)`` tuples.
        name: The deck's name.
        format: The deck's format.
    """
    holder: dict[str, str] = {}

    async def seeder(session):
        repo = DeckRepository(session)
        for card in cards:
            session.add(card)
        await session.commit()
        deck = await repo.create_deck(name=name, format=format)
        holder["id"] = deck.id
        for entry in entries:
            card_id, quantity = entry[0], entry[1]
            sideboard = entry[2] if len(entry) > 2 else False
            await repo.add_card_to_deck(deck.id, card_id, quantity=quantity, sideboard=sideboard)

    return seeder, holder


def _rows(body) -> dict[str, str]:
    return {row["check"]: row["status"] for row in body["rows"]}


def _detail(body, check: str) -> str:
    return next(row["detail"] for row in body["rows"] if row["check"] == check)


# --------------------------------------------------------------------------------------------
# AC 1, AC 2: the route and the rows it returns
# --------------------------------------------------------------------------------------------


class TestLegalDeck:
    """A deck that breaks nothing: an unwrapped report whose answerable rows all pass."""

    @pytest.fixture
    async def legal_deck(self, ready_db):
        seeder, holder = _deck_seeder(
            [_basic("card-mountain", "Mountain")],
            [("card-mountain", 60)],
        )
        await _seed(ready_db, seeder)
        return holder["id"]

    async def test_the_body_is_the_report_itself_unwrapped(
        self, ready_db, legal_deck, lifespan_client
    ):
        """AD-16: no ``{"status": …}``, no ``{"report": …}``, no envelope of any kind."""
        async with lifespan_client(build_app()) as client:
            response = await client.get(_PATH.format(deck_id=legal_deck))

        assert response.status_code == 200
        body = response.json()
        assert set(body) == {
            "is_legal",
            "format",
            "format_recognized",
            "mainboard_count",
            "sideboard_count",
            "rows",
        }
        assert "status" not in body
        assert "report" not in body

    async def test_every_answerable_check_passes(self, ready_db, legal_deck, lifespan_client):
        async with lifespan_client(build_app()) as client:
            body = (await client.get(_PATH.format(deck_id=legal_deck))).json()

        assert _rows(body) == {
            "legality": "pass",
            "size": "pass",
            "copy_limit": "pass",
            "sideboard": "pass",
            "banned": "pass",
            "rotation": "advisory",
        }
        assert body["is_legal"] is True
        assert body["format"] == "standard"
        assert body["format_recognized"] is True

    async def test_the_rows_arrive_in_the_declared_order(
        self, ready_db, legal_deck, lifespan_client
    ):
        """AC 2: c4-10 renders a stable panel, not a set that reshuffles between refetches."""
        async with lifespan_client(build_app()) as client:
            body = (await client.get(_PATH.format(deck_id=legal_deck))).json()

        assert [row["check"] for row in body["rows"]] == list(CHECK_ORDER)
        # Non-vacuity for the order claim: the row set is complete and non-empty, so the
        # comparison above cannot be satisfied by an empty list agreeing with an empty list.
        assert len(body["rows"]) == 6
        assert {row["check"] for row in body["rows"]} == set(CHECK_ORDER)

    async def test_every_row_carries_a_status_and_a_detail(
        self, ready_db, legal_deck, lifespan_client
    ):
        async with lifespan_client(build_app()) as client:
            body = (await client.get(_PATH.format(deck_id=legal_deck))).json()

        for row in body["rows"]:
            assert set(row) == {"check", "status", "detail"}
            assert row["status"] in {"pass", "advisory", "violation"}
            assert row["detail"].strip()


# --------------------------------------------------------------------------------------------
# AC 4: the deck is loaded with its cards, and the counts prove it
# --------------------------------------------------------------------------------------------


class TestCountsAreReal:
    """The silent-zero landmine: a non-eager-loaded deck answers confidently about 0 cards."""

    @pytest.mark.parametrize(
        ("mainboard", "sideboard"),
        [(60, 4), (23, 7)],
        ids=["sixty-and-four", "twenty-three-and-seven"],
    )
    async def test_the_counts_match_the_seeded_quantities(
        self, ready_db, lifespan_client, mainboard, sideboard
    ):
        """Two decks with **different** counts, so the pin cannot be satisfied by a constant.

        ``get_deck`` (rather than ``get_deck_with_cards``) returns a deck whose ``deck_cards``
        is an empty list — ``lazy="noload"`` reads as empty rather than querying — and the
        report that follows is a perfectly plausible ``min_deck_size`` violation about a 0-card
        deck. Nothing crashes. This is the assertion that notices.
        """
        seeder, holder = _deck_seeder(
            [_basic("card-mountain", "Mountain"), _basic("card-island", "Island")],
            [("card-mountain", mainboard), ("card-island", sideboard, True)],
        )
        await _seed(ready_db, seeder)

        async with lifespan_client(build_app()) as client:
            body = (await client.get(_PATH.format(deck_id=holder["id"]))).json()

        assert body["mainboard_count"] == mainboard
        assert body["sideboard_count"] == sideboard
        # The two are mutually distinct and neither is zero, so one wrong number repeated twice
        # (or the 0/0 a never-loaded deck yields) cannot satisfy both assertions by coincidence.
        assert body["mainboard_count"] != body["sideboard_count"]
        assert 0 not in {body["mainboard_count"], body["sideboard_count"]}

    async def test_a_genuinely_empty_deck_still_answers_normally(self, ready_db, lifespan_client):
        """The legitimate zero, so the pin above is not "0 is always wrong".

        A cardless deck is an ordinary ``min_deck_size`` violation, not a bespoke response
        shape: the *client* hides the panel until a deck has cards (UX-DR33), so the honest
        backend behaviour is to answer normally.
        """
        seeder, holder = _deck_seeder([], [], name="Empty Shell")
        await _seed(ready_db, seeder)

        async with lifespan_client(build_app()) as client:
            response = await client.get(_PATH.format(deck_id=holder["id"]))

        assert response.status_code == 200
        body = response.json()
        assert body["mainboard_count"] == 0
        assert _rows(body)["size"] == "violation"
        assert len(body["rows"]) == 6


# --------------------------------------------------------------------------------------------
# AC 3, AC 13: each violation family, distinguishable, over the wire
# --------------------------------------------------------------------------------------------


class TestViolationFamilies:
    """Every answerable check is driven to a violation, and proven not to catch its neighbours."""

    @pytest.fixture
    async def messy_deck(self, ready_db):
        """One deck breaking size, copy limit, sideboard, legality and the ban list at once.

        Five distinguishable cards, and a sixth that is perfectly legal — so an assertion
        cannot pass by treating them alike, and the "no violation" half has a witness.
        """
        seeder, holder = _deck_seeder(
            [
                _card("card-greedy", "Greedy Spell"),
                _card("card-banned", "Banned Bomb", legalities={"standard": "banned"}),
                _card("card-outside", "Modern Staple", legalities={"modern": "legal"}),
                _card("card-fine", "Perfectly Fine"),
                _basic("card-mountain", "Mountain"),
            ],
            [
                ("card-greedy", 5),
                ("card-banned", 1),
                ("card-outside", 1),
                ("card-fine", 1),
                ("card-mountain", 16, True),
            ],
        )
        await _seed(ready_db, seeder)
        return holder["id"]

    async def test_all_five_answerable_checks_report_violations(
        self, ready_db, messy_deck, lifespan_client
    ):
        async with lifespan_client(build_app()) as client:
            body = (await client.get(_PATH.format(deck_id=messy_deck))).json()

        assert _rows(body) == {
            "legality": "violation",
            "size": "violation",
            "copy_limit": "violation",
            "sideboard": "violation",
            "banned": "violation",
            "rotation": "advisory",
        }
        assert body["is_legal"] is False

    async def test_each_row_names_its_own_card_and_not_another_s(
        self, ready_db, messy_deck, lifespan_client
    ):
        """AC 13's teeth: banned and merely-illegal are two rows naming two different cards."""
        async with lifespan_client(build_app()) as client:
            body = (await client.get(_PATH.format(deck_id=messy_deck))).json()

        assert "Banned Bomb" in _detail(body, "banned")
        assert "Modern Staple" in _detail(body, "legality")
        assert "Greedy Spell" in _detail(body, "copy_limit")
        # A projection that treated all three legality outcomes alike would fail exactly here.
        assert "Banned Bomb" not in _detail(body, "legality")
        assert "Modern Staple" not in _detail(body, "banned")

    async def test_the_legal_card_is_named_by_no_row_at_all(
        self, ready_db, messy_deck, lifespan_client
    ):
        """Non-vacuity pairing (AC 25): the sixth card produces nothing anywhere."""
        async with lifespan_client(build_app()) as client:
            body = (await client.get(_PATH.format(deck_id=messy_deck))).json()

        for row in body["rows"]:
            assert "Perfectly Fine" not in row["detail"], row

    async def test_a_banned_card_alone_leaves_the_legality_row_passing(
        self, ready_db, lifespan_client
    ):
        """The sharpest half of Q2: banned must not double-report as a legality violation."""
        seeder, holder = _deck_seeder(
            [
                _basic("card-mountain", "Mountain"),
                _card("card-banned", "Banned Bomb", legalities={"standard": "banned"}),
            ],
            [("card-mountain", 59), ("card-banned", 1)],
        )
        await _seed(ready_db, seeder)

        async with lifespan_client(build_app()) as client:
            body = (await client.get(_PATH.format(deck_id=holder["id"]))).json()

        assert _rows(body)["banned"] == "violation"
        assert _rows(body)["legality"] == "pass"


# --------------------------------------------------------------------------------------------
# AC 7: a deck whose format cannot be checked
# --------------------------------------------------------------------------------------------


class TestNoFormatToCheckAgainst:
    """200 with the same shape, never an error and never a different body (Q4)."""

    @pytest.mark.parametrize("format", ["potato", ""], ids=["unrecognised", "blank"])
    async def test_the_unanswerable_rows_are_advisory(self, ready_db, lifespan_client, format):
        seeder, holder = _deck_seeder(
            [_basic("card-mountain", "Mountain")],
            [("card-mountain", 60)],
            format=format,
        )
        await _seed(ready_db, seeder)

        async with lifespan_client(build_app()) as client:
            response = await client.get(_PATH.format(deck_id=holder["id"]))

        assert response.status_code == 200
        body = response.json()
        # The SAME shape as every other answer — one object, no union, nothing conditional.
        assert set(body) == {
            "is_legal",
            "format",
            "format_recognized",
            "mainboard_count",
            "sideboard_count",
            "rows",
        }
        assert body["format_recognized"] is False
        assert _rows(body)["legality"] == "advisory"
        assert _rows(body)["banned"] == "advisory"
        # The structural checks still answered, so "advisory" is not a blanket give-up.
        assert _rows(body)["size"] == "pass"
        assert _rows(body)["sideboard"] == "pass"

    async def test_a_recognised_format_is_the_non_vacuity_pair(self, ready_db, lifespan_client):
        seeder, holder = _deck_seeder(
            [_basic("card-mountain", "Mountain")],
            [("card-mountain", 60)],
            format="standard",
        )
        await _seed(ready_db, seeder)

        async with lifespan_client(build_app()) as client:
            body = (await client.get(_PATH.format(deck_id=holder["id"]))).json()

        assert body["format_recognized"] is True
        assert _rows(body)["legality"] == "pass"
        assert _rows(body)["banned"] == "pass"

    async def test_the_blank_format_reads_as_prose_not_as_an_empty_quotation(
        self, ready_db, lifespan_client
    ):
        seeder, holder = _deck_seeder(
            [_basic("card-mountain", "Mountain")], [("card-mountain", 60)], format=""
        )
        await _seed(ready_db, seeder)

        async with lifespan_client(build_app()) as client:
            body = (await client.get(_PATH.format(deck_id=holder["id"]))).json()

        assert "''" not in _detail(body, "legality")
        assert "no format" in _detail(body, "legality").lower()


# --------------------------------------------------------------------------------------------
# Q3: the rotation row (AC 14)
# --------------------------------------------------------------------------------------------


class TestRotationRow:
    """Present in every answer, permanently advisory, and honest about why."""

    async def test_rotation_is_advisory_and_says_why(self, ready_db, lifespan_client):
        seeder, holder = _deck_seeder(
            [_basic("card-mountain", "Mountain")], [("card-mountain", 60)]
        )
        await _seed(ready_db, seeder)

        async with lifespan_client(build_app()) as client:
            body = (await client.get(_PATH.format(deck_id=holder["id"]))).json()

        rotation = next(row for row in body["rows"] if row["check"] == "rotation")
        assert rotation["status"] == "advisory"
        assert "release date" in rotation["detail"]
        # Non-vacuity: another row in the same response IS resolved, so "advisory" is a property
        # of rotation rather than of this deck or of the projection as a whole.
        assert _rows(body)["size"] == "pass"


# --------------------------------------------------------------------------------------------
# AC 6: the 404 token
# --------------------------------------------------------------------------------------------


class TestUnknownDeck:
    """A deck id has no declared shape, so every unknown id is simply not found — never a 400."""

    @pytest.mark.parametrize(
        "deck_id",
        ["no-such-deck", "00000000-0000-0000-0000-000000000000", "not a uuid at all"],
        ids=["plain-string", "well-formed-uuid", "free-text"],
    )
    async def test_unknown_id_is_deck_not_found(self, ready_db, lifespan_client, deck_id):
        async with lifespan_client(build_app()) as client:
            response = await client.get(_PATH.format(deck_id=deck_id))

        assert response.status_code == 404
        assert response.json() == {"reason": "deck_not_found"}

    async def test_a_known_id_is_the_non_vacuity_pair(self, ready_db, lifespan_client):
        """The same route, the same database: only the id differs."""
        seeder, holder = _deck_seeder(
            [_basic("card-mountain", "Mountain")], [("card-mountain", 60)]
        )
        await _seed(ready_db, seeder)

        async with lifespan_client(build_app()) as client:
            assert (await client.get(_PATH.format(deck_id=holder["id"]))).status_code == 200


# --------------------------------------------------------------------------------------------
# AC 8: both 503 paths, inherited and proved through the real route
# --------------------------------------------------------------------------------------------


class TestDatabaseStates:
    """No per-route ceremony: ``DbSession`` and the app-wide handler answer both."""

    _ANY = _PATH.format(deck_id="anything")

    async def test_missing_database_file(self, tmp_path, monkeypatch, lifespan_client):
        _point_at(monkeypatch, tmp_path / "absent.db")

        async with lifespan_client(build_app()) as client:
            response = await client.get(self._ANY)

        assert response.status_code == 503
        assert response.json() == {"reason": "database_not_initialized"}

    async def test_schema_present_but_no_cards_is_also_not_initialized(
        self, tmp_path, monkeypatch, lifespan_client
    ):
        empty = _point_at(monkeypatch, tmp_path / "empty.db")
        engine = create_engine(f"sqlite+aiosqlite:///{empty.as_posix()}")
        try:
            await init_database(engine)
        finally:
            await engine.dispose()

        async with lifespan_client(build_app()) as client:
            response = await client.get(self._ANY)

        assert response.status_code == 503
        assert response.json() == {"reason": "database_not_initialized"}

    async def test_corrupt_database_file(self, tmp_path, monkeypatch, lifespan_client):
        corrupt = _point_at(monkeypatch, tmp_path / "corrupt.db")
        corrupt.write_bytes(b"this is definitely not a sqlite database" * 8)

        async with lifespan_client(build_app()) as client:
            response = await client.get(self._ANY)

        assert response.status_code == 503
        assert response.json() == {"reason": "database_unavailable"}

    async def test_a_healthy_database_answers_the_token_instead(self, ready_db, lifespan_client):
        """Non-vacuity for all three: this path is not permanently 503.

        Asserted exactly, not as "not 503" — the loose form would also be satisfied by a
        handler that answered 500 unconditionally (c3-1 review).
        """
        async with lifespan_client(build_app()) as client:
            response = await client.get(self._ANY)

        assert response.status_code == 404
        assert response.json() == {"reason": "deck_not_found"}


# --------------------------------------------------------------------------------------------
# AC 11: the route is not shadowed by the SPA mount
# --------------------------------------------------------------------------------------------


class TestNotShadowedBySpa:
    """Asserted on status **and** body, because ``/api`` is reserved and answers JSON either way.

    c3-1's review R1 measured the trap: an ``/api`` path with no route behind it is refused by
    the mount and answered as ``404 application/json {"reason": "invalid_request"}``. That
    response carries no doctype, so a content-type-only assertion stays green with the router
    deleted. Only ``deck_not_found`` can come from a running handler.
    """

    async def test_the_route_is_served_by_the_endpoint_not_the_spa(self, ready_db, lifespan_client):
        async with lifespan_client(build_app()) as client:
            response = await client.get(_PATH.format(deck_id="unknown"))

        assert response.headers["content-type"].startswith("application/json")
        assert "<!doctype html" not in response.text.lower()
        assert response.status_code == 404
        assert response.json() == {"reason": "deck_not_found"}

    async def test_an_unrouted_sibling_path_is_refused_rather_than_falling_back(
        self, ready_db, lifespan_client
    ):
        """The pair: what the assertion above would see if the route were missing."""
        async with lifespan_client(build_app()) as client:
            response = await client.get("/api/deck/unknown/no-such-check")

        assert response.status_code == 404
        assert response.json() == {"reason": "invalid_request"}

    async def test_the_spa_mount_is_still_the_last_route(self):
        routes = build_app().router.routes
        assert getattr(routes[-1], "name", None) == "spa"

    async def test_the_sibling_detail_route_still_answers(self, ready_db, lifespan_client):
        """The sub-resource path must not shadow — or be shadowed by — its parent."""
        seeder, holder = _deck_seeder(
            [_basic("card-mountain", "Mountain")], [("card-mountain", 60)]
        )
        await _seed(ready_db, seeder)

        async with lifespan_client(build_app()) as client:
            detail = await client.get(_DETAIL_PATH.format(deck_id=holder["id"]))
            check = await client.get(_PATH.format(deck_id=holder["id"]))

        assert detail.status_code == 200
        assert "cards" in detail.json()
        assert check.status_code == 200
        assert "rows" in check.json()


# --------------------------------------------------------------------------------------------
# AC 9, AC 16: what the committed schema says
# --------------------------------------------------------------------------------------------


class TestCommittedSchema:
    """Read from the **committed** artifact — the copy the frontend is generated from."""

    @pytest.fixture(scope="class")
    def schema(self):
        path = REPO_ROOT / "ui" / "src" / "api" / "openapi.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def test_the_literal_path_is_present(self, schema):
        assert _PATH in schema["paths"]
        # Plural `decks` is the list route's spelling; this sub-resource follows the singular
        # detail route, and a reader of an older docstring would have shipped the other one.
        assert "/api/decks/{deck_id}/format-check" not in schema["paths"]

    def test_the_success_body_is_the_report_unwrapped(self, schema):
        body = schema["paths"][_PATH]["get"]["responses"]["200"]["content"]["application/json"][
            "schema"
        ]

        assert body["$ref"].endswith("/FormatCheckReport")

    def test_the_route_declares_deck_not_found_and_nothing_else_new(self, schema):
        responses = schema["paths"][_PATH]["get"]["responses"]

        assert "404" in responses
        assert "deck_not_found" in responses["404"]["description"]
        # Non-vacuity: the app-level declarations are present too, so the 404 above is the
        # per-route declaration rather than a difference in whether responses exist at all.
        #
        # `413` dropped at c5-5: a body-less GET cannot answer it, and it was inherited from the
        # shared include set while `payload_too_large` had no producer anywhere. The curation moved
        # it to the two operations that can (`POST /agent/events`, `PUT /api/active-deck`).
        assert {"400", "500", "503"} <= set(responses)
        assert "413" not in responses

    def test_the_route_takes_no_games_parameter(self, schema):
        """AC 9: UX-DR21 names six checks and platform availability is not one of them."""
        parameters = schema["paths"][_PATH]["get"].get("parameters", [])
        names = {parameter["name"] for parameter in parameters}

        assert "games" not in names
        # Non-vacuity: the path parameter IS declared, so an empty parameter list is not what
        # makes the assertion above pass.
        assert names == {"deck_id"}

    def test_the_new_components_are_present(self, schema):
        names = set(schema["components"]["schemas"])

        assert "FormatCheckReport" in names
        assert "FormatCheckRow" in names

    def test_the_row_status_is_a_closed_three_member_union(self, schema):
        """AC 2: exactly ``pass``, ``advisory`` and ``violation`` reach the wire."""
        status = schema["components"]["schemas"]["FormatCheckRow"]["properties"]["status"]

        assert set(status["enum"]) == {"pass", "advisory", "violation"}

    def test_the_row_check_names_are_the_six(self, schema):
        check = schema["components"]["schemas"]["FormatCheckRow"]["properties"]["check"]

        assert set(check["enum"]) == set(CHECK_ORDER)
