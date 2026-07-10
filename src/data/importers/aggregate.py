"""Streaming per-oracle-identity aggregation of Scryfall printings (games union + canonical pick).

A ``default_cards`` bulk file carries every printing of every card, and any single printing's
``games`` list can mask real availability (a paper-only promo printing hides that the card is on
Arena). This module streams the bulk file once and reduces it to a small map:
``group key -> (union of games across printings, canonical printing id)``. The importer's second
pass keeps only each identity's canonical printing and overrides its ``games`` with the union, so
the database stores one row per oracle identity with true cross-printing availability. For a
single-printing-per-identity bulk set (``oracle_cards``) the aggregation is a natural no-op.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.data.importers.parser import stream_cards

logger = logging.getLogger(__name__)


@dataclass
class OracleAggregate:
    """Aggregate of every printing sharing one oracle identity.

    Attributes:
        games: Union of ``games`` values across all printings seen for this identity.
        canonical_id: Scryfall ``id`` of the printing chosen to represent the identity
            (max ``released_at``, ties broken by min ``id``).
        canonical_released_at: The canonical printing's ``released_at`` ISO date string
            (empty when the printing carries none — ISO dates compare correctly as strings).
    """

    games: set[str] = field(default_factory=set)
    canonical_id: str = ""
    canonical_released_at: str = ""


def group_key(card_json: dict[str, Any]) -> str | None:
    """Return the oracle-identity group key for a raw Scryfall card object.

    Precedence: top-level ``oracle_id``, else ``card_faces[0].oracle_id`` (reversible /
    odd layouts carry oracle ids per face), else the card's own ``id`` (self-group — a
    card is never dropped just because it lacks an oracle id).

    Args:
        card_json: A raw Scryfall card object from the bulk file.

    Returns:
        The group key, or ``None`` when the card has no usable key at all (no oracle id
        anywhere and no ``id``) — such cards bypass aggregation entirely.
    """
    oracle_id = card_json.get("oracle_id")
    if oracle_id:
        return str(oracle_id)
    faces = card_json.get("card_faces")
    if isinstance(faces, list) and faces:
        face = faces[0]
        if isinstance(face, dict) and face.get("oracle_id"):
            return str(face["oracle_id"])
    card_id = card_json.get("id")
    if card_id:
        return str(card_id)
    return None


def build_oracle_aggregates(file_path: Path) -> dict[str, OracleAggregate]:
    """Stream a Scryfall bulk file and aggregate printings per oracle identity (pass 1).

    For each group key (see :func:`group_key`) this unions the ``games`` of every printing
    (absent/``null`` treated as empty) and picks the canonical printing: the one with the
    greatest ``released_at`` (ISO date strings compare lexicographically), ties broken by
    the smallest ``id`` — deterministic across runs.

    Memory stays small: one entry per oracle identity (~35k for ``default_cards``), each a
    tiny set plus two strings.

    Args:
        file_path: Path to the bulk JSON file (a top-level array of card objects).

    Returns:
        Mapping of group key to its :class:`OracleAggregate`.
    """
    aggregates: dict[str, OracleAggregate] = {}
    printings = 0
    for card_json in stream_cards(file_path):
        printings += 1
        key = group_key(card_json)
        if key is None:
            continue
        card_id = str(card_json.get("id") or "")
        released_at = str(card_json.get("released_at") or "")
        games: list[str] = card_json.get("games") or []
        aggregate = aggregates.get(key)
        if aggregate is None:
            aggregates[key] = OracleAggregate(
                games=set(games),
                canonical_id=card_id,
                canonical_released_at=released_at,
            )
            continue
        aggregate.games.update(games)
        if not card_id:
            continue  # a printing without an id can never be the canonical row
        if not aggregate.canonical_id:
            replaces = True
        elif released_at != aggregate.canonical_released_at:
            replaces = released_at > aggregate.canonical_released_at
        else:
            replaces = card_id < aggregate.canonical_id
        if replaces:
            aggregate.canonical_id = card_id
            aggregate.canonical_released_at = released_at
    logger.info("Aggregated %d printings into %d oracle identities", printings, len(aggregates))
    return aggregates
