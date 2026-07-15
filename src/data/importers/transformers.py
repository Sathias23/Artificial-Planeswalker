"""Data transformation functions to convert Scryfall JSON to SQLAlchemy models."""

import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from src.data.importers.aggregate import resolve_oracle_id
from src.data.models.card import CardModel

logger = logging.getLogger(__name__)


class CardTransformError(Exception):
    """Raised when card transformation fails."""

    pass


@dataclass(frozen=True, slots=True)
class TransformReject:
    """Identity and reason for a card the transformer rejected.

    Attributes:
        identity: The card's ``name``, else its ``id``, else ``"unknown"`` — whatever
            best identifies the rejected card to an operator.
        reason: Why the card was rejected: the missing required field name(s), or the
            exception class (and message) raised during transformation.
    """

    identity: str
    reason: str


def _reject_identity(card_json: dict[str, Any]) -> str:
    """Best-effort identity for a rejected card: name, else id, else "unknown"."""
    name = card_json.get("name")
    if name:
        return str(name)
    card_id = card_json.get("id")
    if card_id:
        return str(card_id)
    return "unknown"


#: Canonical WUBRG color ordering used across the codebase.
_WUBRG: tuple[str, ...] = ("W", "U", "B", "R", "G")


def _decimals_to_floats(value: Any) -> Any:
    """Recursively replace ``decimal.Decimal`` values with ``float`` in a JSON-shaped value.

    ijson parses every JSON number as :class:`decimal.Decimal`. Reversible-card faces carry
    a numeric ``cmc``, which would crash the SQLAlchemy ``JSON`` column serializer at flush
    time; sanitizing the stored ``card_faces`` keeps the column JSON-serializable. Faces of
    other layouts carry no numbers, so this is content-neutral for them.

    Args:
        value: Any JSON-shaped value (dict, list, or scalar).

    Returns:
        The same structure with every ``Decimal`` converted to ``float``.
    """
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, list):
        return [_decimals_to_floats(item) for item in value]
    if isinstance(value, dict):
        return {key: _decimals_to_floats(item) for key, item in value.items()}
    return value


def _face_join(faces: list[dict[str, Any]], key: str) -> str:
    """Join distinct-in-order, non-empty face values with the Scryfall ``" // "`` separator.

    Empty-string and null face values are skipped, so a costless back face never produces a
    dangling separator. Duplicate values collapse in order: identical-face art variants come
    out as the plain single value (e.g. two "Anje Falkenrath" faces -> "Anje Falkenrath").

    Args:
        faces: The card's ``card_faces`` objects.
        key: Face field to join (e.g. ``"name"``, ``"type_line"``, ``"mana_cost"``).

    Returns:
        The joined string; empty when no face carries a non-empty value.
    """
    distinct: list[str] = []
    for face in faces:
        value = face.get(key)
        if value is None or value == "":
            continue
        text = str(value)
        if text not in distinct:
            distinct.append(text)
    return " // ".join(distinct)


def _face_first(faces: list[dict[str, Any]], key: str) -> Any:
    """Return face 0's value for *key*, or ``None`` when absent or there are no faces.

    Args:
        faces: The card's ``card_faces`` objects.
        key: Face field to read (e.g. ``"cmc"``).

    Returns:
        The first face's value for *key*, or ``None``.
    """
    if not faces:
        return None
    return faces[0].get(key)


def _face_shared(faces: list[dict[str, Any]], key: str) -> str | None:
    """Return the value every face agrees on for *key*, string-coerced; else ``None``.

    Used for ``power``/``toughness``: reversible faces repeat the printing's combat stats,
    so an all-faces-agree value is the card's own. Disagreement, any face lacking the field,
    or an empty faces list yields ``None`` — matching the multi-face top-level convention.

    Args:
        faces: The card's ``card_faces`` objects.
        key: Face field to compare (e.g. ``"power"``).

    Returns:
        ``str(value)`` when all faces carry the same non-empty value, else ``None``.
    """
    if not faces:
        return None
    first = faces[0].get(key)
    if first is None or first == "":
        return None
    for face in faces[1:]:
        if face.get(key) != first:
            return None
    return str(first)


def _face_color_union(faces: list[dict[str, Any]]) -> list[str]:
    """Union of face ``colors`` values, sorted in canonical WUBRG order.

    Args:
        faces: The card's ``card_faces`` objects.

    Returns:
        The color union as a list ordered ``["W", "U", "B", "R", "G"]``-wise.
    """
    union: set[str] = set()
    for face in faces:
        union.update(face.get("colors") or [])
    return [color for color in _WUBRG if color in union]


def transform_scryfall_card(
    card_json: dict[str, Any], rejects: list[TransformReject] | None = None
) -> CardModel | None:
    """Transform Scryfall JSON card object to CardModel ORM instance.

    Handles required and optional fields with appropriate defaults.
    Returns None for cards that cannot be transformed (invalid data). When *rejects*
    is supplied, every ``None`` return also appends one :class:`TransformReject`
    (identity + reason) to it — a second diagnostics channel that leaves the
    ``None`` return contract untouched.

    Shape-gated face derivation: when the card carries NO top-level ``type_line`` (the
    reversible-card signature — those fields live only on ``card_faces``), ``name``,
    ``type_line``, ``mana_cost``, ``cmc``, ``colors``, ``power`` and ``toughness`` are
    derived from the faces. ``name`` is derived even though reversible cards DO carry a
    top-level name (the doubled ``"Anje Falkenrath // Anje Falkenrath"`` form, which would
    break exact decklist lookups); for every other field a present top-level value wins
    verbatim. Cards WITH a top-level ``type_line`` (all normal layouts, including
    transform/modal_dfc/battle/split/adventure) transform byte-identically to the pre-gate
    behavior. ``oracle_text`` intentionally stays ``""`` for gated multi-face rows —
    consumers join ``card_faces`` (existing multi-face convention).

    Args:
        card_json: Dictionary containing Scryfall card data.
        rejects: Optional collector; a :class:`TransformReject` is appended for every
            rejected card so callers can report which cards failed and why.

    Returns:
        CardModel instance if transformation succeeds, None otherwise.
    """
    try:
        # Shape gate: only a card with NO top-level ``type_line`` derives from its faces.
        # Live transform/MDFC/battle cards ALSO lack top-level mana_cost/colors/power/
        # toughness, so per-field absence must NEVER trigger derivation on its own — the
        # gate is the one signal that separates the reversible shape from normal layouts.
        derive_from_faces = "type_line" not in card_json
        faces: list[dict[str, Any]] = []
        if derive_from_faces:
            raw_faces = card_json.get("card_faces")
            if isinstance(raw_faces, list):
                faces = [face for face in raw_faces if isinstance(face, dict)]

        # Validate required fields. ``oracle_id`` is resolved with a face-level fallback
        # (reversible / multi-face layouts carry it on ``card_faces[0]``, not the top level) —
        # the same resolution ``group_key`` uses, so a reversible card that pass-1 aggregated is
        # no longer rejected here and dropped downstream.
        missing_fields = [field for field in ("id",) if field not in card_json]
        derived_name: str | None = None
        derived_type_line: str | None = None
        if derive_from_faces:
            # Inside the gate ``name``/``type_line`` are satisfied by face derivation; a
            # derived value that comes out empty (absent everywhere, or all-empty faces)
            # is a missing required field — same reject reason string as ever.
            derived_name = _face_join(faces, "name") or card_json.get("name") or None
            derived_type_line = _face_join(faces, "type_line") or None
            if derived_name is None:
                missing_fields.append("name")
            if derived_type_line is None:
                missing_fields.append("type_line")
        else:
            missing_fields.extend(
                field for field in ("name", "type_line") if field not in card_json
            )
        oracle_id = resolve_oracle_id(card_json)
        if oracle_id is None:
            missing_fields.append("oracle_id")

        if missing_fields:
            logger.warning(
                f"Skipping card '{card_json.get('name', 'UNKNOWN')}': "
                f"missing required fields: {missing_fields}"
            )
            if rejects is not None:
                rejects.append(
                    TransformReject(
                        identity=_reject_identity(card_json),
                        reason=f"missing required field(s): {', '.join(missing_fields)}",
                    )
                )
            return None

        assert oracle_id is not None  # a None oracle_id was appended to missing_fields above

        # Extract required fields. Inside the gate, ``name`` is derived DESPITE the present
        # doubled top-level name (sole present-wins exception — ``find_by_name_exact`` must
        # match decklist names); ``type_line`` is face-derived by the gate's definition.
        card_id = card_json["id"]
        if derive_from_faces:
            assert derived_name is not None  # validated non-empty above
            assert derived_type_line is not None
            name = derived_name
            type_line = derived_type_line
        else:
            name = card_json["name"]
            type_line = card_json["type_line"]
        printed_name = card_json.get(
            "printed_name"
        )  # Optional (OM1 cards have different printed names)

        # Non-nullable fields use `get(...) or default`, NOT `get(field, default)`:
        # `.get` only falls back for MISSING keys, so an explicit JSON null
        # (`"field": null`, common on tokens/split cards) would slip through as None
        # and write a NULL into a non-nullable column. `or` also coerces those nulls.
        # Inside the gate a PRESENT top-level key (even an explicit null) wins verbatim;
        # only a fully absent key falls back to the faces.
        # Handle mana cost and CMC (lands and some cards have empty mana_cost)
        if derive_from_faces and "mana_cost" not in card_json:
            mana_cost = _face_join(faces, "mana_cost")
        else:
            mana_cost = card_json.get("mana_cost") or ""
        if derive_from_faces and "cmc" not in card_json:
            cmc = float(_face_first(faces, "cmc") or 0.0)
        else:
            cmc = float(card_json.get("cmc") or 0.0)

        # Handle oracle text (some cards have no text). Stays "" for gated multi-face
        # rows on purpose — consumers join card_faces (existing multi-face convention).
        oracle_text = card_json.get("oracle_text") or ""

        # Handle combat stats (creatures/vehicles only; None for everything else).
        # Scryfall stores these as strings ("2", "*", "1+*"); preserve None for non-creatures.
        # For DFCs the top-level value is absent — the viewer falls back to card_faces.
        # Gated cards store the all-faces-agree value (reversible faces repeat the stats).
        if derive_from_faces and "power" not in card_json:
            power = _face_shared(faces, "power")
        else:
            power = card_json.get("power")
        if derive_from_faces and "toughness" not in card_json:
            toughness = _face_shared(faces, "toughness")
        else:
            toughness = card_json.get("toughness")

        # Official WotC Game Changer flag (Scryfall bulk top-level boolean `game_changer`).
        # Three distinct states must survive: missing key -> None ("unknown"), true -> True,
        # false -> False. Use a bare `.get` with NO `or`/`bool(...)`: `or` would turn a
        # legitimate `False` into `None`, destroying the "confirmed not a GC" state (AD-4).
        game_changer = card_json.get("game_changer")

        # Extract set information with defaults
        rarity = card_json.get("rarity") or "common"
        set_code = card_json.get("set") or "unknown"
        set_name = card_json.get("set_name") or "Unknown Set"
        collector_number = card_json.get("collector_number") or "0"

        # Handle color arrays (default to empty lists). Gated cards union face colors
        # in canonical WUBRG order; color_identity is top-level on reversibles — untouched.
        if derive_from_faces and "colors" not in card_json:
            colors = _face_color_union(faces)
        else:
            colors = card_json.get("colors") or []
        color_identity = card_json.get("color_identity") or []
        color_indicator = card_json.get("color_indicator")  # Optional, can be None

        # Handle keywords (optional, nullable column — preserve None)
        keywords = card_json.get("keywords")  # Can be None or missing

        # Handle legalities (default to empty dict)
        legalities = card_json.get("legalities") or {}

        # Handle multi-face cards (optional). Sanitize ijson Decimals (reversible faces
        # carry numeric cmc) so the JSON column serializes at flush; content-neutral for
        # layouts whose faces carry no numbers.
        card_faces = _decimals_to_floats(card_json.get("card_faces"))  # Can be None or missing

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
            game_changer=game_changer,
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
        if rejects is not None:
            rejects.append(
                TransformReject(
                    identity=_reject_identity(card_json), reason=f"{type(e).__name__}: {e}"
                )
            )
        return None

    except Exception as e:
        card_name = card_json.get("name", "UNKNOWN")
        logger.error(f"Unexpected error transforming card '{card_name}': {e}")
        if rejects is not None:
            rejects.append(
                TransformReject(
                    identity=_reject_identity(card_json), reason=f"{type(e).__name__}: {e}"
                )
            )
        return None
