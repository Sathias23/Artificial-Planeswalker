"""Shared user-facing copy for the first-run / not-initialized tool responses.

Centralized so every tool's ``database_not_initialized`` (and the semantic tools' index-not-built)
message stays consistent and — crucially — names the in-client **tool** to run next, never a
terminal command. A packaged MCPB / Claude Desktop user has no shell to run
``scripts/build_card_embeddings.py``; they ask the assistant to call the tool.
"""

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
