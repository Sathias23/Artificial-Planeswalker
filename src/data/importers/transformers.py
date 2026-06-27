"""Data transformation functions to convert Scryfall JSON to SQLAlchemy models."""

import logging
from typing import Any

from src.data.models.card import CardModel

logger = logging.getLogger(__name__)


class CardTransformError(Exception):
    """Raised when card transformation fails."""

    pass


def transform_scryfall_card(card_json: dict[str, Any]) -> CardModel | None:
    """Transform Scryfall JSON card object to CardModel ORM instance.

    Handles required and optional fields with appropriate defaults.
    Returns None for cards that cannot be transformed (invalid data).

    Args:
        card_json: Dictionary containing Scryfall card data.

    Returns:
        CardModel instance if transformation succeeds, None otherwise.
    """
    try:
        # Validate required fields
        required_fields = ["id", "name", "oracle_id", "type_line"]
        missing_fields = [field for field in required_fields if field not in card_json]

        if missing_fields:
            logger.warning(
                f"Skipping card '{card_json.get('name', 'UNKNOWN')}': "
                f"missing required fields: {missing_fields}"
            )
            return None

        # Extract required fields
        card_id = card_json["id"]
        name = card_json["name"]
        printed_name = card_json.get(
            "printed_name"
        )  # Optional (OM1 cards have different printed names)
        oracle_id = card_json["oracle_id"]
        type_line = card_json["type_line"]

        # Non-nullable fields use `get(...) or default`, NOT `get(field, default)`:
        # `.get` only falls back for MISSING keys, so an explicit JSON null
        # (`"field": null`, common on tokens/split cards) would slip through as None
        # and write a NULL into a non-nullable column. `or` also coerces those nulls.
        # Handle mana cost and CMC (lands and some cards have empty mana_cost)
        mana_cost = card_json.get("mana_cost") or ""
        cmc = float(card_json.get("cmc") or 0.0)

        # Handle oracle text (some cards have no text)
        oracle_text = card_json.get("oracle_text") or ""

        # Handle combat stats (creatures/vehicles only; None for everything else).
        # Scryfall stores these as strings ("2", "*", "1+*"); preserve None for non-creatures.
        # For DFCs the top-level value is absent — the viewer falls back to card_faces.
        power = card_json.get("power")
        toughness = card_json.get("toughness")

        # Extract set information with defaults
        rarity = card_json.get("rarity") or "common"
        set_code = card_json.get("set") or "unknown"
        set_name = card_json.get("set_name") or "Unknown Set"
        collector_number = card_json.get("collector_number") or "0"

        # Handle color arrays (default to empty lists)
        colors = card_json.get("colors") or []
        color_identity = card_json.get("color_identity") or []
        color_indicator = card_json.get("color_indicator")  # Optional, can be None

        # Handle keywords (optional, nullable column — preserve None)
        keywords = card_json.get("keywords")  # Can be None or missing

        # Handle legalities (default to empty dict)
        legalities = card_json.get("legalities") or {}

        # Handle multi-face cards (optional)
        card_faces = card_json.get("card_faces")  # Can be None or missing

        # Handle image URIs (optional)
        # For single-faced cards, image_uris is at top level
        # For double-faced cards, image_uris is in each card_face
        image_uris = card_json.get("image_uris")  # Can be None or missing

        # Handle games availability (default to empty list)
        # Scryfall provides array of platforms: "paper", "arena", "mtgo"
        # Some cards may have null instead of an array
        games = card_json.get("games") or []

        # Create CardModel instance
        card = CardModel(
            id=card_id,
            name=name,
            printed_name=printed_name,
            oracle_id=oracle_id,
            mana_cost=mana_cost,
            cmc=cmc,
            type_line=type_line,
            oracle_text=oracle_text,
            power=power,
            toughness=toughness,
            rarity=rarity,
            set_code=set_code,
            set_name=set_name,
            collector_number=collector_number,
            colors=colors,
            color_identity=color_identity,
            color_indicator=color_indicator,
            keywords=keywords,
            legalities=legalities,
            card_faces=card_faces,
            image_uris=image_uris,
            games=games,
        )

        return card

    except (KeyError, ValueError, TypeError) as e:
        card_name = card_json.get("name", "UNKNOWN")
        logger.warning(f"Failed to transform card '{card_name}': {e}")
        return None

    except Exception as e:
        card_name = card_json.get("name", "UNKNOWN")
        logger.error(f"Unexpected error transforming card '{card_name}': {e}")
        return None
