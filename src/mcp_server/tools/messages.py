"""Shared user-facing copy: the first-run / not-initialized responses and the name-lookup buckets.

Centralized so every tool's ``database_not_initialized`` (and the semantic tools' index-not-built)
message stays consistent and — crucially — names the in-client **tool** to run next, never a
terminal command. A packaged plugin / Claude Desktop user has no shell to run
``scripts/build_card_embeddings.py``; they ask the assistant to call the tool. The ``ambiguous``
wording ``lookup_card_by_name`` and ``find_similar_cards`` share lives here for the same reason.
"""

from typing import Any

from src.data.repositories.card import MAX_NAME_MATCHES, NameResolution

#: Surfaced by every relational + semantic tool when the ``cards`` table is missing or empty.
#: Names the ``initialize_database`` tool (the in-client, consent-gated card import).
DATABASE_NOT_INITIALIZED_MESSAGE = (
    "The card database isn't set up on this machine yet. Ask me to run the `initialize_database` "
    "tool — it downloads the latest Magic card data into the local data directory (a one-time "
    "step, roughly 2-3 minutes). Then retry this."
)

#: Surfaced by the semantic tools when the cards exist but the ``card_vec`` embedding index has not
#: been built. Names the ``build_search_index`` tool (the in-client index build).
INDEX_NOT_BUILT_MESSAGE = (
    "The semantic search index isn't built yet. Ask me to run the `build_search_index` tool — it "
    "downloads a small embedding model and indexes the cards (a one-time step, roughly 5 minutes). "
    "Then retry this."
)

#: Above this many candidates, an ``ambiguous`` lookup asks the caller to refine rather than choose.
REFINE_THRESHOLD = 5


def ambiguous_lookup_message(
    name: str, resolution: NameResolution[Any], *, card_id_hint: bool
) -> str:
    """The ``ambiguous`` message ``lookup_card_by_name`` and ``find_similar_cards`` share.

    Three buckets: up to :data:`REFINE_THRESHOLD` candidates asks which one; more asks the caller
    to refine; a list cut at :data:`~src.data.repositories.card.MAX_NAME_MATCHES` says "more than"
    rather than reporting the cut length as the count.

    Args:
        name: The name as resolved (stripped).
        resolution: An ambiguous resolution (``matches`` populated).
        card_id_hint: Also point at re-calling with a ``card_id`` (``find_similar_cards`` takes
            one; ``lookup_card_by_name`` does not).
    """
    shown = len(resolution.matches)
    count = f"more than {MAX_NAME_MATCHES}" if resolution.more else str(shown)
    found = f"Found {count} cards matching '{name}'."
    if resolution.more or shown > REFINE_THRESHOLD:
        alternative = ", or re-call with a specific card_id" if card_id_hint else ""
        showing = f"; showing the first {shown}" if resolution.more else ""
        return f"{found} Please refine your search{alternative}{showing}."
    pick = " Re-call with a specific card_id." if card_id_hint else ""
    return f"{found} Which one did you mean?{pick}"
