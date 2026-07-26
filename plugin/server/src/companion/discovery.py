"""The discovery file — how a running companion is found, and nothing else (AD-4).

A companion process may bind a port it did not ask for (c1-3's ephemeral fallback), so no caller
can hardcode where it lives. The **sole** rendezvous is one small JSON file at
``src.paths.data_dir()/companion.json`` holding ``{port, token, instance_id}``: the lifespan writes
it on startup and removes it on clean shutdown, and every agent-side caller reads it to learn both
where to connect and how to authenticate. There is no second channel — no env var, no registry key,
no port scan.

This module is a **leaf** (AD-3): stdlib, ``pydantic`` and ``src.paths`` only — never ``fastapi``,
``sqlalchemy`` or ``src.companion.app``, and not even under ``if TYPE_CHECKING:``. That is the
whole point of it. A stdio MCP session must be able to learn a port and a token without
transitively importing a web framework and a server, so the module that answers "where is the app?"
cannot itself depend on the app. ``tests/unit/companion/test_import_boundary.py`` enforces it.

Three design rules are load-bearing:

* **The write is atomic — a temp file in the target's own directory, then ``os.replace``.** A
  reader may arrive at any instant, and it must never observe a half-written file; the target is
  only ever moved into place whole. ``os.rename`` is *wrong* here: over an existing file it raises
  ``FileExistsError`` on Windows, so a second launch after a stale file was left behind would fail
  on the rename — on the primary development platform only. The temp file shares the target's
  directory because ``os.replace`` is atomic only within one filesystem, and the system temp
  directory may be on another volume.
* **A parse failure is *app not running*, not an error.** :func:`read_discovery` returns ``None``
  for an absent, unreadable, truncated, non-JSON or wrong-shaped file, and never raises. AD-15
  accepts that a crashed process leaves a stale file behind; for c6-1's client the ordinary,
  expected case is that there is no usable file at all, so a rejected read logs at DEBUG rather
  than warning on every push.
* **The token is a secret and must never be logged.** It is minted fresh per process
  (:func:`mint_token`), reaches exactly two places — this file and ``app.state`` — and
  :attr:`DiscoveryRecord.token` carries ``repr=False`` so a stray ``logger.info("%s", record)`` or
  a traceback frame cannot print it. It is deliberately **not** a ``SecretStr``: that would
  serialize to ``"**********"`` and write a file no tool could authenticate with.
"""

import contextlib
import logging
import os
import secrets
import tempfile
from pathlib import Path

from pydantic import BaseModel, Field

from src import paths

logger = logging.getLogger(__name__)

COMPANION_FILENAME = "companion.json"
"""The rendezvous file's name — written here once, so writer and reader cannot disagree."""


class DiscoveryRecord(BaseModel):
    """The contents of ``companion.json``: where the companion is, and how to talk to it.

    This model crosses a *filesystem* boundary between two backend-side processes, which is why it
    lives here and not in ``src.companion.contracts`` — that module is scoped to shapes that cross
    the HTTP and WebSocket boundary and are projected into the SPA's generated TypeScript (AD-12).
    This record must never reach the browser at all.

    The constraints are the reader's shape check, and each rejects a record that points at nothing
    usable rather than letting a caller act on it. Unknown keys are **ignored** (pydantic's
    default, deliberately not ``extra="forbid"``): a newer backend that adds a field must not make
    an older reader report *app not running*.

    Attributes:
        port: The loopback port the companion actually bound, constrained to a real port number.
        token: The per-process agent credential. ``repr=False`` keeps it out of ``repr()`` and
            ``str()``; ``model_dump_json`` still writes it, which is the point of the file.
        instance_id: The per-process identity, echoed by ``GET /health`` so a caller can confirm
            that whatever answered on that port is the process this record describes (FR-14).

    Example:
        >>> record = DiscoveryRecord(port=51234, token="s3cret", instance_id="0f6e")
        >>> "s3cret" in repr(record)
        False
    """

    port: int = Field(ge=1, le=65535)
    token: str = Field(min_length=1, repr=False)
    instance_id: str = Field(min_length=1)


def discovery_path() -> Path:
    """Return the full path of the discovery file, resolved at call time.

    Resolved **at call time**, never at import: :func:`src.paths.data_dir` ends in
    ``mkdir(parents=True, exist_ok=True)``, so a module-level or default-argument call would create
    the user's data directory merely by importing this module and would break AD-10's inertness
    guarantee. Calling through ``src.paths`` (rather than ``platformdirs`` or a hardcoded ``~/…``)
    is also what makes ``PLANESWALKER_DATA_DIR`` work for writer and reader alike.

    Returns:
        ``src.paths.data_dir() / COMPANION_FILENAME``. The parent directory is created as a side
        effect of resolving it; the file itself may or may not exist.
    """
    return paths.data_dir() / COMPANION_FILENAME


def mint_token() -> str:
    """Mint a fresh agent credential for this process.

    Called once per process by the lifespan, so two starts never share a token and a restarted
    backend invalidates the one a tool was holding — which is exactly the case c6-1's retry-once
    absorbs. 32 bytes of ``secrets`` entropy, rendered as 43 URL-safe characters.

    Returns:
        A new high-entropy token. Never log it.
    """
    return secrets.token_urlsafe(32)


def write_discovery(record: DiscoveryRecord) -> Path:
    """Publish *record* atomically, so no reader can ever observe a partial file.

    The sequence is deliberate: write the serialized record to a uniquely-named temp file **in the
    target's own directory**, ``flush`` and ``fsync`` it so the bytes are on disk before it is
    visible under the real name, restrict its permissions, then ``os.replace`` it into place. A
    failure at any step removes the temp file (best-effort — a cleanup failure of its own never
    displaces the original error) and re-raises, leaving no ``.tmp`` litter and the previous file
    (if any) exactly as it was.

    ``mkstemp`` rather than a fixed ``companion.json.tmp`` so two processes starting at once cannot
    write the same temp file and hand each other a spliced record. ``os.replace`` rather than
    ``os.rename`` because the latter raises ``FileExistsError`` over an existing file on Windows.

    ``os.chmod(…, 0o600)`` is **POSIX-effective only** — on Windows the file stays ``0o666`` and the
    protection is the per-user ``%LOCALAPPDATA%`` directory it sits in. It is applied to the temp
    file *before* the replace so the file is never briefly world-readable under its real name.

    The containing directory is **not** fsynced. On POSIX that is what full durability of a rename
    would need and on Windows a directory cannot be opened for it at all; it is skipped because the
    file is rewritten on every start and a crash that loses it leaves *app not running*, which is
    true.

    Args:
        record: The rendezvous to publish.

    Returns:
        The path the record was written to.

    Raises:
        OSError: The data directory is unwritable, or the replace failed (on Windows, a reader
            holding the target open is enough). The caller — the lifespan — lets this abort the
            launch: a companion that cannot publish its rendezvous is unreachable by every agent
            tool while appearing to run, and a loud failure is the diagnosable one (Decide-once #3).
    """
    target = discovery_path()
    directory = target.parent
    descriptor, temp_name = tempfile.mkstemp(
        dir=directory, prefix=f"{COMPANION_FILENAME}.", suffix=".tmp"
    )
    temp_path = Path(temp_name)
    try:
        try:
            handle = os.fdopen(descriptor, "w", encoding="utf-8")
        except BaseException:
            # fdopen only takes ownership of the descriptor on success; without this close the
            # descriptor leaks, and on Windows it would also hold the temp file against the unlink.
            os.close(descriptor)
            raise
        with handle:
            handle.write(record.model_dump_json())
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp_path, 0o600)
        os.replace(temp_path, target)
    except BaseException:
        # The cleanup itself can fail (Windows: an AV/indexer briefly holding the fresh temp file
        # open) — that must not displace the original exception, which names the real problem.
        with contextlib.suppress(OSError):
            temp_path.unlink(missing_ok=True)
        raise
    return target


def read_discovery() -> DiscoveryRecord | None:
    """Read the published rendezvous, or ``None`` when there is no usable one.

    **Never raises.** Every unusable state — an unresolvable data directory, no file, a directory
    at the path, no read permission, bytes that are not UTF-8, bytes that are not JSON, JSON of
    the wrong shape, a file truncated mid-write by some other writer — means the same thing to a
    caller: *the app is not running*. One ``read_bytes`` plus one ``model_validate_json`` puts
    decode, parse and shape validation inside a single ``except (OSError, ValueError)``, which is
    a complete net because ``pydantic.ValidationError``, ``json.JSONDecodeError`` and
    ``UnicodeDecodeError`` are all ``ValueError`` subclasses. The path resolution sits under its
    own ``OSError`` guard because :func:`discovery_path` ends in a ``mkdir`` that can itself fail.
    It is deliberately **not** ``except Exception``: a ``MemoryError`` during a read is not "app
    not running".

    Rejections log at DEBUG, not WARNING — for c6-1's client the expected case is that no file
    exists, and a warning per push would be noise in the user's terminal.

    Returns:
        The published record, or ``None`` if there is no usable one.
    """
    try:
        path = discovery_path()
    except OSError as exc:
        logger.debug("Data directory unresolvable (%s); treating as app not running", exc)
        return None
    try:
        return DiscoveryRecord.model_validate_json(path.read_bytes())
    except (OSError, ValueError) as exc:
        logger.debug("No usable discovery file at %s (%s)", path, type(exc).__name__)
        return None


def remove_discovery(instance_id: str) -> bool:
    """Retract our own rendezvous — and only ours.

    Ownership-guarded rather than a bare ``unlink``: from c1-8 onward a second launch may meet a
    file it did not write, and a shutting-down process (or a test) must not delete a *live*
    instance's rendezvous. The file is read back and unlinked only when its recorded
    ``instance_id`` matches. A foreign entry, an absent file and an unparseable one are all left
    exactly as found. It also composes with the never-published case for free: a process that
    skipped the write removes nothing, with no special case.

    **Never raises.** An ``OSError`` — on Windows, another process holding the file open is
    enough — is logged at WARNING and swallowed, because this runs inside the lifespan's teardown
    where a raise would strand the engine dispose that follows it. The path resolution carries its
    own guard for the same reason: :func:`discovery_path` ends in a ``mkdir`` that can fail.

    The read-compare-unlink sequence is not atomic: a second instance that replaces the file
    between our read and our unlink loses its rendezvous. The window is microseconds on a path
    that runs once per process lifetime; the accepted trade is recorded in ``deferred-work.md``
    against c1-8, the story that first makes two instances contend for this file.

    Args:
        instance_id: The caller's own identity, as minted by the lifespan.

    Returns:
        ``True`` if our file was removed; ``False`` if there was nothing of ours to remove or the
        unlink failed.
    """
    try:
        path = discovery_path()
    except OSError:
        logger.warning("Data directory unresolvable; nothing of ours to remove", exc_info=True)
        return False
    record = read_discovery()
    if record is None:
        logger.debug("No discovery file of ours to remove at %s", path)
        return False
    if record.instance_id != instance_id:
        logger.debug(
            "Discovery file at %s belongs to instance %s, not %s; leaving it alone",
            path,
            record.instance_id,
            instance_id,
        )
        return False
    try:
        path.unlink(missing_ok=True)
    except OSError:
        logger.warning("Could not remove the discovery file at %s", path, exc_info=True)
        return False
    logger.debug("Removed discovery file %s", path)
    return True
