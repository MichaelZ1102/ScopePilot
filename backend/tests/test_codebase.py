"""Tests for CodebaseService: code source CRUD, repo scanning, code impact analysis."""
import asyncio
import pytest
from datetime import datetime, timezone

from app.services.codebase import (
    CodebaseService, CodebaseError,
    CodeSourceStore, RepoSnapshotStore, CodeImpactStore,
    _code_sources, _repo_snapshots, _code_impacts,
)


class TestCodeSourceCRUD:
    """Code Source create, list, get, delete."""

    WS_ID = 1

    def test_create_source(self):
        source = asyncio.run(CodebaseService.create_source({
            "name": "Test Repo",
            "provider": "github",
            "repo_url": "https://github.com/owner/repo",
            "default_branch": "main",
        }, workspace_id=self.WS_ID))

        assert source["id"] == 1
        assert source["name"] == "Test Repo"
        assert source["provider"] == "github"
        assert source["scan_status"] == "pending"
        assert source["workspace_id"] == self.WS_ID
        assert "created_at" in source

    def test_list_sources(self):
        asyncio.run(CodebaseService.create_source({"name": "A", "repo_url": "https://a.com"}, self.WS_ID))
        asyncio.run(CodebaseService.create_source({"name": "B", "repo_url": "https://b.com"}, self.WS_ID))

        sources = CodebaseService.list_sources(self.WS_ID)
        assert len(sources) == 2

        # Other workspace should see nothing
        assert len(CodebaseService.list_sources(99)) == 0

    def test_get_source(self):
        s = asyncio.run(CodebaseService.create_source({"name": "X", "repo_url": "https://x.com"}, self.WS_ID))

        found = CodebaseService.get_source(s["id"], self.WS_ID)
        assert found is not None
        assert found["name"] == "X"

        # Wrong workspace
        assert CodebaseService.get_source(s["id"], 99) is None

    def test_delete_source(self):
        s = asyncio.run(CodebaseService.create_source({"name": "X", "repo_url": "https://x.com"}, self.WS_ID))
        assert asyncio.run(CodebaseService.delete_source(s["id"], self.WS_ID)) is True
        assert CodebaseService.get_source(s["id"], self.WS_ID) is None

    def test_delete_source_wrong_workspace(self):
        s = asyncio.run(CodebaseService.create_source({"name": "X", "repo_url": "https://x.com"}, self.WS_ID))
        assert asyncio.run(CodebaseService.delete_source(s["id"], 99)) is False
        assert CodebaseService.get_source(s["id"], self.WS_ID) is not None


class TestCodeImpactAnalysis:
    """Keyword-based code impact analysis."""

    WS_ID = 1
    SPRINT_ID = 10
    TICKET_ID = 100

    def _setup_source_with_files(self, files: list[str]) -> int:
        source = asyncio.run(CodebaseService.create_source({
            "name": "Impact Test",
            "repo_url": "https://github.com/owner/repo",
        }, self.WS_ID))

        # Manually create a snapshot with file tree
        snap_id = RepoSnapshotStore._persist_next_id()
        _repo_snapshots[snap_id] = {
            "id": snap_id,
            "code_source_id": source["id"],
            "branch": "main",
            "commit_sha": "abc123",
            "file_tree": {"files": files, "dirs": []},
            "language_breakdown": {"Python": 5000},
            "total_files": len(files),
            "total_lines": 1000,
            "scanned_at": datetime.now(timezone.utc).isoformat(),
        }
        return source["id"]

    def test_impact_keyword_match(self):
        source_id = self._setup_source_with_files([
            "src/api/users.py",
            "src/api/products.py",
            "src/models/user.py",
            "tests/test_users.py",
            "config/settings.py",
        ])

        impact = asyncio.run(CodebaseService.analyze_impact(
            source_id=source_id,
            ticket_id=self.TICKET_ID,
            sprint_id=self.SPRINT_ID,
            workspace_id=self.WS_ID,
            ticket_summary="User management API endpoint",
            ticket_description="Update the user profile endpoint",
        ))

        assert impact["ticket_id"] == self.TICKET_ID
        assert impact["sprint_id"] == self.SPRINT_ID
        assert len(impact["affected_files"]) > 0
        assert any("users" in f["path"] for f in impact["affected_files"])

    def test_impact_no_match(self):
        source_id = self._setup_source_with_files([
            "src/inventory.py",
            "src/shipping.py",
        ])

        impact = asyncio.run(CodebaseService.analyze_impact(
            source_id=source_id,
            ticket_id=self.TICKET_ID,
            sprint_id=self.SPRINT_ID,
            workspace_id=self.WS_ID,
            ticket_summary="Billing system overhaul",
        ))

        # No match keywords — should still return with empty files
        assert impact["affected_files"] == []

    def test_impact_no_snapshot_raises(self):
        source = asyncio.run(CodebaseService.create_source({
            "name": "No Scan",
            "repo_url": "https://github.com/owner/repo",
        }, self.WS_ID))

        with pytest.raises(CodebaseError, match="No snapshot available"):
            asyncio.run(CodebaseService.analyze_impact(
                source_id=source["id"],
                ticket_id=self.TICKET_ID,
                sprint_id=self.SPRINT_ID,
                workspace_id=self.WS_ID,
            ))

    def test_get_impacts_for_sprint(self):
        source_id = self._setup_source_with_files(["src/main.py"])
        asyncio.run(CodebaseService.analyze_impact(source_id, self.TICKET_ID, self.SPRINT_ID, self.WS_ID, ticket_summary="main fix"))
        asyncio.run(CodebaseService.analyze_impact(source_id, 101, self.SPRINT_ID, self.WS_ID, ticket_summary="another fix"))

        impacts = CodebaseService.get_impacts_for_sprint(self.SPRINT_ID, self.WS_ID)
        assert len(impacts) == 2

    def test_get_impact_for_ticket(self):
        source_id = self._setup_source_with_files(["src/main.py"])
        asyncio.run(CodebaseService.analyze_impact(source_id, self.TICKET_ID, self.SPRINT_ID, self.WS_ID, ticket_summary="fix"))

        impact = CodebaseService.get_impact_for_ticket(self.TICKET_ID, self.WS_ID)
        assert impact is not None
        assert impact["ticket_id"] == self.TICKET_ID
