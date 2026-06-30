"""Codebase service: GitHub/GitLab repo scanning and code impact analysis.

Phase 2: In-memory store persisted to local JSON via SqliteStore.
"""
import logging
import re
from datetime import datetime, timezone
from typing import Optional

import httpx
from ..database import SqliteStore
from ..encryption import decrypt, encrypt

logger = logging.getLogger(__name__)


class CodeSourceStore(SqliteStore):
    _entity_name = "code_sources"
    _store: dict[int, dict] = {}
    _next_id: int = 1


class RepoSnapshotStore(SqliteStore):
    _entity_name = "repo_snapshots"
    _store: dict[int, dict] = {}
    _next_id: int = 1


class CodeImpactStore(SqliteStore):
    _entity_name = "code_impacts"
    _store: dict[int, dict] = {}
    _next_id: int = 1


_code_sources = CodeSourceStore._store
_repo_snapshots = RepoSnapshotStore._store
_code_impacts = CodeImpactStore._store


class CodebaseError(Exception):
    """Base exception for codebase service."""


class CodebaseService:
    """Service for managing code sources, scanning repos, and predicting code impact."""

    @staticmethod
    def _read_access_token(token: str) -> tuple[str, bool]:
        if not token:
            return "", False
        try:
            return decrypt(token), False
        except Exception:
            if token.startswith("gAAAA"):
                raise CodebaseError("Stored access token cannot be decrypted. Please re-enter the token.")
            return token, True

    @staticmethod
    def _without_secrets(source: dict) -> dict:
        return {key: value for key, value in source.items() if key != "access_token"}

    # ── Code Source CRUD ──────────────────────────────────────────────────

    @classmethod
    async def create_source(cls, data: dict, workspace_id: int) -> dict:
        source_id = CodeSourceStore._persist_next_id()
        source = {
            "id": source_id,
            "workspace_id": workspace_id,
            "project_id": data.get("project_id"),
            "name": data["name"],
            "provider": data.get("provider", "github"),
            "repo_url": data["repo_url"],
            "default_branch": data.get("default_branch", "main"),
            "access_token": encrypt(data.get("access_token", "")),
            "webhook_secret": None,
            "last_scanned_at": None,
            "scan_status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        return await CodeSourceStore._persist_add(source)

    @classmethod
    def list_sources(cls, workspace_id: int) -> list[dict]:
        return [
            cls._without_secrets(s) for s in CodeSourceStore.list_by("workspace_id", workspace_id)
            if s["workspace_id"] == workspace_id
        ]

    @classmethod
    def get_source(cls, source_id: int, workspace_id: int) -> Optional[dict]:
        source = CodeSourceStore.get(source_id)
        if source and source["workspace_id"] == workspace_id:
            return source
        return None

    @classmethod
    async def delete_source(cls, source_id: int, workspace_id: int) -> bool:
        source = cls.get_source(source_id, workspace_id)
        if source:
            await CodeSourceStore._persist_delete(source_id)
            # Clean up related snapshots and impacts
            for snapshot in RepoSnapshotStore.list_by("code_source_id", source_id):
                await RepoSnapshotStore._persist_delete(snapshot["id"])
            for impact in CodeImpactStore.list_by("code_source_id", source_id):
                await CodeImpactStore._persist_delete(impact["id"])
            return True
        return False

    # ── Scanning ──────────────────────────────────────────────────────────

    @classmethod
    async def scan_repository(cls, source_id: int, workspace_id: int) -> dict:
        """Scan a remote repository and store a snapshot."""
        source = cls.get_source(source_id, workspace_id)
        if not source:
            raise CodebaseError("Code source not found")

        source["scan_status"] = "scanning"
        await CodeSourceStore.update_fields(source_id, {"scan_status": "scanning"})

        try:
            if source["provider"] == "github":
                snapshot = await cls._scan_github(source)
            else:
                snapshot = await cls._scan_generic(source)

            snapshot_id = RepoSnapshotStore._persist_next_id()
            snapshot["id"] = snapshot_id
            await RepoSnapshotStore._persist_add(snapshot)

            source["last_scanned_at"] = snapshot["scanned_at"]
            source["scan_status"] = "done"
            await CodeSourceStore.update_fields(source_id, {"last_scanned_at": snapshot["scanned_at"], "scan_status": "done"})

            return snapshot

        except Exception as e:
            source["scan_status"] = "failed"
            await CodeSourceStore.update_fields(source_id, {"scan_status": "failed"})
            logger.error(f"Scan failed for source {source_id}: {e}")
            raise CodebaseError(f"Scan failed: {e}")

    @classmethod
    async def _scan_github(cls, source: dict) -> dict:
        """Scan a GitHub repo via the GitHub API."""
        repo_url = source["repo_url"].rstrip("/")
        match = re.search(r"github\.com[:/]([^/]+)/([^/#?]+)", repo_url)
        if not match:
            raise CodebaseError(f"Invalid GitHub URL: {repo_url}")
        owner, repo = match.group(1), match.group(2).removesuffix(".git")
        token, should_migrate_token = cls._read_access_token(source.get("access_token") or "")
        if should_migrate_token:
            encrypted_token = encrypt(token)
            source["access_token"] = encrypted_token
            await CodeSourceStore.update_fields(source["id"], {"access_token": encrypted_token})

        headers = {"Accept": "application/vnd.github.v3+json", "User-Agent": "ScopePilot/0.2"}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        branch = source.get("default_branch", "main")

        async with httpx.AsyncClient(timeout=15.0) as client:
            branch_url = f"https://api.github.com/repos/{owner}/{repo}/branches/{branch}"
            branch_resp = await client.get(branch_url, headers=headers)
            if branch_resp.status_code != 200:
                raise CodebaseError(f"GitHub branch API error: {branch_resp.status_code} {branch_resp.text[:200]}")
            branch_data = branch_resp.json()
            commit_sha = branch_data.get("commit", {}).get("sha", "")

            lang_url = f"https://api.github.com/repos/{owner}/{repo}/languages"
            lang_resp = await client.get(lang_url, headers=headers)
            lang_data = lang_resp.json() if lang_resp.status_code == 200 else {}

            tree_url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}?recursive=1"
            tree_resp = await client.get(tree_url, headers=headers)
            if tree_resp.status_code != 200:
                raise CodebaseError(f"GitHub tree API error: {tree_resp.status_code} {tree_resp.text[:200]}")
            tree_data = tree_resp.json()

            files = []
            if "tree" in tree_data:
                for item in tree_data["tree"]:
                    if item["type"] == "blob":
                        files.append({"path": item["path"], "mode": item["mode"], "size": item.get("size", 0)})

            total_files = len(files)
            total_bytes = sum(f.get("size", 0) for f in files)

            file_tree = {
                "files": [f["path"] for f in files[:1000]],
                "dirs": sorted(set("/".join(f["path"].split("/")[:-1]) for f in files if "/" in f["path"])),
            }
        snapshot = {
            "code_source_id": source["id"],
            "branch": branch,
            "commit_sha": commit_sha,
            "file_tree": file_tree,
            "language_breakdown": lang_data,
            "total_files": total_files,
            "total_bytes": total_bytes,
            "total_lines": 0,  # Not estimated — use total_bytes for accuracy
            "scanned_at": datetime.now(timezone.utc).isoformat(),
        }
        return snapshot

    @classmethod
    async def _scan_generic(cls, source: dict) -> dict:
        return {
            "code_source_id": source["id"],
            "branch": source.get("default_branch", "main"),
            "commit_sha": None,
            "file_tree": {"files": [], "dirs": [], "note": f"Full scan not available for {source['provider']}."},
            "language_breakdown": {},
            "total_files": 0, "total_lines": 0,
            "scanned_at": datetime.now(timezone.utc).isoformat(),
        }

    # ── Snapshots ─────────────────────────────────────────────────────────

    @classmethod
    def get_latest_snapshot(cls, source_id: int, workspace_id: int) -> Optional[dict]:
        source = cls.get_source(source_id, workspace_id)
        if not source:
            return None
        snapshots = RepoSnapshotStore.list_by("code_source_id", source_id)
        if not snapshots:
            return None
        return max(snapshots, key=lambda s: s["scanned_at"])

    # ── Code Impact Analysis ──────────────────────────────────────────────

    @classmethod
    async def analyze_impact(cls, source_id: int, ticket_id: int, sprint_id: int,
                       workspace_id: int, ticket_summary: str = "",
                       ticket_description: str = "", snapshot: Optional[dict] = None) -> dict:
        if not snapshot:
            snap = cls.get_latest_snapshot(source_id, workspace_id)
            if not snap:
                raise CodebaseError("No snapshot available. Scan the repository first.")
            snapshot = snap

        files = snapshot.get("file_tree", {}).get("files", [])
        if not files:
            impact_data = {
                "code_source_id": source_id, "ticket_id": ticket_id, "sprint_id": sprint_id,
                "affected_files": [], "summary": "No file data available. Run a scan first.",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            impact_id = CodeImpactStore._persist_next_id()
            impact_data["id"] = impact_id
            return await CodeImpactStore._persist_add(impact_data)

        keywords = set()
        for text in [ticket_summary, ticket_description]:
            words = re.findall(r'[a-zA-Z_][a-zA-Z0-9_]{2,}', text)
            keywords.update(w.lower() for w in words)

        affected = []
        for fpath in files:
            path_lower = fpath.lower()
            matched_keywords = [kw for kw in keywords if kw in path_lower]
            if matched_keywords:
                confidence = min(0.5 + 0.1 * len(matched_keywords), 0.95)
                change_type = "modify"
                if "test" in path_lower:
                    change_type = "test"
                elif "migration" in path_lower or "seed" in path_lower:
                    change_type = "create"
                elif "config" in path_lower:
                    change_type = "config"
                affected.append({"path": fpath, "change_type": change_type,
                                 "confidence": round(confidence, 2),
                                 "matched_keywords": matched_keywords[:5]})

        affected.sort(key=lambda x: x["confidence"], reverse=True)
        affected = affected[:20]

        changed_dirs = set("/".join(a["path"].split("/")[:-1]) for a in affected if "/" in a["path"])
        summary = (
            f"Impact analysis found {len(affected)} potentially affected files "
            f"across {len(changed_dirs)} directories. "
            f"Top areas: {', '.join(sorted(changed_dirs)[:5])}."
        ) if affected else "No specific files matched."

        impact_id = CodeImpactStore._persist_next_id()
        impact = {
            "id": impact_id, "code_source_id": source_id, "ticket_id": ticket_id,
            "sprint_id": sprint_id, "affected_files": affected, "summary": summary,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        return await CodeImpactStore._persist_add(impact)

    @classmethod
    def get_impacts_for_sprint(cls, sprint_id: int, workspace_id: int) -> list[dict]:
        impacts = CodeImpactStore.list_by("sprint_id", sprint_id)
        # Filter by workspace through the code source chain
        return [i for i in impacts
                if (CodeSourceStore.get(i.get("code_source_id")) or {}).get("workspace_id") == workspace_id]

    @classmethod
    def get_impact_for_ticket(cls, ticket_id: int, workspace_id: int) -> Optional[dict]:
        impacts = CodeImpactStore.list_by("ticket_id", ticket_id)
        # Filter by workspace through the code source chain
        filtered = [i for i in impacts
                    if (CodeSourceStore.get(i.get("code_source_id")) or {}).get("workspace_id") == workspace_id]
        return filtered[0] if filtered else None
