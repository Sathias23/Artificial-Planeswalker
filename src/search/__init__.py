"""Semantic card search package (sqlite-vec + fastembed).

Phase-1 provides the synchronous :class:`ConnectionFactory` (sqlite-vec load + WAL +
per-thread connections, Story 1.2), the :class:`Embedder` port (process-lifetime
fastembed singleton + persistent cache, Story 2.1), and the ``card_vec`` ``vec0`` schema
(:func:`create_card_vec_table` / :func:`drop_card_vec_table`, Story 2.2). The index
builder and search tools land in the remaining Epic 2 stories.
"""

from src.search.connection import ConnectionFactory
from src.search.embedder import EMBEDDING_DIM, Embedder, get_embedder
from src.search.schema import CARD_VEC_TABLE, create_card_vec_table, drop_card_vec_table

__all__ = [
    "CARD_VEC_TABLE",
    "EMBEDDING_DIM",
    "ConnectionFactory",
    "Embedder",
    "create_card_vec_table",
    "drop_card_vec_table",
    "get_embedder",
]
