"""Story c3-3: the format-check row projection, and the ``banned_card`` split beneath it.

Two things live here, and they are separable on purpose.

**The projection** (Q1, Brad 2026-07-31) turns ``validate_deck``'s violations-and-silence into one
row per UX-DR21 check, including the checks that *passed* — which the validator has no way to
report, because ``DeckValidationReport`` carries ``violations`` and nothing else. It lives in
``src/logic`` beside the rules it summarises, so ``src/companion`` holds nothing rule-shaped
(AD-1), and it is tested here rather than through the route because it is pure.

**The split** (Q2) teaches ``validate_deck`` that ``banned`` is not the same as "not in this
format". Measured across the shipped 38,261-card corpus: 1,275 ``banned`` legality entries and 89
``restricted`` ones, against 516,401 ``not_legal`` — so the data supports three outcomes where the
code had one. Measured across the 40 real saved decks: **zero** banned and **zero** restricted
cards, which is why every fixture below is synthetic. A test seeded from real data would pass by
finding nothing.

``restricted`` is deliberately **unchanged** by the split: a restricted card is legal in Vintage
with a 1-copy limit, which this validator does not model, so it stays a ``format_legality``
violation exactly as before. Ledgered, not fixed — see ``deferred-work.md``.
"""

from datetime import UTC, datetime
from typing import get_args

import pytest

from src.data.schemas.card import Card
from src.data.schemas.deck import Deck, DeckCard
from src.logic.deck_validator import (
    CHECK_FOR_RULE,
    CHECK_ORDER,
    DeckViolationRule,
    FormatCheckReport,
    format_check,
    validate_deck,
)


def _card(card_id: str, name: str, *, legalities: dict[str, str], basic: bool = False) -> Card:
    """Build a card whose legalities are the point of the fixture.

    Every field that any assertion reads is derived from *card_id*, so two cards in one deck are
    never interchangeable (c3-1 review R3: identical fixtures cannot catch a mis-paired
    projection).
    """
    return Card(
        id=card_id,
        name=name,
        oracle_id=f"oracle-{card_id}",
        mana_cost="{R}",
        cmc=0.0 if basic else 1.0,
        type_line="Basic Land — Mountain" if basic else f"Instant — {card_id}",
        oracle_text=f"{name} does something.",
        rarity="common",
        set_code="TST",
        set_name="Test Set",
        collector_number="1",
        colors=["R"],
        color_identity=["R"],
        keywords=[],
        legalities=legalities,
        games=["paper", "arena", "mtgo"],
    )


def _entry(card: Card, quantity: int, *, sideboard: bool = False) -> DeckCard:
    return DeckCard(
        deck_id="deck-fc",
        card_id=card.id,
        quantity=quantity,
        sideboard=sideboard,
        card=card,
    )


def _deck(entries: list[DeckCard], *, format: str | None = "standard") -> Deck:
    return Deck(
        id="deck-fc",
        name="Format Check Deck",
        format=format,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        deck_cards=entries,
    )


def _mountain(count: int, *, sideboard: bool = False) -> DeckCard:
    """A copy-limit-exempt filler entry, so a deck can reach 60 without tripping other rules."""
    return _entry(
        _card("mountain", "Mountain", legalities={"standard": "legal"}, basic=True),
        count,
        sideboard=sideboard,
    )


def _rows(report: FormatCheckReport) -> dict[str, str]:
    """The report as ``{check: status}``, for assertions that read the whole panel at once."""
    return {row.check: row.status for row in report.rows}


def _detail(report: FormatCheckReport, check: str) -> str:
    return next(row.detail for row in report.rows if row.check == check)


# ------------------------------------------------------------------------------------------
# The shape and the order (AC 2)
# ------------------------------------------------------------------------------------------


class TestRowShape:
    """One row per UX-DR21 check, in a declared order, with a closed three-member status."""

    def test_the_rows_are_exactly_the_six_checks_in_the_declared_order(self) -> None:
        report = format_check(_deck([_mountain(60)]))

        assert [row.check for row in report.rows] == list(CHECK_ORDER)
        # The order is EXPERIENCE.md:37's own listing, quoted there as
        # "Legality, size, copy limit, sideboard, banned, rotation exposure".
        assert CHECK_ORDER == ("legality", "size", "copy_limit", "sideboard", "banned", "rotation")

    def test_every_row_carries_a_status_and_a_non_empty_detail(self) -> None:
        report = format_check(_deck([_mountain(60)]))

        for row in report.rows:
            assert row.status in {"pass", "advisory", "violation"}, row
            assert row.detail.strip(), row

    def test_the_order_is_stable_across_two_calls_on_the_same_deck(self) -> None:
        """c4-10 renders a panel, not a set: a reshuffle between refetches is a defect."""
        deck = _deck([_mountain(60)])

        assert [row.check for row in format_check(deck).rows] == [
            row.check for row in format_check(deck).rows
        ]

    def test_the_counts_mirror_the_validator(self) -> None:
        deck = _deck([_mountain(60), _mountain(4, sideboard=True)])

        report = format_check(deck)
        underlying = validate_deck(deck, format="standard")

        assert report.mainboard_count == underlying.mainboard_count == 60
        assert report.sideboard_count == underlying.sideboard_count == 4
        assert report.is_legal == underlying.is_legal


class TestRuleCoverage:
    """Every validator rule is either mapped to a row or explicitly declared unrepresented."""

    def test_every_rule_in_the_literal_has_an_entry(self) -> None:
        """The exhaustiveness pin: a rule added to the vocabulary without a row goes red here.

        Keyed on the ``Literal``'s own members rather than on a remembered list, so it cannot
        drift — which is the whole reason ``DeckViolationRule`` is a named alias.
        """
        assert set(CHECK_FOR_RULE) == set(get_args(DeckViolationRule))

    def test_every_mapped_row_is_a_real_check(self) -> None:
        mapped = {check for check in CHECK_FOR_RULE.values() if check is not None}

        assert mapped <= set(CHECK_ORDER)
        # Non-vacuity: the mapping genuinely reaches rows, so the subset above is not empty-set
        # trivia.
        assert mapped

    def test_game_availability_is_deliberately_unrepresented(self) -> None:
        """UX-DR21 names six checks and platform availability is not one of them (AC 9)."""
        assert CHECK_FOR_RULE["game_availability"] is None

    def test_rotation_is_fed_by_no_rule_at_all(self) -> None:
        """Q3: rotation has no local data source, so nothing in src/logic can produce it."""
        assert "rotation" not in set(CHECK_FOR_RULE.values())


# ------------------------------------------------------------------------------------------
# The happy path, and its non-vacuity pair (AC 25)
# ------------------------------------------------------------------------------------------


class TestLegalDeck:
    """A deck that breaks nothing: five passes and the one permanent advisory."""

    def test_a_legal_standard_deck_passes_every_answerable_check(self) -> None:
        report = format_check(_deck([_mountain(60)]))

        assert _rows(report) == {
            "legality": "pass",
            "size": "pass",
            "copy_limit": "pass",
            "sideboard": "pass",
            "banned": "pass",
            "rotation": "advisory",
        }
        assert report.is_legal is True
        assert report.format_recognized is True

    def test_the_all_pass_claim_is_not_vacuous(self) -> None:
        """The pair for the above: the same shape reports violations when there are some.

        Without this, "every row is pass" could be satisfied by a projection that emitted no
        rows at all, or that hard-coded ``pass``.
        """
        undersized = format_check(_deck([_mountain(10)]))

        assert _rows(undersized)["size"] == "violation"
        assert undersized.is_legal is False
        # ...and the checks that genuinely still hold are still reported as passing, so the
        # violation above is discriminating rather than a blanket downgrade.
        assert _rows(undersized)["copy_limit"] == "pass"
        assert _rows(undersized)["sideboard"] == "pass"


class TestEachViolationFamilyReachesItsRow:
    """One deck per family, each proving the row it lands in and the rows it does not."""

    def test_min_deck_size_lands_on_size(self) -> None:
        report = format_check(_deck([_mountain(10)]))

        assert _rows(report)["size"] == "violation"
        assert "10" in _detail(report, "size")

    def test_copy_limit_lands_on_copy_limit(self) -> None:
        greedy = _card("greedy", "Greedy Spell", legalities={"standard": "legal"})
        report = format_check(_deck([_mountain(56), _entry(greedy, 5)]))

        assert _rows(report)["copy_limit"] == "violation"
        assert "Greedy Spell" in _detail(report, "copy_limit")
        # The size check is satisfied by the same deck, so the row above is not collateral.
        assert _rows(report)["size"] == "pass"

    def test_singleton_also_lands_on_copy_limit(self) -> None:
        """A singleton format reports ``singleton``, not ``copy_limit`` — same row either way."""
        pair = _card("pair", "Doubled Spell", legalities={"brawl": "legal"})
        deck = _deck([_entry(pair, 2)], format="brawl")

        report = format_check(deck)

        assert _rows(report)["copy_limit"] == "violation"
        assert "Doubled Spell" in _detail(report, "copy_limit")
        assert any(v.rule == "singleton" for v in validate_deck(deck, format="brawl").violations)

    def test_max_sideboard_size_lands_on_sideboard(self) -> None:
        report = format_check(_deck([_mountain(60), _mountain(16, sideboard=True)]))

        assert _rows(report)["sideboard"] == "violation"
        assert "16" in _detail(report, "sideboard")

    def test_format_legality_lands_on_legality(self) -> None:
        elsewhere = _card("elsewhere", "Modern Staple", legalities={"modern": "legal"})
        report = format_check(_deck([_mountain(59), _entry(elsewhere, 1)]))

        assert _rows(report)["legality"] == "violation"
        assert "Modern Staple" in _detail(report, "legality")
        # ...and it did NOT land on the banned row, which is the whole point of Q2's split.
        assert _rows(report)["banned"] == "pass"

    def test_several_violations_of_one_family_collapse_into_one_row(self) -> None:
        """The panel has one row per check, so N violations become one detail naming the rest."""
        first = _card("first", "First Offender", legalities={"modern": "legal"})
        second = _card("second", "Second Offender", legalities={"modern": "legal"})
        report = format_check(_deck([_mountain(58), _entry(first, 1), _entry(second, 1)]))

        detail = _detail(report, "legality")
        assert "First Offender" in detail
        assert "+1 more" in detail
        # Exactly one row, not two — the shape is one row per CHECK, not per violation.
        assert len([row for row in report.rows if row.check == "legality"]) == 1


# ------------------------------------------------------------------------------------------
# Q2: banned is its own check (AC 13)
# ------------------------------------------------------------------------------------------


class TestBannedSplit:
    """Three distinguishable cards in one deck, so no assertion can pass by treating them alike."""

    @pytest.fixture
    def three_card_deck(self) -> Deck:
        """One banned, one merely not legal, one plainly legal — all in standard.

        Constructed rather than seeded: zero of the 40 real saved decks contain a banned or a
        restricted card, so a fixture built from real data would let every assertion below pass
        vacuously.
        """
        return _deck(
            [
                _mountain(57),
                _entry(_card("banned", "Banned Bomb", legalities={"standard": "banned"}), 1),
                _entry(_card("outside", "Modern Staple", legalities={"modern": "legal"}), 1),
                _entry(_card("fine", "Perfectly Fine", legalities={"standard": "legal"}), 1),
            ]
        )

    def test_the_banned_card_lands_on_the_banned_row(self, three_card_deck) -> None:
        report = format_check(three_card_deck)

        assert _rows(report)["banned"] == "violation"
        assert "Banned Bomb" in _detail(report, "banned")

    def test_the_merely_illegal_card_lands_on_the_legality_row(self, three_card_deck) -> None:
        report = format_check(three_card_deck)

        assert _rows(report)["legality"] == "violation"
        assert "Modern Staple" in _detail(report, "legality")

    def test_the_two_rows_do_not_name_each_other_s_card(self, three_card_deck) -> None:
        """The teeth: a projection that treated the three alike would fail exactly here."""
        report = format_check(three_card_deck)

        assert "Banned Bomb" not in _detail(report, "legality")
        assert "Modern Staple" not in _detail(report, "banned")

    def test_the_legal_card_produces_no_row_at_all(self, three_card_deck) -> None:
        """Non-vacuity pairing (AC 25): the third card is named by neither row."""
        report = format_check(three_card_deck)

        assert "Perfectly Fine" not in _detail(report, "legality")
        assert "Perfectly Fine" not in _detail(report, "banned")

    def test_the_underlying_violations_carry_the_new_rule(self, three_card_deck) -> None:
        """The split is in ``src/logic``, not in the projection — so the MCP tool gains it too."""
        violations = validate_deck(three_card_deck, format="standard").violations

        banned = [v for v in violations if v.rule == "banned_card"]
        legality = [v for v in violations if v.rule == "format_legality"]
        assert [v.card_name for v in banned] == ["Banned Bomb"]
        assert [v.card_name for v in legality] == ["Modern Staple"]

    def test_a_restricted_card_is_still_a_plain_legality_violation(self) -> None:
        """Deliberately unchanged by the split, and pinned so it cannot drift silently.

        A restricted card is legal with a 1-copy limit, which this validator does not model. It
        was reported as "not legal" before Q2 and still is — ledgered in ``deferred-work.md``,
        not fixed here.
        """
        restricted = _card("restricted", "Restricted Relic", legalities={"vintage": "restricted"})
        deck = _deck([_entry(restricted, 1)], format="vintage")

        violations = validate_deck(deck, format="vintage").violations

        assert any(
            v.rule == "format_legality" and v.card_name == "Restricted Relic" for v in violations
        )
        assert not any(v.rule == "banned_card" for v in violations)
        assert _rows(format_check(deck))["banned"] == "pass"


# ------------------------------------------------------------------------------------------
# Q3: rotation (AC 14)
# ------------------------------------------------------------------------------------------


class TestRotationRow:
    """One row, permanently advisory, because the local card data carries no release dates."""

    @pytest.mark.parametrize(
        "deck_factory",
        [
            lambda: _deck([_mountain(60)]),
            lambda: _deck([_mountain(1)]),
            lambda: _deck([_mountain(60)], format="potato"),
            lambda: _deck([_mountain(60)], format=None),
        ],
        ids=["legal", "illegal", "unknown-format", "no-format"],
    )
    def test_rotation_is_advisory_whatever_the_deck(self, deck_factory) -> None:
        report = format_check(deck_factory())

        rotation = next(row for row in report.rows if row.check == "rotation")
        assert rotation.status == "advisory"
        assert rotation.detail

    def test_rotation_is_never_pass_and_never_violation(self) -> None:
        """The honest half: this project cannot answer rotation, so it must not claim to.

        Paired with the parametrised test above, which proves the row exists at all — together
        they say "always present, never resolved".
        """
        report = format_check(_deck([_mountain(60)]))

        rotation = next(row for row in report.rows if row.check == "rotation")
        assert rotation.status not in {"pass", "violation"}
        # Non-vacuity: some other row in the very same report IS resolved, so "advisory" here is
        # a property of rotation and not of the projection as a whole.
        assert _rows(report)["size"] == "pass"


# ------------------------------------------------------------------------------------------
# Q4: no format to check against (AC 7)
# ------------------------------------------------------------------------------------------


class TestNoFormatToCheckAgainst:
    """Keyed on the validator's existing ``unknown_format`` outcome — no schema change, no union."""

    @pytest.mark.parametrize(
        "format", ["potato", "", "   ", None], ids=["unknown", "blank", "whitespace", "null"]
    )
    def test_the_unanswerable_rows_are_advisory_not_violations(self, format) -> None:
        report = format_check(_deck([_mountain(60)], format=format))

        assert _rows(report)["legality"] == "advisory"
        assert _rows(report)["banned"] == "advisory"
        assert report.format_recognized is False

    def test_the_structural_rules_are_still_evaluated(self) -> None:
        """Size and copy limits are format-independent, so they keep answering."""
        report = format_check(_deck([_mountain(10)], format="potato"))

        assert _rows(report)["size"] == "violation"
        assert _rows(report)["copy_limit"] == "pass"
        assert _rows(report)["sideboard"] == "pass"

    def test_a_recognised_format_is_the_non_vacuity_pair(self) -> None:
        report = format_check(_deck([_mountain(60)], format="standard"))

        assert report.format_recognized is True
        assert _rows(report)["legality"] == "pass"
        assert _rows(report)["banned"] == "pass"

    def test_an_unrecognised_format_name_is_quoted_back(self) -> None:
        report = format_check(_deck([_mountain(60)], format="potato"))

        assert "potato" in _detail(report, "legality")

    def test_a_missing_format_says_so_rather_than_quoting_an_empty_string(self) -> None:
        """``'' is not a recognized format`` is true but reads as a bug; the panel gets prose."""
        report = format_check(_deck([_mountain(60)], format=None))

        detail = _detail(report, "legality")
        assert "''" not in detail
        assert "no format" in detail.lower()

    def test_an_unknown_format_never_produces_a_per_card_legality_storm(self) -> None:
        """``validate_deck`` skips the per-card check deliberately; the row must reflect that."""
        elsewhere = _card("elsewhere", "Modern Staple", legalities={"modern": "legal"})
        report = format_check(_deck([_mountain(59), _entry(elsewhere, 1)], format="potato"))

        assert "Modern Staple" not in _detail(report, "legality")


# ------------------------------------------------------------------------------------------
# The format the report carries
# ------------------------------------------------------------------------------------------


class TestReportedFormat:
    """The report names the format that was actually checked — normalised, not as stored."""

    def test_the_format_is_normalised(self) -> None:
        report = format_check(_deck([_mountain(60)], format="  StAnDaRd "))

        assert report.format == "standard"
        assert report.format_recognized is True

    def test_the_deck_s_own_format_is_the_default(self) -> None:
        assert format_check(_deck([_mountain(60)], format="brawl")).format == "brawl"

    def test_an_explicit_format_overrides_the_deck_s(self) -> None:
        """The parameter exists for a what-if caller; the route never passes it."""
        deck = _deck([_mountain(60)], format="standard")

        assert format_check(deck, format="modern").format == "modern"

    def test_a_null_format_is_reported_as_the_empty_string(self) -> None:
        report = format_check(_deck([_mountain(60)], format=None))

        assert report.format == ""
        assert report.format_recognized is False
