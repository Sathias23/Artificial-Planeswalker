"""Read-only deck viewer: deck -> view-model -> self-contained HTML page.

Presentation layer that turns a :class:`src.data.schemas.deck.Deck` into the
data object consumed by ``template.html`` (a vanilla recreation of the
``Deck Viewer`` design). Sits above ``src/data`` and imports only its schemas.
"""

from src.viewer.present import deck_viewer_path, present_deck
from src.viewer.render import render_html
from src.viewer.view_model import build_view_model

__all__ = ["build_view_model", "deck_viewer_path", "present_deck", "render_html"]
