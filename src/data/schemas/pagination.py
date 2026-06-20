"""Pydantic schema for paginated repository results."""

from pydantic import BaseModel


class PaginatedResult[T](BaseModel):
    """A single page of results together with pagination metadata.

    Wraps an already-converted page of domain schemas (e.g. ``Card``) returned by
    repository query methods such as ``CardRepository.search_advanced``.

    Attributes:
        items: The items on the current page.
        total_count: Total number of matching items across all pages.
        page: Current 1-based page number.
        page_size: Maximum number of items per page.
        total_pages: Total number of pages for the current query.
    """

    items: list[T]
    total_count: int
    page: int
    page_size: int
    total_pages: int
