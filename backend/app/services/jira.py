"""Jira service for importing sprints and tickets from Jira API.

Uses scopepilot.jira_client (from scopepilot-cli package) to communicate
with Jira. In-memory store persisted to local JSON via SqliteStore mixin.
"""
from datetime import datetime, timezone
from typing import Optional

from scopepilot.jira_client import JiraClient, JiraConfig, JiraError, JiraNotFoundError
from ..database import SqliteStore
from ..encryption import decrypt
from .lifecycle import LifecycleService

# ── In-memory store (persisted to JSON) ──────────────────────────────────


class SprintStore(SqliteStore):
    _entity_name = "sprints"
    _store: dict[int, dict] = {}
    _next_id: int = 1


class TicketStore(SqliteStore):
    _entity_name = "tickets"
    _store: dict[int, dict] = {}
    _next_id: int = 1


_sprints = SprintStore._store
_tickets = TicketStore._store


class JiraServiceError(Exception):
    """Base exception for Jira service errors."""


class JiraService:
    """Service-layer for Jira sprint import and retrieval."""

    # ── Client factory ───────────────────────────────────────────────────

    @staticmethod
    def create_client(project: dict) -> JiraClient:
        """Build a JiraClient from a project's stored Jira configuration."""
        try:
            api_token = decrypt(project["jira_api_token"])
        except Exception as exc:
            raise JiraServiceError(
                "Stored Jira API token cannot be decrypted. Please update the project Jira token."
            ) from exc
        config = JiraConfig(
            url=project["jira_url"].rstrip("/"),
            email=project["jira_email"],
            api_token=api_token,
            project_key=project.get("jira_project_key"),
        )
        return JiraClient(config)

    # ── Import ─────────────────────────────────────────────────────────────

    @classmethod
    async def import_sprint(cls, project: dict, sprint_name: str, workspace_id: int = None) -> dict:
        """Fetch a sprint + tickets from Jira and store internally.

        Args:
            project: Project dict with jira config.
            sprint_name: Sprint name to find.
            workspace_id: If provided, validates project belongs to this workspace.

        Raises:
            JiraServiceError: If workspace_id is provided but doesn't match project.
        """
        if workspace_id is not None and project.get("workspace_id") != workspace_id:
            raise JiraServiceError("Project does not belong to this workspace")

        client = cls.create_client(project)

        # 1. Fetch sprint data
        sprint_data = client.find_sprint(sprint_name)

        # 2. Fetch tickets
        jira_tickets = client.get_sprint_issues(
            sprint_data["id"],
        )

        existing_sprint = next(
            (
                item for item in SprintStore.list_by("project_id", project["id"])
                if item.get("jira_sprint_id") == sprint_data["id"]
            ),
            None,
        )
        if existing_sprint:
            await SprintStore.update_fields(
                existing_sprint["id"],
                {
                    "name": sprint_data["name"],
                    "state": sprint_data.get("state", "active"),
                    "started_at": sprint_data.get("startDate"),
                    "ended_at": sprint_data.get("endDate"),
                },
            )
            await cls._sync_ticket_records(
                existing_sprint,
                jira_tickets,
                workspace_id or project["workspace_id"],
            )
            return cls.get_sprint(existing_sprint["id"])

        # 3. Build internal sprint record
        sprint_id = SprintStore._persist_next_id()

        sprint = {
            "id": sprint_id,
            "project_id": project["id"],
            "jira_sprint_id": sprint_data["id"],
            "name": sprint_data["name"],
            "state": sprint_data.get("state", "active"),
            "started_at": sprint_data.get("startDate"),
            "ended_at": sprint_data.get("endDate"),
            "imported_at": datetime.now(timezone.utc).isoformat(),
            "total_tickets": len(jira_tickets),
            "analysis_status": "pending",
            "analysis_data": None,
            "analysis_stale_at": None,
            "latest_analysis_run_id": None,
            "last_synced_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        await SprintStore._persist_add(sprint)

        # 4. Build internal ticket records
        ticket_ids = []
        for jt in jira_tickets:
            tid = TicketStore._persist_next_id()
            ticket = {
                "id": tid,
                "sprint_id": sprint_id,
                "key": jt.get("key", ""),
                "summary": jt.get("summary", ""),
                "description": jt.get("description"),
                "issue_type": jt.get("issue_type"),
                "status": jt.get("status"),
                "priority": jt.get("priority"),
                "assignee": jt.get("assignee"),
                "labels": jt.get("labels", []),
                "story_points": jt.get("story_points"),
                "acceptance_criteria": jt.get("acceptance_criteria", []),
                "comments": jt.get("comments", []),
                "figma_links": jt.get("figma_links", []),
                "analysis_data": None,
                "analysis_status": "pending",
                "analysis_stale_at": None,
                "latest_analysis_run_id": None,
                "report_included": True,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "source_updated_at": jt.get("source_updated_at"),
                "source_status": "active",
            }
            await TicketStore._persist_add(ticket)
            ticket_ids.append(tid)

        sprint["ticket_ids"] = ticket_ids
        await SprintStore.update_fields(
            sprint_id,
            {"ticket_ids": ticket_ids, "total_tickets": len(ticket_ids)},
        )
        return {**sprint, "tickets": [TicketStore.get(tid) for tid in ticket_ids if TicketStore.get(tid)]}

    @classmethod
    async def sync_sprint(cls, sprint_id: int, project: dict, workspace_id: int) -> dict:
        """Synchronize an imported Sprint with Jira and mark changed analyses stale."""
        sprint = cls.get_sprint(sprint_id)
        if not sprint or sprint.get("project_id") != project.get("id"):
            raise JiraServiceError("Sprint not found")
        if project.get("workspace_id") != workspace_id:
            raise JiraServiceError("Project does not belong to this workspace")

        sync_run = await LifecycleService.create_sync_run(
            workspace_id=workspace_id,
            project_id=project["id"],
            sprint_id=sprint_id,
        )
        try:
            client = cls.create_client(project)
            jira_tickets = client.get_sprint_issues(sprint["jira_sprint_id"])
            summary = await cls._sync_ticket_records(
                SprintStore.get(sprint_id),
                jira_tickets,
                workspace_id,
            )
            await LifecycleService.finish_sync_run(
                sync_run["id"],
                status="completed",
                summary=summary,
            )
            return {
                "sprint": cls.get_sprint(sprint_id),
                "sync_run": {**sync_run, "status": "completed", "summary": summary},
                "summary": summary,
            }
        except Exception as exc:
            await LifecycleService.finish_sync_run(
                sync_run["id"],
                status="failed",
                error_message=str(exc),
            )
            if isinstance(exc, JiraServiceError):
                raise
            raise JiraServiceError(str(exc)) from exc

    @classmethod
    async def _sync_ticket_records(
        cls,
        sprint: dict,
        jira_tickets: list[dict],
        workspace_id: int,
    ) -> dict:
        """Upsert Jira tickets and return a deterministic change summary."""
        now = datetime.now(timezone.utc).isoformat()
        existing_tickets = {
            ticket.get("key"): ticket
            for ticket in cls.list_tickets(sprint["id"])
            if ticket.get("source_status", "active") == "active"
        }
        incoming_by_key = {ticket.get("key"): ticket for ticket in jira_tickets}
        tracked_fields = (
            "summary",
            "description",
            "issue_type",
            "status",
            "priority",
            "assignee",
            "labels",
            "story_points",
            "acceptance_criteria",
            "comments",
            "figma_links",
            "source_updated_at",
        )
        added: list[str] = []
        updated: list[str] = []
        removed: list[str] = []
        unchanged: list[str] = []
        active_ids: list[int] = []

        for key, incoming in incoming_by_key.items():
            current = existing_tickets.get(key)
            if current is None:
                ticket_id = TicketStore._persist_next_id()
                record = {
                    "id": ticket_id,
                    "sprint_id": sprint["id"],
                    "key": key or "",
                    "summary": incoming.get("summary", ""),
                    "description": incoming.get("description"),
                    "issue_type": incoming.get("issue_type"),
                    "status": incoming.get("status"),
                    "priority": incoming.get("priority"),
                    "assignee": incoming.get("assignee"),
                    "labels": incoming.get("labels", []),
                    "story_points": incoming.get("story_points"),
                    "acceptance_criteria": incoming.get("acceptance_criteria", []),
                    "comments": incoming.get("comments", []),
                    "figma_links": incoming.get("figma_links", []),
                    "analysis_data": None,
                    "analysis_status": "pending",
                    "analysis_stale_at": None,
                    "latest_analysis_run_id": None,
                    "report_included": True,
                    "created_at": now,
                    "updated_at": now,
                    "source_updated_at": incoming.get("source_updated_at"),
                    "source_status": "active",
                }
                await TicketStore._persist_add(record)
                active_ids.append(ticket_id)
                added.append(key)
                continue

            active_ids.append(current["id"])
            changes = {
                field: incoming.get(field)
                for field in tracked_fields
                if current.get(field) != incoming.get(field)
            }
            if changes:
                changes["updated_at"] = now
                changes["source_status"] = "active"
                if current.get("analysis_data"):
                    changes["analysis_status"] = "stale"
                    changes["analysis_stale_at"] = now
                    await LifecycleService.invalidate_review(
                        current["id"],
                        workspace_id,
                        "Jira Ticket 已更新，需要重新分析和审核。",
                    )
                await TicketStore.update_fields(current["id"], changes)
                updated.append(key)
            else:
                unchanged.append(key)

        for key, current in existing_tickets.items():
            if key in incoming_by_key:
                continue
            removed.append(key)
            await TicketStore.update_fields(
                current["id"],
                {
                    "source_status": "removed",
                    "analysis_status": "stale" if current.get("analysis_data") else "pending",
                    "analysis_stale_at": now if current.get("analysis_data") else None,
                    "updated_at": now,
                },
            )
            await LifecycleService.invalidate_review(
                current["id"],
                workspace_id,
                "Ticket 已从 Jira Sprint 移除。",
            )

        sprint_updates = {
            "ticket_ids": active_ids,
            "total_tickets": len(active_ids),
            "last_synced_at": now,
            "updated_at": now,
        }
        if added or updated or removed:
            sprint_updates["analysis_status"] = "stale"
            sprint_updates["analysis_stale_at"] = now
        await SprintStore.update_fields(sprint["id"], sprint_updates)
        return {
            "added": added,
            "updated": updated,
            "removed": removed,
            "unchanged": unchanged,
            "total": len(active_ids),
            "synced_at": now,
        }

    # ── Retrieve ─────────────────────────────────────────────────────────

    @classmethod
    def get_sprint(cls, sprint_id: int) -> Optional[dict]:
        """Get a sprint with its tickets."""
        sprint = SprintStore.get(sprint_id)
        if sprint is None:
            return None
        ticket_ids = sprint.get("ticket_ids", [])
        if not ticket_ids:
            ticket_ids = [
                ticket["id"]
                for ticket in TicketStore.list_by("sprint_id", sprint_id)
                if ticket.get("source_status", "active") == "active"
            ]
        return {
            **sprint,
            "tickets": [TicketStore.get(tid) for tid in ticket_ids if TicketStore.get(tid)],
        }

    @classmethod
    def list_sprints(cls, project_id: int) -> list[dict]:
        """List sprints for a project."""
        return [
            {"id": s["id"], "name": s["name"], "state": s["state"],
             "total_tickets": s["total_tickets"], "analysis_status": s["analysis_status"],
             "imported_at": s.get("imported_at")}
            for s in SprintStore.list_by("project_id", project_id)
        ]

    @classmethod
    def get_ticket(cls, ticket_id: int) -> Optional[dict]:
        return TicketStore.get(ticket_id)

    @classmethod
    def list_tickets(cls, sprint_id: int) -> list[dict]:
        """List all tickets in a sprint."""
        return TicketStore.list_by("sprint_id", sprint_id)

    @classmethod
    async def update_sprint(cls, sprint_id: int, updates: dict):
        if SprintStore.get(sprint_id):
            await SprintStore.update_fields(sprint_id, updates)

    @classmethod
    async def update_ticket(cls, ticket_id: int, updates: dict):
        if TicketStore.get(ticket_id):
            await TicketStore.update_fields(ticket_id, updates)

    @classmethod
    async def delete_project_data(cls, project_id: int):
        """Delete all sprints and tickets belonging to a project (cascade)."""
        sprint_ids = [s["id"] for s in SprintStore.list_by("project_id", project_id)]
        ticket_ids = [t["id"] for t in TicketStore.list_all() if t["sprint_id"] in sprint_ids]
        for tid in ticket_ids:
            await TicketStore._persist_delete(tid)
        for sid in sprint_ids:
            await SprintStore._persist_delete(sid)
        return len(sprint_ids), len(ticket_ids)
