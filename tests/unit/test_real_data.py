"""The shared real-data helpers open the developer's database without writing beside it."""

import sqlite3
from pathlib import Path

from sqlalchemy import text

from src.data.database import create_engine
from tests.fixtures.real_data import read_only_url


async def test_the_read_only_url_opens_a_path_holding_uri_characters(tmp_path: Path):
    """An unquoted ``#`` or ``%`` in the data dir would make SQLite open a different, empty file."""
    db_dir = tmp_path / "data#dir%20"
    db_dir.mkdir()
    db_file = db_dir / "cards.db"
    seed = sqlite3.connect(db_file)
    with seed:
        seed.execute("CREATE TABLE marker (x INTEGER)")
        seed.execute("INSERT INTO marker VALUES (42)")
    seed.close()

    engine = create_engine(read_only_url(db_file), ensure_indexes=False)
    try:
        async with engine.connect() as conn:
            assert (await conn.execute(text("SELECT x FROM marker"))).scalar_one() == 42
    finally:
        await engine.dispose()
    assert sorted(path.name for path in db_dir.iterdir()) == ["cards.db"]
