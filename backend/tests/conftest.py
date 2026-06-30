"""Test fixtures and configuration for ScopePilot backend tests.

All tests use isolated in-memory stores (reset between tests)
and a temporary SQLite database in tmp_path.
"""
import os
import pathlib
import pytest
from typing import Generator, Any

# ── Force no real DB, use isolated SQLite ────────────────────────────────
os.environ["DATABASE_URL"] = ""
os.environ["SECRET_KEY"] = "test-secret-key-for-unit-tests-only"

# Import must come after env setup
from app.database import SqliteStore, DB_DIR, DB_PATH


@pytest.fixture(autouse=True)
def _isolate_db(tmp_path: pathlib.Path) -> Generator[None, Any, None]:
    """Replace the global DB path with a temp file for each test.

    Also resets all SqliteStore subclass in-memory stores to empty.
    """
    # Redirect DB to tmp
    original_db_dir = DB_DIR
    original_db_path = DB_PATH
    
    new_dir = tmp_path / ".scopepilot"
    new_dir.mkdir()
    
    import app.database as db_mod
    db_mod.DB_DIR = new_dir
    db_mod.DB_PATH = new_dir / "scopepilot.db"

    # Reset all SqliteStore subclass stores
    for cls in SqliteStore.__subclasses__():
        cls._store.clear()
        cls._next_id = 1

    # Clear threading local connections (prevent stale connections to old DB)
    if hasattr(db_mod._local, "conn") and db_mod._local.conn is not None:
        try:
            db_mod._local.conn.close()
        except Exception:
            pass
        db_mod._local.conn = None

    # Reset team billing store
    from app.services.team import _billing
    _billing.clear()

    # Reset token blacklist
    from app.services import _blacklisted_tokens
    _blacklisted_tokens.clear()

    yield

    # Restore
    db_mod.DB_DIR = original_db_dir
    db_mod.DB_PATH = original_db_path
