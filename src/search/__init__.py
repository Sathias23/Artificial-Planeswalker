"""Semantic card search package (sqlite-vec + fastembed).

Phase-1 provides the synchronous :class:`ConnectionFactory` (sqlite-vec load + WAL +
per-thread connections, Story 1.2), the :class:`Embedder` port (process-lifetime
fastembed singleton + persistent cache, Story 2.1), the ``card_vec`` ``vec0`` schema
(:func:`create_card_vec_table` / :func:`drop_card_vec_table`, Story 2.2), the index
builder (:func:`build_card_embeddings` + its ``card_embedding_meta`` companion-hash table,
Story 2.3) that populates the vectors + filterable metadata and tracks per-card content
hashes for idempotent, incremental re-builds, and the reusable hybrid query path
(:func:`hybrid_search` returning :class:`CardHit` rows — KNN + metadata pre-filter + JOIN
post-filter + oracle de-dup, Story 2.4) that the semantic-search tools consume.
``find_similar_cards`` (Story 2.5, reusing :func:`hybrid_search` with a seed card's stored
vector) and the RAG sanity eval (Story 2.6) land in the remaining Epic 2 stories.
"""

from src.search.connection import ConnectionFactory
from src.search.embedder import EMBEDDING_DIM, Embedder, get_embedder
from src.search.index_builder import (
    BuildStatistics,
    build_card_embeddings,
    compose_card_text,
    content_hash,
)
from src.search.query import CardHit, hybrid_search
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
    "get_embedder",
    "hybrid_search",
]
