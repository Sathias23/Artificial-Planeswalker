"""Unit tests for the PaginatedResult schema's invariant validators."""

import pytest
from pydantic import ValidationError

from src.data.schemas.card import Card
from src.data.schemas.pagination import PaginatedResult


def _card() -> Card:
    return Card(
        id="card-1",
        name="Lightning Bolt",
        oracle_id="oracle-1",
        mana_cost="{R}",
        cmc=1.0,
        type_line="Instant",
        oracle_text="Deals 3 damage.",
        rarity="common",
        set_code="LEA",
        set_name="Alpha",
        collector_number="161",
        colors=["R"],
        color_identity=["R"],
        legalities={"standard": "legal"},
    )


def test_valid_paginated_result_constructs() -> None:
    """A well-formed page passes validation."""
    result: PaginatedResult[Card] = PaginatedResult(
        items=[_card()], total_count=1, page=1, page_size=20, total_pages=1
    )

    assert result.total_count == 1
    assert result.total_pages == 1


def test_empty_result_with_zero_total_pages_is_valid() -> None:
    """An empty search result (total_count=0, total_pages=0) must remain valid.

    search_advanced returns total_pages=0 when nothing matches; the validators must
    not break that contract.
    """
    result: PaginatedResult[Card] = PaginatedResult(
        items=[], total_count=0, page=1, page_size=20, total_pages=0
    )

    assert result.items == []
    assert result.total_count == 0
    assert result.total_pages == 0


@pytest.mark.parametrize("page", [0, -1])
def test_page_below_one_raises(page: int) -> None:
    """page is 1-based; values below 1 are invalid."""
    with pytest.raises(ValidationError):
        PaginatedResult(items=[], total_count=0, page=page, page_size=20, total_pages=0)


@pytest.mark.parametrize("page_size", [0, -5])
def test_page_size_below_one_raises(page_size: int) -> None:
    """page_size must be at least 1."""
    with pytest.raises(ValidationError):
        PaginatedResult(items=[], total_count=0, page=1, page_size=page_size, total_pages=0)


def test_negative_total_count_raises() -> None:
    """total_count is a non-negative count."""
    with pytest.raises(ValidationError):
        PaginatedResult(items=[], total_count=-1, page=1, page_size=20, total_pages=0)


def test_negative_total_pages_raises() -> None:
    """total_pages is a non-negative count."""
    with pytest.raises(ValidationError):
        PaginatedResult(items=[], total_count=0, page=1, page_size=20, total_pages=-1)
