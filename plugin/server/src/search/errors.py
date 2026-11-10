"""Named failures for the two third-party pieces semantic search loads at run time.

The sqlite-vec extension and the fastembed model are the search stack's only dependencies that can
be missing on a working install: a Python build without loadable-extension support, an
antivirus-quarantined DLL, or a first model download with no network. Each is caught where it
happens (:mod:`src.search.connection`, :mod:`src.search.embedder`) and re-raised as one of these, so
the MCP tool edge can answer it as ``status="error"`` by type without ever catching a bare
``ValueError`` or ``OSError`` (``src/mcp_server/tools/failures.py``).
"""


class SearchBackendUnavailableError(RuntimeError):
    """A semantic-search dependency could not be loaded; the message names which one and why."""


class VectorExtensionUnavailableError(SearchBackendUnavailableError):
    """The sqlite-vec extension could not be loaded into a new SQLite connection."""


class EmbeddingModelUnavailableError(SearchBackendUnavailableError):
    """The fastembed embedding model could not be loaded (or downloaded on first use)."""
