"""The one canonical Spellbook combo record shape (AD-11, Story 5.6).

``ComboRecord`` is the single frozen shape used verbatim by the combo-snapshot
repository (Story 6.3), the pure scoring core's matcher
(:mod:`src.logic.assessment.combos`), and Epic 7's ``flags.combos`` serialization —
one vocabulary, no per-layer forks. It lives HERE, at the schema layer, rather than in
the core (a deliberate, documented deviation from the epic's "defined in the core"
wording): the repository must return Pydantic schemas, never ORM (AD-5), and the strict
``data → logic`` import direction means a shape defined in ``src/logic`` could never be
returned by a ``src/data`` repository. The core still owns all combo *semantics* —
bucket assignment, the bracket map, and the derived ``type`` /
``earliest_turn_estimate`` values live in :mod:`src.logic.assessment.combos`.

The two ``Literal`` enums are closed on purpose: an unknown ``bracket_tag`` or
``bucket`` raises a Pydantic ``ValidationError`` at the repo/core boundary — the second
line of defense behind Story 6.2's import-time wire normalization. If Spellbook's
vocabulary ever drifts, it must fail loudly there or here, never silently map to a
wrong Bracket floor.

The name-key normalization policy (:func:`name_keys`) lives here for the same reason
``ComboRecord`` does: the data-layer importer (Story 6.2) and the pure matcher
(:mod:`src.logic.assessment.combos`) must share ONE normalization — the DFC front-face
hazard bit stories 5.3, 5.6, and 5.9 — and the strict ``data → logic`` import direction
means ``src/data`` can never import it from ``src/logic``.
"""

from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

#: Scryfall's face separator in joined multi-face names (``"Alive // Well"``).
_FACE_SEPARATOR: Final = " // "


def name_keys(name: str) -> tuple[str, ...]:
    """Return the lookup keys a deck-card name is indexed under.

    The decide-once normalization policy: comparison is lowercased, and a multi-face
    ``Card.name`` (the ``" // "``-joined form) is indexed under BOTH the full joined
    name and its front face — Spellbook names single faces, ``Card.name`` may be
    ``"A // B"`` (the pre-phase-2 ``detect_synergies`` '//' lesson). Variant piece
    names and commander names are compared lowercased against these keys.

    Args:
        name: The card name as stored on :class:`~src.data.schemas.card.Card`.

    Returns:
        One or two lowercased keys (full name, plus the front face when distinct).
    """
    lowered = name.lower()
    if _FACE_SEPARATOR in lowered:
        return (lowered, lowered.split(_FACE_SEPARATOR)[0])
    return (lowered,)


#: The matcher-assigned inclusion bucket (FR13): every piece present vs. exactly one
#: missing. Variants missing two or more pieces are excluded from output entirely, so
#: no third token exists.
ComboBucket = Literal["included", "almost_included"]

#: Commander Spellbook's closed bracket-tag vocabulary — exactly the six spine tokens
#: (AD-11). Story 6.2 normalizes wire casing into these; anything else is an error,
#: never a silent alias.
ComboBracketTag = Literal[
    "CASUAL", "ODDBALL", "POWERFUL", "PRECON_APPROPRIATE", "RUTHLESS", "SPICY"
]


class ComboRecord(BaseModel):
    """One Commander Spellbook combo variant — the AD-11 cross-layer contract.

    Immutable end to end: the model is frozen and the name collections are tuples.
    ``bucket`` is ``None`` in stored/repository rows; only the core matcher
    (:func:`src.logic.assessment.combos.match_combos`) assigns it, via
    ``model_copy(update=...)`` — the matched record is the SAME type, never a parallel
    "MatchedCombo" shape. Derived values (``type``, ``earliest_turn_estimate``) are
    deliberately NOT fields — they are computed in the pure core and never stored, so
    re-tuning the heuristics never forces a re-import (AD-11).

    Attributes:
        spellbook_id: Spellbook variant id (e.g. ``"1234-5678"``).
        cards: Piece names, multiplicity-inclusive, normalized to ascending bytewise
            order on construction; at least one piece (a combo with no pieces is
            meaningless — an empty tuple raises ``ValidationError``).
        commander_required: Whether the variant needs a piece in the command zone.
        bucket: Matcher-assigned inclusion bucket; ``None`` until matched.
        bracket_tag: Spellbook's power-bracket tag (closed six-token enum).
        produces: Produced results (e.g. ``"Infinite mana"``), normalized sorted like
            ``cards``.
        popularity: EDHREC deck count; ``None`` when unknown.
    """

    model_config = ConfigDict(frozen=True)

    spellbook_id: str
    cards: tuple[str, ...] = Field(min_length=1)
    commander_required: bool
    bucket: ComboBucket | None = None
    bracket_tag: ComboBracketTag
    produces: tuple[str, ...]
    popularity: int | None = None

    @field_validator("cards", "produces")
    @classmethod
    def _sort_names(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        """Normalize name tuples to ascending bytewise order (duplicates preserved)."""
        return tuple(sorted(v))


class ComboSnapshotMeta(BaseModel):
    """The combo snapshot's single metadata row — the ``data_vintage`` source (AD-5/AD-7).

    Mirrors :class:`~src.data.models.combo.ComboSnapshotMetaModel` minus the pinned
    ``id``. Both timestamps stay ISO-8601 **strings**: they are stored metadata passed
    through verbatim to Epic 7's ``data_vintage`` serialization — no datetime parsing,
    nothing clock-derived (AD-8).

    Attributes:
        imported_at: UTC time the import script wrote the snapshot (ISO-8601 string).
        export_timestamp: The bulk file's top-level ``timestamp`` (ISO-8601 string).
        export_version: The bulk file's top-level ``version``.
        variant_count: Number of variants imported into ``combo_variants``.
    """

    model_config = ConfigDict(frozen=True, from_attributes=True)

    imported_at: str
    export_timestamp: str
    export_version: str
    variant_count: int
