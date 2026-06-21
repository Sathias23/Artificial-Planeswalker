"""Pydantic schema for paginated repository results."""

from pydantic import BaseModel, Field


class PaginatedResult[T](BaseModel):
    """A single page of results together with pagination metadata.

    Wraps an already-converted page of domain schemas (e.g. ``Card``) returned by
    repository query methods such as ``CardRepository.search_advanced``.

    Attributes:
        items: The items on the current page.
        total_count: Total number of matching items across all pages (>= 0).
        page: Current 1-based page number (>= 1).
        page_size: Maximum number of items per page (>= 1).
        total_pages: Total number of pages for the current query (>= 0; 0 when no matches).
    """

    items: list[T]
    total_count: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    total_pages: int = Field(ge=0)
