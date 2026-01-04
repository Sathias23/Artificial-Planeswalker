"""Test fixtures for card data used in unit and integration tests."""

from src.data.models.card import CardModel


def create_standard_legal_cards() -> list[CardModel]:
    """Create sample Standard-legal cards for testing format filtering.

    Returns:
        List of CardModel instances with standard: "legal" in their legalities
    """
    return [
        # Standard-legal red instant
        CardModel(
            id="play-fire-001",
            name="Play with Fire",
            oracle_id="oracle-play-fire",
            mana_cost="{R}",
            cmc=1.0,
            type_line="Instant",
            oracle_text="Play with Fire deals 2 damage to any target.",
            rarity="uncommon",
            set_code="MID",
            set_name="Innistrad: Midnight Hunt",
            collector_number="154",
            colors=["R"],
            color_identity=["R"],
            color_indicator=None,
            keywords=None,
            legalities={"standard": "legal", "modern": "legal", "legacy": "legal"},
            card_faces=None,
            games=["paper", "arena", "mtgo"],
        ),
        # Standard-legal red creature with haste
        CardModel(
            id="fearless-001",
            name="Fearless Fledgling",
            oracle_id="oracle-fearless",
            mana_cost="{1}{W}",
            cmc=2.0,
            type_line="Creature — Griffin",
            oracle_text=(
                "Flying. Landfall — Whenever a land enters the battlefield, "
                "put a +1/+1 counter on Fearless Fledgling."
            ),
            rarity="uncommon",
            set_code="ZNR",
            set_name="Zendikar Rising",
            collector_number="015",
            colors=["W"],
            color_identity=["W"],
            color_indicator=None,
            keywords=["Flying"],
            legalities={"standard": "legal", "modern": "legal", "legacy": "legal"},
            card_faces=None,
            games=["paper", "arena", "mtgo"],
        ),
        # Standard-legal blue instant
        CardModel(
            id="consider-001",
            name="Consider",
            oracle_id="oracle-consider",
            mana_cost="{U}",
            cmc=1.0,
            type_line="Instant",
            oracle_text="Surveil 1. Draw a card.",
            rarity="common",
            set_code="MID",
            set_name="Innistrad: Midnight Hunt",
            collector_number="044",
            colors=["U"],
            color_identity=["U"],
            color_indicator=None,
            keywords=None,
            legalities={"standard": "legal", "modern": "legal", "legacy": "legal"},
            card_faces=None,
            games=["paper", "arena", "mtgo"],
        ),
        # Standard-legal colorless artifact
        CardModel(
            id="meteor-001",
            name="Meteorite",
            oracle_id="oracle-meteor",
            mana_cost="{5}",
            cmc=5.0,
            type_line="Artifact",
            oracle_text=(
                "When Meteorite enters the battlefield, it deals 2 damage to any target. "
                "{T}: Add one mana of any color."
            ),
            rarity="uncommon",
            set_code="M19",
            set_name="Core Set 2019",
            collector_number="233",
            colors=[],
            color_identity=[],
            color_indicator=None,
            keywords=None,
            legalities={"standard": "legal", "modern": "legal", "legacy": "legal"},
            card_faces=None,
            games=["paper", "arena", "mtgo"],
        ),
    ]


def create_sample_cards() -> list[CardModel]:
    """Create a diverse set of sample cards for testing.

    Returns:
        List of CardModel instances with various attributes:
        - Single-color cards (Red, Blue, Green)
        - Multi-color card (Red/Blue)
        - Colorless artifact
        - Various types (Instant, Creature, Artifact)
        - Different rarities and sets
    """
    return [
        # Single-color red instant
        CardModel(
            id="bolt-001",
            name="Lightning Bolt",
            oracle_id="oracle-bolt",
            mana_cost="{R}",
            cmc=1.0,
            type_line="Instant",
            oracle_text="Lightning Bolt deals 3 damage to any target.",
            rarity="common",
            set_code="LEA",
            set_name="Limited Edition Alpha",
            collector_number="161",
            colors=["R"],
            color_identity=["R"],
            color_indicator=None,
            keywords=None,
            legalities={"standard": "not_legal", "modern": "legal", "legacy": "legal"},
            card_faces=None,
            games=["paper", "mtgo"],
        ),
        # Single-color red instant (similar name)
        CardModel(
            id="strike-001",
            name="Lightning Strike",
            oracle_id="oracle-strike",
            mana_cost="{1}{R}",
            cmc=2.0,
            type_line="Instant",
            oracle_text="Lightning Strike deals 3 damage to any target.",
            rarity="common",
            set_code="M15",
            set_name="Magic 2015",
            collector_number="155",
            colors=["R"],
            color_identity=["R"],
            color_indicator=None,
            keywords=None,
            legalities={"standard": "not_legal", "modern": "legal", "legacy": "legal"},
            card_faces=None,
            games=["paper", "mtgo"],
        ),
        # Single-color red sorcery
        CardModel(
            id="chain-001",
            name="Chain Lightning",
            oracle_id="oracle-chain",
            mana_cost="{R}",
            cmc=1.0,
            type_line="Sorcery",
            oracle_text=(
                "Chain Lightning deals 3 damage to any target. "
                "Then that player or that permanent's controller may pay {R}{R}."
            ),
            rarity="uncommon",
            set_code="LEG",
            set_name="Legends",
            collector_number="137",
            colors=["R"],
            color_identity=["R"],
            color_indicator=None,
            keywords=None,
            legalities={"standard": "not_legal", "modern": "not_legal", "legacy": "legal"},
            card_faces=None,
            games=["paper", "mtgo"],
        ),
        # Single-color blue instant
        CardModel(
            id="counter-001",
            name="Counterspell",
            oracle_id="oracle-counter",
            mana_cost="{U}{U}",
            cmc=2.0,
            type_line="Instant",
            oracle_text="Counter target spell.",
            rarity="common",
            set_code="LEA",
            set_name="Limited Edition Alpha",
            collector_number="055",
            colors=["U"],
            color_identity=["U"],
            color_indicator=None,
            keywords=None,
            legalities={"standard": "not_legal", "modern": "not_legal", "legacy": "legal"},
            card_faces=None,
            games=["paper", "mtgo"],
        ),
        # Single-color green creature
        CardModel(
            id="elf-001",
            name="Llanowar Elves",
            oracle_id="oracle-elf",
            mana_cost="{G}",
            cmc=1.0,
            type_line="Creature — Elf Druid",
            oracle_text="{T}: Add {G}.",
            rarity="common",
            set_code="LEA",
            set_name="Limited Edition Alpha",
            collector_number="197",
            colors=["G"],
            color_identity=["G"],
            color_indicator=None,
            keywords=None,
            legalities={"standard": "not_legal", "modern": "legal", "legacy": "legal"},
            card_faces=None,
            games=["paper", "mtgo"],
        ),
        # Multi-color creature (Red/Blue)
        CardModel(
            id="dragon-001",
            name="Niv-Mizzet, Parun",
            oracle_id="oracle-niv",
            mana_cost="{U}{U}{U}{R}{R}{R}",
            cmc=6.0,
            type_line="Legendary Creature — Dragon Wizard",
            oracle_text=(
                "Flying. Whenever you draw a card, Niv-Mizzet, Parun deals 1 damage to any target."
            ),
            rarity="rare",
            set_code="GRN",
            set_name="Guilds of Ravnica",
            collector_number="192",
            colors=["U", "R"],
            color_identity=["U", "R"],
            color_indicator=None,
            keywords=["Flying"],
            legalities={"standard": "not_legal", "modern": "legal", "legacy": "legal"},
            card_faces=None,
            games=["paper", "mtgo"],
        ),
        # Colorless artifact
        CardModel(
            id="sol-ring-001",
            name="Sol Ring",
            oracle_id="oracle-sol",
            mana_cost="{1}",
            cmc=1.0,
            type_line="Artifact",
            oracle_text="{T}: Add {C}{C}.",
            rarity="uncommon",
            set_code="LEA",
            set_name="Limited Edition Alpha",
            collector_number="265",
            colors=[],
            color_identity=[],
            color_indicator=None,
            keywords=None,
            legalities={"standard": "not_legal", "modern": "not_legal", "legacy": "legal"},
            card_faces=None,
            games=["paper", "mtgo"],
        ),
        # Legendary instant
        CardModel(
            id="fire-001",
            name="Lightning Helix",
            oracle_id="oracle-helix",
            mana_cost="{R}{W}",
            cmc=2.0,
            type_line="Instant",
            oracle_text=("Lightning Helix deals 3 damage to any target and you gain 3 life."),
            rarity="uncommon",
            set_code="RAV",
            set_name="Ravnica: City of Guilds",
            collector_number="261",
            colors=["R", "W"],
            color_identity=["R", "W"],
            color_indicator=None,
            keywords=None,
            legalities={"standard": "not_legal", "modern": "legal", "legacy": "legal"},
            card_faces=None,
            games=["paper", "mtgo"],
        ),
        # Creature with Dragon subtype
        CardModel(
            id="dragon-002",
            name="Shivan Dragon",
            oracle_id="oracle-shivan",
            mana_cost="{4}{R}{R}",
            cmc=6.0,
            type_line="Creature — Dragon",
            oracle_text="Flying. {R}: Shivan Dragon gets +1/+0 until end of turn.",
            rarity="rare",
            set_code="LEA",
            set_name="Limited Edition Alpha",
            collector_number="175",
            colors=["R"],
            color_identity=["R"],
            color_indicator=None,
            keywords=["Flying"],
            legalities={"standard": "not_legal", "modern": "legal", "legacy": "legal"},
            card_faces=None,
            games=["paper", "mtgo"],
        ),
        # Low-cost red creature with haste
        CardModel(
            id="goblin-001",
            name="Goblin Guide",
            oracle_id="oracle-goblin-guide",
            mana_cost="{R}",
            cmc=1.0,
            type_line="Creature — Goblin Scout",
            oracle_text=(
                "Haste. Whenever Goblin Guide attacks, defending player reveals "
                "the top card of their library."
            ),
            rarity="rare",
            set_code="ZEN",
            set_name="Zendikar",
            collector_number="126",
            colors=["R"],
            color_identity=["R"],
            color_indicator=None,
            keywords=["Haste"],
            legalities={"standard": "not_legal", "modern": "legal", "legacy": "legal"},
            card_faces=None,
            games=["paper", "mtgo"],
        ),
        # Another creature with haste
        CardModel(
            id="swiftspear-001",
            name="Monastery Swiftspear",
            oracle_id="oracle-swiftspear",
            mana_cost="{R}",
            cmc=1.0,
            type_line="Creature — Human Monk",
            oracle_text="Haste. Prowess",
            rarity="uncommon",
            set_code="KTK",
            set_name="Khans of Tarkir",
            collector_number="118",
            colors=["R"],
            color_identity=["R"],
            color_indicator=None,
            keywords=["Haste", "Prowess"],
            legalities={"standard": "not_legal", "modern": "legal", "legacy": "legal"},
            card_faces=None,
            games=["paper", "mtgo"],
        ),
        # Mid-cost creature with different keyword
        CardModel(
            id="angel-001",
            name="Serra Angel",
            oracle_id="oracle-serra",
            mana_cost="{3}{W}{W}",
            cmc=5.0,
            type_line="Creature — Angel",
            oracle_text="Flying, vigilance",
            rarity="uncommon",
            set_code="LEA",
            set_name="Limited Edition Alpha",
            collector_number="38",
            colors=["W"],
            color_identity=["W"],
            color_indicator=None,
            keywords=["Flying", "Vigilance"],
            legalities={"standard": "not_legal", "modern": "legal", "legacy": "legal"},
            card_faces=None,
            games=["paper", "mtgo"],
        ),
    ]


def create_color_mode_test_cards() -> list[CardModel]:
    """Create cards for testing color mode filtering.

    Returns:
        List of CardModel instances with various color combinations:
        - Colorless cards
        - Mono-colored cards (W, U, B, R, G)
        - Two-color cards (W/U, R/W, U/R)
        - Three-color cards (W/U/B)
    """
    return [
        # Colorless artifact
        CardModel(
            id="colorless-001",
            name="Worn Powerstone",
            oracle_id="oracle-powerstone",
            mana_cost="{3}",
            cmc=3.0,
            type_line="Artifact",
            oracle_text="{T}: Add {C}{C}.",
            rarity="uncommon",
            set_code="C17",
            set_name="Commander 2017",
            collector_number="225",
            colors=[],
            color_identity=[],
            color_indicator=None,
            keywords=None,
            legalities={"standard": "not_legal", "modern": "legal", "legacy": "legal"},
            card_faces=None,
            games=["paper", "mtgo"],
        ),
        # Mono-white
        CardModel(
            id="mono-w-001",
            name="Path to Exile",
            oracle_id="oracle-path",
            mana_cost="{W}",
            cmc=1.0,
            type_line="Instant",
            oracle_text=(
                "Exile target creature. Its controller may search their library for "
                "a basic land card."
            ),
            rarity="uncommon",
            set_code="CON",
            set_name="Conflux",
            collector_number="014",
            colors=["W"],
            color_identity=["W"],
            color_indicator=None,
            keywords=None,
            legalities={"standard": "not_legal", "modern": "legal", "legacy": "legal"},
            card_faces=None,
            games=["paper", "mtgo"],
        ),
        # Mono-blue
        CardModel(
            id="mono-u-001",
            name="Opt",
            oracle_id="oracle-opt",
            mana_cost="{U}",
            cmc=1.0,
            type_line="Instant",
            oracle_text="Scry 1. Draw a card.",
            rarity="common",
            set_code="XLN",
            set_name="Ixalan",
            collector_number="065",
            colors=["U"],
            color_identity=["U"],
            color_indicator=None,
            keywords=None,
            legalities={"standard": "not_legal", "modern": "legal", "legacy": "legal"},
            card_faces=None,
            games=["paper", "mtgo"],
        ),
        # White-blue (Azorius)
        CardModel(
            id="wu-001",
            name="Supreme Verdict",
            oracle_id="oracle-verdict",
            mana_cost="{1}{W}{W}{U}",
            cmc=4.0,
            type_line="Sorcery",
            oracle_text="This spell can't be countered. Destroy all creatures.",
            rarity="rare",
            set_code="RTR",
            set_name="Return to Ravnica",
            collector_number="201",
            colors=["W", "U"],
            color_identity=["W", "U"],
            color_indicator=None,
            keywords=None,
            legalities={"standard": "not_legal", "modern": "legal", "legacy": "legal"},
            card_faces=None,
            games=["paper", "mtgo"],
        ),
        # Red-white (Boros)
        CardModel(
            id="rw-001",
            name="Boros Charm",
            oracle_id="oracle-boros-charm",
            mana_cost="{R}{W}",
            cmc=2.0,
            type_line="Instant",
            oracle_text=(
                "Choose one: Deal 4 damage to target player; or permanents you control "
                "gain indestructible."
            ),
            rarity="uncommon",
            set_code="GTC",
            set_name="Gatecrash",
            collector_number="148",
            colors=["R", "W"],
            color_identity=["R", "W"],
            color_indicator=None,
            keywords=None,
            legalities={"standard": "not_legal", "modern": "legal", "legacy": "legal"},
            card_faces=None,
            games=["paper", "mtgo"],
        ),
        # Blue-red (Izzet)
        CardModel(
            id="ur-001",
            name="Electrolyze",
            oracle_id="oracle-electrolyze",
            mana_cost="{1}{U}{R}",
            cmc=3.0,
            type_line="Instant",
            oracle_text="Electrolyze deals 2 damage divided as you choose. Draw a card.",
            rarity="uncommon",
            set_code="GPT",
            set_name="Guildpact",
            collector_number="121",
            colors=["U", "R"],
            color_identity=["U", "R"],
            color_indicator=None,
            keywords=None,
            legalities={"standard": "not_legal", "modern": "legal", "legacy": "legal"},
            card_faces=None,
            games=["paper", "mtgo"],
        ),
        # Three-color (Esper - W/U/B)
        CardModel(
            id="wub-001",
            name="Esper Charm",
            oracle_id="oracle-esper-charm",
            mana_cost="{W}{U}{B}",
            cmc=3.0,
            type_line="Instant",
            oracle_text=(
                "Choose one: Destroy target enchantment; or draw two cards; or target "
                "player discards two cards."
            ),
            rarity="uncommon",
            set_code="ALA",
            set_name="Shards of Alara",
            collector_number="167",
            colors=["W", "U", "B"],
            color_identity=["W", "U", "B"],
            color_indicator=None,
            keywords=None,
            legalities={"standard": "not_legal", "modern": "legal", "legacy": "legal"},
            card_faces=None,
            games=["paper", "mtgo"],
        ),
        # Another mono-red for testing
        CardModel(
            id="mono-r-001",
            name="Shock",
            oracle_id="oracle-shock",
            mana_cost="{R}",
            cmc=1.0,
            type_line="Instant",
            oracle_text="Shock deals 2 damage to any target.",
            rarity="common",
            set_code="M19",
            set_name="Core Set 2019",
            collector_number="156",
            colors=["R"],
            color_identity=["R"],
            color_indicator=None,
            keywords=None,
            legalities={"standard": "not_legal", "modern": "legal", "legacy": "legal"},
            card_faces=None,
            games=["paper", "mtgo"],
        ),
    ]


def create_multiface_card() -> CardModel:
    """Create a sample multi-face (Transform) card for testing.

    Returns:
        CardModel with card_faces data for a double-faced card
    """
    return CardModel(
        id="delver-001",
        name="Delver of Secrets",
        oracle_id="oracle-delver",
        mana_cost="{U}",
        cmc=1.0,
        type_line="Creature — Human Wizard // Creature — Human Insect",
        oracle_text=(
            "At the beginning of your upkeep, look at the top card of your library. "
            "You may reveal that card. If an instant or sorcery card is revealed "
            "this way, transform Delver of Secrets."
        ),
        rarity="common",
        set_code="ISD",
        set_name="Innistrad",
        collector_number="51",
        colors=["U"],
        color_identity=["U"],
        color_indicator=None,
        keywords=["Flying"],
        legalities={"standard": "not_legal", "modern": "legal", "legacy": "legal"},
        card_faces=[
            {
                "name": "Delver of Secrets",
                "mana_cost": "{U}",
                "type_line": "Creature — Human Wizard",
                "oracle_text": (
                    "At the beginning of your upkeep, look at the top card of your "
                    "library. You may reveal that card. If an instant or sorcery card "
                    "is revealed this way, transform Delver of Secrets."
                ),
                "colors": ["U"],
                "power": "1",
                "toughness": "1",
            },
            {
                "name": "Insectile Aberration",
                "mana_cost": "",
                "type_line": "Creature — Human Insect",
                "oracle_text": "Flying",
                "colors": ["U"],
                "power": "3",
                "toughness": "2",
            },
        ],
        games=["paper", "mtgo"],
    )


def create_om1_spm_cards() -> list[CardModel]:
    """Create sample OM1/SPM card pairs for testing games filtering with same Oracle ID.

    Simulates the scenario described in SPIDER_MAN_INVESTIGATION.md where:
    - SPM (Marvel's Spider-Man) cards are paper-only
    - OM1 (Through the Omenpaths) cards are digital-only (Arena/MTGO)
    - Both printings share the SAME Oracle ID and oracle name
    - OM1 cards may have different printed names (Universes Within)

    Returns:
        List of CardModel instances representing SPM and OM1 printings
    """
    # Shared Oracle ID for both printings
    shared_oracle_id = "b5b43d01-fce6-4a00-9c19-7a7e2a09d833"

    return [
        # SPM version - Paper only
        CardModel(
            id="spm-276",
            name="Ultimate Green Goblin",
            oracle_id=shared_oracle_id,
            mana_cost="{4}{R}{G}",
            cmc=6.0,
            type_line="Legendary Creature — Goblin Villain",
            oracle_text=(
                "Trample, haste. Whenever Ultimate Green Goblin attacks, "
                "it deals damage equal to its power to target creature defending player controls."
            ),
            rarity="rare",
            set_code="SPM",
            set_name="Marvel's Spider-Man",
            collector_number="276",
            colors=["R", "G"],
            color_identity=["R", "G"],
            color_indicator=None,
            keywords=["Trample", "Haste"],
            legalities={"standard": "not_legal", "modern": "legal", "legacy": "legal"},
            card_faces=None,
            games=["paper"],  # Paper only
        ),
        # OM1 version - Digital only (Arena/MTGO)
        CardModel(
            id="om1-153",
            name="Ultimate Green Goblin",  # Same oracle name
            oracle_id=shared_oracle_id,  # Same Oracle ID
            mana_cost="{4}{R}{G}",
            cmc=6.0,
            type_line="Legendary Creature — Goblin Villain",
            oracle_text=(
                "Trample, haste. Whenever Ultimate Green Goblin attacks, "
                "it deals damage equal to its power to target creature defending player controls."
            ),
            rarity="rare",
            set_code="OM1",
            set_name="Through the Omenpaths",
            collector_number="153",
            colors=["R", "G"],
            color_identity=["R", "G"],
            color_indicator=None,
            keywords=["Trample", "Haste"],
            legalities={"standard": "not_legal", "modern": "legal", "legacy": "legal"},
            card_faces=None,
            games=["arena", "mtgo"],  # Digital only
        ),
        # Add another example pair for thoroughness
        # SPM version
        CardModel(
            id="spm-123",
            name="Doctor Octopus",
            oracle_id="a1b2c3d4-e5f6-4a5b-9c8d-7e6f5a4b3c2d",
            mana_cost="{3}{U}{B}",
            cmc=5.0,
            type_line="Legendary Creature — Human Villain",
            oracle_text="When Doctor Octopus enters the battlefield, draw two cards.",
            rarity="mythic",
            set_code="SPM",
            set_name="Marvel's Spider-Man",
            collector_number="123",
            colors=["U", "B"],
            color_identity=["U", "B"],
            color_indicator=None,
            keywords=None,
            legalities={"standard": "not_legal", "modern": "legal", "legacy": "legal"},
            card_faces=None,
            games=["paper"],  # Paper only
        ),
        # OM1 version
        CardModel(
            id="om1-089",
            name="Doctor Octopus",
            oracle_id="a1b2c3d4-e5f6-4a5b-9c8d-7e6f5a4b3c2d",
            mana_cost="{3}{U}{B}",
            cmc=5.0,
            type_line="Legendary Creature — Human Villain",
            oracle_text="When Doctor Octopus enters the battlefield, draw two cards.",
            rarity="mythic",
            set_code="OM1",
            set_name="Through the Omenpaths",
            collector_number="089",
            colors=["U", "B"],
            color_identity=["U", "B"],
            color_indicator=None,
            keywords=None,
            legalities={"standard": "not_legal", "modern": "legal", "legacy": "legal"},
            card_faces=None,
            games=["arena", "mtgo"],  # Digital only
        ),
    ]
