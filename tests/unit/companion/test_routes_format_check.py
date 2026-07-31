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

import ast
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
# AC 5: no deck-construction rule followed the response into src/companion
# --------------------------------------------------------------------------------------------

_VALIDATOR_MODULE = "src.logic.deck_validator"

_PROJECTION_SURFACE = frozenset(
    {
        "format_check",
        "FormatCheckReport",
        "FormatCheckRow",
        "FormatCheckStatus",
        "FormatCheckName",
        "CHECK_ORDER",
    }
)
"""The only names ``src/companion`` may take from the validator module.

An allowlist rather than a ban list, on purpose: ``validate_deck``, ``DeckViolation``,
``_MIN_MAINBOARD`` and every future rule constant are refused by *not being on it*, so the guard
does not need to be updated when the validator grows a new internal.
"""

_LIMIT_LITERALS = frozenset({60, 15, 4})
"""Construction limits that have no business being compared in a shell.

**``1`` is deliberately excluded, and that is a declared limit rather than an oversight.** The
singleton limit is 1, but ``> 1`` / ``== 1`` are ubiquitous in ordinary code (lengths, indices,
retry counts), so banning it would produce noise instead of a signal. A shell reimplementing the
singleton rule specifically would slip past this family; nothing else here would.
"""

_FORMAT_NAMES = frozenset(
    {
        "standard",
        "modern",
        "commander",
        "brawl",
        "legacy",
        "vintage",
        "pioneer",
        "pauper",
        "historic",
        "timeless",
        "alchemy",
        "gladiator",
        "oathbreaker",
        "duel",
        "predh",
        "premodern",
        "oldschool",
        "penny",
        "future",
        "standardbrawl",
        "competitivebrawl",
        "paupercommander",
        "tlr",
    }
)
"""The 23 Scryfall legality keys, for the "a format-name set was rebuilt here" family."""


_LEGALITIES = "legalities"

_VALIDATOR_PACKAGE, _VALIDATOR_LEAF = _VALIDATOR_MODULE.rsplit(".", 1)


def _is_limit(value: object) -> bool:
    """Is *value* one of the construction limits, in any numeric spelling?

    ``60.0`` counts: ``60.0 in {60, 15, 4}`` is ``True`` and ``n < 60.0`` is the same rule with a
    decimal point. Booleans are excluded explicitly, because ``True == 1`` and ``False == 0`` in
    Python would otherwise classify every ``x == True`` as a copy limit — which is why the
    exclusion is an ``isinstance`` check and not a comment claiming ``is`` handles it.
    """
    return (
        not isinstance(value, bool) and isinstance(value, int | float) and value in _LIMIT_LITERALS
    )


def _format_names_in(elements: list[ast.expr]) -> list[str]:
    """Return the Scryfall legality keys among *elements*' string constants."""
    return [
        e.value
        for e in elements
        if isinstance(e, ast.Constant) and isinstance(e.value, str) and e.value in _FORMAT_NAMES
    ]


def find_rule_violations(source: str, rel_path: str) -> list[str]:
    """Return every deck-construction rule reimplemented in *source* (AD-1, AC 5).

    Pure and AST-only, so it can be probed against a planted violation without touching a real
    file, and so a rule hidden in a module no test imports is still seen. Four families:

    * **card legality read in the shell** — the name ``legalities`` in *any* position: an
      attribute, a subscript key, a ``getattr`` argument, or a bare string bound to a variable
      and used as a key later. Keyed on the word rather than on the syntax, because the syntax
      is exactly what an evasion varies.
    * **the validator reached past its projection** — any import of the validator module, or of
      a name from it, outside :data:`_PROJECTION_SURFACE`. Covers ``from X import y``,
      ``import X.y``, ``import X.y as z`` and ``from X import y``-of-the-module, because
      ``import src.logic.deck_validator as dv`` then ``dv.validate_deck(...)`` reaches
      everything an allowlist on ``from``-imports alone would refuse.
    * **a construction limit used** — an integer from :data:`_LIMIT_LITERALS` appearing anywhere
      as an integer constant. Deliberately *not* restricted to comparisons: ``_MIN = 60`` then
      ``n < _MIN`` is the same rule with one more line, and ``match n: case 60`` is the same rule
      with different syntax.
    * **a format-name set rebuilt** — two or more Scryfall legality keys appearing together in a
      collection display or as dict keys, whatever else is in it.
    * **copies counted in the shell** — any ``.quantity`` access. AC 5 names "any copy counting"
      beside the limits, and a shell summing quantities is doing the arithmetic the copy limit is
      made of, whether or not it then compares against ``4``.

    **Declared limits, so they are decisions rather than discoveries.** ``1`` is outside the
    limit family (see :data:`_LIMIT_LITERALS`). A rule written in TypeScript is invisible to
    every Python guard. And a fully dynamic form — a limit read from a config file, a legality
    key assembled from fragments — defeats an AST walk by construction; the same stance
    ``test_import_boundary.py`` takes applies, and its wording is the rule: *a guard satisfied by
    obfuscation is theatre*, so a reviewer seeing one must treat it as a violation.

    Args:
        source: Python source text.
        rel_path: Repo-relative path, used in the returned messages.

    Returns:
        One message per breach, naming the file, the line and the family.
    """
    tree = ast.parse(source)
    found: list[str] = []

    def flag(line: int, symbol: str, family: str) -> None:
        found.append(f"{rel_path}:{line} — {symbol} ({family})")

    def flag_validator_import(line: int, dotted: str) -> None:
        flag(line, dotted, "the validator is reached past its projection")

    for node in ast.walk(tree):
        # --- legality, in any spelling ---
        if isinstance(node, ast.Attribute) and node.attr == _LEGALITIES:
            flag(node.lineno, ast.unparse(node), "a card's legality is read in the shell")
        elif isinstance(node, ast.Constant) and node.value == _LEGALITIES:
            # The string itself, wherever it appears: `card["legalities"]`, `getattr(card,
            # "legalities")`, and `KEY = "legalities"` followed by `card[KEY]` — the last of
            # which no subscript-shaped check can see (review, 2026-08-01).
            flag(node.lineno, repr(node.value), "a card's legality is read in the shell")

        # --- the validator, past its projection ---
        elif isinstance(node, ast.ImportFrom):
            if node.module == _VALIDATOR_MODULE:
                for alias in node.names:
                    if alias.name not in _PROJECTION_SURFACE:
                        flag_validator_import(node.lineno, f"{_VALIDATOR_MODULE}.{alias.name}")
            elif node.module == _VALIDATOR_PACKAGE:
                # `from src.logic import deck_validator` binds the whole module, so every name
                # on it is reachable — an allowlist cannot constrain what happens next.
                for alias in node.names:
                    if alias.name == _VALIDATOR_LEAF:
                        flag_validator_import(node.lineno, _VALIDATOR_MODULE)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == _VALIDATOR_MODULE:
                    flag_validator_import(node.lineno, alias.name)

        # --- a construction limit, in any position ---
        elif isinstance(node, ast.Constant) and _is_limit(node.value):
            flag(
                node.lineno,
                str(node.value),
                "a deck-construction limit appears in the shell",
            )

        # --- copies counted in the shell (AC 5 names "any copy counting" alongside the limits) ---
        elif isinstance(node, ast.Attribute) and node.attr == "quantity":
            flag(node.lineno, ast.unparse(node), "deck-card copies are counted in the shell")

        # --- a format-name set, in any container ---
        elif isinstance(node, ast.Set | ast.List | ast.Tuple):
            if len(_format_names_in(node.elts)) >= 2:
                flag(node.lineno, ast.unparse(node), "a format-name set is rebuilt in the shell")
        elif isinstance(node, ast.Dict):
            keys = [k for k in node.keys if k is not None]
            if len(_format_names_in(keys)) >= 2:
                flag(node.lineno, ast.unparse(node), "a format-name set is rebuilt in the shell")

    return found


class TestNoRuleInTheShell:
    """AD-1: this shell consumes the validators and defines no second truth."""

    def test_the_companion_package_reimplements_no_construction_rule(self):
        offenders = [
            message
            for file in sorted((REPO_ROOT / "src" / "companion").rglob("*.py"))
            if "__pycache__" not in file.parts
            for message in find_rule_violations(
                file.read_text(encoding="utf-8-sig"),
                file.resolve().relative_to(REPO_ROOT).as_posix(),
            )
        ]

        assert not offenders, (
            "src/companion must reimplement no deck-construction rule — AD-1 makes src/logic "
            "the one truth:\n" + "\n".join(f"  {line}" for line in offenders)
        )

    def test_the_scan_is_not_looking_at_an_empty_tree(self):
        """Non-vacuity for the scan above: it genuinely visited the route module."""
        files = [
            file.resolve().relative_to(REPO_ROOT).as_posix()
            for file in (REPO_ROOT / "src" / "companion").rglob("*.py")
            if "__pycache__" not in file.parts
        ]

        assert "src/companion/app/routes/decks.py" in files
        assert len(files) > 5

    @pytest.mark.parametrize(
        ("source", "family"),
        [
            pytest.param(
                "def go(card):\n    return card.legalities.get('standard')\n",
                "legality is read",
                id="attribute-legalities",
            ),
            pytest.param(
                "def go(card):\n    return card['legalities']['standard']\n",
                "legality is read",
                id="subscript-legalities",
            ),
            pytest.param(
                "from src.logic.deck_validator import validate_deck\n",
                "reached past its projection",
                id="import-the-validator-itself",
            ),
            pytest.param(
                "from src.logic.deck_validator import _MIN_MAINBOARD\n",
                "reached past its projection",
                id="import-a-rule-constant",
            ),
            pytest.param(
                "def go(deck):\n    return len(deck.cards) < 60\n",
                "limit",
                id="min-deck-size",
            ),
            pytest.param(
                "def go(deck):\n    return deck.sideboard > 15\n",
                "limit",
                id="max-sideboard",
            ),
            pytest.param(
                "def go(entry):\n    return entry.quantity > 4\n",
                "limit",
                id="copy-limit",
            ),
            pytest.param(
                'SINGLETON = {"brawl", "commander"}\n',
                "format-name set",
                id="format-set",
            ),
            pytest.param(
                'KNOWN = ["standard", "modern", "pioneer"]\n',
                "format-name set",
                id="format-list",
            ),
            # --- Every spelling the review of 2026-08-01 measured slipping through. The four
            # families above were keyed on the syntax each plant happened to use, so the guard's
            # only proven property was that it caught its own four examples. Each of these
            # returned [] against the first version; each is now pinned.
            pytest.param(
                "import src.logic.deck_validator as dv\n",
                "reached past its projection",
                id="evasion-aliased-module-import",
            ),
            pytest.param(
                "from src.logic import deck_validator\n",
                "reached past its projection",
                id="evasion-from-package-module-import",
            ),
            pytest.param(
                "MIN = 60\n\n\ndef go(deck):\n    return len(deck.cards) < MIN\n",
                "limit",
                id="evasion-hoisted-limit",
            ),
            pytest.param(
                "def go(deck):\n    return len(deck.cards) < 60.0\n",
                "limit",
                id="evasion-float-limit",
            ),
            pytest.param(
                "def go(n):\n    match n:\n        case 60:\n            return True\n",
                "limit",
                id="evasion-match-case-limit",
            ),
            pytest.param(
                "def go(card):\n    return getattr(card, 'legalities')\n",
                "legality is read",
                id="evasion-getattr-legalities",
            ),
            pytest.param(
                "KEY = 'legalities'\n\n\ndef go(card):\n    return card[KEY]\n",
                "legality is read",
                id="evasion-variable-key-legalities",
            ),
            pytest.param(
                "SINGLETON = {'brawl': 1, 'commander': 1}\n",
                "format-name set",
                id="evasion-dict-shaped-format-map",
            ),
            pytest.param(
                "KNOWN = {'standard', 'modern', 'zzz'}\n",
                "format-name set",
                id="evasion-format-set-with-a-non-format-member",
            ),
            pytest.param(
                "def go(deck):\n    return sum(e.quantity for e in deck.cards)\n",
                "copies are counted",
                id="copy-counting-without-a-limit",
            ),
        ],
    )
    def test_the_guard_fires_on_a_planted_rule(self, source, family):
        """Every family is proven to catch something, so none of them is decoration."""
        offenders = find_rule_violations(source, "src/companion/app/routes/decks.py")

        assert offenders, f"the {family} family caught nothing"
        assert any(family in message for message in offenders), offenders

    def test_the_whole_reimplementation_is_caught(self):
        """The composite the adversarial layer built: four rules in seven lines, and the first
        version of this guard returned ``[]`` for all of it.

        Kept as one case rather than split across the parametrised list above, because what it
        demonstrates is not any single family but that the families **compose** — this is what a
        real AD-1 breach would look like, and it is the shape the guard exists for.
        """
        source = (
            "MIN = 60\n"
            "SINGLETON = {'brawl': 1, 'commander': 1}\n"
            "\n\n"
            "def check(deck, fmt):\n"
            "    limit = 1 if fmt in SINGLETON else 4\n"
            "    bad = [c for c in deck.cards if getattr(c, 'legalities').get(fmt) != 'legal']\n"
            "    return len(deck.cards) < MIN or bad\n"
        )

        offenders = find_rule_violations(source, "src/companion/app/routes/decks.py")

        families = {message.rsplit("(", 1)[-1].rstrip(")") for message in offenders}
        assert "a deck-construction limit appears in the shell" in families, offenders
        assert "a card's legality is read in the shell" in families, offenders
        assert "a format-name set is rebuilt in the shell" in families, offenders

    @pytest.mark.parametrize(
        "source",
        [
            pytest.param(
                "from src.logic.deck_validator import FormatCheckReport, format_check\n",
                id="the-sanctioned-projection-import",
            ),
            pytest.param("def go(items):\n    return len(items) > 1\n", id="a-length-check"),
            pytest.param('TAGS = {"fun", "budget"}\n', id="a-non-format-string-set"),
            pytest.param('LABELS = ["standard"]\n', id="a-single-string-list"),
            pytest.param("def go(flag):\n    return flag == True\n", id="a-boolean-comparison"),
            pytest.param("def go(n):\n    return n == 3\n", id="an-unrelated-integer"),
        ],
    )
    def test_the_guard_stays_silent_on_permitted_code(self, source):
        """The other half: a guard that fires on everything is not a guard."""
        assert find_rule_violations(source, "src/companion/app/routes/decks.py") == []


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
        assert {"400", "413", "500", "503"} <= set(responses)

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
