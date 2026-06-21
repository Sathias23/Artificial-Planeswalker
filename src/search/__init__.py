"""Semantic card search package (sqlite-vec + fastembed).

Phase-1 provides the synchronous :class:`ConnectionFactory` (sqlite-vec load + WAL +
per-thread connections, Story 1.2) and the :class:`Embedder` port (process-lifetime
fastembed singleton + persistent cache, Story 2.1). The ``card_vec`` schema, index
builder, and search tools land in the remaining Epic 2 stories.
"""

from src.search.connection import ConnectionFactory
from src.search.embedder import EMBEDDING_DIM, Embedder, get_embedder

__all__ = ["EMBEDDING_DIM", "ConnectionFactory", "Embedder", "get_embedder"]
