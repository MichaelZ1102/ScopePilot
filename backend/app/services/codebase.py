"""Codebase service: GitHub/GitLab repo scanning and code impact analysis.

Phase 2: In-memory store persisted to local JSON via SqliteStore.
"""
import asyncio
import base64
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import quote, urlsplit

import httpx
from ..config import settings
from ..database import SqliteStore
from ..encryption import decrypt, encrypt
from scopepilot.codebase_scanner import index_source_text, scan_local_repository

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

    @classmethod
    def validate_source_config(cls, data: dict) -> None:
        """Validate provider-specific repository settings before persistence or scan."""
        provider = str(data.get("provider") or "github").lower()
        repo_url = str(data.get("repo_url") or "").strip()
        branch = str(data.get("default_branch") or "main").strip()
        token = str(data.get("access_token") or "")

        if provider in {"gitlab", "bitbucket"}:
            raise CodebaseError(
                f"{provider.title()} repository scanning is not supported yet."
            )
        if provider not in {"github", "local"}:
            raise CodebaseError(f"Unsupported code source provider: {provider}")
        if not branch or ".." in branch or not re.fullmatch(r"[A-Za-z0-9._/-]+", branch):
            raise CodebaseError("Invalid default branch name")
        if any(character in token for character in ("\r", "\n")):
            raise CodebaseError("Access token must not contain line breaks")

        if provider == "github":
            parsed = urlsplit(repo_url)
            path_parts = [part for part in parsed.path.split("/") if part]
            try:
                port = parsed.port
            except ValueError as exc:
                raise CodebaseError("GitHub repository URL contains an invalid port") from exc
            if (
                parsed.scheme != "https"
                or parsed.hostname not in {"github.com", "www.github.com"}
                or port not in {None, 443}
                or parsed.username is not None
                or parsed.password is not None
                or parsed.query
                or parsed.fragment
                or len(path_parts) != 2
                or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]{0,38}", path_parts[0])
                or not re.fullmatch(r"[A-Za-z0-9._-]+(?:\.git)?", path_parts[1])
            ):
                raise CodebaseError(
                    "GitHub repository URL must use https://github.com/{owner}/{repository}"
                )
            return

        if token:
            raise CodebaseError("Local repositories do not use an access token")
        cls._validated_local_path(repo_url)

    @staticmethod
    def _validated_local_path(repo_path: str) -> Path:
        environment = settings.deployment_environment.strip().lower()
        if environment in {"production", "staging", "hosted"}:
            raise CodebaseError("Local repository scanning is disabled in hosted environments")

        configured_roots = settings.local_code_scan_roots
        if isinstance(configured_roots, str):
            configured_roots = [configured_roots]
        roots = []
        for configured_root in configured_roots:
            try:
                roots.append(Path(configured_root).expanduser().resolve(strict=True))
            except (OSError, RuntimeError):
                logger.warning("Ignoring invalid local code scan root: %s", configured_root)
        if not roots:
            raise CodebaseError(
                "Local repository scanning is disabled. Configure LOCAL_CODE_SCAN_ROOTS for development."
            )
        try:
            candidate = Path(repo_path).expanduser().resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise CodebaseError("Local repository path does not exist") from exc
        if not candidate.is_dir():
            raise CodebaseError("Local repository path must be a directory")
        if not any(candidate == root or candidate.is_relative_to(root) for root in roots):
            raise CodebaseError("Local repository path is outside the configured scan roots")
        return candidate

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
    def list_sources(cls, workspace_id: int, project_id: Optional[int] = None) -> list[dict]:
        return [
            cls._without_secrets(s) for s in CodeSourceStore.list_by("workspace_id", workspace_id)
            if s["workspace_id"] == workspace_id
            and (project_id is None or s.get("project_id") == project_id)
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
        previous_snapshot = cls.get_latest_snapshot(source_id, workspace_id)

        source["scan_status"] = "scanning"
        await CodeSourceStore.update_fields(source_id, {"scan_status": "scanning"})

        try:
            cls.validate_source_config(source)
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

            previous_sha = (previous_snapshot or {}).get("commit_sha")
            next_sha = snapshot.get("commit_sha")
            if previous_snapshot and previous_sha != next_sha:
                from .jira import TicketStore
                from .lifecycle import LifecycleService
                from .notifications import NotificationService
                now = datetime.now(timezone.utc).isoformat()
                ticket_ids = {
                    impact.get("ticket_id")
                    for impact in CodeImpactStore.list_by("code_source_id", source_id)
                    if impact.get("ticket_id")
                }
                for ticket_id in ticket_ids:
                    ticket = TicketStore.get(ticket_id)
                    if not ticket or not ticket.get("analysis_data"):
                        continue
                    await TicketStore.update_fields(
                        ticket_id,
                        {
                            "analysis_status": "stale",
                            "analysis_stale_at": now,
                            "updated_at": now,
                        },
                    )
                    await LifecycleService.invalidate_review(
                        ticket_id,
                        workspace_id,
                        "代码仓库提交版本已变化，需要重新核对影响分析。",
                    )
                    await NotificationService.emit(
                        workspace_id=workspace_id,
                        event_type="analysis.stale",
                        title=f"{ticket.get('key', ticket_id)} 分析已过期",
                        message="关联代码仓库的提交版本发生变化。",
                        resource_type="ticket",
                        resource_id=ticket_id,
                        details={"source": "code", "code_source_id": source_id},
                    )

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
        branch_ref = quote(branch, safe="")

        async with httpx.AsyncClient(timeout=15.0) as client:
            branch_url = f"https://api.github.com/repos/{owner}/{repo}/branches/{branch_ref}"
            branch_resp = await client.get(branch_url, headers=headers)
            if branch_resp.status_code != 200:
                raise CodebaseError(f"GitHub branch API error: {branch_resp.status_code} {branch_resp.text[:200]}")
            branch_data = branch_resp.json()
            commit_sha = branch_data.get("commit", {}).get("sha", "")

            lang_url = f"https://api.github.com/repos/{owner}/{repo}/languages"
            lang_resp = await client.get(lang_url, headers=headers)
            lang_data = lang_resp.json() if lang_resp.status_code == 200 else {}

            tree_url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{branch_ref}?recursive=1"
            tree_resp = await client.get(tree_url, headers=headers)
            if tree_resp.status_code != 200:
                raise CodebaseError(f"GitHub tree API error: {tree_resp.status_code} {tree_resp.text[:200]}")
            tree_data = tree_resp.json()

            files = []
            if "tree" in tree_data:
                for item in tree_data["tree"]:
                    if item["type"] == "blob":
                        files.append({
                            "path": item["path"],
                            "mode": item["mode"],
                            "size": item.get("size", 0),
                            "blob_url": item.get("url", ""),
                        })

            total_files = len(files)
            total_bytes = sum(f.get("size", 0) for f in files)

            file_tree = {
                "files": [f["path"] for f in files[:1000]],
                "dirs": sorted(set("/".join(f["path"].split("/")[:-1]) for f in files if "/" in f["path"])),
            }
            source_extensions = {
                ".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".go", ".rs",
                ".rb", ".php", ".cs", ".sql", ".graphql", ".gql", ".proto",
            }
            source_files = [
                item for item in files
                if any(item["path"].lower().endswith(ext) for ext in source_extensions)
                and item.get("size", 0) <= 256_000
                and item.get("blob_url")
            ][:200]
            semaphore = asyncio.Semaphore(10)

            async def fetch_index(item: dict) -> Optional[dict]:
                async with semaphore:
                    response = await client.get(item["blob_url"], headers=headers)
                if response.status_code != 200:
                    return None
                payload = response.json()
                if payload.get("encoding") != "base64" or not payload.get("content"):
                    return None
                try:
                    text = base64.b64decode(payload["content"]).decode("utf-8", errors="ignore")
                except Exception:
                    return None
                entry = index_source_text(item["path"], text)
                entry["line_count"] = text.count("\n") + (1 if text else 0)
                return entry

            indexed = await asyncio.gather(*(fetch_index(item) for item in source_files))
            code_index = [entry for entry in indexed if entry]
            total_lines = sum(entry.get("line_count", 0) for entry in code_index)
        snapshot = {
            "code_source_id": source["id"],
            "branch": branch,
            "commit_sha": commit_sha,
            "file_tree": file_tree,
            "language_breakdown": lang_data,
            "total_files": total_files,
            "total_bytes": total_bytes,
            "total_lines": total_lines,
            "code_index": code_index,
            "scanned_at": datetime.now(timezone.utc).isoformat(),
        }
        return snapshot

    @classmethod
    async def _scan_generic(cls, source: dict) -> dict:
        if source.get("provider") == "local":
            try:
                local_path = cls._validated_local_path(source["repo_url"])
                scanned = await asyncio.to_thread(
                    scan_local_repository,
                    str(local_path),
                    source.get("default_branch"),
                )
                return {
                    **scanned,
                    "code_source_id": source["id"],
                }
            except Exception as exc:
                raise CodebaseError(f"Local repository scan failed: {exc}") from exc
        raise CodebaseError(f"Repository scanning is not supported for {source.get('provider', 'unknown')}")

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
        code_index = {
            entry.get("path"): entry
            for entry in snapshot.get("code_index", [])
            if entry.get("path")
        }
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
            index_entry = code_index.get(fpath, {})
            symbol_matches = [
                symbol for symbol in index_entry.get("symbols", [])
                if any(keyword in symbol.lower() for keyword in keywords)
            ]
            route_matches = [
                route for route in index_entry.get("routes", [])
                if any(keyword in route.lower() for keyword in keywords)
            ]
            term_matches = [
                keyword for keyword in keywords
                if keyword in set(index_entry.get("searchable_terms", []))
            ]
            if matched_keywords or symbol_matches or route_matches or term_matches:
                evidence_score = (
                    len(matched_keywords) * 2
                    + len(symbol_matches) * 3
                    + len(route_matches) * 3
                    + min(len(term_matches), 4)
                )
                confidence = min(0.35 + 0.08 * evidence_score, 0.98)
                change_type = "modify"
                if "test" in path_lower:
                    change_type = "test"
                elif "migration" in path_lower or "seed" in path_lower:
                    change_type = "create"
                elif "config" in path_lower:
                    change_type = "config"
                reasons = []
                if matched_keywords:
                    reasons.append(f"文件路径匹配：{', '.join(matched_keywords[:5])}")
                if symbol_matches:
                    reasons.append(f"代码符号匹配：{', '.join(symbol_matches[:5])}")
                if route_matches:
                    reasons.append(f"路由匹配：{', '.join(route_matches[:5])}")
                if term_matches:
                    reasons.append(f"文件内容匹配：{', '.join(term_matches[:5])}")
                affected.append({
                    "path": fpath,
                    "change_type": change_type,
                    "confidence": round(confidence, 2),
                    "matched_keywords": matched_keywords[:5],
                    "symbols": symbol_matches[:10],
                    "routes": route_matches[:10],
                    "imports": index_entry.get("imports", [])[:20],
                    "reasons": reasons,
                })

        affected.sort(key=lambda x: x["confidence"], reverse=True)
        affected = affected[:20]

        changed_dirs = set("/".join(a["path"].split("/")[:-1]) for a in affected if "/" in a["path"])
        summary = (
            f"识别到 {len(affected)} 个可能受影响文件，分布在 {len(changed_dirs)} 个目录。"
            f"重点区域：{', '.join(sorted(changed_dirs)[:5]) or '仓库根目录'}。"
        ) if affected else "未在路径、代码符号、路由或文件内容中找到明确匹配。"

        impact_id = CodeImpactStore._persist_next_id()
        impact = {
            "id": impact_id, "code_source_id": source_id, "ticket_id": ticket_id,
            "sprint_id": sprint_id, "affected_files": affected, "summary": summary,
            "source_commit_sha": snapshot.get("commit_sha"),
            "analysis_method": "path-symbol-route-content",
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
        return max(filtered, key=lambda item: item.get("created_at", "")) if filtered else None
