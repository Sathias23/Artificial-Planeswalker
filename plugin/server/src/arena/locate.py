"""Find the MTG Arena client's log and local card database on this machine.

Both are resolved fresh on every call and never cached: the client renames ``Player.log`` to
``Player-prev.log`` each time it starts, and replaces the card database on a content update.

Only the Windows locations are verified against a live client. The macOS and Linux (Steam Proton)
candidates follow the same layout and are best effort; ``MTGA_LOG_PATH``, ``MTGA_CARD_DATABASE``
and ``MTGA_INSTALL_DIR`` override discovery on any platform.
"""

import os
import sys
from pathlib import Path

LOG_PATH_ENV = "MTGA_LOG_PATH"
CARD_DATABASE_ENV = "MTGA_CARD_DATABASE"
INSTALL_DIR_ENV = "MTGA_INSTALL_DIR"

_LOG_RELATIVE = Path("Wizards Of The Coast") / "MTGA" / "Player.log"
_STEAM_APP_ID = "2141910"
_CARD_DATABASE_GLOB = "Raw_CardDatabase_*.mtga"


def player_log_candidates() -> list[Path]:
    """Return where ``Player.log`` may live, most specific first.

    Returns:
        ``MTGA_LOG_PATH`` alone when it is set (an explicit override is never second-guessed),
        otherwise the default location for this platform.
    """
    override = os.getenv(LOG_PATH_ENV)
    if override:
        return [Path(override).expanduser()]

    home = Path.home()
    if sys.platform == "win32":
        return [home / "AppData" / "LocalLow" / _LOG_RELATIVE]
    if sys.platform == "darwin":
        return [home / "Library" / "Logs" / _LOG_RELATIVE]
    proton_home = (
        Path("steamapps") / "compatdata" / _STEAM_APP_ID / "pfx" / "drive_c" / "users" / "steamuser"
    )
    return [
        steam_root / proton_home / "AppData" / "LocalLow" / _LOG_RELATIVE
        for steam_root in (home / ".steam" / "steam", home / ".local" / "share" / "Steam")
    ]


def find_player_log() -> Path | None:
    """Return the first existing ``Player.log`` candidate, or ``None`` when there is none."""
    for candidate in player_log_candidates():
        if candidate.is_file():
            return candidate
    return None


def _install_dir_candidates(hint: Path | None) -> list[Path]:
    """Return directories that may hold the client's downloaded data, most specific first."""
    candidates: list[Path] = []
    override = os.getenv(INSTALL_DIR_ENV)
    if override:
        candidates.append(Path(override).expanduser())
    if hint is not None:
        candidates.append(hint)
    if sys.platform == "win32":
        for variable, default in (
            ("ProgramFiles", r"C:\Program Files"),
            ("ProgramFiles(x86)", r"C:\Program Files (x86)"),
        ):
            root = Path(os.getenv(variable) or default)
            candidates.append(root / "Wizards of the Coast" / "MTGA")
            candidates.append(root / "Steam" / "steamapps" / "common" / "MTGA")
            candidates.append(root / "Epic Games" / "MagicTheGathering")
    elif sys.platform == "darwin":
        candidates.append(Path.home() / "Library" / "Application Support" / "com.wizards.mtga")
    return candidates


def find_card_database(install_dir_hint: Path | None = None) -> Path | None:
    """Return the client's local card database file, or ``None`` when it cannot be found.

    Args:
        install_dir_hint: The install directory the log itself names (see
            :func:`src.arena.log_reader.scan_log`), which finds a client installed anywhere.

    Returns:
        ``MTGA_CARD_DATABASE`` when it names an existing file; otherwise the newest
        ``Raw_CardDatabase_*.mtga`` under the first candidate directory that has one.
    """
    override = os.getenv(CARD_DATABASE_ENV)
    if override:
        path = Path(override).expanduser()
        return path if path.is_file() else None

    for install_dir in _install_dir_candidates(install_dir_hint):
        for raw_dir in (
            install_dir / "MTGA_Data" / "Downloads" / "Raw",
            install_dir / "Downloads" / "Raw",
        ):
            try:
                found = sorted(
                    raw_dir.glob(_CARD_DATABASE_GLOB), key=lambda p: p.stat().st_mtime, reverse=True
                )
            except OSError:
                continue
            if found:
                return found[0]
    return None
