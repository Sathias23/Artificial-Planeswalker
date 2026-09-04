"""Semantic card search package (sqlite-vec + fastembed).

Provides the synchronous :class:`ConnectionFactory` (sqlite-vec load + WAL +
per-thread connections), the :class:`Embedder` port (process-lifetime
fastembed singleton + persistent cache), the ``card_vec`` ``vec0`` schema
(:func:`create_card_vec_table` / :func:`drop_card_vec_table`), the index
builder (:func:`build_card_embeddings` + its ``card_embedding_meta`` companion-hash table)
that populates the vectors + filterable metadata and tracks per-card content
hashes for idempotent, incremental re-builds, the reusable hybrid query path
(:func:`hybrid_search` returning :class:`CardHit` rows — KNN + metadata pre-filter + JOIN
post-filter + oracle de-dup) that the semantic-search tools consume, and the
seed-vector read-back (:func:`get_card_vector` — a primary-key point lookup that deserializes a
stored embedding) that lets ``find_similar_cards`` seed :func:`hybrid_search` from a
card it already has (no re-embed).
"""

from src.search.connection import ConnectionFactory
from src.search.embedder import EMBEDDING_DIM, Embedder, get_embedder
from src.search.index_builder import (
    BuildStatistics,
    build_card_embeddings,
    compose_card_text,
    content_hash,
    strip_reminder_text,
)
from src.search.query import CardHit, get_card_vector, hybrid_search
from src.search.schema import (
    CARD_EMBEDDING_META_TABLE,
    CARD_VEC_TABLE,
    clear_card_embedding_meta,
    create_card_embedding_meta_table,
    create_card_vec_table,
    drop_card_vec_table,
)

__all__ = [
    "CARD_EMBEDDING_META_TABLE",
    "CARD_VEC_TABLE",
    "EMBEDDING_DIM",
    "BuildStatistics",
    "CardHit",
    "ConnectionFactory",
    "Embedder",
    "build_card_embeddings",
    "clear_card_embedding_meta",
    "compose_card_text",
    "content_hash",
    "create_card_embedding_meta_table",
    "create_card_vec_table",
    "drop_card_vec_table",
    "get_card_vector",
    "get_embedder",
    "hybrid_search",
    "strip_reminder_text",
]
