"""Semantic card search package (sqlite-vec + fastembed).

Phase-1 provides the synchronous :class:`ConnectionFactory` (sqlite-vec load + WAL +
per-thread connections). The embedder, ``card_vec`` schema, index builder, and search
tools land in Epic 2.
"""

from src.search.connection import ConnectionFactory

__all__ = ["ConnectionFactory"]
