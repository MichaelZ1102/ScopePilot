"""Jira service for importing sprints and tickets from Jira API.

Uses scopepilot.jira_client (from scopepilot-cli package) to communicate
with Jira. In-memory store for Phase 1, to be replaced by SQLAlchemy in Phase 2.
"""
from datetime import datetime
from typing import Optional

from scopepilot.jira_client import JiraClient, JiraConfig, JiraError, JiraNotFoundError

# ── In-memory store (Phase 1) ──────────────────────────────────────────────
_sprints: dict[int, dict] = {}
_tickets: dict[int, dict] = {}
_next_sprint_id: int = 1
_next_ticket_id: int = 1


class JiraServiceError(Exception):
    """Base exception for Jira service errors."""


class JiraService:
    """Service-layer for Jira sprint import and retrieval."""

    # ── Client factory ────────────────────────────────────────────────────

    @staticmethod
    def create_client(project: dict) -> JiraClient:
        """Build a JiraClient from a project's stored Jira configuration."""
        config = JiraConfig(
            url=project["jira_url"].rstrip("/"),
            email=project["jira_email"],
            api_token=project["jira_api_token"],
            project_key=project.get("jira_project_key"),
        )
        return JiraClient(config)

    # ── Import ─────────────────────────────────────────────────────────────

    @classmethod
    def import_sprint(
        cls, project: dict, sprint_name_or_id: str
    ) -> dict:
        """Import a sprint (and its tickets) from Jira.

        Args:
            project: Project dict from the in-memory project store.
            sprint_name_or_id: Sprint display name (fuzzy match) or numeric ID.

        Returns:
            Sprint dict with nested ``tickets`` list.
        """
        global _next_sprint_id, _next_ticket_id

        client = cls.create_client(project)

        try:
            # Locate the sprint -------------------------------------------------
            sprint = None

            # 1. Try as a name (fuzzy match)
            try:
                sprint = client.find_sprint(sprint_name_or_id)
            except JiraError:
                pass

            # 2. Try as a numeric ID
            if sprint is None:
                try:
                    sprint_id = int(sprint_name_or_id)
                    sprint = client.get_sprint_by_id(sprint_id)
                except (ValueError, TypeError):
                    raise JiraServiceError(
                        f"Sprint not found: {sprint_name_or_id!r}"
                    )
                except JiraNotFoundError:
                    raise JiraServiceError(
                        f"Sprint with id {sprint_name_or_id!r} does not exist"
                    )
                except JiraError as exc:
                    raise JiraServiceError(str(exc))

            if sprint is None:
                raise JiraServiceError(
                    f"Sprint not found: {sprint_name_or_id!r}"
                )

            # Fetch issues -------------------------------------------------------
            issues_data = client.get_sprint_issues(sprint["id"])

            # Build ticket records (sprint_id filled after sprint record) --------
            ticket_records: list[dict] = []
            for issue in issues_data:
                td = client.extract_ticket_data(issue)
                tid = _next_ticket_id
                _next_ticket_id += 1
                ticket_records.append(
                    {
                        "id": tid,
                        "sprint_id": None,  # patched below
                        "key": td["key"],
                        "summary": td["summary"],
                        "description": td["description"],
                        "issue_type": td["issue_type"],
                        "status": td["status"],
                        "priority": td["priority"],
                        "assignee": td["assignee"],
                        "labels": td["labels"],
                        "story_points": td["story_points"],
                        "acceptance_criteria": td["acceptance_criteria"],
                        "comments": td["comments"],
                        "figma_links": td.get("figma_links", []),
                        "created_at": datetime.utcnow().isoformat(),
                    }
                )

            # Create sprint record -----------------------------------------------
            now = datetime.utcnow().isoformat()
            sid = _next_sprint_id
            _next_sprint_id += 1

            sprint_record: dict = {
                "id": sid,
                "project_id": project["id"],
                "jira_sprint_id": sprint["id"],
                "name": sprint.get("name", sprint_name_or_id),
                "state": sprint.get("state", "active"),
                "started_at": sprint.get("startDate"),
                "ended_at": sprint.get("endDate"),
                "imported_at": now,
                "total_tickets": len(ticket_records),
                "analysis_status": "pending",
                "analysis_data": None,
            }

            # Patch ticket sprint_ids
            for t in ticket_records:
                t["sprint_id"] = sid

            # Persist
            _sprints[sid] = sprint_record
            for t in ticket_records:
                _tickets[t["id"]] = t

        finally:
            client.close()

        return {**sprint_record, "tickets": ticket_records}

    # ── Queries ────────────────────────────────────────────────────────────

    @staticmethod
    def get_sprint(sprint_id: int) -> Optional[dict]:
        """Return a sprint dict with its tickets, or *None*."""
        sprint = _sprints.get(sprint_id)
        if sprint is None:
            return None
        tickets = [
            t for t in _tickets.values() if t["sprint_id"] == sprint_id
        ]
        return {**sprint, "tickets": tickets}

    @staticmethod
    def list_sprints(project_id: int) -> list[dict]:
        """Return all sprints belonging to a project."""
        return [
            s for s in _sprints.values() if s["project_id"] == project_id
        ]

    @staticmethod
    def get_ticket(ticket_id: int) -> Optional[dict]:
        """Return a single ticket dict, or *None*."""
        return _tickets.get(ticket_id)

    @staticmethod
    def list_tickets(sprint_id: int) -> list[dict]:
        """Return all tickets belonging to a sprint."""
        return [
            t for t in _tickets.values() if t["sprint_id"] == sprint_id
        ]
