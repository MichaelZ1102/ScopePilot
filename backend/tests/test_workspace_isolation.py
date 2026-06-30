"""Tests for workspace isolation (cross-workspace access prevention)."""
"""Tests for workspace isolation (cross-workspace access prevention)."""
import asyncio
import pytest
from datetime import datetime, timezone

from app.api.v1.projects import ProjectStore, _projects, _next_id


def _make_project(pid: int, name: str, ws_id: int) -> dict:
    return {
        "id": pid,
        "name": name,
        "jira_url": "https://jira.test.com",
        "jira_email": "test@test.com",
        "jira_api_token": "encrypted-token",
        "jira_project_key": "TEST",
        "workspace_id": ws_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


class TestWorkspaceIsolation:
    def setup_method(self):
        ProjectStore._store.clear()
        ProjectStore._next_id = 1

    def test_list_projects_filters_by_workspace(self):
        asyncio.run(ProjectStore._persist_add(_make_project(1, "Project-A", ws_id=1)))
        asyncio.run(ProjectStore._persist_add(_make_project(2, "Project-B", ws_id=1)))
        asyncio.run(ProjectStore._persist_add(_make_project(3, "Project-C", ws_id=2)))

        ws1_projects = [p for p in _projects.values() if p["workspace_id"] == 1]
        ws2_projects = [p for p in _projects.values() if p["workspace_id"] == 2]

        assert len(ws1_projects) == 2
        assert len(ws2_projects) == 1
        assert all(p["workspace_id"] == 1 for p in ws1_projects)

    def test_cannot_access_other_workspace_project(self):
        asyncio.run(ProjectStore._persist_add(_make_project(1, "Secret-Project", ws_id=2)))

        # User from workspace 1 should NOT see project 1
        project = _projects.get(1)
        assert project is not None
        assert project["workspace_id"] == 2

        # This simulates the access check: project["workspace_id"] != ws_id → 404
        def access_check(project_id, token_ws_id):
            p = _projects.get(project_id)
            if not p or p["workspace_id"] != token_ws_id:
                raise PermissionError("Cross-workspace access denied")
            return p

        with pytest.raises(PermissionError, match="Cross-workspace access denied"):
            access_check(1, token_ws_id=1)

        # Same user accessing their own workspace succeeds
        asyncio.run(ProjectStore._persist_add(_make_project(2, "My-Project", ws_id=1)))
        result = access_check(2, token_ws_id=1)
        assert result["name"] == "My-Project"
