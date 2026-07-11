"""Calibration benchmark set for the deterministic scoring core (Story 5.1 / feature 2.1).

A committed, held-out set of decklists with documented *categorical* expected outcomes — the
acceptance gate for Epic 5 (NFR6, Success Metric 1). Story 5.9 ("Pure ``score()`` entry point +
benchmark validation") resolves each entry's card *names* against the local Scryfall snapshot and
asserts the finished scorer against these expectations.

This module is **data + a pure offline loader only**. It deliberately contains **no scorer, no
scoring math, and no dependency on ``src/logic/assessment/``** (which does not exist yet). The raw
Arena-format decklists live one-per-entry under ``benchmark/``; :func:`load_benchmark` parses them
with a small self-contained parser (no DB, no network, no ``import_decklist``).

Expected outcomes are **categorical/directional, never an exact numeric score** (AC4): WotC frames
Brackets as intent-based and "not an exact science," and NFR5 warns the Game Changers list / metas
shift — so the set anchors the **Bracket**, the **cEDH-candidate boolean**, and a **descriptive tier
label** only. The *asserting* story (5.9) owns the tolerance ("bracket up when in doubt": accept a
precon floor within ``[expected, expected + 1]``; accept any cEDH floor ``>= 4``, never assert
Bracket 5, AD-7); the data here stays a single clean target.

Import convention (matches ``tests/fixtures/card_data.py``)::

    from tests.fixtures.benchmark_decks import load_benchmark
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Literal

#: Format fork (FR20). Commander decks carry a Bracket; Standard has none (``expected_bracket`` is
#: ``None``) and rides the heuristic-only fork Story 5.9 validates.
type BenchmarkFormat = Literal["commander", "standard"]

#: Allowed tier-label vocabulary — the FR24 / deck-assess "Option F" words. Story 5.8/5.9's
#: ``FormatProfile`` owns the *authoritative* label->threshold mapping; this vocabulary must stay
#: consistent with that module when it lands. Recorded here as the expected *human* label per entry.
TIER_LABELS: frozenset[str] = frozenset(
    {"Unfocused", "Focused", "Tuned", "High-Power", "Competitive"}
)

#: Directory holding one raw Arena-format decklist (``<key>.txt``) per benchmark entry.
_BENCHMARK_DIR = Path(__file__).parent / "benchmark"

# Arena section headers (case-insensitive), mirroring ``deck_import.py:24-33``. ``Commander`` +
# ``Deck`` form the mainboard; ``Sideboard`` / ``Companion`` are tolerated and skipped. The optional
# ``About`` metadata block (``Name <deck name>`` lines) is skipped until the next real section.
_COMMANDER_SECTION = "commander"
_MAINBOARD_SECTIONS: frozenset[str] = frozenset({"commander", "deck"})
_SKIPPED_SECTIONS: frozenset[str] = frozenset({"sideboard", "companion"})
_SECTION_HEADERS: frozenset[str] = _MAINBOARD_SECTIONS | _SKIPPED_SECTIONS
_ABOUT_HEADER = "about"

# Card-line grammar, mirroring ``deck_import.py:37`` ``_CARD_LINE_RE``. ``1 Sol Ring (C21) 263`` is
# valid; a bare ``1 Sol Ring`` does not parse — the ``(SET) COLLECTOR`` suffix is required. The set
# and collector annotations are cosmetic for name resolution but keep the files valid Arena exports.
_CARD_LINE_RE = re.compile(
    r"^(?P<quantity>\d+)\s+(?P<name>.+)\s+"
    r"\((?P<set_code>[^()\s]+)\)\s+(?P<collector_number>\S+)$"
)


@dataclass(frozen=True, slots=True)
class BenchmarkCard:
    """One parsed mainboard card line from a benchmark decklist.

    Attributes:
        name: The exact oracle card name (verbatim from the Arena line), resolvable against the
            local Scryfall snapshot downstream.
        quantity: Number of copies on the line (>= 1; Commander entries are singleton, Standard
            entries may run up to 4).
        is_commander: ``True`` when the line sits under the ``Commander`` section header — the only
            commander signal, since the ``Deck`` schema has no commander field.
    """

    name: str
    quantity: int
    is_commander: bool


@dataclass(frozen=True, slots=True)
class BenchmarkEntry:
    """A single held-out decklist plus its documented, categorical expected outcome.

    Expected outcomes are categorical only (AC4) — never an exact numeric score or per-dimension
    number. ``cards`` is empty in the static manifest and populated by :func:`load_benchmark` from
    the committed ``decklist_file``.

    Attributes:
        key: Stable snake_case id (unique across the set); also the decklist filename stem.
        format: ``"commander"`` or ``"standard"`` (FR20).
        decklist_file: Filename of the committed raw Arena decklist under ``benchmark/``.
        cards: Parsed mainboard cards; ``()`` in the manifest, filled by :func:`load_benchmark`.
        expected_bracket: Commander Bracket ``1..5``; ``None`` for Standard (Standard has no
            Bracket, FR20). cEDH lists floor at ``4`` and never assert ``5`` (AD-7/FR18).
        expected_cedh_candidate: Whether the deck should flag as a cEDH candidate.
        expected_tier_label: A descriptive tier word from :data:`TIER_LABELS` (FR24).
        source: Provenance for auditability / refresh (precon or archetype name + date, NFR5).
        notes: One-line rationale for why this deck anchors this outcome.
    """

    key: str
    format: BenchmarkFormat
    decklist_file: str
    cards: tuple[BenchmarkCard, ...]
    expected_bracket: int | None
    expected_cedh_candidate: bool
    expected_tier_label: str
    source: str
    notes: str


def parse_arena_decklist(text: str) -> tuple[BenchmarkCard, ...]:
    """Parse Arena-export text into mainboard cards, in source order.

    A small, self-contained pure function (no DB, no network, no ``import_decklist``). It tracks the
    current section header, marks ``Commander``-section cards ``is_commander=True``, includes the
    ``Deck`` section as the rest of the mainboard, and skips the ``About`` metadata block plus any
    ``Sideboard`` / ``Companion`` sections. Lines that are neither a recognized header nor a valid
    card line are tolerated and skipped.

    Args:
        text: The full Arena-export decklist text.

    Returns:
        The mainboard cards (Commander + Deck sections) in the order they appear.
    """
    cards: list[BenchmarkCard] = []
    section: str | None = None
    in_metadata = False

    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue

        folded = stripped.casefold()
        if folded == _ABOUT_HEADER:
            section, in_metadata = None, True
            continue
        if folded in _SECTION_HEADERS:
            section, in_metadata = folded, False
            continue

        if in_metadata or section not in _MAINBOARD_SECTIONS:
            continue

        match = _CARD_LINE_RE.fullmatch(stripped)
        if match is None:
            continue
        cards.append(
            BenchmarkCard(
                name=match.group("name").strip(),
                quantity=int(match.group("quantity")),
                is_commander=section == _COMMANDER_SECTION,
            )
        )

    return tuple(cards)


def load_benchmark() -> tuple[BenchmarkEntry, ...]:
    """Load the benchmark set: each manifest entry with its decklist parsed and attached.

    Reads each entry's ``decklist_file`` from ``benchmark/`` (a ``Path(__file__)``-relative walk,
    the ``scryfall_sample.json`` loading precedent), parses it with :func:`parse_arena_decklist`,
    and returns the entries in a **deterministic, stable order** — the static manifest order, which
    is not sorted by anything nondeterministic.

    Returns:
        The benchmark entries in manifest order, each with ``cards`` populated.
    """
    return tuple(
        replace(
            entry,
            cards=parse_arena_decklist(
                (_BENCHMARK_DIR / entry.decklist_file).read_text(encoding="utf-8")
            ),
        )
        for entry in _MANIFEST
    )


def _entry(
    key: str,
    *,
    format: BenchmarkFormat,
    expected_bracket: int | None,
    expected_cedh_candidate: bool,
    expected_tier_label: str,
    source: str,
    notes: str,
) -> BenchmarkEntry:
    """Build a manifest ``BenchmarkEntry`` (``cards`` empty until :func:`load_benchmark`)."""
    return BenchmarkEntry(
        key=key,
        format=format,
        decklist_file=f"{key}.txt",
        cards=(),
        expected_bracket=expected_bracket,
        expected_cedh_candidate=expected_cedh_candidate,
        expected_tier_label=expected_tier_label,
        source=source,
        notes=notes,
    )


# The calibration anchor — a handful of entries (AC3), not a corpus: >= 3 WotC Commander precons
# (Bracket 2), >= 2 known cEDH lists (Bracket 4 floor, candidate), >= 1 Standard deck (no Bracket),
# plus one "upgraded" Commander deck (Bracket 3) as a middle anchor. Card names were transcribed
# from public lists and validated name-by-name against the local Scryfall snapshot on 2026-07-12
# (resolvable; see per-entry `notes` for any post-transcription corrections); verify-by-shape, not
# by hardcoded card names (NFR5, epic-4 retro).
_MANIFEST: tuple[BenchmarkEntry, ...] = (
    _entry(
        "precon_prosper_tome_bound",
        format="commander",
        expected_bracket=2,
        expected_cedh_candidate=False,
        expected_tier_label="Focused",
        source="Commander Legends: Battle for Baldur's Gate precon 'Exit from Exile' "
        "(Prosper, Tome-Bound), 2022 — representative Bracket-2 list; transcribed 2026-07-12.",
        notes="BR treasures/impulse precon-power goodstuff: rocks + removal, no fast mana beyond "
        "Sol Ring, no Game Changers or two-card combos — anchors the Bracket-2 floor.",
    ),
    _entry(
        "precon_talrand_sky_summoner",
        format="commander",
        expected_bracket=2,
        expected_cedh_candidate=False,
        expected_tier_label="Focused",
        source="Mono-U Talrand, Sky Summoner spellslinger (M13 commander), "
        "representative Bracket-2 draw-go list; transcribed 2026-07-12.",
        notes="Counters + card draw + drake payoffs, no GC (Rhystic Study / Cyclonic Rift / Mystic "
        "Remora deliberately excluded), no combo — a clean second Bracket-2 anchor in a new color.",
    ),
    _entry(
        "precon_wilhelt_rotcleaver",
        format="commander",
        expected_bracket=2,
        expected_cedh_candidate=False,
        expected_tier_label="Focused",
        source="Innistrad: Midnight Hunt precon 'Undead Unleashed' (Wilhelt, the Rotcleaver), "
        "2021 — representative Bracket-2 UB zombies list; transcribed 2026-07-12.",
        notes="Zombie tribal aggro/value at precon power; a third Bracket-2 anchor with a tribal "
        "shape distinct from the goodstuff/spellslinger precons.",
    ),
    _entry(
        "upgraded_atraxa_superfriends",
        format="commander",
        expected_bracket=3,
        expected_cedh_candidate=False,
        expected_tier_label="Tuned",
        source="Upgraded Atraxa, Praetors' Voice superfriends (Commander 2016 face card), "
        "tuned WUBG planeswalkers/+1+1 build; transcribed 2026-07-12.",
        notes="Middle anchor (Bracket 3): a 1-3 Game Changers-class build (Doubling Season, The "
        "Chain Veil, fetch/dual manabase, efficient interaction) above precon power, below cEDH.",
    ),
    _entry(
        "cedh_tymna_thrasios",
        format="commander",
        expected_bracket=4,
        expected_cedh_candidate=True,
        expected_tier_label="Competitive",
        source="cEDH archetype: Tymna the Weaver + Thrasios, Triton Hero '4c Blue Farm' partners "
        "(canonical WUBG interaction/consultation shell); transcribed 2026-07-12.",
        notes="Thassa's Oracle + Demonic Consultation / Tainted Pact wincon, full fast-mana + "
        "free-counter suite — floors at Bracket 4, flags cEDH candidate (never Bracket 5).",
    ),
    _entry(
        "cedh_kinnan_bonder_prodigy",
        format="commander",
        expected_bracket=4,
        expected_cedh_candidate=True,
        expected_tier_label="Competitive",
        source="cEDH archetype: Kinnan, Bonder Prodigy GU big-mana (Basalt Monolith engine + "
        "Thassa's Oracle finish); transcribed 2026-07-12.",
        notes="Second cEDH anchor in a two-color shell: fast mana + Kinnan doubling into a compact "
        "combo finish — Bracket-4 floor, cEDH candidate; distinct from the 4c partners list. "
        "(2026-07-12 code review: the initial transcription duplicated the commander into the "
        "mainboard — a real singleton decklist can't do that — swapped for Arcane Signet, a "
        "near-universal cEDH rock not otherwise in this list.)",
    ),
    _entry(
        "standard_mono_red_aggro",
        format="standard",
        expected_bracket=None,
        expected_cedh_candidate=False,
        expected_tier_label="Tuned",
        source="Standard Mono-Red Aggro (Foundations-era meta archetype), ~60-card constructed "
        "list with 15-card sideboard; transcribed 2026-07-12.",
        notes="Heuristic-only fork (FR20): no Bracket, no cEDH flag. Validates that Story 5.9's "
        "Standard path scores without the Commander Bracket machinery.",
    ),
)
