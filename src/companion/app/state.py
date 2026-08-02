"""The companion's ephemeral display state — what the glass is currently showing (CM-3, FR-07).

**The first state this backend owns.** Everything served before c3-4 was a projection of
``cards.db`` — ask twice, get the same answer, because the answer was never ours. The active deck is
different: it is a slot in *this process's* memory, and its whole contract is that it is
**ephemeral**. A restart reports none (FR-07). That is not a limitation to work around; it is the
specified behaviour, and it is why nothing here is written to disk, cached, or published in the
discovery file.

**Why the state lives here and not in the MCP server.** The spine's inherited-constraints table and
PRD CM-3 both rule that the *backend* owns the active deck. The MCP tools are stateless and
self-contained (project-context D5): ``companion_set_active_deck`` (c6-2) calls the HTTP endpoint
and keeps nothing, so two agent sessions talking to one companion see one active deck rather than
two disagreeing ones. ``tests/unit/companion/test_routes_active_deck.py`` asserts the MCP side
stays clean rather than trusting this paragraph.

**Why this module rather than a bare ``app.state.active_deck_id``.** The Structural Seed names it:
``app/state.py # active deck, connections, tickets — in memory (AD-5)``. c5-2's WebSocket tickets
and c5-4's connection registry join this module rather than inventing a third home, and keeping
display state out of ``main.py`` leaves that module about identity and wiring. The holder follows
the shipped convention exactly — an inert object the lifespan creates, reached through one accessor
(:func:`active_deck`, mirroring :func:`src.companion.app.deps.database` and
:func:`src.companion.app.main.bound_port`).

**No lock, deliberately — do not cargo-cult** :class:`~src.companion.app.deps.Database`'s. That
class holds one because engine creation is a multi-step check-then-assign whose next ``await`` would
reintroduce silent double-creation. Setting a ``str | None`` is a **single assignment with no
read-modify-write and no interleaving point** on single-threaded asyncio: two concurrent writes
produce one of the two values, which is exactly what any lock would also produce. A lock here would
be defence against nothing, and would read to the next author as though a race existed. If a future
story makes a write multi-step — a compare-and-set, a write that consults the old value — that is
the change that earns a lock, and it should say so at the same time.
"""

from fastapi import FastAPI


class ActiveDeckSlot:
    """The in-memory slot naming the deck the UI is currently showing (FR-07).

    **Named a "slot", not an "ActiveDeck", on purpose.** The *wire* model
    :class:`~src.companion.contracts.ActiveDeck` already owns that name, and
    :mod:`src.companion.app.routes.active_deck` imports both — one to store, one to answer with.
    Two classes called ``ActiveDeck`` in one route module is an ``as`` alias waiting to be written
    and a reader waiting to be confused about which layer they are in.

    Constructing one is free and cannot fail — no I/O, no path resolution, no configuration — which
    is what lets the lifespan create it beside :class:`~src.companion.app.deps.Database` without
    widening the startup surface AD-10 keeps deliberately narrow.

    **Nothing here validates that the deck exists.** That is AD-16's ruling, not an omission: the
    MCP tool has database access and is the party that must report ``deck_not_found`` to the agent,
    so the backend stores what it is given. A slot holding an id no ``GET /api/deck/{id}`` can
    resolve is a legitimate state, and the UI's answer to it is the ordinary ``deck_not_found``
    path it already handles.

    Example:
        >>> ActiveDeckSlot().deck_id is None
        True
    """

    def __init__(self) -> None:
        self._deck_id: str | None = None

    @property
    def deck_id(self) -> str | None:
        """The deck currently being displayed, or ``None`` if none has been set this process.

        Read-only through the property so :meth:`set` is the single write site — the same reason
        :attr:`~src.companion.app.deps.Database.engine` is read-only.
        """
        return self._deck_id

    def set(self, deck_id: str) -> None:
        """Point the display at *deck_id*, replacing whatever was there.

        Idempotent by construction, which is why the wire verb is ``PUT`` and not ``POST``: setting
        the same deck twice is the same state.

        Args:
            deck_id: The deck to display. Stored verbatim — never trimmed, normalised or
                case-folded, because the value has to be *reported* back byte-for-byte and c3-1
                ruled a deck id has no declared shape, so there is no canonical form to normalise
                toward. (A reader handing it to ``GET /api/deck/{deck_id}`` still URL-encodes it
                like any path segment — verbatim storage is not a promise that every storable id
                is a valid raw path fragment.)
        """
        self._deck_id = deck_id


def active_deck(app: FastAPI) -> ActiveDeckSlot | None:
    """Return the :class:`ActiveDeckSlot` for *app*, or ``None`` if the lifespan never ran.

    The single reader of ``app.state.active_deck``, mirroring
    :func:`src.companion.app.deps.database` and :func:`src.companion.app.main.bound_port` so the
    state key has one construction site and one accessor. ``None`` means **the lifespan never ran**
    — a constructed-but-never-started app, which on a supported path only happens in a test.

    Args:
        app: The application to read.

    Returns:
        The holder, or ``None`` before startup.
    """
    # Annotated local rather than `return getattr(...)`: app.state is Any, and warn_return_any
    # would flag returning it directly.
    holder: ActiveDeckSlot | None = getattr(app.state, "active_deck", None)
    return holder
