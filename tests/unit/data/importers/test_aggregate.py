"""Unit tests for the pass-1 oracle-identity aggregation (games union + canonical pick)."""

import json
from pathlib import Path

from src.data.importers.aggregate import build_oracle_aggregates, group_key, resolve_oracle_id


def test_resolve_oracle_id_precedence() -> None:
    """Top-level ``oracle_id`` wins; else the first face's; else ``None`` (not the printing id)."""
    assert resolve_oracle_id({"oracle_id": "top", "card_faces": [{"oracle_id": "face"}]}) == "top"
    assert resolve_oracle_id({"card_faces": [{"oracle_id": "face"}]}) == "face"
    assert resolve_oracle_id({"id": "printing-only"}) is None


def test_group_key_falls_back_to_id_but_resolve_does_not() -> None:
    """``group_key`` keeps its printing-``id`` self-group fallback for aggregation; the oracle-id
    resolver (used by the transformer) does not — a printing id is not an oracle identity."""
    card = {"id": "printing-only"}
    assert group_key(card) == "printing-only"
    assert resolve_oracle_id(card) is None


def _write_cards(tmp_path: Path, cards: list[dict]) -> Path:
    """Write a JSON array of raw card dicts and return the file path."""
    file_path = tmp_path / "bulk.json"
    file_path.write_text(json.dumps(cards), encoding="utf-8")
    return file_path


def _printing(
    card_id: str,
    oracle_id: str | None = "oid-1",
    *,
    released_at: str | None = "2024-01-01",
    games: list[str] | None = None,
    **extra,
) -> dict:
    """Build a minimal raw Scryfall printing dict."""
    card: dict = {"id": card_id, "name": "Test Card"}
    if oracle_id is not None:
        card["oracle_id"] = oracle_id
    if released_at is not None:
        card["released_at"] = released_at
    if games is not None:
        card["games"] = games
    card.update(extra)
    return card


class TestGroupKey:
    """group_key precedence: oracle_id -> card_faces[0].oracle_id -> own id."""

    def test_top_level_oracle_id_wins(self) -> None:
        card = {"id": "p1", "oracle_id": "oid-x", "card_faces": [{"oracle_id": "face-oid"}]}
        assert group_key(card) == "oid-x"

    def test_falls_back_to_first_face_oracle_id(self) -> None:
        card = {"id": "p1", "card_faces": [{"oracle_id": "face-oid"}, {"oracle_id": "other"}]}
        assert group_key(card) == "face-oid"

    def test_falls_back_to_own_id_when_no_oracle_id_anywhere(self) -> None:
        card = {"id": "p1", "card_faces": [{"name": "no oracle id here"}]}
        assert group_key(card) == "p1"

    def test_returns_none_when_no_usable_key(self) -> None:
        assert group_key({"name": "keyless"}) is None


class TestBuildOracleAggregates:
    """Streaming aggregation over a real tmp_path JSON file."""

    def test_unions_games_across_printings_of_same_oracle_id(self, tmp_path: Path) -> None:
        """Paper-only + arena/mtgo printings of one oracle id union to all three platforms."""
        file_path = _write_cards(
            tmp_path,
            [
                _printing("p-paper", released_at="2025-09-01", games=["paper"]),
                _printing("p-digital", released_at="2025-08-01", games=["arena", "mtgo"]),
            ],
        )

        aggregates = build_oracle_aggregates(file_path)

        assert set(aggregates) == {"oid-1"}
        assert aggregates["oid-1"].games == {"arena", "mtgo", "paper"}

    def test_canonical_is_max_released_at(self, tmp_path: Path) -> None:
        """The printing with the latest released_at is canonical, regardless of file order."""
        file_path = _write_cards(
            tmp_path,
            [
                _printing("p-old", released_at="2020-05-15", games=["paper"]),
                _printing("p-new", released_at="2025-09-01", games=["arena"]),
                _printing("p-mid", released_at="2023-01-01", games=["mtgo"]),
            ],
        )

        aggregates = build_oracle_aggregates(file_path)

        assert aggregates["oid-1"].canonical_id == "p-new"
        assert aggregates["oid-1"].canonical_released_at == "2025-09-01"
        assert aggregates["oid-1"].games == {"arena", "mtgo", "paper"}

    def test_canonical_tiebreak_is_min_id(self, tmp_path: Path) -> None:
        """Equal released_at ties break to the smallest id — deterministic across runs."""
        file_path = _write_cards(
            tmp_path,
            [
                _printing("p-bbb", released_at="2025-01-01"),
                _printing("p-aaa", released_at="2025-01-01"),
                _printing("p-ccc", released_at="2025-01-01"),
            ],
        )

        aggregates = build_oracle_aggregates(file_path)

        assert aggregates["oid-1"].canonical_id == "p-aaa"

    def test_missing_top_level_oracle_id_groups_by_first_face(self, tmp_path: Path) -> None:
        """Reversible/odd layouts group by card_faces[0].oracle_id."""
        file_path = _write_cards(
            tmp_path,
            [
                _printing(
                    "p-face-1",
                    oracle_id=None,
                    released_at="2024-01-01",
                    games=["paper"],
                    card_faces=[{"oracle_id": "face-oid"}],
                ),
                _printing(
                    "p-face-2",
                    oracle_id=None,
                    released_at="2025-01-01",
                    games=["arena"],
                    card_faces=[{"oracle_id": "face-oid"}],
                ),
            ],
        )

        aggregates = build_oracle_aggregates(file_path)

        assert set(aggregates) == {"face-oid"}
        assert aggregates["face-oid"].games == {"arena", "paper"}
        assert aggregates["face-oid"].canonical_id == "p-face-2"

    def test_no_oracle_id_at_all_self_groups_by_id(self, tmp_path: Path) -> None:
        """A card with no oracle id anywhere self-groups under its own id — never dropped."""
        file_path = _write_cards(
            tmp_path,
            [_printing("p-lonely", oracle_id=None, games=["paper"])],
        )

        aggregates = build_oracle_aggregates(file_path)

        assert set(aggregates) == {"p-lonely"}
        assert aggregates["p-lonely"].canonical_id == "p-lonely"
        assert aggregates["p-lonely"].games == {"paper"}

    def test_absent_and_null_games_treated_as_empty(self, tmp_path: Path) -> None:
        """Missing or explicit-null games contribute nothing to the union (and don't raise)."""
        file_path = _write_cards(
            tmp_path,
            [
                _printing("p-absent", released_at="2024-01-01"),  # no games key
                {
                    "id": "p-null",
                    "oracle_id": "oid-1",
                    "released_at": "2025-01-01",
                    "games": None,
                },
                _printing("p-arena", released_at="2023-01-01", games=["arena"]),
            ],
        )

        aggregates = build_oracle_aggregates(file_path)

        assert aggregates["oid-1"].games == {"arena"}
        assert aggregates["oid-1"].canonical_id == "p-null"  # latest released_at still wins

    def test_oracle_cards_style_input_is_a_no_op(self, tmp_path: Path) -> None:
        """One printing per oracle id (oracle_cards) — every card is its own canonical."""
        file_path = _write_cards(
            tmp_path,
            [
                _printing("p-1", oracle_id="oid-a", games=["paper", "arena"]),
                _printing("p-2", oracle_id="oid-b", games=["paper"]),
            ],
        )

        aggregates = build_oracle_aggregates(file_path)

        assert aggregates["oid-a"].canonical_id == "p-1"
        assert aggregates["oid-a"].games == {"arena", "paper"}
        assert aggregates["oid-b"].canonical_id == "p-2"
        assert aggregates["oid-b"].games == {"paper"}

    def test_empty_file_yields_empty_map(self, tmp_path: Path) -> None:
        file_path = _write_cards(tmp_path, [])

        assert build_oracle_aggregates(file_path) == {}
