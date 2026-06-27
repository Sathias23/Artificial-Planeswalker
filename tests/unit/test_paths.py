"""Unit tests for the central data-path resolver (``src/paths.py``)."""

import pytest

import src.paths as paths
from src.paths import data_dir, database_path, database_url, fastembed_cache_dir


def test_data_dir_honors_override(tmp_path, monkeypatch) -> None:
    """PLANESWALKER_DATA_DIR overrides the OS default and the directory is created."""
    target = tmp_path / "pw_data"
    monkeypatch.setenv("PLANESWALKER_DATA_DIR", str(target))
    resolved = data_dir()
    assert resolved == target
    assert resolved.is_dir()


def test_data_dir_default_uses_platformdirs(tmp_path, monkeypatch) -> None:
    """With no override, data_dir() delegates to platformdirs (app name, no author) and mkdirs."""
    monkeypatch.delenv("PLANESWALKER_DATA_DIR", raising=False)
    recorded: dict[str, object] = {}
    fake = tmp_path / "artificial-planeswalker"

    def fake_user_data_dir(app: str, *args: object, **kwargs: object) -> str:
        recorded["app"] = app
        recorded["appauthor"] = kwargs.get("appauthor")
        return str(fake)

    monkeypatch.setattr(paths, "user_data_dir", fake_user_data_dir)
    resolved = data_dir()
    assert recorded["app"] == "artificial-planeswalker"
    assert recorded["appauthor"] is False
    assert resolved == fake
    assert resolved.is_absolute()
    assert resolved.is_dir()


@pytest.mark.parametrize("blank", ["", "   "])
def test_blank_override_falls_back_to_default(tmp_path, monkeypatch, blank) -> None:
    """An empty or whitespace-only PLANESWALKER_DATA_DIR is treated as unset."""
    fake = tmp_path / "artificial-planeswalker"
    monkeypatch.setattr(paths, "user_data_dir", lambda *a, **k: str(fake))
    monkeypatch.setenv("PLANESWALKER_DATA_DIR", blank)
    assert data_dir() == fake


def test_relative_override_resolved_to_absolute(tmp_path, monkeypatch) -> None:
    """A relative PLANESWALKER_DATA_DIR is resolved to an absolute path (CWD-anchored)."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PLANESWALKER_DATA_DIR", "pw_rel")
    resolved = data_dir()
    assert resolved.is_absolute()
    assert resolved == (tmp_path / "pw_rel").resolve()


def test_database_path_under_data_dir(tmp_path, monkeypatch) -> None:
    """cards.db nests directly under the data dir."""
    monkeypatch.setenv("PLANESWALKER_DATA_DIR", str(tmp_path))
    assert database_path() == tmp_path / "cards.db"


def test_fastembed_cache_dir_under_data_dir(tmp_path, monkeypatch) -> None:
    """The model cache nests under the data dir and is created."""
    monkeypatch.setenv("PLANESWALKER_DATA_DIR", str(tmp_path))
    cache = fastembed_cache_dir()
    assert cache == tmp_path / "fastembed_cache"
    assert cache.is_dir()


def test_database_url_prefers_explicit_env(tmp_path, monkeypatch) -> None:
    """An explicit CARDS_DATABASE_URL wins over the central default (back-compat)."""
    monkeypatch.setenv("PLANESWALKER_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("CARDS_DATABASE_URL", "sqlite+aiosqlite:///./data/cards.db")
    assert database_url() == "sqlite+aiosqlite:///./data/cards.db"


def test_database_url_defaults_to_central(tmp_path, monkeypatch) -> None:
    """With no CARDS_DATABASE_URL, the URL targets cards.db in the central dir (posix form)."""
    monkeypatch.delenv("CARDS_DATABASE_URL", raising=False)
    monkeypatch.setenv("PLANESWALKER_DATA_DIR", str(tmp_path))
    expected = f"sqlite+aiosqlite:///{(tmp_path / 'cards.db').as_posix()}"
    assert database_url() == expected
