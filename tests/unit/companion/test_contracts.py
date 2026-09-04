"""Tests for the agent event envelope and its six payloads (c5-1, AD-6, AD-7).

The models are driven **directly**: no ``build_app()``, no ``lifespan_client``. A leaf that needs an
app to be tested is not a leaf (``test_discovery.py``'s rule), and c5-1 adds no route to piggy-back
on — which is why this is the first file in the repo dedicated to ``contracts.py`` rather than
another model block inside the route story that introduced it.

House rules this file follows:

* **caps are asserted as literal numbers, never by importing the constant.** A test that reads
  ``_MAX_ITEMS`` stays green when somebody changes 60 to 5; the number *is* the contract, and the
  numbers here are the ones AD-7 names;
* **every rejection is paired with an acceptance from the same call** — at-cap accepted, one over
  rejected, in one test. A cap test that only ever rejects proves the model refuses things, not
  that it accepts the legal maximum;
* **closed sets are compared as sets against a hand-written literal**, never counted and never
  iterated over their own source, so adding a member reddens deliberately (``test_errors.py``'s
  rule).
"""

import doctest
from datetime import UTC, datetime, timedelta, timezone
from typing import Any, get_args

import pytest
from pydantic import TypeAdapter, ValidationError

from src.companion import contracts as contracts_module
from src.companion.contracts import (
    _MAX_CARD_ID_LENGTH,
    _MAX_ENVELOPE_BYTES,
    _MAX_EVENT_ID_LENGTH,
    DEFAULT_TITLE_BY_KIND,
    ActiveDeckChangedEvent,
    ActiveDeckChangedPayload,
    AgentEvent,
    Confidence,
    DeckChangedEvent,
    DeckChangedPayload,
    EventIngestReceipt,
    EventKind,
    GroupItem,
    GroupsEvent,
    GroupsPayload,
    SuggestionItem,
    SuggestionsEvent,
    SuggestionsPayload,
    SwapItem,
    SwapsEvent,
    SwapsPayload,
    TierItem,
    TierLetter,
    TierListEvent,
    TierListPayload,
)

_AGENT_EVENT: TypeAdapter[Any] = TypeAdapter(AgentEvent)

_TS = datetime(2026, 8, 7, 9, 15, tzinfo=UTC)

# HAND-WRITTEN, deliberately. Every "is every kind covered?" assertion below compares against this
# tuple rather than against `get_args(EventKind)` — an assertion that iterates the very list it is
# checking is tautological and would stay green if a kind were dropped from both sides at once.
_KINDS = (
    "suggestions",
    "swaps",
    "tier_list",
    "groups",
    "deck_changed",
    "active_deck_changed",
)

# Also hand-written: the kind -> envelope class pairing the union is supposed to express.
_CLASS_BY_KIND = {
    "suggestions": SuggestionsEvent,
    "swaps": SwapsEvent,
    "tier_list": TierListEvent,
    "groups": GroupsEvent,
    "deck_changed": DeckChangedEvent,
    "active_deck_changed": ActiveDeckChangedEvent,
}

_PAYLOAD_CLASS_BY_KIND = {
    "suggestions": SuggestionsPayload,
    "swaps": SwapsPayload,
    "tier_list": TierListPayload,
    "groups": GroupsPayload,
    "deck_changed": DeckChangedPayload,
    "active_deck_changed": ActiveDeckChangedPayload,
}

_TIER_LETTERS = ("S", "A", "B", "C", "D")

_CONFIDENCES = ("low", "medium", "high")

# The four push kinds carry a view; the two system signals do not.
_VIEW_KINDS = ("suggestions", "swaps", "tier_list", "groups")


def _envelope(kind: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """A minimal well-formed envelope of *kind*, so a rejection test has a valid twin to vary."""
    return {
        "kind": kind,
        "id": "0f6e2a11-9c3d-4b7e-8a52-1d4f6c8b0e33",
        "ts": _TS.isoformat(),
        "payload": {} if payload is None else payload,
    }


def _suggestion(**overrides: Any) -> dict[str, Any]:
    return {"card_id": "c1", "reason": "Fills the two-drop gap.", **overrides}


def _swap(**overrides: Any) -> dict[str, Any]:
    return {
        "out_card_id": "c1",
        "in_card_id": "c2",
        "rationale": "Same role, one turn earlier.",
        "out_qty": 1,
        "in_qty": 1,
        **overrides,
    }


def _tier(**overrides: Any) -> dict[str, Any]:
    return {"letter": "S", "name": "Auto-include", **overrides}


def _group(**overrides: Any) -> dict[str, Any]:
    return {"title": "Ramp", "rationale": "Accelerates into the six-drops.", **overrides}


class TestTheKindVocabulary:
    """AC 3 / AC 4 / AD-6: six kinds, closed, with the two system signals kept distinct."""

    def test_the_kind_set_is_exactly_these_six(self):
        # Compared as sets against the hand-written tuple above, not counted: adding a seventh kind
        # reddens here first, which is where the six-vs-five artefact contradiction gets decided.
        assert set(get_args(EventKind)) == set(_KINDS)

    def test_deck_changed_and_active_deck_changed_are_both_present_and_distinct(self):
        # The contradiction c5-1 ruled on: AD-6 and the epic's Contracts section list five kinds
        # naming only `deck_changed`. Conflating the two makes a client refetch the deck it is
        # leaving rather than the one it is switching to.
        kinds = set(get_args(EventKind))
        assert {"deck_changed", "active_deck_changed"} <= kinds
        assert DeckChangedEvent is not ActiveDeckChangedEvent

    def test_the_tier_letters_are_exactly_these_five(self):
        assert set(get_args(TierLetter)) == set(_TIER_LETTERS)

    def test_the_confidence_tokens_are_exactly_these_three(self):
        # Three tokens matching `assess_deck_power`'s vocabulary, not a 0-1 float (Q2).
        assert set(get_args(Confidence)) == set(_CONFIDENCES)


class TestTheUnion:
    """AC 1 / AC 7 / AD-6: one discriminated union, every member its own named model."""

    def test_every_kind_has_its_own_member_and_no_two_kinds_share_one(self):
        # The shape the story flagged as highest-risk: a union guard that passes against a union of
        # one. This does not count members — it reconstructs the kind -> class mapping FROM the
        # union's actual members and compares it to the hand-written table, so a missing member, a
        # duplicated member and a mis-tagged member each fail differently.
        members = get_args(get_args(AgentEvent)[0])
        found = {get_args(member.model_fields["kind"].annotation)[0]: member for member in members}

        assert found == _CLASS_BY_KIND

    def test_every_member_is_a_named_model_not_an_inline_object(self):
        # Why it matters: only a named model becomes a `$ref` branch in the generated schema, which
        # is the shape `test_errors.py`'s `_is_ref_rooted` union arm admits. NOTHING IN THE SUITE
        # CATCHES AN INLINE MEMBER TODAY — that walk visits 2xx response bodies of existing routes,
        # and this union will be a request body. This assertion is the only thing standing there.
        members = get_args(get_args(AgentEvent)[0])

        assert all(isinstance(member, type) and member.__name__ for member in members)
        assert len({member.__name__ for member in members}) == len(_KINDS)

    @pytest.mark.parametrize("kind", _KINDS)
    def test_each_kind_parses_to_its_own_class_with_its_own_payload_class(self, kind):
        event = _AGENT_EVENT.validate_python(_envelope(kind))

        assert type(event) is _CLASS_BY_KIND[kind]
        assert type(event.payload) is _PAYLOAD_CLASS_BY_KIND[kind]

    def test_an_unknown_kind_is_rejected_and_a_known_one_is_accepted(self):
        # The non-vacuity pair: a discriminator that rejected everything would pass the first half.
        with pytest.raises(ValidationError):
            _AGENT_EVENT.validate_python(_envelope("kaboom"))

        assert _AGENT_EVENT.validate_python(_envelope("swaps")).kind == "swaps"

    def test_a_payload_from_the_wrong_kind_is_rejected_and_the_right_one_accepted(self):
        # Narrowing on `kind` is only trustworthy if the payload is actually pinned to it.
        with pytest.raises(ValidationError):
            _AGENT_EVENT.validate_python(_envelope("tier_list", {"items": [_suggestion()]}))

        assert _AGENT_EVENT.validate_python(_envelope("tier_list", {"items": [_tier()]})).payload


class TestTheEnvelopeFields:
    """AC 1 / AC 5 / AC 6 / AD-6: `{kind, id, ts, payload}`, opaque id, aware timestamp."""

    def test_the_serialised_envelope_carries_exactly_these_four_keys(self):
        event = _AGENT_EVENT.validate_python(_envelope("groups"))

        assert set(event.model_dump().keys()) == {"kind", "id", "ts", "payload"}

    def test_a_naive_ts_is_refused_and_an_aware_one_accepted(self):
        # AC 6: history sorts across kinds and across tabs, so two events minted in different
        # offsets have to be comparable. A naive value has no offset to compare.
        with pytest.raises(ValidationError):
            _AGENT_EVENT.validate_python(
                _envelope("swaps") | {"ts": datetime(2026, 8, 7, 9, 15).isoformat()}
            )

        assert _AGENT_EVENT.validate_python(_envelope("swaps")).ts == _TS

    def test_a_non_utc_offset_is_accepted_and_compares_against_utc(self):
        # Aware-not-naive is the constraint; the offset itself is not policed. What matters is that
        # the two are ORDERABLE, which is the property FR-18's history actually needs.
        elsewhere = _TS.astimezone(timezone(timedelta(hours=10)))
        event = _AGENT_EVENT.validate_python(_envelope("swaps") | {"ts": elsewhere.isoformat()})

        assert event.ts == _TS

    def test_an_empty_id_is_refused_and_a_one_character_id_accepted(self):
        with pytest.raises(ValidationError):
            _AGENT_EVENT.validate_python(_envelope("swaps") | {"id": ""})

        assert _AGENT_EVENT.validate_python(_envelope("swaps") | {"id": "x"}).id == "x"

    def test_the_id_is_opaque_so_a_non_uuid_is_accepted(self):
        # AC 5 / review finding S-7: identity and dedupe, never ordering. Pinning a uuid shape here
        # would be a promise the contract deliberately does not make, and a reader that sorts by
        # `id` gets a wrong order the moment a producer switches id schemes.
        assert _AGENT_EVENT.validate_python(_envelope("swaps") | {"id": "seq-000017"}).id

    @pytest.mark.parametrize("missing", ["kind", "id", "ts", "payload"])
    def test_every_envelope_field_is_required(self, missing):
        body = _envelope("swaps")
        del body[missing]

        with pytest.raises(ValidationError):
            _AGENT_EVENT.validate_python(body)

    def test_an_unknown_envelope_field_is_refused_and_the_known_ones_accepted(self):
        # Same reasoning as `ActiveDeckRequest`'s `extra="forbid"`: silently dropping a field
        # answers success to an agent whose mental model of this body is wrong.
        with pytest.raises(ValidationError):
            _AGENT_EVENT.validate_python(_envelope("swaps") | {"severity": "high"})

        assert _AGENT_EVENT.validate_python(_envelope("swaps")).kind == "swaps"


class TestTheItemShapes:
    """AC 8 / AC 12 / AD-7: four distinct shapes over a bare card reference, ids and no names."""

    @pytest.mark.parametrize(
        ("model", "expected"),
        [
            (SuggestionItem, {"card_id", "reason", "category", "confidence"}),
            (
                SwapItem,
                {"out_card_id", "in_card_id", "rationale", "out_qty", "in_qty", "confidence"},
            ),
            (TierItem, {"letter", "name", "note", "card_ids"}),
            (GroupItem, {"title", "rationale", "card_ids"}),
        ],
    )
    def test_each_item_shape_is_exactly_these_fields(self, model, expected):
        # Compared as sets, so both a missing field and a stray one fail here. This is the
        # assertion that holds AC 8's "not one fat optional bag": four shapes, no shared soup.
        assert set(model.model_fields) == expected

    def test_no_item_shape_carries_a_card_name_or_a_price(self):
        # FR-13: payloads carry Scryfall printing uuids only — duplicating card data here would be
        # a second copy that can disagree with the database. And `price` is struck (Q3): no price
        # data exists anywhere in this system, so the field could never be populated.
        banned = {"name", "card_name", "mana_cost", "type_line", "price", "prices"}
        for model in (SuggestionItem, SwapItem, TierItem, GroupItem):
            # `TierItem.name` is the TIER's name, not a card's — it is checked by identity of the
            # model, not by the word, which is why this loop excludes it explicitly.
            fields = set(model.model_fields) - ({"name"} if model is TierItem else set())
            assert not fields & banned, f"{model.__name__} carries {sorted(fields & banned)}"

    def test_a_card_id_is_not_validated_for_shape(self):
        # AD-7: ids are not validated at ingest. An unknown id resolves to the unknown-card
        # placeholder downstream, not to a rejected push.
        assert SuggestionItem(**_suggestion(card_id="not-a-uuid-at-all")).card_id
        assert TierItem(**_tier(card_ids=["nope", "also-nope"])).card_ids == ["nope", "also-nope"]

    def test_confidence_is_optional_and_closed(self):
        assert SuggestionItem(**_suggestion()).confidence is None
        assert SwapItem(**_swap()).confidence is None
        assert SuggestionItem(**_suggestion(confidence="high")).confidence == "high"

        with pytest.raises(ValidationError):
            SuggestionItem(**_suggestion(confidence="very"))

    def test_an_unknown_item_field_is_refused_and_the_known_ones_accepted(self):
        with pytest.raises(ValidationError):
            SuggestionItem(**_suggestion(priority=1))

        assert SuggestionItem(**_suggestion()).card_id == "c1"


class TestSwapQuantities:
    """AC 11: zero copies is a designed, rendered case — not a malformed payload."""

    def test_zero_is_accepted_on_both_sides_and_negative_is_rejected(self):
        # A `ge=1` constraint here would reject a payload the experience specification asks for:
        # a swap whose in-card has zero copies available renders "0 copies".
        item = SwapItem(**_swap(out_qty=0, in_qty=0))
        assert (item.out_qty, item.in_qty) == (0, 0)

        with pytest.raises(ValidationError):
            SwapItem(**_swap(in_qty=-1))


class TestTierAccessibility:
    """AC 10 / UX-DR26/41: colour never carries rank alone, so the name may not be blank."""

    def test_the_letter_is_closed_and_an_unknown_one_is_rejected(self):
        assert TierItem(**_tier(letter="D")).letter == "D"

        with pytest.raises(ValidationError):
            TierItem(**_tier(letter="F"))

    def test_an_empty_name_is_refused_and_a_one_character_name_accepted(self):
        # The letter is a colour ramp; `name` is the accessible carrier of rank. An empty name
        # silently breaks an accessibility floor rather than merely looking unfinished.
        with pytest.raises(ValidationError):
            TierItem(**_tier(name=""))

        assert TierItem(**_tier(name="A")).name == "A"

    def test_a_group_title_may_not_be_empty_either(self):
        with pytest.raises(ValidationError):
            GroupItem(**_group(title=""))

        assert GroupItem(**_group(title="R")).title == "R"


class TestEmptyAndOrder:
    """AC 13 / AC 14: empty is valid everywhere, and nothing sorts, dedupes or re-orders."""

    @pytest.mark.parametrize("kind", _KINDS)
    def test_an_empty_payload_is_accepted_for_every_kind(self, kind):
        # The UI skips an empty view rather than rejecting it, so "I looked and found nothing" has
        # to be expressible.
        assert _AGENT_EVENT.validate_python(_envelope(kind)).payload is not None

    def test_an_empty_card_id_list_is_accepted_inside_a_tier_and_a_group(self):
        assert TierItem(**_tier(card_ids=[])).card_ids == []
        assert GroupItem(**_group(card_ids=[])).card_ids == []

    def test_tiers_keep_payload_order_and_a_repeated_letter_is_legal(self):
        # `epics:3489`: tiers appear in payload order, not re-sorted by the UI. Two `A` tiers with
        # different names is a legal payload — the agent's ordering is the agent's argument.
        payload = TierListPayload(
            items=[
                _tier(letter="D", name="Cut"),
                _tier(letter="A", name="Strong"),
                _tier(letter="A", name="Also strong"),
            ]
        )

        assert [(item.letter, item.name) for item in payload.items] == [
            ("D", "Cut"),
            ("A", "Strong"),
            ("A", "Also strong"),
        ]

    def test_card_ids_keep_payload_order_and_duplicates_survive(self):
        payload = TierItem(**_tier(card_ids=["c3", "c1", "c1", "c2"]))

        assert payload.card_ids == ["c3", "c1", "c1", "c2"]

    def test_groups_keep_payload_order(self):
        payload = GroupsPayload(items=[_group(title="Zebra"), _group(title="Alpha")])

        assert [item.title for item in payload.items] == ["Zebra", "Alpha"]


class TestTheAgentViewTitle:
    """AC 9 / Q6: an optional agent-authored header, with a fallback the contract owns."""

    @pytest.mark.parametrize("kind", _VIEW_KINDS)
    def test_every_view_payload_carries_an_optional_title(self, kind):
        assert _AGENT_EVENT.validate_python(_envelope(kind)).payload.title is None
        assert (
            _AGENT_EVENT.validate_python(
                _envelope(kind, {"title": "Resilience options"})
            ).payload.title
            == "Resilience options"
        )

    def test_the_payload_title_is_a_different_slot_from_a_groups_per_group_title(self):
        payload = GroupsPayload(title="What this deck is doing", items=[_group(title="Ramp")])

        assert payload.title != payload.items[0].title

    def test_a_fallback_exists_for_every_view_kind_and_none_is_blank(self):
        # The view heading is the `aria-labelledby` target of a `role="dialog"`, so an absent title
        # leaves a dialog unlabelled. Compared as sets against the hand-written view tuple.
        assert set(DEFAULT_TITLE_BY_KIND) == set(_VIEW_KINDS)
        assert all(title.strip() for title in DEFAULT_TITLE_BY_KIND.values())

    def test_the_system_signals_have_no_fallback_because_they_draw_no_view(self):
        # Four entries, not six, and this is the assertion that says so on purpose: a signal opens
        # no dialog, so a string here would be UI copy invented for something that never draws.
        assert not {"deck_changed", "active_deck_changed"} & set(DEFAULT_TITLE_BY_KIND)


class TestTheSystemSignals:
    """AC 15 / Q5: both signals carry a deck id, nullable, on the one existing bound."""

    @pytest.mark.parametrize("model", [DeckChangedPayload, ActiveDeckChangedPayload])
    def test_the_signal_payload_is_exactly_a_deck_id(self, model):
        assert set(model.model_fields) == {"deck_id"}

    @pytest.mark.parametrize("model", [DeckChangedPayload, ActiveDeckChangedPayload])
    def test_the_deck_id_is_nullable_and_a_real_id_is_still_accepted(self, model):
        # Nullable now rather than later: a Phase-3 deck-agnostic `deck_changed` would otherwise
        # break a contract already committed into a `.d.ts` and two mirrored plugin bundles.
        assert model().deck_id is None
        assert model(deck_id=None).deck_id is None
        assert model(deck_id="076ac3ed").deck_id == "076ac3ed"

    @pytest.mark.parametrize("model", [DeckChangedPayload, ActiveDeckChangedPayload])
    def test_the_deck_id_reuses_the_existing_256_bound(self, model):
        # 256 is `_MAX_DECK_ID_LENGTH`, asserted as the literal so a second, different bound cannot
        # be introduced here without reddening.
        assert model(deck_id="x" * 256).deck_id

        with pytest.raises(ValidationError):
            model(deck_id="x" * 257)

    def test_a_signal_carries_no_items_and_no_title(self):
        assert not {"items", "title"} & set(DeckChangedPayload.model_fields)
        assert not {"items", "title"} & set(ActiveDeckChangedPayload.model_fields)


class TestTheCaps:
    """AC 16 / AC 22 / AD-7: every cap paired — at-cap accepted, one over rejected."""

    def test_sixty_suggestions_are_accepted_and_sixty_one_are_rejected(self):
        assert len(SuggestionsPayload(items=[_suggestion()] * 60).items) == 60

        with pytest.raises(ValidationError):
            SuggestionsPayload(items=[_suggestion()] * 61)

    def test_sixty_swaps_are_accepted_and_sixty_one_are_rejected(self):
        assert len(SwapsPayload(items=[_swap()] * 60).items) == 60

        with pytest.raises(ValidationError):
            SwapsPayload(items=[_swap()] * 61)

    def test_sixty_card_ids_are_accepted_and_sixty_one_are_rejected(self):
        assert len(TierItem(**_tier(card_ids=["c"] * 60)).card_ids) == 60
        assert len(GroupItem(**_group(card_ids=["c"] * 60)).card_ids) == 60

        with pytest.raises(ValidationError):
            TierItem(**_tier(card_ids=["c"] * 61))
        with pytest.raises(ValidationError):
            GroupItem(**_group(card_ids=["c"] * 61))

    def test_twelve_tiers_are_accepted_and_thirteen_are_rejected(self):
        assert len(TierListPayload(items=[_tier()] * 12).items) == 12

        with pytest.raises(ValidationError):
            TierListPayload(items=[_tier()] * 13)

    def test_twelve_groups_are_accepted_and_thirteen_are_rejected(self):
        assert len(GroupsPayload(items=[_group()] * 12).items) == 12

        with pytest.raises(ValidationError):
            GroupsPayload(items=[_group()] * 13)

    def test_a_two_hundred_character_reason_is_accepted_and_two_hundred_and_one_rejected(self):
        # 200 is what makes "one line of secondary text beneath the card name" honest.
        assert len(SuggestionItem(**_suggestion(reason="r" * 200)).reason) == 200

        with pytest.raises(ValidationError):
            SuggestionItem(**_suggestion(reason="r" * 201))

    def test_a_six_hundred_character_rationale_is_accepted_and_six_hundred_and_one_rejected(self):
        assert len(SwapItem(**_swap(rationale="r" * 600)).rationale) == 600
        assert len(GroupItem(**_group(rationale="r" * 600)).rationale) == 600

        with pytest.raises(ValidationError):
            SwapItem(**_swap(rationale="r" * 601))
        with pytest.raises(ValidationError):
            GroupItem(**_group(rationale="r" * 601))

    def test_an_eighty_character_title_is_accepted_and_eighty_one_rejected(self):
        assert len(SuggestionsPayload(title="t" * 80).title or "") == 80
        assert len(GroupItem(**_group(title="t" * 80)).title) == 80

        with pytest.raises(ValidationError):
            SuggestionsPayload(title="t" * 81)
        with pytest.raises(ValidationError):
            GroupItem(**_group(title="t" * 81))

    def test_an_eighty_character_category_is_accepted_and_eighty_one_rejected(self):
        # Q4: AD-7's cap list left `category` unbounded by anything but the envelope byte cap, and
        # it renders inside a badge.
        assert len(SuggestionItem(**_suggestion(category="c" * 80)).category or "") == 80

        with pytest.raises(ValidationError):
            SuggestionItem(**_suggestion(category="c" * 81))

    def test_a_forty_character_tier_name_is_accepted_and_forty_one_rejected(self):
        # Q4: it renders inside a 132px chip.
        assert len(TierItem(**_tier(name="n" * 40)).name) == 40

        with pytest.raises(ValidationError):
            TierItem(**_tier(name="n" * 41))

    def test_a_two_hundred_character_tier_note_is_accepted_and_two_hundred_and_one_rejected(self):
        assert len(TierItem(**_tier(note="n" * 200)).note or "") == 200

        with pytest.raises(ValidationError):
            TierItem(**_tier(note="n" * 201))

    def test_the_envelope_byte_cap_is_sixty_four_kilobytes_and_is_not_enforced_here(self):
        # AC 16 / Q9: declared here, ENFORCED SINCE c5-5 by `app.body_cap.BodyCapMiddleware` —
        # which is outside this leaf entirely, so this assertion is unchanged and still correct.
        # WHAT THIS CANNOT SEE: it is a bound on the
        # REQUEST, and a model validator runs after parsing — so it could reject an oversized
        # envelope but not stop the process from buffering it, which is the property that matters.
        # The assertion below is therefore that the constant exists and that no model enforces it.
        assert _MAX_ENVELOPE_BYTES == 64 * 1024

        # GENUINELY oversized, not merely named that way (c5-1 review round 2, Brad 2026-08-07): 12
        # groups (the _MAX_BUCKETS cap) each carrying a 600-char rationale and 60 (_MAX_ITEMS)
        # near-max-length card ids clears 64 KB comfortably while staying within every per-field
        # cap — proving an oversized envelope is constructible AND currently accepted, not just that
        # a normal-sized one is small.
        oversized = _envelope(
            "groups",
            {"items": [_group(rationale="r" * 600, card_ids=["c" * 128] * 60) for _ in range(12)]},
        )
        serialised = _AGENT_EVENT.dump_json(_AGENT_EVENT.validate_python(oversized))
        assert len(serialised) > 64 * 1024, (
            "payload must actually clear the cap to prove non-enforcement"
        )


class TestReviewRoundTwoIdCaps:
    """c5-1 review round 2: `_MAX_CARD_ID_LENGTH`/`_MAX_EVENT_ID_LENGTH` had zero coverage."""

    def test_a_128_character_card_id_is_accepted_and_129_is_rejected(self):
        assert len(SuggestionItem(**_suggestion(card_id="c" * 128)).card_id) == 128
        assert len(TierItem(**_tier(card_ids=["c" * 128])).card_ids[0]) == 128

        with pytest.raises(ValidationError):
            SuggestionItem(**_suggestion(card_id="c" * 129))
        with pytest.raises(ValidationError):
            TierItem(**_tier(card_ids=["c" * 129]))

    def test_a_128_character_event_id_is_accepted_and_129_is_rejected(self):
        assert len(_AGENT_EVENT.validate_python(_envelope("swaps") | {"id": "x" * 128}).id) == 128

        with pytest.raises(ValidationError):
            _AGENT_EVENT.validate_python(_envelope("swaps") | {"id": "x" * 129})

    def test_the_two_id_caps_are_both_a_hundred_and_twenty_eight(self):
        # Asserted as literals, per this file's own house rule — not by comparing the two constants
        # to each other, which would stay green if both drifted to the same wrong number together.
        assert _MAX_CARD_ID_LENGTH == 128
        assert _MAX_EVENT_ID_LENGTH == 128


class TestReviewRoundTwoBlankTextGuards:
    """c5-1 review round 2: whitespace-only strings, and fields round 1's ruling missed."""

    def test_a_whitespace_only_envelope_id_is_refused(self):
        # Round 1 tested only `""`; `min_length=1` alone accepts `"   "`, which is the case
        # `_refuse_blank_text` exists to catch and no test exercised.
        with pytest.raises(ValidationError):
            _AGENT_EVENT.validate_python(_envelope("swaps") | {"id": "   "})

    def test_a_whitespace_only_tier_name_is_refused(self):
        with pytest.raises(ValidationError):
            TierItem(**_tier(name="   "))

    def test_a_whitespace_only_group_title_is_refused(self):
        with pytest.raises(ValidationError):
            GroupItem(**_group(title="   "))

    @pytest.mark.parametrize("kind", _VIEW_KINDS)
    def test_an_empty_or_whitespace_only_payload_title_is_refused_and_none_still_means_default(
        self, kind
    ):
        # The exact bug `_NonBlankTitle` was written to prevent: an empty string is not `None`, so
        # without this it would defeat `DEFAULT_TITLE_BY_KIND` and leave a `role="dialog"` labelled
        # by an empty string. Neither case was tested before this round.
        with pytest.raises(ValidationError):
            _AGENT_EVENT.validate_python(_envelope(kind, {"title": ""}))
        with pytest.raises(ValidationError):
            _AGENT_EVENT.validate_python(_envelope(kind, {"title": "   "}))

        assert _AGENT_EVENT.validate_python(_envelope(kind)).payload.title is None

    def test_an_empty_or_whitespace_only_reason_is_refused_and_real_text_is_accepted(self):
        with pytest.raises(ValidationError):
            SuggestionItem(**_suggestion(reason=""))
        with pytest.raises(ValidationError):
            SuggestionItem(**_suggestion(reason="   "))

        assert SuggestionItem(**_suggestion(reason="Fixes the curve.")).reason

    def test_an_empty_or_whitespace_only_rationale_is_refused_on_swaps_and_groups(self):
        with pytest.raises(ValidationError):
            SwapItem(**_swap(rationale=""))
        with pytest.raises(ValidationError):
            SwapItem(**_swap(rationale="   "))
        with pytest.raises(ValidationError):
            GroupItem(**_group(rationale=""))
        with pytest.raises(ValidationError):
            GroupItem(**_group(rationale="   "))

    @pytest.mark.parametrize("model", [DeckChangedPayload, ActiveDeckChangedPayload])
    def test_an_empty_or_whitespace_only_deck_id_is_refused_but_none_is_still_accepted(self, model):
        # `None` means "refetch whatever is active" (Q5) — an empty string is a third state that is
        # neither that sentinel nor a real id, and round 1's blank-string ruling did not reach it.
        with pytest.raises(ValidationError):
            model(deck_id="")
        with pytest.raises(ValidationError):
            model(deck_id="   ")

        assert model(deck_id=None).deck_id is None
        assert model().deck_id is None


class TestReviewRoundTwoExamplesRoundTrip:
    """c5-1 review round 2: the ten `json_schema_extra` wire examples were never re-validated."""

    @pytest.mark.parametrize(
        "model",
        [SuggestionItem, SwapItem, TierItem, GroupItem],
    )
    def test_each_item_shapes_json_schema_example_still_validates(self, model):
        examples = model.model_config["json_schema_extra"]["examples"]
        assert examples, f"{model.__name__} must ship at least one example"

        for example in examples:
            assert model.model_validate(example)

    @pytest.mark.parametrize("kind", _KINDS)
    def test_each_events_json_schema_example_still_validates(self, kind):
        cls = _CLASS_BY_KIND[kind]
        examples = cls.model_config["json_schema_extra"]["examples"]
        assert examples, f"{cls.__name__} must ship at least one example"

        for example in examples:
            event = _AGENT_EVENT.validate_python(example)
            assert event.kind == kind


class TestTheIngestReceipt:
    """c5-5's one new wire model: what ``POST /agent/events`` answers with (Q1, Brad 2026-08-08).

    Driven directly like everything else in this file — the *route's* behaviour, including which
    number actually reaches this model, is ``test_routes_agent_events.py``'s subject. What is
    asserted here is the shape alone.
    """

    def test_it_carries_the_client_count_and_nothing_else(self):
        # One field, by name. AD-16's unwrapped-success rule plus CM-1's no-echo rule leave exactly
        # this: the agent learns how many browsers received its push and learns nothing else back.
        # Spelled `clients` to match the SPINE sequence diagram's `200 {clients: 1}`.
        assert EventIngestReceipt(clients=3).model_dump() == {"clients": 3}

    def test_zero_is_an_ordinary_value_rather_than_an_error(self):
        # A push nobody heard is a success (`ws.broadcast`'s own contract): the companion with no
        # tab open is the ordinary state, not a failure the agent should retry.
        assert EventIngestReceipt(clients=0).clients == 0


class TestReviewRoundTwoDoctests:
    """c5-1 review round 2: the `Example:` doctest blocks were never confirmed to run anywhere.

    They cross the wire verbatim as the schema `description`, and `probe_harness.py`'s owned argv
    does not include `--doctest-modules` (nor would it reach `src/`, since `testpaths` is scoped to
    `tests/`) — so a stale example would previously have shipped unverified. This test runs them
    directly via `doctest`, which folds them into the same suite this file is already collected by.
    """

    def test_every_doctest_example_in_the_contracts_module_passes(self):
        results = doctest.testmod(contracts_module, verbose=False)
        assert results.attempted > 0, "expected at least one doctest example to have run"
        assert results.failed == 0, f"{results.failed} doctest example(s) failed in contracts.py"
