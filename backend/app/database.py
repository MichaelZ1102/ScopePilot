"""SQLite persistence for in-memory stores.

Replaces JSON FileStore with a proper SQLite database.
Zero external dependencies — uses Python's built-in sqlite3.
ACID transactions, single file, no corruption risk.

Data file: ~/.scopepilot/scopepilot.db
"""
import json
import logging
import sqlite3
import threading
from pathlib import Path
from typing import Optional, Any
from datetime import datetime
import asyncio

logger = logging.getLogger(__name__)

# ── Database file ────────────────────────────────────────────────────────
DB_DIR = Path.home() / ".scopepilot"
DB_PATH = DB_DIR / "scopepilot.db"

# Thread-local connections (sqlite3 is not thread-safe by default)
_local = threading.local()


def _get_conn() -> sqlite3.Connection:
    """Get a thread-local SQLite connection."""
    if not hasattr(_local, "conn") or _local.conn is None:
        DB_DIR.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(DB_PATH), check_same_thread=False, timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA busy_timeout=5000")
        # Checkpoint and truncate WAL on fresh connection
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.row_factory = sqlite3.Row
        _local.conn = conn
    return _local.conn


def _init_table(entity: str):
    """Create the data table and meta table if they don't exist."""
    conn = _get_conn()
    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS "{entity}" (
            id INTEGER PRIMARY KEY,
            data TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS _meta (
            entity TEXT PRIMARY KEY,
            next_id INTEGER NOT NULL DEFAULT 1
        )
    """)
    # Ensure meta row exists
    conn.execute(
        "INSERT OR IGNORE INTO _meta (entity, next_id) VALUES (?, 1)",
        (entity,),
    )
    conn.commit()


def _get_next_id(entity: str) -> int:
    """Atomically increment and return the next ID for an entity."""
    conn = _get_conn()
    cur = conn.execute(
        "UPDATE _meta SET next_id = next_id + 1 WHERE entity = ? RETURNING next_id",
        (entity,),
    )
    row = cur.fetchone()
    conn.commit()
    if row and row[0] is not None:
        return row[0] - 1  # RETURNING gives the NEW value; subtract 1 for the old value
    return 1


def _set_next_id(entity: str, value: int):
    """Set the next_id for an entity (used when loading from DB)."""
    conn = _get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO _meta (entity, next_id) VALUES (?, ?)",
        (entity, value),
    )
    conn.commit()


def _upsert(entity: str, record_id: int, data: dict):
    """Insert or replace a record."""
    conn = _get_conn()
    conn.execute(
        f'INSERT OR REPLACE INTO "{entity}" (id, data) VALUES (?, ?)',
        (record_id, _to_json(data)),
    )
    conn.commit()


def _delete(entity: str, record_id: int):
    """Delete a record."""
    conn = _get_conn()
    conn.execute(f'DELETE FROM "{entity}" WHERE id = ?', (record_id,))
    conn.commit()


def _load_all(entity: str) -> list[dict]:
    """Load all records for an entity from SQLite."""
    conn = _get_conn()
    try:
        cur = conn.execute(f'SELECT id, data FROM "{entity}"')
        rows = cur.fetchall()
        records = []
        for row in rows:
            rec = _from_json(row["data"])
            rec["id"] = row["id"]
            records.append(rec)
        return records
    except sqlite3.OperationalError:
        # Table doesn't exist yet
        return []


def _to_json(data: dict) -> str:
    """Serialize dict to JSON string with datetime support."""
    return json.dumps(data, default=_json_default, ensure_ascii=False)


def _json_default(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    return str(obj)


def _from_json(s: str) -> dict:
    """Deserialize JSON string to dict."""
    return json.loads(s)


# ── SqliteStore — drop-in replacement for FileStore ──────────────────────

class SqliteStore:
    """Mixin for in-memory stores backed by SQLite.

    Usage (identical to FileStore):
        class MyStore(SqliteStore):
            _entity_name = "my_entities"  # SQLite table name
            _store: dict[int, dict] = {}
            _next_id: int = 1
    """
    _entity_name: str = ""  # set by subclass — used as SQLite table name

    @classmethod
    def _save_to_disk(cls):
        """Write-through: sync one record to SQLite.
        
        Called after every in-memory write. Persists the entire store
        in batch to avoid N+1 writes.
        """
        if not cls._entity_name:
            return
        try:
            _init_table(cls._entity_name)
            # Batch upsert all records
            conn = _get_conn()
            conn.execute(f'DELETE FROM "{cls._entity_name}"')
            data_rows = []
            for rid, rec in cls._store.items():
                rec_safe = {k: v for k, v in rec.items() if k != "id"}
                data_rows.append((rid, _to_json(rec_safe)))
            conn.executemany(
                f'INSERT INTO "{cls._entity_name}" (id, data) VALUES (?, ?)',
                data_rows,
            )
            _set_next_id(cls._entity_name, cls._next_id)
            conn.commit()
        except Exception as e:
            logger.warning(f"SQLite save failed for {cls._entity_name}: {e}")

    @classmethod
    def _load_from_disk(cls):
        """Load all records from SQLite into in-memory store."""
        if not cls._entity_name:
            return
        try:
            _init_table(cls._entity_name)
            records = _load_all(cls._entity_name)
            cls._store.clear()
            max_id = 0
            for rec in records:
                rid = rec.get("id", 0)
                cls._store[rid] = rec
                max_id = max(max_id, rid)
            if records:
                cls._next_id = max_id + 1
                _set_next_id(cls._entity_name, cls._next_id)
            logger.info(f"Loaded {len(records)} records from SQLite table '{cls._entity_name}'")
        except Exception as e:
            logger.warning(f"SQLite load failed for {cls._entity_name}: {e}")

    @classmethod
    async def _persist_add(cls, record: dict) -> dict:
        """Add a record and persist via single-row upsert."""
        cls._store[record["id"]] = record
        _init_table(cls._entity_name)
        rec_safe = {k: v for k, v in record.items() if k != "id"}
        await asyncio.to_thread(_upsert, cls._entity_name, record["id"], rec_safe)
        return record

    @classmethod
    async def _persist_update(cls, record_id: int, updates: dict) -> Optional[dict]:
        """Update a record in the store and persist via single-row upsert."""
        record = cls._store.get(record_id)
        if record is None:
            return None
        record.update(updates)
        _init_table(cls._entity_name)
        rec_safe = {k: v for k, v in record.items() if k != "id"}
        await asyncio.to_thread(_upsert, cls._entity_name, record_id, rec_safe)
        return record

    @classmethod
    async def _persist_delete(cls, record_id: int) -> bool:
        """Delete a record and persist via single-row delete."""
        if record_id in cls._store:
            del cls._store[record_id]
            _init_table(cls._entity_name)
            await asyncio.to_thread(_delete, cls._entity_name, record_id)
            return True
        return False

    @classmethod
    def _persist_next_id(cls) -> int:
        """Get next ID and advance counter."""
        rid = cls._next_id
        cls._next_id += 1
        # Don't save every ID increment — only on actual data writes
        return rid

    @classmethod
    def _load_all_at_startup(cls):
        """Convenience: call this at module level or app startup."""
        cls._load_from_disk()
