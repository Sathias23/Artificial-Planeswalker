"""Tests for the discovery file — the companion's sole rendezvous (c1-7, AD-4).

The leaf functions are driven **directly**: a leaf that needs an app to be tested is not a leaf.
Only the lifespan behaviours (publish, skip, retract, leak) go through the ``lifespan_client`` seam
on a real ``build_app()``.

House rules this file follows:

* fixtures write ``companion.json`` variants with plain ``Path.write_text`` / ``write_bytes``,
  never through ``write_discovery`` — a test whose fixture is built by the code under test proves
  nothing (c1-6's rule);
* assertions are on **observable filesystem state** — the file exists / does not / holds exactly
  these bytes / the directory has no leftovers — never "a mock went uncalled";
* every "returns ``None``" case is paired with a well-formed file that returns a populated record
  from the same call, so the reader cannot pass by refusing everything (c1-6 AC 14, after
  Greptile's PR #12 catch).
"""

import importlib
import json
import logging
import os
import sys

import pytest

from src.companion import discovery
from src.companion.app import main
from src.companion.app.main import build_app
from src.companion.discovery import (
    COMPANION_FILENAME,
    DiscoveryRecord,
    discovery_path,
    mint_token,
    read_discovery,
    remove_discovery,
    write_discovery,
)

_DISCOVERY_MODULE = "src.companion.discovery"
_FRESH_PREFIXES = ("src.companion", "src.paths")

VALID = {"port": 51234, "token": "a-token", "instance_id": "an-instance"}
"""A well-formed record body, written by hand so no test depends on the writer."""


def _write_raw(text: str) -> None:
    """Put *text* at the discovery path verbatim, bypassing :func:`write_discovery`."""
    discovery_path().write_text(text, encoding="utf-8")


def _fresh_discovery(monkeypatch):
    """Import ``src.companion.discovery`` from scratch, restoring ``sys.modules`` afterwards.

    Mirrors ``test_app.py::_fresh_main``: the module's top-level code must actually re-execute for
    an import-time ``data_dir()`` call to be observable at all.
    """
    dotted = tuple(prefix + "." for prefix in _FRESH_PREFIXES)
    stale = [name for name in sys.modules if name in _FRESH_PREFIXES or name.startswith(dotted)]
    for name in stale:
        monkeypatch.delitem(sys.modules, name)
    return importlib.import_module(_DISCOVERY_MODULE)


def _temp_leftovers(directory):
    """Return every file in *directory* that is not the discovery file itself."""
    return [path.name for path in directory.iterdir() if path.name != COMPANION_FILENAME]


# --------------------------------------------------------------------------------------
# AC 12 — the isolation fixture is active
# --------------------------------------------------------------------------------------


def test_the_isolation_fixture_is_active(tmp_path):
    """The autouse conftest fixture points discovery at this test's tmp_path, not the real dir.

    Deleting that fixture must turn a test red rather than quietly writing into the developer's
    ``%LOCALAPPDATA%``.
    """
    assert discovery_path().parent == tmp_path


# --------------------------------------------------------------------------------------
# AC 6 — the reader never raises; every unusable file is *app not running*
# --------------------------------------------------------------------------------------


def test_reader_returns_a_record_for_a_well_formed_file():
    """Non-vacuity anchor for the whole AC 6 matrix: a good file yields a populated record."""
    _write_raw(json.dumps(VALID))
    record = read_discovery()
    assert record is not None
    assert (record.port, record.token, record.instance_id) == (51234, "a-token", "an-instance")


def test_reader_returns_none_when_the_file_is_absent():
    """The ordinary case for a tool: nothing published yet (FileNotFoundError → OSError)."""
    assert not discovery_path().exists()
    assert read_discovery() is None


def test_reader_returns_none_when_a_directory_sits_at_the_path():
    """PermissionError on Windows, IsADirectoryError on POSIX — both OSError, both *not running*."""
    discovery_path().mkdir()
    assert read_discovery() is None


def test_reader_returns_none_for_bytes_that_are_not_json():
    """json.JSONDecodeError is a ValueError, so the single ``except`` catches it."""
    _write_raw("this is not json at all")
    assert read_discovery() is None


def test_reader_returns_none_for_a_truncated_write():
    """The half-written file this story's atomic write makes impossible is still read safely."""
    _write_raw(json.dumps(VALID)[: len(json.dumps(VALID)) // 2])
    assert read_discovery() is None


def test_reader_returns_none_for_bytes_that_are_not_utf8():
    """model_validate_json raises ValidationError (a ValueError) rather than UnicodeDecodeError."""
    discovery_path().write_bytes(b'{"port": 1, "token": "\xff\xfe", "instance_id": "x"}')
    assert read_discovery() is None


@pytest.mark.skipif(os.name == "nt", reason="chmod does not remove read access on Windows")
def test_reader_returns_none_when_the_file_is_unreadable():
    """PermissionError → OSError → *app not running*, never a crash in the caller."""
    path = discovery_path()
    path.write_text(json.dumps(VALID), encoding="utf-8")
    path.chmod(0o000)
    try:
        assert read_discovery() is None
    finally:
        path.chmod(0o600)


def test_reader_logs_a_rejection_at_debug_not_warning(caplog):
    """For c6-1's client the expected case is no file at all; a WARNING per push is noise."""
    _write_raw("not json")
    with caplog.at_level(logging.DEBUG, logger=discovery.__name__):
        assert read_discovery() is None
    assert caplog.records, "a rejected read should leave a diagnostic trail"
    assert {record.levelno for record in caplog.records} == {logging.DEBUG}


# --------------------------------------------------------------------------------------
# AC 7 — the reader validates shape, and ignores unknown keys
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("label", "body"),
    [
        ("empty object", {}),
        ("missing port", {"token": "t", "instance_id": "i"}),
        ("missing token", {"port": 1, "instance_id": "i"}),
        ("missing instance_id", {"port": 1, "token": "t"}),
        ("port zero", {**VALID, "port": 0}),
        ("port negative", {**VALID, "port": -1}),
        ("port above 65535", {**VALID, "port": 65536}),
        ("port not an int", {**VALID, "port": "not-a-port"}),
        ("empty token", {**VALID, "token": ""}),
        ("empty instance_id", {**VALID, "instance_id": ""}),
        ("token not a str", {**VALID, "token": 12345}),
        ("top-level list", [VALID]),
    ],
)
def test_reader_rejects_a_malformed_shape(label, body):
    """Every rejected shape reads as *app not running* — no exception reaches the caller."""
    _write_raw(json.dumps(body))
    assert read_discovery() is None, label


@pytest.mark.parametrize("port", [1, 8765, 65535])
def test_reader_accepts_every_port_at_and_inside_the_bounds(port):
    """Paired with the rejection matrix above: the bounds accept, they do not merely refuse."""
    _write_raw(json.dumps({**VALID, "port": port}))
    record = read_discovery()
    assert record is not None
    assert record.port == port


def test_reader_ignores_unknown_keys():
    """A newer backend that adds a field must not make an older reader report *not running*."""
    _write_raw(json.dumps({**VALID, "future_field": "from a later story", "another": [1, 2]}))
    record = read_discovery()
    assert record is not None
    assert record.port == 51234
    assert not hasattr(record, "future_field")


def test_the_filename_is_declared_once():
    """``COMPANION_FILENAME`` is the one place the name is written."""
    assert COMPANION_FILENAME == "companion.json"
    assert discovery_path().name == COMPANION_FILENAME


# --------------------------------------------------------------------------------------
# AC 2 — the location honours PLANESWALKER_DATA_DIR, and importing the leaf creates nothing
# --------------------------------------------------------------------------------------


def test_the_path_sits_under_an_overridden_data_dir(tmp_path, monkeypatch):
    """``discovery_path()`` goes through ``src.paths.data_dir()``, so the override reaches it."""
    override = tmp_path / "elsewhere"
    monkeypatch.setenv("PLANESWALKER_DATA_DIR", str(override))

    assert discovery_path() == override / COMPANION_FILENAME


def test_importing_the_leaf_creates_no_directory(tmp_path, monkeypatch):
    """``data_dir()`` mkdirs, so an import-time resolution would create the user's data directory.

    The sibling assertion to ``test_app.py::test_import_and_construction_create_no_directory``,
    made from the leaf's own side (AD-10).
    """
    never_created = tmp_path / "never-created"
    monkeypatch.setenv("PLANESWALKER_DATA_DIR", str(never_created))
    before = set(tmp_path.iterdir())

    module = _fresh_discovery(monkeypatch)

    assert module.COMPANION_FILENAME == "companion.json"
    assert not never_created.exists(), (
        "importing the discovery leaf resolved a data path — data_dir() mkdirs, so a stdio MCP "
        "session would create state merely by importing the module that finds the app (AD-10)"
    )
    assert set(tmp_path.iterdir()) == before


def test_the_path_is_resolved_at_call_time(tmp_path, monkeypatch):
    """Writer and reader can never disagree about the location: both re-resolve on every call."""
    first = tmp_path / "first"
    monkeypatch.setenv("PLANESWALKER_DATA_DIR", str(first))
    assert discovery_path().parent == first

    second = tmp_path / "second"
    monkeypatch.setenv("PLANESWALKER_DATA_DIR", str(second))
    assert discovery_path().parent == second


# --------------------------------------------------------------------------------------
# AC 3 — the write is atomic
# --------------------------------------------------------------------------------------


def test_write_then_read_round_trips():
    """Non-vacuity anchor for the atomicity tests below: the happy path really publishes."""
    record = DiscoveryRecord(port=51234, token="a-token", instance_id="an-instance")

    written = write_discovery(record)

    assert written == discovery_path()
    assert read_discovery() == record
    assert json.loads(written.read_text(encoding="utf-8")) == {
        "port": 51234,
        "token": "a-token",
        "instance_id": "an-instance",
    }


def test_write_leaves_no_temp_file_behind():
    """``mkstemp`` litter beside the real file would be a visible mess in the user's data dir."""
    write_discovery(DiscoveryRecord(port=1, token="t", instance_id="i"))

    assert _temp_leftovers(discovery_path().parent) == []


def test_write_succeeds_over_an_existing_file():
    """The second launch case — and the one ``os.rename`` would break on Windows only."""
    write_discovery(DiscoveryRecord(port=1, token="old", instance_id="first"))

    write_discovery(DiscoveryRecord(port=2, token="new", instance_id="second"))

    record = read_discovery()
    assert record is not None
    assert (record.port, record.token, record.instance_id) == (2, "new", "second")
    assert _temp_leftovers(discovery_path().parent) == []


def test_write_does_not_use_os_rename(monkeypatch):
    """Teeth: this goes red the instant someone "simplifies" ``os.replace`` to ``os.rename``.

    ``os.rename`` over an existing file raises ``FileExistsError`` on Windows (verified), so the
    substitution would ship a bug visible only on the primary dev platform, and only on the second
    launch after a stale file was left behind. The mutation is asserted directly rather than
    inferred from a mock's call count.
    """

    def boom(*args, **kwargs):
        raise AssertionError("write_discovery must use os.replace, never os.rename")

    write_discovery(DiscoveryRecord(port=1, token="old", instance_id="first"))
    monkeypatch.setattr(os, "rename", boom)

    write_discovery(DiscoveryRecord(port=2, token="new", instance_id="second"))

    record = read_discovery()
    assert record is not None
    assert record.port == 2


def test_an_interrupted_write_leaves_the_previous_file_intact(monkeypatch):
    """No reader can observe a partial file: the target is only ever moved into place whole."""
    write_discovery(DiscoveryRecord(port=1, token="old", instance_id="first"))
    before = discovery_path().read_bytes()

    def explode(*args, **kwargs):
        raise OSError("replace failed")

    monkeypatch.setattr(os, "replace", explode)

    with pytest.raises(OSError, match="replace failed"):
        write_discovery(DiscoveryRecord(port=2, token="new", instance_id="second"))

    assert discovery_path().read_bytes() == before, "the previous record was disturbed"
    assert _temp_leftovers(discovery_path().parent) == [], "a failed write left .tmp litter behind"


def test_an_interrupted_first_write_creates_no_file(monkeypatch):
    """With no previous file, a failed publish leaves the directory exactly as it was."""
    directory = discovery_path().parent

    def explode(*args, **kwargs):
        raise OSError("replace failed")

    monkeypatch.setattr(os, "replace", explode)

    with pytest.raises(OSError, match="replace failed"):
        write_discovery(DiscoveryRecord(port=1, token="t", instance_id="i"))

    assert not discovery_path().exists()
    assert list(directory.iterdir()) == []


def test_the_temp_file_is_created_in_the_target_directory(monkeypatch, tmp_path):
    """``os.replace`` is atomic only within one filesystem; the system temp dir may be elsewhere."""
    seen = {}
    real_mkstemp = discovery.tempfile.mkstemp

    def recording_mkstemp(*args, **kwargs):
        seen["dir"] = kwargs.get("dir")
        return real_mkstemp(*args, **kwargs)

    monkeypatch.setattr(discovery.tempfile, "mkstemp", recording_mkstemp)

    write_discovery(DiscoveryRecord(port=1, token="t", instance_id="i"))

    assert seen["dir"] == discovery_path().parent


# --------------------------------------------------------------------------------------
# AC 4 — the token is a per-process secret
# --------------------------------------------------------------------------------------


def test_minted_tokens_carry_full_entropy():
    """32 bytes of ``secrets`` entropy, rendered as 43 URL-safe characters."""
    token = mint_token()

    assert len(token) == 43
    assert token.strip() == token


def test_minted_tokens_are_never_repeated():
    """Two starts must not share a token — a restart invalidates the one a tool was holding."""
    minted = {mint_token() for _ in range(100)}

    assert len(minted) == 100


def test_the_token_is_absent_from_repr_and_str():
    """``Field(repr=False)`` stops a stray ``logger.info("%s", record)`` or traceback leaking it."""
    record = DiscoveryRecord(port=1, token="super-secret-value", instance_id="i")

    assert "super-secret-value" not in repr(record)
    assert "super-secret-value" not in str(record)
    assert "super-secret-value" not in f"{record}"


def test_the_token_is_still_serialized_to_the_file():
    """The pairing that rules out ``SecretStr``: a masked token would authenticate nothing."""
    record = DiscoveryRecord(port=1, token="super-secret-value", instance_id="i")

    assert json.loads(record.model_dump_json())["token"] == "super-secret-value"


# --------------------------------------------------------------------------------------
# AC 11 — clean shutdown removes our own entry, and only ours
# --------------------------------------------------------------------------------------


def test_removal_deletes_our_own_entry():
    """Non-vacuity anchor for the three refusal cases below."""
    write_discovery(DiscoveryRecord(port=1, token="t", instance_id="ours"))

    assert remove_discovery("ours") is True
    assert not discovery_path().exists()


def test_removal_leaves_a_foreign_entry_byte_for_byte():
    """A second dev instance (or a test) must not delete a live instance's rendezvous."""
    write_discovery(DiscoveryRecord(port=1, token="t", instance_id="theirs"))
    before = discovery_path().read_bytes()

    assert remove_discovery("ours") is False
    assert discovery_path().read_bytes() == before


def test_removal_with_no_file_is_a_clean_no_op():
    """A process that never published removes nothing — no special case needed (AC 9 composes)."""
    assert not discovery_path().exists()

    assert remove_discovery("ours") is False


def test_removal_leaves_an_unparseable_file_alone():
    """Unowned until proven otherwise: an unreadable record is not ours to delete."""
    _write_raw("not json at all")

    assert remove_discovery("ours") is False
    assert discovery_path().read_text(encoding="utf-8") == "not json at all"


def test_removal_swallows_and_logs_an_unlink_failure(monkeypatch, caplog):
    """On Windows another process holding the file open is enough — and teardown must not raise."""
    write_discovery(DiscoveryRecord(port=1, token="t", instance_id="ours"))

    def explode(*args, **kwargs):
        raise OSError("file is held open")

    monkeypatch.setattr(discovery.Path, "unlink", explode)

    with caplog.at_level(logging.WARNING, logger=discovery.__name__):
        assert remove_discovery("ours") is False

    assert any("Could not remove the discovery file" in r.getMessage() for r in caplog.records)


# --------------------------------------------------------------------------------------
# AC 8, 9, 10, 14 — the lifespan publishes the rendezvous, and is the only writer
# --------------------------------------------------------------------------------------


async def test_the_lifespan_publishes_the_port_it_actually_bound(lifespan_client):
    """The record names ``bound_port(app)``, so an ephemeral fallback is what lands in the file."""
    app = build_app()
    app.state.bound_port = 49999

    async with lifespan_client(app, bound_port=49999):
        record = read_discovery()
        assert record is not None
        assert record.port == 49999
        assert record.instance_id == app.state.instance_id
        assert record.token == main.agent_token(app)


async def test_the_published_record_round_trips_through_the_real_reader(lifespan_client):
    """Writer and reader agree — the same call a companion MCP tool will make in c6-1."""
    app = build_app()

    async with lifespan_client(app) as client:
        response = await client.get("/health")
        record = read_discovery()

    assert record is not None
    assert response.json()["instance_id"] == record.instance_id


async def test_no_bound_port_means_no_file(lifespan_client, caplog):
    """Nothing truthful to publish, so the publish is skipped at WARNING and startup continues."""
    app = build_app()

    with caplog.at_level(logging.WARNING, logger=main.__name__):
        async with lifespan_client(app, bound_port=None):
            assert not discovery_path().exists()

    assert any(record.levelno == logging.WARNING for record in caplog.records)


async def test_a_failed_publish_fails_the_launch(monkeypatch):
    """The publish sits *before* the lifespan ``try``, so uvicorn exits loudly (Decide-once #3)."""

    def explode(*args, **kwargs):
        raise OSError("data directory is unwritable")

    monkeypatch.setattr(discovery, "write_discovery", explode)
    app = build_app()
    app.state.bound_port = 49999

    with pytest.raises(OSError, match="data directory is unwritable"):
        async with main.lifespan(app):
            pytest.fail("startup should not have completed")


async def test_a_clean_shutdown_retracts_the_rendezvous(lifespan_client):
    """The epic AC: the discovery file is removed on clean shutdown."""
    app = build_app()

    async with lifespan_client(app):
        assert discovery_path().exists()

    assert not discovery_path().exists()


async def test_shutdown_leaves_a_foreign_entry_byte_for_byte(lifespan_client):
    """The ownership guard, driven through the real teardown rather than the leaf alone."""
    app = build_app()

    async with lifespan_client(app):
        # Another instance replaces our file while we are running (c1-8's whole subject).
        _write_raw(json.dumps({"port": 1, "token": "theirs", "instance_id": "another-instance"}))
        before = discovery_path().read_bytes()

    assert discovery_path().exists(), "shutdown deleted a live instance's rendezvous"
    assert discovery_path().read_bytes() == before


def test_agent_token_is_none_before_the_lifespan_runs():
    """Same shape as ``bound_port``: ``None`` means the lifespan never ran."""
    assert main.agent_token(build_app()) is None


async def test_agent_token_returns_the_minted_credential(lifespan_client):
    """AC 5's leak test needs to know the string it is searching for."""
    app = build_app()

    async with lifespan_client(app):
        token = main.agent_token(app)

    assert token is not None
    assert len(token) == 43


# --------------------------------------------------------------------------------------
# AC 5 — the token appears in no log line, no REST response and no schema (AD-5)
# --------------------------------------------------------------------------------------


async def test_the_token_leaks_into_no_log_response_or_schema(lifespan_client, caplog):
    """Four surfaces, one lifespan: logs (root, DEBUG), the health body, headers, and the schema.

    ``record.args`` is inspected as well as ``record.getMessage()`` because a ``%``-style record
    hides its arguments from the unformatted ``msg`` — belt and braces on a credential.
    """
    app = build_app()

    with caplog.at_level(logging.DEBUG):
        async with lifespan_client(app) as client:
            token = main.agent_token(app)
            response = await client.get("/health")
            schema = json.dumps(app.openapi())
            # Read while the app is still up: teardown retracts the file (AC 11).
            published = read_discovery()

    assert token is not None
    assert caplog.records, "nothing was captured — the leak check would be vacuous"

    for entry in caplog.records:
        assert token not in entry.getMessage(), f"token leaked into a log message: {entry.name}"
        assert token not in repr(entry.args), f"token leaked into log args: {entry.name}"

    assert token not in response.text
    assert token not in repr(dict(response.headers))
    assert token not in schema
    # Non-vacuity: the token really is discoverable somewhere — just not on those four surfaces.
    assert published is not None
    assert published.token == token
