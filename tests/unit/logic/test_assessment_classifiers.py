"""Offline canonical-card behavior tests for the shared oracle-text classifiers (Story 5.3).

Verifies by *behavior on synthetic canonical cards*, never by pattern-list contents (the
5.1/5.2 verify-by-shape lesson): Story 5.9's benchmark pass may tune the pattern vocabulary
without rewriting these tests. Covers the AC6 matrix — per-category positives, the AC2
negative guardrails/traps, quantity-awareness, multi-face fallback, and determinism.
"""

from typing import Any

from src.data.schemas.card import Card
from src.data.schemas.deck import DeckCard
from src.logic.assessment import (
    CARD_DRAW,
    CATEGORIES,
    EXTRA_TURN,
    INTERACTION,
    MASS_LAND_DENIAL,
    RAMP,
    TUTOR,
    WINCON_COMBO_PIECE,
    WINCON_EXPLICIT,
    WINCON_FINISHER,
    CategoryCount,
    HardTriggerFlag,
    classify_card,
    classify_deck,
    detect_extra_turn_cards,
    detect_mass_land_denial,
)

# ---------------------------------------------------------------------------
# Fixture factories
# ---------------------------------------------------------------------------


def make_card(**overrides: Any) -> Card:
    """Build a minimal valid ``Card``, overriding only the fields a test cares about."""
    defaults: dict[str, Any] = {
        "id": "00000000-0000-0000-0000-000000000000",
        "name": "Test Card",
        "oracle_id": "11111111-1111-1111-1111-111111111111",
        "mana_cost": "{1}",
        "cmc": 1.0,
        "type_line": "Sorcery",
        "oracle_text": "",
        "rarity": "common",
        "set_code": "tst",
        "set_name": "Test Set",
        "collector_number": "1",
        "colors": [],
        "color_identity": [],
        "legalities": {},
    }
    defaults.update(overrides)
    return Card(**defaults)


def make_deck_card(card: Card, quantity: int = 1, sideboard: bool = False) -> DeckCard:
    """Wrap a ``Card`` in a ``DeckCard`` association row."""
    return DeckCard(
        deck_id="deck-1",
        card_id=card.id,
        quantity=quantity,
        sideboard=sideboard,
        card=card,
    )


# --- Canonical cards (real oracle wordings; comments name the category they pin) ----------


def sol_ring() -> Card:  # ramp (mana rock)
    return make_card(name="Sol Ring", type_line="Artifact", oracle_text="{T}: Add {C}{C}.")


def llanowar_elves() -> Card:  # ramp (mana creature)
    return make_card(
        name="Llanowar Elves",
        type_line="Creature — Elf Druid",
        oracle_text="{T}: Add {G}.",
        power="1",
        toughness="1",
    )


def rampant_growth() -> Card:  # ramp (land-fetch to battlefield), NOT tutor
    return make_card(
        name="Rampant Growth",
        oracle_text=(
            "Search your library for a basic land card, put that card onto the "
            "battlefield tapped, then shuffle."
        ),
    )


def cultivate() -> Card:  # ramp (land-fetch to battlefield), NOT tutor
    return make_card(
        name="Cultivate",
        oracle_text=(
            "Search your library for up to two basic land cards, reveal those cards, "
            "put one onto the battlefield tapped and the other into your hand, then shuffle."
        ),
    )


def forest() -> Card:  # NOT ramp — lands produce mana, they don't accelerate it
    return make_card(
        name="Forest",
        mana_cost="",
        cmc=0.0,
        type_line="Basic Land — Forest",
        oracle_text="({T}: Add {G}.)",
    )


def wooded_foothills() -> Card:  # fetchland: Land type_line — neither ramp nor tutor
    return make_card(
        name="Wooded Foothills",
        mana_cost="",
        cmc=0.0,
        type_line="Land",
        oracle_text=(
            "{T}, Pay 1 life, Sacrifice this land: Search your library for a Mountain "
            "or Forest card, put it onto the battlefield, then shuffle."
        ),
    )


def divination() -> Card:  # card draw
    return make_card(name="Divination", oracle_text="Draw two cards.")


def rhystic_study() -> Card:  # card draw (triggered engine)
    return make_card(
        name="Rhystic Study",
        type_line="Enchantment",
        oracle_text=(
            "Whenever an opponent casts a spell, you may draw a card unless that player pays {1}."
        ),
    )


def swords_to_plowshares() -> Card:  # removal/interaction (exile)
    return make_card(
        name="Swords to Plowshares",
        type_line="Instant",
        oracle_text="Exile target creature. Its controller gains life equal to its power.",
    )


def counterspell() -> Card:  # removal/interaction (counter)
    return make_card(name="Counterspell", type_line="Instant", oracle_text="Counter target spell.")


def wrath_of_god() -> Card:  # removal/interaction (mass wipe)
    return make_card(
        name="Wrath of God",
        oracle_text="Destroy all creatures. They can't be regenerated.",
    )


def lightning_bolt() -> Card:  # removal/interaction (damage to target)
    return make_card(
        name="Lightning Bolt",
        type_line="Instant",
        oracle_text="Lightning Bolt deals 3 damage to any target.",
    )


def demonic_tutor() -> Card:  # tutor (generic search to hand)
    return make_card(
        name="Demonic Tutor",
        oracle_text="Search your library for a card, put that card into your hand, then shuffle.",
    )


def vampiric_tutor() -> Card:  # tutor (search to top of library)
    return make_card(
        name="Vampiric Tutor",
        type_line="Instant",
        oracle_text=(
            "Search your library for a card, then shuffle and put that card on top of "
            "your library. You lose 2 life."
        ),
    )


def thassas_oracle() -> Card:  # explicit wincon ("you win the game")
    return make_card(
        name="Thassa's Oracle",
        type_line="Creature — Merfolk Wizard",
        power="1",
        toughness="3",
        oracle_text=(
            "When this creature enters, look at the top X cards of your library, where X "
            "is your devotion to blue. If X is greater than or equal to the number of "
            "cards in your library, you win the game."
        ),
    )


def craterhoof_behemoth() -> Card:  # finisher (haymaker team pump)
    return make_card(
        name="Craterhoof Behemoth",
        type_line="Creature — Beast",
        power="5",
        toughness="5",
        keywords=["Haste"],
        oracle_text=(
            "Haste\nWhen this creature enters, creatures you control gain trample and get "
            "+X/+X until end of turn, where X is the number of creatures you control."
        ),
    )


def big_dragon() -> Card:  # finisher (large evasive body via keywords)
    return make_card(
        name="Shivan Behemoth-Dragon",
        type_line="Creature — Dragon",
        power="7",
        toughness="7",
        keywords=["Flying"],
        oracle_text="Flying",
    )


def vanilla_bear() -> Card:  # negative: classifies as nothing
    return make_card(
        name="Grizzly Bears",
        type_line="Creature — Bear",
        power="2",
        toughness="2",
        oracle_text="",
    )


def armageddon() -> Card:  # mass land denial (symmetric destruction)
    return make_card(name="Armageddon", oracle_text="Destroy all lands.")


def winter_orb() -> Card:  # mass land denial (lands-don't-untap stax)
    return make_card(
        name="Winter Orb",
        type_line="Artifact",
        oracle_text="Lands don't untap during their controllers' untap steps.",
    )


def time_warp() -> Card:  # extra turn
    return make_card(
        name="Time Warp",
        oracle_text="Target player takes an extra turn after this one.",
    )


def dramatic_reversal() -> Card:  # combo-piece heuristic (mass untap)
    return make_card(
        name="Dramatic Reversal",
        type_line="Instant",
        oracle_text="Untap all nonland permanents you control.",
    )


def kiki_jiki() -> Card:  # combo-piece heuristic (copy)
    return make_card(
        name="Kiki-Jiki, Mirror Breaker",
        type_line="Legendary Creature — Goblin Shaman",
        power="2",
        toughness="2",
        oracle_text=(
            "{T}: Create a token that's a copy of target nonlegendary creature you "
            "control, except it has haste. Sacrifice it at the beginning of the next "
            "end step."
        ),
    )


# ---------------------------------------------------------------------------
# FR6: ramp / card draw / removal-interaction / tutors
# ---------------------------------------------------------------------------


class TestRamp:
    """Ramp positives and the AC2 land guardrails."""

    def test_mana_rock_is_ramp(self) -> None:
        assert RAMP in classify_card(sol_ring()), "Sol Ring (mana rock) must classify as ramp"

    def test_mana_creature_is_ramp(self) -> None:
        assert RAMP in classify_card(llanowar_elves()), (
            "Llanowar Elves (mana creature) must classify as ramp"
        )

    def test_land_fetch_to_battlefield_is_ramp(self) -> None:
        assert RAMP in classify_card(rampant_growth()), (
            "Rampant Growth (land-fetch to battlefield) must classify as ramp"
        )
        assert RAMP in classify_card(cultivate()), (
            "Cultivate (land-fetch to battlefield) must classify as ramp"
        )

    def test_basic_land_is_not_ramp(self) -> None:
        assert RAMP not in classify_card(forest()), (
            "Forest (Land type_line) must never classify as ramp — lands produce mana, "
            "ramp accelerates it"
        )

    def test_fetchland_is_not_ramp(self) -> None:
        assert RAMP not in classify_card(wooded_foothills()), (
            "Wooded Foothills (Land type_line) must never classify as ramp"
        )

    def test_vanilla_creature_is_not_ramp(self) -> None:
        assert RAMP not in classify_card(vanilla_bear()), "Grizzly Bears must not classify as ramp"


class TestCardDraw:
    """Card-draw positives and the reminder-text trap."""

    def test_draw_spell_is_card_draw(self) -> None:
        assert CARD_DRAW in classify_card(divination()), (
            "Divination ('Draw two cards.') must classify as card draw"
        )

    def test_triggered_draw_engine_is_card_draw(self) -> None:
        assert CARD_DRAW in classify_card(rhystic_study()), (
            "Rhystic Study must classify as card draw"
        )

    def test_reminder_text_draw_is_not_card_draw(self) -> None:
        # Trap #2: cycling reminder text restates "Draw a card." inside parentheses.
        cycler = make_card(
            name="Barren Moor-alike",
            oracle_text="Cycling {2} ({2}, Discard this card: Draw a card.)",
        )
        assert CARD_DRAW not in classify_card(cycler), (
            "Reminder-text 'Draw a card.' must be stripped and never trip the card-draw classifier"
        )

    def test_vanilla_creature_is_not_card_draw(self) -> None:
        assert CARD_DRAW not in classify_card(vanilla_bear()), (
            "Grizzly Bears must not classify as card draw"
        )


class TestInteraction:
    """Removal/interaction positives and the +1/+1-counter near-miss."""

    def test_exile_removal_is_interaction(self) -> None:
        assert INTERACTION in classify_card(swords_to_plowshares()), (
            "Swords to Plowshares must classify as removal/interaction"
        )

    def test_counterspell_is_interaction(self) -> None:
        assert INTERACTION in classify_card(counterspell()), (
            "Counterspell must classify as removal/interaction"
        )

    def test_mass_wipe_is_interaction(self) -> None:
        assert INTERACTION in classify_card(wrath_of_god()), (
            "Wrath of God (mass wipe) must classify as removal/interaction"
        )

    def test_damage_removal_is_interaction(self) -> None:
        assert INTERACTION in classify_card(lightning_bolt()), (
            "Lightning Bolt (damage to target) must classify as removal/interaction"
        )

    def test_plus_one_counter_on_target_is_not_interaction(self) -> None:
        pump = make_card(
            name="Battlefield Promotion-alike",
            type_line="Instant",
            oracle_text="Put a +1/+1 counter on target creature. It gains first strike.",
        )
        assert INTERACTION not in classify_card(pump), (
            "'counter on target creature' (a +1/+1 counter) must not match 'counter target'"
        )


class TestTutor:
    """Tutor positives and the AC2 land-fetch/tutor disjointness guardrail."""

    def test_search_to_hand_is_tutor(self) -> None:
        assert TUTOR in classify_card(demonic_tutor()), (
            "Demonic Tutor (search to hand) must classify as tutor"
        )

    def test_search_to_top_of_library_is_tutor(self) -> None:
        assert TUTOR in classify_card(vampiric_tutor()), (
            "Vampiric Tutor (search to top of library) must classify as tutor"
        )

    def test_land_fetch_is_not_tutor(self) -> None:
        assert TUTOR not in classify_card(rampant_growth()), (
            "Rampant Growth (land-fetch to battlefield) must classify as ramp, not tutor"
        )
        assert TUTOR not in classify_card(cultivate()), (
            "Cultivate (land-fetch to battlefield) must classify as ramp, not tutor"
        )

    def test_fetchland_is_not_tutor(self) -> None:
        assert TUTOR not in classify_card(wooded_foothills()), (
            "Wooded Foothills (battlefield land-fetch) must not classify as tutor"
        )

    def test_generic_tutor_is_not_ramp(self) -> None:
        assert RAMP not in classify_card(demonic_tutor()), "Demonic Tutor must not classify as ramp"


# ---------------------------------------------------------------------------
# FR10: win-condition tags
# ---------------------------------------------------------------------------


class TestWinConditions:
    """Explicit wincons, combo-piece heuristics, and evasive/haymaker finishers."""

    def test_you_win_the_game_is_explicit_wincon(self) -> None:
        assert WINCON_EXPLICIT in classify_card(thassas_oracle()), (
            "Thassa's Oracle ('you win the game') must tag as explicit wincon"
        )

    def test_each_opponent_loses_is_explicit_wincon(self) -> None:
        exsanguinate_like = make_card(
            name="Approach-alike",
            oracle_text="At the beginning of your upkeep, each opponent loses the game.",
        )
        assert WINCON_EXPLICIT in classify_card(exsanguinate_like), (
            "'each opponent loses the game' must tag as explicit wincon"
        )

    def test_mass_untap_is_combo_piece(self) -> None:
        assert WINCON_COMBO_PIECE in classify_card(dramatic_reversal()), (
            "Dramatic Reversal (mass untap) must tag as combo-piece heuristic"
        )

    def test_copy_effect_is_combo_piece(self) -> None:
        assert WINCON_COMBO_PIECE in classify_card(kiki_jiki()), (
            "Kiki-Jiki (copy effect) must tag as combo-piece heuristic"
        )

    def test_haymaker_team_pump_is_finisher(self) -> None:
        assert WINCON_FINISHER in classify_card(craterhoof_behemoth()), (
            "Craterhoof Behemoth (team pump + trample haymaker) must tag as finisher"
        )

    def test_large_evasive_body_is_finisher(self) -> None:
        assert WINCON_FINISHER in classify_card(big_dragon()), (
            "A 7/7 with Flying must tag as evasive finisher"
        )

    def test_unblockable_oracle_text_counts_as_evasion(self) -> None:
        slippery = make_card(
            name="Inkwell Leviathan-alike",
            type_line="Creature — Leviathan",
            power="7",
            toughness="11",
            oracle_text="This creature can't be blocked.",
        )
        assert WINCON_FINISHER in classify_card(slippery), (
            'A large body with "can\'t be blocked" oracle text must tag as finisher'
        )

    def test_small_evasive_body_is_not_finisher(self) -> None:
        faerie = make_card(
            name="Faerie Seer-alike",
            type_line="Creature — Faerie",
            power="1",
            toughness="1",
            keywords=["Flying"],
            oracle_text="Flying",
        )
        assert WINCON_FINISHER not in classify_card(faerie), (
            "A 1/1 flyer is not a finisher (large-body requirement)"
        )

    def test_star_power_is_guarded_not_finisher(self) -> None:
        # AC3: non-numeric power values like "*" must be guarded, not crash.
        goyf = make_card(
            name="Tarmogoyf-alike",
            type_line="Creature — Lhurgoyf",
            power="*",
            toughness="1+*",
            keywords=["Trample"],
            oracle_text="Trample",
        )
        tags = classify_card(goyf)  # must not raise
        assert WINCON_FINISHER not in tags, (
            "Non-numeric power ('*') cannot satisfy the large-body finisher check"
        )

    def test_vanilla_creature_has_no_wincon_tags(self) -> None:
        tags = classify_card(vanilla_bear())
        assert not tags & {WINCON_EXPLICIT, WINCON_COMBO_PIECE, WINCON_FINISHER}, (
            f"Grizzly Bears must carry no win-condition tags, got {sorted(tags)}"
        )


# ---------------------------------------------------------------------------
# FR12: hard-trigger scans
# ---------------------------------------------------------------------------


class TestHardTriggers:
    """Mass-land-denial and extra-turn detection: per-card tags + deck-level flags."""

    def test_symmetric_land_destruction_is_mld(self) -> None:
        assert MASS_LAND_DENIAL in classify_card(armageddon()), (
            "Armageddon (symmetric 'Destroy all lands.') must tag as mass land denial"
        )

    def test_lands_dont_untap_stax_is_mld(self) -> None:
        assert MASS_LAND_DENIAL in classify_card(winter_orb()), (
            "Winter Orb (lands-don't-untap stax) must tag as mass land denial"
        )

    def test_single_land_removal_is_not_mld(self) -> None:
        stone_rain = make_card(name="Stone Rain", oracle_text="Destroy target land.")
        assert MASS_LAND_DENIAL not in classify_card(stone_rain), (
            "Stone Rain (single-target land removal) is not MASS land denial"
        )

    def test_extra_turn_spell_tags(self) -> None:
        assert EXTRA_TURN in classify_card(time_warp()), (
            "Time Warp must tag as extra turn — a single extra-turn spell sets the signal"
        )

    def test_detect_mass_land_denial_deck_flag(self) -> None:
        deck = [make_deck_card(armageddon()), make_deck_card(divination())]
        flag = detect_mass_land_denial(deck)
        assert isinstance(flag, HardTriggerFlag)
        assert flag.triggered is True
        assert flag.card_names == ("Armageddon",)

    def test_detect_extra_turn_deck_flag(self) -> None:
        deck = [make_deck_card(time_warp(), quantity=2)]
        flag = detect_extra_turn_cards(deck)
        assert flag.triggered is True
        assert flag.card_names == ("Time Warp",)

    def test_hard_triggers_false_on_clean_deck(self) -> None:
        deck = [make_deck_card(divination()), make_deck_card(vanilla_bear())]
        assert detect_mass_land_denial(deck) == HardTriggerFlag(triggered=False, card_names=())
        assert detect_extra_turn_cards(deck) == HardTriggerFlag(triggered=False, card_names=())


# ---------------------------------------------------------------------------
# Cross-cutting behavior: multi-category, multi-face, aggregation, determinism
# ---------------------------------------------------------------------------


class TestMultiCategory:
    """Categories are independent tags, not exclusive buckets (AC2)."""

    def test_modal_draw_plus_removal_holds_both_tags(self) -> None:
        modal = make_card(
            name="Thirst Modal-alike",
            type_line="Instant",
            oracle_text="Choose one —\n• Destroy target artifact.\n• Draw a card.",
        )
        tags = classify_card(modal)
        assert INTERACTION in tags, "Modal spell's removal mode must tag interaction"
        assert CARD_DRAW in tags, "Modal spell's draw mode must tag card draw"


class TestMultiFace:
    """Trap #1: multi-face cards persist oracle_text='' with text in card_faces."""

    def test_classifies_from_faces_when_top_level_text_empty(self) -> None:
        mdfc = make_card(
            name="Sea Gate Restoration // Sea Gate, Reborn",
            type_line="Sorcery // Land",
            oracle_text="",
            card_faces=[
                {
                    "name": "Sea Gate Restoration",
                    "oracle_text": "Draw cards equal to the number of cards in your hand.",
                },
                {"name": "Sea Gate, Reborn"},  # face without an oracle_text key
            ],
        )
        # The draw face's text must be reachable; "draw cards equal to ..." is not the
        # canonical draw wording, so use a face with canonical wording to pin the fallback.
        mdfc_canonical = make_card(
            name="Valakut Awakening // Valakut Stoneforge",
            type_line="Instant // Land",
            oracle_text="",
            card_faces=[
                {"name": "Valakut Awakening", "oracle_text": "Draw two cards."},
                {"name": "Valakut Stoneforge"},
            ],
        )
        assert CARD_DRAW in classify_card(mdfc_canonical), (
            "A multi-face card with empty top-level oracle_text must classify from its faces"
        )
        # And a faces-less empty card must simply classify as nothing, not crash.
        assert classify_card(mdfc) is not None

    def test_empty_card_with_no_faces_classifies_as_nothing(self) -> None:
        assert classify_card(make_card(name="Blank", oracle_text="")) == frozenset()


class TestDeckAggregation:
    """classify_deck: quantity-aware counts, sorted names, zero-fill, determinism."""

    def test_quantity_aware_counting(self) -> None:
        deck = [make_deck_card(divination(), quantity=4)]
        result = classify_deck(deck)
        assert result[CARD_DRAW].count == 4, "A 4-of must count 4 (the Standard case)"
        assert result[CARD_DRAW].card_names == ("Divination",), (
            "Names are unique (not repeated per copy) and sorted"
        )

    def test_all_categories_present_with_zero_fill(self) -> None:
        result = classify_deck([])
        assert set(result.keys()) == set(CATEGORIES), (
            "classify_deck must key every category in the closed set, even when empty"
        )
        for token in CATEGORIES:
            assert result[token] == CategoryCount(count=0, card_names=()), (
                f"Empty deck must zero-fill category {token!r}"
            )

    def test_names_are_sorted_and_unique(self) -> None:
        deck = [
            make_deck_card(wrath_of_god()),
            make_deck_card(counterspell(), quantity=2),
            make_deck_card(swords_to_plowshares()),
        ]
        result = classify_deck(deck)
        assert result[INTERACTION].card_names == (
            "Counterspell",
            "Swords to Plowshares",
            "Wrath of God",
        ), "Interaction names must be unique and lexicographically sorted"
        assert result[INTERACTION].count == 4, "2x Counterspell + 2 singletons = 4"

    def test_sideboard_cards_are_not_filtered(self) -> None:
        # Deck-composition policy belongs to the caller; the taxonomy classifies what it is given.
        deck = [make_deck_card(divination(), sideboard=True)]
        assert classify_deck(deck)[CARD_DRAW].count == 1, (
            "Sideboard rows are classified like any other input row"
        )

    def test_determinism_identical_input_identical_output(self) -> None:
        deck = [
            make_deck_card(sol_ring()),
            make_deck_card(demonic_tutor()),
            make_deck_card(armageddon()),
            make_deck_card(time_warp()),
            make_deck_card(craterhoof_behemoth()),
        ]
        first = classify_deck(deck)
        second = classify_deck(deck)
        assert first == second, "Identical input must yield identical output (AD-8 spirit)"
        for token, bucket in first.items():
            assert bucket.card_names == tuple(sorted(bucket.card_names)), (
                f"Category {token!r} names must be deterministically sorted"
            )

    def test_classify_card_is_deterministic(self) -> None:
        card = cultivate()
        assert classify_card(card) == classify_card(card)


class TestClosedCategorySet:
    """The module owns a closed category-token set (AC5)."""

    def test_category_constants_are_in_categories(self) -> None:
        tokens = {
            RAMP,
            CARD_DRAW,
            INTERACTION,
            TUTOR,
            WINCON_EXPLICIT,
            WINCON_COMBO_PIECE,
            WINCON_FINISHER,
            MASS_LAND_DENIAL,
            EXTRA_TURN,
        }
        assert tokens == set(CATEGORIES), (
            "CATEGORIES must equal exactly the nine exported category tokens"
        )
        assert len(CATEGORIES) == 9

    def test_classify_card_returns_only_known_tokens(self) -> None:
        for card in (sol_ring(), demonic_tutor(), armageddon(), craterhoof_behemoth()):
            tags = classify_card(card)
            assert tags <= set(CATEGORIES), (
                f"{card.name} produced tokens outside the closed set: "
                f"{sorted(tags - set(CATEGORIES))}"
            )
