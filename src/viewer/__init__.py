"""Read-only deck viewer: deck -> view-model -> self-contained HTML page.

**FROZEN (AD-15).** The companion app has superseded this package. No new capability lands
here: no new module, no new public function, no new behaviour. Anything a deck view needs to
grow belongs in ``src/companion`` and ``ui/``, and the companion never reuses this package's
``template.html`` — two renderers of one deck would diverge. Removal is scheduled for the next
minor release once the companion is proven; until then this keeps working exactly as it does
today, so ``view_deck`` and ``scripts/view_deck.py`` stay usable with the companion closed.
The freeze is enforced by ``tests/unit/viewer/test_viewer_freeze.py``, which pins the module
list and the public surface below.

Presentation layer that turns a :class:`src.data.schemas.deck.Deck` into the
data object consumed by ``template.html`` (a vanilla recreation of the
``Deck Viewer`` design). Sits above ``src/data`` and imports only its schemas.
"""

from src.viewer.present import deck_viewer_path, present_deck
from src.viewer.render import render_html
from src.viewer.view_model import build_view_model

__all__ = ["build_view_model", "deck_viewer_path", "present_deck", "render_html"]
