"""Tests for SqliteStore persistence layer."""
import asyncio
import pytest
import tempfile
import os
from app.database import SqliteStore, _init_table, _get_next_id, _set_next_id


class TestStore(SqliteStore):
    _entity_name = "test_entities"
    _store: dict[int, dict] = {}
    _next_id: int = 1


class TestSqliteStoreBasic:
    def test_add_and_retrieve(self):
        import asyncio
        record = {"id": TestStore._persist_next_id(), "name": "test-item", "value": 42}
        result = asyncio.run(TestStore._persist_add(record))
        assert result["id"] == 1
        assert TestStore._store[1]["name"] == "test-item"

    def test_update(self):
        import asyncio
        record = {"id": TestStore._persist_next_id(), "name": "original", "value": 0}
        asyncio.run(TestStore._persist_add(record))
        updated = asyncio.run(TestStore._persist_update(1, {"value": 99}))
        assert updated["value"] == 99
        assert TestStore._store[1]["value"] == 99

    def test_delete(self):
        import asyncio
        record = {"id": TestStore._persist_next_id(), "name": "to-delete"}
        asyncio.run(TestStore._persist_add(record))
        assert 1 in TestStore._store
        result = asyncio.run(TestStore._persist_delete(1))
        assert result is True
        assert 1 not in TestStore._store

    def test_delete_nonexistent(self):
        import asyncio
        result = asyncio.run(TestStore._persist_delete(999))
        assert result is False


class TestNextId:
    def test_ids_increment(self):
        id1 = TestStore._persist_next_id()
        id2 = TestStore._persist_next_id()
        id3 = TestStore._persist_next_id()
        assert id1 == 1
        assert id2 == 2
        assert id3 == 3

    def test_ids_unique_across_calls(self):
        ids = {TestStore._persist_next_id() for _ in range(100)}
        assert len(ids) == 100  # All unique
