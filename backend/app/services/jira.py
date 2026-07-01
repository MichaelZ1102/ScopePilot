"""Jira service for importing sprints and tickets from Jira API.

Uses scopepilot.jira_client (from scopepilot-cli package) to communicate
with Jira. In-memory store persisted to local JSON via SqliteStore mixin.
"""
from datetime import datetime, timezone
from typing import Optional

from scopepilot.jira_client import JiraClient, JiraConfig, JiraError, JiraNotFoundError
from ..database import SqliteStore
from ..encryption import decrypt

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
                "report_included": True,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            await TicketStore._persist_add(ticket)
            ticket_ids.append(tid)

        sprint["ticket_ids"] = ticket_ids
        return {**sprint, "tickets": [TicketStore.get(tid) for tid in ticket_ids if TicketStore.get(tid)]}

    # ── Retrieve ─────────────────────────────────────────────────────────

    @classmethod
    def get_sprint(cls, sprint_id: int) -> Optional[dict]:
        """Get a sprint with its tickets."""
        sprint = SprintStore.get(sprint_id)
        if sprint is None:
            return None
        ticket_ids = sprint.get("ticket_ids", [])
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
