"""Offline well-formedness guard for the Story 5.1 calibration benchmark set (AC7).

The analogue of ``test_rag_eval.py``'s offline pure-logic guard
(``test_evaluate_hit_rate_and_failure_message``): with **no scorer, no DB, no model, and no
integration marker**, it proves the committed benchmark is well-formed — every file parses,
per-format counts sit in a documented range, field domains hold, the AC3 membership minimums are
met, and :func:`load_benchmark` is deterministic. It runs in the fast subset under
``uv run pytest -m "not integration"``.

Per the Epic-4 retro lesson (NFR5: the Game Changers list and decklists change over time), this
guard is **verify-by-shape, not by hardcoded card names** — it asserts counts, ranges, and domains,
never "card X is in deck Y". Failures name the offending entry so a break points at the bad data.
"""

from __future__ import annotations

from tests.fixtures.benchmark_decks import (
    TIER_LABELS,
    BenchmarkEntry,
    load_benchmark,
    parse_arena_decklist,
)

# --- Documented count ranges (the AC7 "documented range" constants) -------------------------
# Commander decks are exactly-100 singleton lists (99 + commander[s]); the small tolerance leaves
# room for an NFR5 refresh (a swapped card, a partner pair) without a brittle exact-100 assert.
COMMANDER_MAINBOARD_RANGE: tuple[int, int] = (98, 102)
#: A Commander deck has one commander, or two for a partner/background pair (e.g. Tymna + Thrasios).
COMMANDER_COUNT_RANGE: tuple[int, int] = (1, 2)
#: Constructed Standard minimum is 60; the ceiling allows a slightly-larger meta list on refresh.
STANDARD_MAINBOARD_RANGE: tuple[int, int] = (60, 62)

#: cEDH lists floor at Bracket 4 and are flagged candidates — never assert Bracket 5 (AD-7/FR18).
CEDH_BRACKET: int = 4

# AC3 membership minimums across the format fork.
MIN_PRECONS = 3  # WotC Commander precons at the Bracket-2 floor
MIN_CEDH = 2  # known cEDH lists (Bracket-4 floor, candidate)
MIN_STANDARD = 1  # Standard deck for the heuristic-only fork (FR20)


def _mainboard_total(entry: BenchmarkEntry) -> int:
    return sum(card.quantity for card in entry.cards)


def _commanders(entry: BenchmarkEntry) -> list[str]:
    return [card.name for card in entry.cards if card.is_commander]


def _in_range(value: int, bounds: tuple[int, int]) -> bool:
    lo, hi = bounds
    return lo <= value <= hi


def test_every_decklist_file_exists_and_parses() -> None:
    """AC1/AC5: every entry's committed file loads and yields a non-empty parsed mainboard."""
    entries = load_benchmark()
    assert entries, "load_benchmark() returned no entries"
    for entry in entries:
        assert entry.cards, (
            f"{entry.key}: {entry.decklist_file} parsed to zero mainboard cards "
            "(missing file, empty Deck section, or unparsable lines?)"
        )


def test_keys_are_unique() -> None:
    """AC7: entry keys are unique (they double as decklist filenames)."""
    keys = [entry.key for entry in load_benchmark()]
    dupes = sorted({k for k in keys if keys.count(k) > 1})
    assert not dupes, f"duplicate benchmark keys: {dupes}"


def test_expected_bracket_domain() -> None:
    """AC7: every expected_bracket is None or in 1..5."""
    for entry in load_benchmark():
        bracket = entry.expected_bracket
        assert bracket is None or bracket in range(1, 6), (
            f"{entry.key}: expected_bracket {bracket!r} is not None or in 1..5"
        )


def test_tier_labels_in_vocabulary() -> None:
    """AC2/AC7: every expected_tier_label is in the allowed FR24 vocabulary."""
    for entry in load_benchmark():
        assert entry.expected_tier_label in TIER_LABELS, (
            f"{entry.key}: tier label {entry.expected_tier_label!r} not in {sorted(TIER_LABELS)}"
        )


def test_commander_entries_shape() -> None:
    """AC7: Commander entries have 1-2 commanders and a mainboard in the documented range."""
    commander_entries = [e for e in load_benchmark() if e.format == "commander"]
    assert commander_entries, "no Commander entries found"
    for entry in commander_entries:
        commanders = _commanders(entry)
        assert _in_range(len(commanders), COMMANDER_COUNT_RANGE), (
            f"{entry.key}: {len(commanders)} commander-section card(s), "
            f"expected {COMMANDER_COUNT_RANGE} — commanders: {commanders}"
        )
        total = _mainboard_total(entry)
        assert _in_range(total, COMMANDER_MAINBOARD_RANGE), (
            f"{entry.key}: mainboard total {total} outside {COMMANDER_MAINBOARD_RANGE}"
        )
        assert entry.expected_bracket is not None, (
            f"{entry.key}: Commander entry must carry a Bracket (got None)"
        )


def test_standard_entries_shape() -> None:
    """AC7: Standard entries have ~60 mainboard cards, no Bracket, and no cEDH flag (FR20)."""
    standard_entries = [e for e in load_benchmark() if e.format == "standard"]
    assert standard_entries, "no Standard entries found"
    for entry in standard_entries:
        total = _mainboard_total(entry)
        assert _in_range(total, STANDARD_MAINBOARD_RANGE), (
            f"{entry.key}: Standard mainboard total {total} outside {STANDARD_MAINBOARD_RANGE}"
        )
        assert entry.expected_bracket is None, (
            f"{entry.key}: Standard entry must have expected_bracket None (got "
            f"{entry.expected_bracket!r})"
        )
        assert entry.expected_cedh_candidate is False, (
            f"{entry.key}: Standard entry must not be a cEDH candidate"
        )
        assert not _commanders(entry), f"{entry.key}: Standard entry must have no Commander section"


def test_cedh_entries_invariants() -> None:
    """AC3/AC7: every cEDH-candidate entry floors at Bracket 4 (never 5)."""
    cedh_entries = [e for e in load_benchmark() if e.expected_cedh_candidate]
    assert cedh_entries, "no cEDH-candidate entries found"
    for entry in cedh_entries:
        assert entry.expected_bracket == CEDH_BRACKET, (
            f"{entry.key}: cEDH candidate must be Bracket {CEDH_BRACKET} "
            f"(got {entry.expected_bracket!r}) — never assert Bracket 5"
        )


def test_membership_minimums() -> None:
    """AC3: the set covers the required anchors across both format forks."""
    entries = load_benchmark()
    precons = [e for e in entries if e.format == "commander" and e.expected_bracket == 2]
    cedh = [e for e in entries if e.expected_cedh_candidate]
    standard = [e for e in entries if e.format == "standard"]

    assert len(precons) >= MIN_PRECONS, f"need >= {MIN_PRECONS} precons, found {len(precons)}"
    assert len(cedh) >= MIN_CEDH, f"need >= {MIN_CEDH} cEDH lists, found {len(cedh)}"
    assert len(standard) >= MIN_STANDARD, (
        f"need >= {MIN_STANDARD} Standard deck(s), found {len(standard)}"
    )


def test_no_duplicate_card_names_within_entry() -> None:
    """AC3/AC6: no card name appears on more than one line within a single entry.

    A real Commander singleton decklist can't include a card twice (the commander included) —
    a duplicate is a shape signal that the entry doesn't reflect a legal, real decklist. Standard
    entries also record one line per card (quantity carries the copy count), so the same check
    applies to both formats.
    """
    for entry in load_benchmark():
        names = [card.name for card in entry.cards]
        dupes = sorted({name for name in names if names.count(name) > 1})
        assert not dupes, f"{entry.key}: duplicate card name(s) within entry: {dupes}"


def test_load_benchmark_is_deterministic() -> None:
    """AC5: two calls return equal entries in the same order."""
    first = load_benchmark()
    second = load_benchmark()
    assert first == second
    assert [e.key for e in first] == [e.key for e in second]


def test_parse_arena_decklist_sections_and_metadata() -> None:
    """AC5: the pure parser flags commanders, skips About metadata + Sideboard/Companion, and

    tolerates blank / unparsable lines — proven offline on a hand-written export.
    """
    text = "\n".join(
        [
            "About",
            "Name My Test Deck",  # metadata — skipped
            "",
            "Commander",
            "1 Tymna the Weaver (CMR) 1",
            "1 Thrasios, Triton Hero (CMR) 2",
            "",
            "Deck",
            "1 Sol Ring (C21) 263",
            "not a card line",  # tolerated / skipped
            "10 Island (UNF) 100",
            "",
            "Sideboard",
            "1 Pyroblast (EMA) 130",  # skipped — not mainboard
            "Companion",
            "1 Jegantha, the Wellspring (IKO) 222",  # skipped
        ]
    )
    cards = parse_arena_decklist(text)
    names = [c.name for c in cards]

    assert names == ["Tymna the Weaver", "Thrasios, Triton Hero", "Sol Ring", "Island"]
    assert [c.is_commander for c in cards] == [True, True, False, False]
    assert cards[-1].quantity == 10
    # About metadata, the unparsable line, and Sideboard/Companion never leak into the mainboard.
    assert "Pyroblast" not in names
    assert "Jegantha, the Wellspring" not in names
    assert "My Test Deck" not in names
