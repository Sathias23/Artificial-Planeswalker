"""The held single-instance lock's real-descriptor contract (Story c1-9, AC 8-11, 15).

No mocks. Mocking ``msvcrt``/``fcntl`` would prove only that a mock was called, while the failure
this module exists to prevent — a second process getting the lock — lives in the kernel. Every test
here opens real descriptors against a real file under this test's own ``PLANESWALKER_DATA_DIR``
(the autouse ``isolated_data_dir`` fixture in ``conftest.py``), which is also what keeps them
contention-free against each other and against a companion the developer may actually be running.

The same-process contention case is only meaningful because of AC 9's primitive choice: ``flock``
is per open-file-description and Windows' ``msvcrt.locking`` denies a second descriptor outright,
whereas POSIX record locks (``lockf``/``F_SETLK``) are owned by the *process* and would hand the
second acquire a silent success. Swap the primitive and
:func:`test_a_second_descriptor_in_this_process_is_refused` goes red rather than vacuous.
"""

import errno
import os
import sys
import time
from pathlib import Path

import pytest

from src.companion.app import singleton


@pytest.fixture
def held_lock():
    """Yield an acquired lock descriptor and guarantee its release.

    Returns:
        The open descriptor :func:`~src.companion.app.singleton.acquire_instance_lock` returned.
    """
    fd = singleton.acquire_instance_lock()
    assert fd is not None, "the first acquire in an isolated data dir must succeed"
    try:
        yield fd
    finally:
        singleton.release_instance_lock(fd)


class TestLockPath:
    """``lock_path()`` resolves at call time, under the data directory, beside the rendezvous."""

    def test_lock_path_is_the_lock_filename_under_the_data_dir(self, tmp_path: Path):
        assert singleton.lock_path() == tmp_path / singleton.LOCK_FILENAME

    def test_lock_path_follows_the_data_dir_env_var(self, tmp_path, monkeypatch):
        """Resolution is at call time, so a later ``PLANESWALKER_DATA_DIR`` change is honoured."""
        elsewhere = tmp_path / "elsewhere"
        monkeypatch.setenv("PLANESWALKER_DATA_DIR", str(elsewhere))

        assert singleton.lock_path().parent == elsewhere

    def test_the_lock_file_is_not_the_discovery_file(self):
        """The lock carries no port, token or identity — it is a separate file (AC 10)."""
        from src.companion import discovery

        assert singleton.LOCK_FILENAME != discovery.COMPANION_FILENAME


class TestAcquireAndRelease:
    """Acquiring, contending and releasing — all against real descriptors."""

    def test_acquire_returns_an_open_descriptor(self, held_lock: int):
        assert isinstance(held_lock, int)
        assert os.fstat(held_lock).st_size == 0

    def test_acquire_creates_the_lock_file_under_the_data_dir(self, tmp_path: Path, held_lock: int):
        assert (tmp_path / singleton.LOCK_FILENAME).exists()

    def test_a_second_descriptor_in_this_process_is_refused(self, held_lock: int):
        """The non-vacuity anchor: ``flock``/``LK_NBLCK`` deny a second *descriptor*, not merely a
        second process — which is what makes this cheap test meaningful (AC 9, AC 15)."""
        assert singleton.acquire_instance_lock() is None

    def test_a_refused_acquire_returns_immediately(self, held_lock: int):
        """AC 9: non-blocking, and this is what makes that testable rather than merely intended.

        Without a deadline the blocking mutation is invisible to the suite: ``msvcrt.LK_LOCK``
        retries ten times at one-second intervals and *then* raises, which
        :func:`acquire_instance_lock` would report as ordinary contention — so every assertion
        about refusal still passes, ten seconds later each. Swapping ``LK_NBLCK`` for ``LK_LOCK``
        was measured at 591 s for this file against a 0.06 s baseline; this bound turns that hang
        into a failure. The threshold is deliberately loose: the real refusal takes microseconds,
        and the mutation takes ten seconds, so nothing lives near two.
        """
        started = time.monotonic()

        assert singleton.acquire_instance_lock() is None

        elapsed = time.monotonic() - started
        assert elapsed < 2.0, (
            f"a contended acquire took {elapsed:.1f}s — it must never block and retry "
            "(LK_NBLCK, not LK_LOCK; LOCK_EX | LOCK_NB, not a blocking flock)"
        )

    def test_release_then_acquire_succeeds(self):
        first = singleton.acquire_instance_lock()
        assert first is not None
        singleton.release_instance_lock(first)

        second = singleton.acquire_instance_lock()
        assert second is not None
        singleton.release_instance_lock(second)

    def test_the_lock_file_survives_a_release(self, tmp_path: Path):
        """Never unlinked: on POSIX ``flock`` binds to the inode, so unlink-and-recreate would hand
        a second process a different file to lock (AC 10, Decide-once #4)."""
        fd = singleton.acquire_instance_lock()
        assert fd is not None
        singleton.release_instance_lock(fd)

        lock_file = tmp_path / singleton.LOCK_FILENAME
        assert lock_file.exists()
        assert lock_file.stat().st_size == 0

    def test_the_refused_path_leaks_no_descriptor(self, held_lock: int):
        """AC 11's fd-close: many refusals in a row must not pin file handles open.

        The probe pins the *next descriptor number*: both platforms allocate the lowest free
        number, so 64 leaked descriptors would push the post-refusal probe 64 numbers higher.
        (The earlier proxy — a fresh acquire succeeds after the holder releases — passed
        identically with or without the leak, because leaked descriptors hold no lock.)
        """

        def next_fd_number() -> int:
            probe = os.open(os.devnull, os.O_RDONLY)
            os.close(probe)
            return probe

        before = next_fd_number()
        for _ in range(64):
            assert singleton.acquire_instance_lock() is None

        assert next_fd_number() == before, "the refusal path leaked its file descriptor"


class TestFailureSplit:
    """AC 11: exactly one failure is swallowed, and "cannot open at all" is not it."""

    def test_an_unopenable_path_propagates_oserror(self, tmp_path, monkeypatch):
        """A data directory we cannot open a file in must fail loudly, not read as contention.

        Contention reports as ``PermissionError`` on Windows — indistinguishable from a real
        permission problem — which is exactly why the ``os.open`` sits *outside* the guard.
        """
        unopenable = tmp_path / "no-such-directory" / singleton.LOCK_FILENAME
        monkeypatch.setattr(singleton, "lock_path", lambda: unopenable)

        with pytest.raises(OSError):
            singleton.acquire_instance_lock()

    def test_a_lock_call_failure_that_is_not_contention_propagates(self, monkeypatch):
        """Only "someone else has it" is swallowed (AC 11, c1-9 review ruling): a locking
        subsystem that cannot lock at all (``ENOLCK`` — NFS without lockd, some SMB/FUSE mounts)
        must fail loudly, not refuse with a message pointing at a companion that does not exist.

        The one deliberate seam-patch in this file: no filesystem on a dev machine raises
        ``ENOLCK``, so the errno is injected at the platform primitive.
        """

        def cannot_lock(*args: object) -> None:
            raise OSError(errno.ENOLCK, "No locks available")

        if sys.platform == "win32":
            monkeypatch.setattr(singleton.msvcrt, "locking", cannot_lock)
        else:
            monkeypatch.setattr(singleton.fcntl, "flock", cannot_lock)

        with pytest.raises(OSError) as excinfo:
            singleton.acquire_instance_lock()

        assert excinfo.value.errno == errno.ENOLCK

    def test_release_on_an_already_closed_descriptor_does_not_raise(self):
        """It runs in a ``finally``, where a raise would mask the error already propagating."""
        fd = singleton.acquire_instance_lock()
        assert fd is not None
        singleton.release_instance_lock(fd)

        singleton.release_instance_lock(fd)

    def test_release_on_a_never_opened_descriptor_does_not_raise(self):
        singleton.release_instance_lock(-1)


class TestModuleIsInert:
    """AD-10: nothing here may run at import, and no port number may be named (AC 19, gotcha 7)."""

    def test_importing_the_module_creates_no_data_directory(self, tmp_path, monkeypatch):
        import importlib

        never = tmp_path / "never-created"
        monkeypatch.setenv("PLANESWALKER_DATA_DIR", str(never))
        importlib.reload(singleton)

        assert not never.exists()

    def test_the_module_names_no_port_number(self):
        source = Path(singleton.__file__).read_text(encoding="utf-8")

        assert "8765" not in source
