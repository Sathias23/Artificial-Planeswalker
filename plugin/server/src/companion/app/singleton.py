"""The held OS advisory lock that makes "exactly one companion" true, not nearly true (FR-01).

**What it is for.** c1-8's identity probe closed the steady-state duplicate: a launch that finds a
verified-live companion refuses. It could not close the *startup* window, because two launches that
both probe before either publishes both see an empty rendezvous and both proceed. Measured at
``8bfc909``, two launches spawned 6 ms apart produced two live companions sharing one discovery
file, leaving the loser reachable by nothing. An OS advisory lock is the only primitive that answers
"am I first?" atomically across processes, so this module supplies the atomic *whether* while the
probe keeps supplying the informative *who and where*.

**Why the lock is held, not created and deleted.** The descriptor stays open for the process's whole
lifetime and the kernel drops the lock when the process dies — by Ctrl-C, by ``kill``, by a crash,
by the power going out. That is what makes it compatible with AD-15's stance that a crash is an
ordinary event: there is no stale-lock state to recover from, no PID file to test for liveness and
no heuristic to get wrong. A create-and-delete lock *file* would have inherited every one of those
problems.

**Why the file is never unlinked.** On POSIX, ``flock`` attaches to the inode behind the open
descriptor. Unlink-and-recreate would hand the next launch a *different* inode to lock, and both
processes would believe they own the machine. A zero-byte file that outlives every run is therefore
the correct artifact, not untidiness.

**Why it is a separate file from ``companion.json``.** The rendezvous is c1-7's atomically published
data (port, token, identity) and is read for its contents; this file is never read, never parsed and
carries nothing. Overloading one file with both roles would put a lock on the very inode the atomic
``os.replace`` is designed to swap out from under readers. Both live under
:func:`src.paths.data_dir`, so ``PLANESWALKER_DATA_DIR`` isolates the lock exactly as it does the
rendezvous — which is what lets two deliberate instances coexist under different data directories,
and what keeps the test suite's per-test isolation contention-free.

**Why these two primitives and no others.** On POSIX it is ``flock``, never ``lockf``/``F_SETLK``:
record locks are owned by the *process*, so a second ``lockf`` on another descriptor in the same
process succeeds and closing *any* descriptor to the file drops every lock the process holds on it —
which would both weaken the guarantee and make the cheap same-process contention test silently
vacuous. On Windows it is ``msvcrt.LK_NBLCK`` and never ``LK_LOCK``: the latter blocks, retrying ten
times over ten seconds, and a launch that hangs for ten seconds behind another launch is
indistinguishable from a hung application.

This module is **app-layer, not a leaf** (AD-3), and that is a decision rather than an accident:
taking this lock is the process runner's job, no agent-side caller may ever take it, and a leaf
module named ``singleton`` would invite exactly that. It imports stdlib plus :mod:`src.paths` only.
Nothing here runs at import (AD-10) — in particular :func:`lock_path` resolves the data directory at
call time, because :func:`src.paths.data_dir` ends in a ``mkdir``.
"""

import errno
import logging
import os
import sys
from pathlib import Path

from src import paths

logger = logging.getLogger(__name__)

# The platform branch is written against ``sys.platform`` rather than ``os.name`` because that is
# the form mypy narrows on: each platform's run type-checks only its own half, and the other half is
# unreachable rather than an error against a typeshed that lacks the constant. Both
# ``mypy src/`` and ``mypy src/ --platform linux`` are therefore mandatory and neither is redundant.
if sys.platform == "win32":
    import msvcrt
else:
    import fcntl

LOCK_FILENAME = "companion.lock"
"""The lock file's name — written here once, so no two callers can disagree about it."""

_LOCK_BYTES = 1
"""How much of the file is locked. One byte at offset 0; the contents are never read."""

_CONTENTION_ERRNOS = frozenset({errno.EACCES, errno.EAGAIN, errno.EWOULDBLOCK, errno.EDEADLK})
"""The errnos that mean "someone else holds the lock" — the only failures acquire swallows.

Windows ``msvcrt.locking(LK_NBLCK)`` reports contention as ``EACCES`` (measured, AC 11) and can
report ``EDEADLK``; POSIX ``flock(LOCK_NB)`` reports ``EWOULDBLOCK`` (``EAGAIN`` on Linux). Any
other failure of the lock call — ``ENOLCK``/``ENOTSUP`` on a filesystem that cannot lock at all,
such as NFS without lockd or some SMB/FUSE mounts — propagates loudly instead (c1-9 review
ruling): reporting it as contention would print "another companion is already starting up" on
every launch, forever, pointing at a companion that does not exist."""


def lock_path() -> Path:
    """Return the full path of the lock file, resolved at call time.

    Resolved **at call time**, never at import, for :func:`src.companion.discovery.discovery_path`'s
    reason: :func:`src.paths.data_dir` ends in ``mkdir(parents=True, exist_ok=True)``, so a
    module-level or default-argument call would create the user's data directory merely by importing
    this module and break AD-10's inertness guarantee.

    Returns:
        ``src.paths.data_dir() / LOCK_FILENAME``. The parent directory is created as a side effect
        of resolving it; the file itself is created by :func:`acquire_instance_lock`.
    """
    return paths.data_dir() / LOCK_FILENAME


def acquire_instance_lock() -> int | None:
    """Claim this machine's single companion slot, without blocking.

    The file is opened first and locked second, and only the *lock* call is guarded. That split is
    deliberate: contention reports as ``PermissionError`` (``EACCES``) on Windows, which is
    indistinguishable from a genuine permission problem, so a guard wrapped around both calls would
    quietly report "someone else has it" for a data directory this process simply cannot write. A
    launch that cannot open a file there will fail c1-7's discovery publish moments later anyway,
    and c1-7's Decide-once #3 already rules such a launch should fail loudly rather than half-start.

    The lock is **not** released here on success — that is the whole design. Hold the returned
    descriptor for the process's lifetime and pass it to :func:`release_instance_lock` from a
    ``finally``; see the module docstring for why the kernel's release-on-death is the point.

    Returns:
        The open file descriptor while this process holds the lock, or ``None`` when another
        process — or another descriptor, even in this same process — already holds it.

    Raises:
        OSError: If the lock file cannot be opened at all (a missing, unwritable or unresolvable
            data directory), or if the lock call itself fails for any reason other than
            contention (a filesystem that cannot lock — see ``_CONTENTION_ERRNOS``).
            Deliberately **not** swallowed; only contention is.

    Example:
        >>> lock = acquire_instance_lock()  # doctest: +SKIP
        >>> if lock is None:  # doctest: +SKIP
        ...     print("another companion is already starting up")
    """
    path = lock_path()
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        if sys.platform == "win32":
            msvcrt.locking(fd, msvcrt.LK_NBLCK, _LOCK_BYTES)
        else:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as exc:
        # Close the descriptor we just opened before deciding anything: a leak here is invisible
        # in a single run and pins a file handle open for the life of the process.
        os.close(fd)
        if exc.errno not in _CONTENTION_ERRNOS:
            # Not "someone else has it" — a locking subsystem that cannot lock. Fail loudly
            # rather than refuse with a message pointing at a companion that does not exist.
            raise
        logger.debug("Instance lock at %s is held elsewhere (%s)", path, exc)
        return None
    logger.debug("Instance lock acquired at %s", path)
    return fd


def release_instance_lock(fd: int) -> None:
    """Release the lock by closing *fd*.

    Closing the descriptor is what releases the lock on both platforms — but on Windows the byte
    is explicitly unlocked first, because Microsoft documents locks still pending at close as
    released by the OS only "depending on available system resources": relying on the close alone
    could leave a stop-then-immediate-relaunch spuriously refused under load (c1-9 review ruling).
    On POSIX ``flock`` drops synchronously with the open-file description. The file itself is
    deliberately left in place — see the module docstring; deleting it is a correctness bug.

    **Never raises.** This runs inside :func:`src.companion.app.server.run`'s outermost ``finally``,
    where a raise would replace whatever error was already propagating. A close that fails has left
    nothing for the caller to do, and the kernel releases the lock at process exit regardless.

    Args:
        fd: The descriptor returned by :func:`acquire_instance_lock`. Call this **at most once**
            per acquisition: once closed, the descriptor number can be reused by any later
            ``open``, and a second call would then close an unrelated descriptor — silently,
            because that close succeeds. A second call on a number that has *not* been reused, or
            one that was never opened, fails as ``EBADF``, which is logged and otherwise ignored.
    """
    if sys.platform == "win32":
        try:
            msvcrt.locking(fd, msvcrt.LK_UNLCK, _LOCK_BYTES)
        except OSError:
            # Nothing to unlock — the descriptor is already closed, or the lock call never
            # succeeded. The close below, or process exit, releases whatever remains.
            logger.debug("Explicit unlock of descriptor %d failed", fd, exc_info=True)
    try:
        os.close(fd)
    except OSError:
        logger.warning("Could not close the instance lock descriptor %d", fd, exc_info=True)
