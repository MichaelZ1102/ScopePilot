"""API route integration tests — test all Phase 2-5 endpoints with TestClient.

Uses in-memory stores (no database needed) and a test FastAPI app.
"""
import pytest
from fastapi.testclient import TestClient
from datetime import datetime

from app.main import app


client = TestClient(app)


# ── Helper: get a valid JWT token for testing ────────────────────────────

def _make_token(workspace_id: int = 1, sub: str = "test@test.com") -> str:
    from app.services import create_access_token as cat
    return cat({"sub": sub, "user_id": 1, "workspace_id": workspace_id})


AUTH_HEADER = {"Authorization": f"Bearer {_make_token()}"}
WS2_HEADER = {"Authorization": f"Bearer {_make_token(workspace_id=2)}"}

API_PREFIX = "/api/v1"


class TestCodeSourceAPI:
    """Code source CRUD + scan trigger endpoints."""

    BASE = f"{API_PREFIX}/code-sources/"

    def test_list_empty(self):
        resp = client.get(self.BASE, headers=AUTH_HEADER)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_create_source(self):
        resp = client.post(self.BASE, json={
            "name": "Test Repo",
            "provider": "github",
            "repo_url": "https://github.com/owner/repo",
        }, headers=AUTH_HEADER)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Test Repo"
        assert data["scan_status"] == "pending"

    def test_get_source(self):
        created = client.post(self.BASE, json={
            "name": "My Repo", "repo_url": "https://github.com/a/b",
        }, headers=AUTH_HEADER).json()

        resp = client.get(f"/api/v1/code-sources/{created['id']}", headers=AUTH_HEADER)
        assert resp.status_code == 200
        assert resp.json()["name"] == "My Repo"

    def test_get_source_404(self):
        resp = client.get("/api/v1/code-sources/9999", headers=AUTH_HEADER)
        assert resp.status_code == 404

    def test_get_source_wrong_ws(self):
        created = client.post(self.BASE, json={
            "name": "X", "repo_url": "https://github.com/a/b",
        }, headers=AUTH_HEADER).json()

        resp = client.get(f"/api/v1/code-sources/{created['id']}", headers=WS2_HEADER)
        assert resp.status_code == 404

    def test_delete_source(self):
        created = client.post(self.BASE, json={
            "name": "Del", "repo_url": "https://github.com/a/b",
        }, headers=AUTH_HEADER).json()

        resp = client.delete(f"/api/v1/code-sources/{created['id']}", headers=AUTH_HEADER)
        assert resp.status_code == 204

    def test_unauthorized(self):
        resp = client.get(self.BASE)
        assert resp.status_code == 401

    def test_scan_trigger_no_such_source(self):
        resp = client.post("/api/v1/code-sources/9999/scan", headers=AUTH_HEADER)
        assert resp.status_code == 400  # CodebaseError → 400


class TestApiSpecAPI:
    """OpenAPI spec import and test plan generation."""

    BASE = f"{API_PREFIX}/api-tests"

    SAMPLE_SPEC = """
    {
        "openapi": "3.0.0",
        "info": {"title": "Test API", "version": "1.0"},
        "paths": {
            "/items": {
                "get": {
                    "summary": "List items",
                    "tags": ["items"],
                    "responses": {"200": {"description": "OK"}}
                }
            }
        }
    }
    """

    def test_import_from_content(self):
        resp = client.post(f"{self.BASE}/specs/from-content", json={
            "content": self.SAMPLE_SPEC,
            "name": "Test API",
        }, headers=AUTH_HEADER)
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Test API"
        assert data["endpoint_count"] == 1

    def test_import_invalid_json(self):
        resp = client.post(f"{self.BASE}/specs/from-content", json={
            "content": "not json",
            "name": "Bad",
        }, headers=AUTH_HEADER)
        assert resp.status_code == 400

    def test_list_specs(self):
        client.post(f"{self.BASE}/specs/from-content", json={
            "content": self.SAMPLE_SPEC, "name": "A",
        }, headers=AUTH_HEADER)
        resp = client.get(f"{self.BASE}/specs", headers=AUTH_HEADER)
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_generate_test_plan(self):
        spec = client.post(f"{self.BASE}/specs/from-content", json={
            "content": self.SAMPLE_SPEC, "name": "Plan Test",
        }, headers=AUTH_HEADER).json()

        resp = client.post(f"{self.BASE}/specs/{spec['id']}/generate", headers=AUTH_HEADER)
        assert resp.status_code == 201
        plan = resp.json()
        assert plan["endpoints_analyzed"] == 1
        assert plan["scenario_count"] >= 1

    def test_list_plans(self):
        resp = client.get(f"{self.BASE}/plans", headers=AUTH_HEADER)
        assert resp.status_code == 200

    def test_export_markdown(self):
        spec = client.post(f"{self.BASE}/specs/from-content", json={
            "content": self.SAMPLE_SPEC, "name": "MD Export",
        }, headers=AUTH_HEADER).json()
        plan = client.post(f"{self.BASE}/specs/{spec['id']}/generate", headers=AUTH_HEADER).json()

        resp = client.get(f"{self.BASE}/plans/{plan['id']}/export/markdown", headers=AUTH_HEADER)
        assert resp.status_code == 200
        data = resp.json()
        assert "# Test API" in data["markdown"] or "# Test Plan: Test API" in data["markdown"]

    def test_export_postman(self):
        spec = client.post(f"{self.BASE}/specs/from-content", json={
            "content": self.SAMPLE_SPEC, "name": "Postman Export",
        }, headers=AUTH_HEADER).json()
        plan = client.post(f"{self.BASE}/specs/{spec['id']}/generate", headers=AUTH_HEADER).json()

        resp = client.get(f"{self.BASE}/plans/{plan['id']}/export/postman", headers=AUTH_HEADER)
        assert resp.status_code == 200
        assert "collection" in resp.json()


class TestFigmaAPI:
    """Figma design analysis API."""

    BASE = f"{API_PREFIX}/figma"

    def test_analyze_invalid_url(self):
        """Should fail on invalid URL, not hit real Figma API."""
        resp = client.post(f"{self.BASE}/analyze", json={
            "figma_url": "https://google.com",
            "figma_token": "test-token",
        }, headers=AUTH_HEADER)
        # Should fail with 400 — invalid Figma URL format
        assert resp.status_code == 400
        assert "Invalid Figma URL" in resp.json()["detail"]

    def test_analyze_no_token(self):
        resp = client.post(f"{self.BASE}/analyze", json={
            "figma_url": "https://www.figma.com/file/abc123/Test",
            "figma_token": "",
        }, headers=AUTH_HEADER)
        assert resp.status_code == 400  # Missing token

    def test_list_analyses_empty(self):
        resp = client.get(f"{self.BASE}/analyses", headers=AUTH_HEADER)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_unauthorized(self):
        resp = client.get(f"{self.BASE}/analyses")
        assert resp.status_code == 401


class TestTeamAPI:
    """Team, billing, sharing API."""

    BASE = f"{API_PREFIX}/team"

    def test_list_tiers(self):
        resp = client.get(f"{self.BASE}/tiers")
        assert resp.status_code == 200
        assert len(resp.json()) == 3

    def test_get_billing(self):
        resp = client.get(f"{self.BASE}/billing", headers=AUTH_HEADER)
        assert resp.status_code == 200
        assert resp.json()["tier"] == "free"

    def test_get_usage(self):
        resp = client.get(f"{self.BASE}/usage", headers=AUTH_HEADER)
        assert resp.status_code == 200
        assert "current" in resp.json()

    def test_list_members_empty(self):
        resp = client.get(f"{self.BASE}/members", headers=AUTH_HEADER)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_add_member(self):
        resp = client.post(f"{self.BASE}/members", json={
            "email": "alice@test.com", "name": "Alice",
        }, headers=AUTH_HEADER)
        assert resp.status_code == 201
        assert resp.json()["email"] == "alice@test.com"

    def test_share_report(self):
        # Upgrade workspace so sharing is allowed
        client.post(f"{self.BASE}/billing/upgrade", json={"tier": "pro"}, headers=AUTH_HEADER)
        resp = client.post(f"{self.BASE}/share", json={
            "sprint_id": 1, "title": "Test Report",
        }, headers=AUTH_HEADER)
        assert resp.status_code == 201
        data = resp.json()
        assert "share_token" in data
        assert data["view_count"] == 0

    def test_share_unauthorized(self):
        resp = client.post(f"{self.BASE}/share", json={
            "sprint_id": 1, "title": "X",
        })
        assert resp.status_code == 401

    def test_list_shared(self):
        client.post(f"{self.BASE}/billing/upgrade", json={"tier": "pro"}, headers=AUTH_HEADER)
        resp = client.get(f"{self.BASE}/shared", headers=AUTH_HEADER)
        assert resp.status_code == 200

    def test_revoke_share(self):
        client.post(f"{self.BASE}/billing/upgrade", json={"tier": "pro"}, headers=AUTH_HEADER)
        shared = client.post(f"{self.BASE}/share", json={
            "sprint_id": 1, "title": "Revoke",
        }, headers=AUTH_HEADER).json()

        resp = client.delete(f"{self.BASE}/shared/{shared['id']}", headers=AUTH_HEADER)
        assert resp.status_code == 204


class TestAuth:
    """Authentication and workspace endpoints."""

    def test_register(self):
        resp = client.post(f"{API_PREFIX}/auth/register", json={
            "email": "new@test.com", "name": "New User", "password": "test1234",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["user"]["email"] == "new@test.com"

    def test_register_duplicate(self):
        client.post(f"{API_PREFIX}/auth/register", json={
            "email": "dup@test.com", "name": "Dup", "password": "test1234",
        })
        resp = client.post(f"{API_PREFIX}/auth/register", json={
            "email": "dup@test.com", "name": "Dup2", "password": "test1234",
        })
        assert resp.status_code == 400
        assert "already registered" in resp.json()["detail"]

    def test_login(self):
        client.post(f"{API_PREFIX}/auth/register", json={
            "email": "login@test.com", "name": "Login", "password": "pass123",
        })
        resp = client.post(f"{API_PREFIX}/auth/login", json={
            "email": "login@test.com", "password": "pass123",
        })
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    def test_login_bad_password(self):
        resp = client.post(f"{API_PREFIX}/auth/login", json={
            "email": "nobody@test.com", "password": "wrong",
        })
        assert resp.status_code == 401

    def test_get_me(self):
        # Register a real user first
        client.post(f"{API_PREFIX}/auth/register", json={
            "email": "me@test.com", "name": "Me", "password": "pass123",
        })
        # Login to get valid token
        login_resp = client.post(f"{API_PREFIX}/auth/login", json={
            "email": "me@test.com", "password": "pass123",
        })
        token = login_resp.json()["access_token"]
        resp = client.get(f"{API_PREFIX}/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json()["email"] == "me@test.com"
