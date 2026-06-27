"""Render a deck into the self-contained viewer HTML page."""

import json
from pathlib import Path

from src.data.schemas.deck import Deck
from src.viewer.view_model import build_view_model

_TEMPLATE_PATH = Path(__file__).parent / "template.html"
_PLACEHOLDER = "__DECK_JSON__"


def render_html(deck: Deck) -> str:
    """Render a deck into a standalone HTML document.

    Builds the view-model (see :func:`build_view_model`), serialises it to JSON,
    and injects it into ``template.html`` at the ``__DECK_JSON__`` placeholder
    inside the ``<script type="application/json">`` island.

    Args:
        deck: A deck with ``deck_cards[].card`` populated.

    Returns:
        The complete HTML document as a string.
    """
    view_model = build_view_model(deck)
    # Escape ``</`` so an oracle/name containing ``</script`` cannot break out
    # of the JSON island; ``<\/`` is a valid JSON escape that parses back to
    # ``</``.
    payload = json.dumps(view_model, ensure_ascii=False).replace("</", "<\\/")
    template = _TEMPLATE_PATH.read_text(encoding="utf-8")
    return template.replace(_PLACEHOLDER, payload)
