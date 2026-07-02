"""Ticket analysis lifecycle, review, artifact links, snapshots, and audit records."""
from datetime import datetime, timezone
from typing import Optional

from ..database import SqliteStore


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class AnalysisRunStore(SqliteStore):
    _entity_name = "analysis_runs"
    _store: dict[int, dict] = {}
    _next_id: int = 1


class TicketReviewStore(SqliteStore):
    _entity_name = "ticket_reviews"
    _store: dict[int, dict] = {}
    _next_id: int = 1


class TicketArtifactLinkStore(SqliteStore):
    _entity_name = "ticket_artifact_links"
    _store: dict[int, dict] = {}
    _next_id: int = 1


class ReportSnapshotStore(SqliteStore):
    _entity_name = "report_snapshots"
    _store: dict[int, dict] = {}
    _next_id: int = 1


class SyncRunStore(SqliteStore):
    _entity_name = "sync_runs"
    _store: dict[int, dict] = {}
    _next_id: int = 1


class AuditLogStore(SqliteStore):
    _entity_name = "audit_logs"
    _store: dict[int, dict] = {}
    _next_id: int = 1


class ReportCommentStore(SqliteStore):
    _entity_name = "report_comments"
    _store: dict[int, dict] = {}
    _next_id: int = 1


class ActionItemStore(SqliteStore):
    _entity_name = "action_items"
    _store: dict[int, dict] = {}
    _next_id: int = 1


class DeliveryLinkStore(SqliteStore):
    _entity_name = "delivery_links"
    _store: dict[int, dict] = {}
    _next_id: int = 1


class LifecycleService:
    """Persist the lifecycle records shared by analysis and reporting features."""

    @staticmethod
    async def create_analysis_run(
        *,
        workspace_id: int,
        project_id: int,
        sprint_id: int,
        ticket_id: Optional[int],
        analysis_type: str,
        result: dict,
        source_versions: Optional[dict] = None,
        model: str = "",
        prompt_version: str = "v1",
        status: str = "completed",
        error_message: str = "",
    ) -> dict:
        previous = LifecycleService.list_analysis_runs(
            workspace_id=workspace_id,
            ticket_id=ticket_id,
            sprint_id=sprint_id,
            analysis_type=analysis_type,
        )
        version = max((run.get("version", 0) for run in previous), default=0) + 1
        now = _now()
        record = {
            "id": AnalysisRunStore._persist_next_id(),
            "workspace_id": workspace_id,
            "project_id": project_id,
            "sprint_id": sprint_id,
            "ticket_id": ticket_id,
            "analysis_type": analysis_type,
            "version": version,
            "status": status,
            "result": result,
            "source_versions": source_versions or {},
            "model": model,
            "prompt_version": prompt_version,
            "error_message": error_message[:2000],
            "created_at": now,
            "completed_at": now if status == "completed" else None,
        }
        return await AnalysisRunStore._persist_add(record)

    @staticmethod
    def list_analysis_runs(
        *,
        workspace_id: int,
        ticket_id: Optional[int] = None,
        sprint_id: Optional[int] = None,
        analysis_type: Optional[str] = None,
    ) -> list[dict]:
        records = [
            run for run in AnalysisRunStore.list_by("workspace_id", workspace_id)
            if ticket_id is None or run.get("ticket_id") == ticket_id
        ]
        if sprint_id is not None:
            records = [run for run in records if run.get("sprint_id") == sprint_id]
        if analysis_type is not None:
            records = [run for run in records if run.get("analysis_type") == analysis_type]
        return sorted(
            records,
            key=lambda run: (run.get("version", 0), run.get("created_at", "")),
            reverse=True,
        )

    @staticmethod
    def get_analysis_run(
        run_id: int,
        workspace_id: int,
        ticket_id: Optional[int] = None,
    ) -> Optional[dict]:
        run = AnalysisRunStore.get(run_id)
        if (
            run
            and run.get("workspace_id") == workspace_id
            and (ticket_id is None or run.get("ticket_id") == ticket_id)
        ):
            return run
        return None

    @staticmethod
    async def archive_analysis_run(
        run_id: int,
        ticket_id: int,
        workspace_id: int,
    ) -> Optional[dict]:
        run = LifecycleService.get_analysis_run(run_id, workspace_id, ticket_id)
        if not run:
            return None
        return await AnalysisRunStore.update_fields(
            run_id,
            {"status": "archived", "archived_at": _now()},
        )

    @staticmethod
    def get_latest_analysis_run(
        ticket_id: int,
        workspace_id: int,
        analysis_type: str = "ticket",
    ) -> Optional[dict]:
        runs = LifecycleService.list_analysis_runs(
            workspace_id=workspace_id,
            ticket_id=ticket_id,
            analysis_type=analysis_type,
        )
        return runs[0] if runs else None

    @staticmethod
    def get_review(ticket_id: int, workspace_id: int) -> Optional[dict]:
        reviews = [
            review for review in TicketReviewStore.list_by("ticket_id", ticket_id)
            if review.get("workspace_id") == workspace_id
        ]
        return max(reviews, key=lambda review: review.get("updated_at", ""), default=None)

    @staticmethod
    async def set_review(
        *,
        workspace_id: int,
        project_id: int,
        sprint_id: int,
        ticket_id: int,
        analysis_run_id: Optional[int],
        status: str,
        reviewer_id: int,
        reviewer_name: str,
        comment: str = "",
    ) -> dict:
        now = _now()
        current = LifecycleService.get_review(ticket_id, workspace_id)
        data = {
            "workspace_id": workspace_id,
            "project_id": project_id,
            "sprint_id": sprint_id,
            "ticket_id": ticket_id,
            "analysis_run_id": analysis_run_id,
            "status": status,
            "reviewer_id": reviewer_id,
            "reviewer_name": reviewer_name,
            "comment": comment,
            "reviewed_at": now if status in {"approved", "rejected"} else None,
            "updated_at": now,
        }
        if current:
            updated = await TicketReviewStore.update_fields(current["id"], data)
            return updated or current
        data["id"] = TicketReviewStore._persist_next_id()
        data["created_at"] = now
        return await TicketReviewStore._persist_add(data)

    @staticmethod
    async def invalidate_review(ticket_id: int, workspace_id: int, reason: str) -> Optional[dict]:
        review = LifecycleService.get_review(ticket_id, workspace_id)
        if not review or review.get("status") == "unreviewed":
            return review
        return await TicketReviewStore.update_fields(
            review["id"],
            {
                "status": "unreviewed",
                "comment": reason,
                "reviewed_at": None,
                "updated_at": _now(),
            },
        )

    @staticmethod
    async def link_artifact(
        *,
        workspace_id: int,
        project_id: int,
        sprint_id: int,
        ticket_id: int,
        artifact_type: str,
        artifact_id: int,
        metadata: Optional[dict] = None,
    ) -> dict:
        existing = next(
            (
                link for link in TicketArtifactLinkStore.list_by("ticket_id", ticket_id)
                if link.get("workspace_id") == workspace_id
                and link.get("artifact_type") == artifact_type
                and link.get("artifact_id") == artifact_id
            ),
            None,
        )
        if existing:
            if metadata is not None:
                await TicketArtifactLinkStore.update_fields(
                    existing["id"],
                    {"metadata": metadata, "updated_at": _now()},
                )
            return existing

        now = _now()
        record = {
            "id": TicketArtifactLinkStore._persist_next_id(),
            "workspace_id": workspace_id,
            "project_id": project_id,
            "sprint_id": sprint_id,
            "ticket_id": ticket_id,
            "artifact_type": artifact_type,
            "artifact_id": artifact_id,
            "metadata": metadata or {},
            "created_at": now,
            "updated_at": now,
        }
        return await TicketArtifactLinkStore._persist_add(record)

    @staticmethod
    def list_artifact_links(ticket_id: int, workspace_id: int) -> list[dict]:
        return [
            link for link in TicketArtifactLinkStore.list_by("ticket_id", ticket_id)
            if link.get("workspace_id") == workspace_id
        ]

    @staticmethod
    async def unlink_artifact(link_id: int, ticket_id: int, workspace_id: int) -> bool:
        link = TicketArtifactLinkStore.get(link_id)
        if (
            not link
            or link.get("ticket_id") != ticket_id
            or link.get("workspace_id") != workspace_id
        ):
            return False
        return await TicketArtifactLinkStore._persist_delete(link_id)

    @staticmethod
    async def create_report_snapshot(
        *,
        workspace_id: int,
        project_id: int,
        sprint_id: int,
        ticket_id: Optional[int],
        report_type: str,
        title: str,
        content: str,
        structured_content: dict,
        created_by: int,
        status: str = "published",
    ) -> dict:
        existing = [
            snapshot for snapshot in ReportSnapshotStore.list_by("workspace_id", workspace_id)
            if snapshot.get("sprint_id") == sprint_id
            and snapshot.get("ticket_id") == ticket_id
            and snapshot.get("report_type") == report_type
        ]
        version = max((item.get("version", 0) for item in existing), default=0) + 1
        now = _now()
        record = {
            "id": ReportSnapshotStore._persist_next_id(),
            "workspace_id": workspace_id,
            "project_id": project_id,
            "sprint_id": sprint_id,
            "ticket_id": ticket_id,
            "report_type": report_type,
            "title": title,
            "content": content,
            "structured_content": structured_content,
            "version": version,
            "status": status,
            "created_by": created_by,
            "created_at": now,
            "published_at": now if status == "published" else None,
        }
        return await ReportSnapshotStore._persist_add(record)

    @staticmethod
    def list_report_snapshots(
        workspace_id: int,
        sprint_id: Optional[int] = None,
        ticket_id: Optional[int] = None,
    ) -> list[dict]:
        snapshots = ReportSnapshotStore.list_by("workspace_id", workspace_id)
        if sprint_id is not None:
            snapshots = [item for item in snapshots if item.get("sprint_id") == sprint_id]
        if ticket_id is not None:
            snapshots = [item for item in snapshots if item.get("ticket_id") == ticket_id]
        return sorted(snapshots, key=lambda item: item.get("created_at", ""), reverse=True)

    @staticmethod
    async def archive_report_snapshot(
        snapshot_id: int,
        workspace_id: int,
    ) -> Optional[dict]:
        snapshot = ReportSnapshotStore.get(snapshot_id)
        if not snapshot or snapshot.get("workspace_id") != workspace_id:
            return None
        return await ReportSnapshotStore.update_fields(
            snapshot_id,
            {
                "status": "archived",
                "archived_at": _now(),
            },
        )

    @staticmethod
    async def delete_project_records(
        project_id: int,
        workspace_id: int,
        ticket_ids: set[int],
    ) -> None:
        """Delete project-scoped lifecycle data while preserving audit history."""
        project_stores = (
            AnalysisRunStore,
            ReportSnapshotStore,
            SyncRunStore,
        )
        ticket_stores = (
            TicketReviewStore,
            TicketArtifactLinkStore,
            ReportCommentStore,
            ActionItemStore,
            DeliveryLinkStore,
        )
        for store in project_stores:
            for record in list(store.list_by("workspace_id", workspace_id)):
                if record.get("project_id") == project_id:
                    await store._persist_delete(record["id"])
        for store in ticket_stores:
            for record in list(store.list_by("workspace_id", workspace_id)):
                if record.get("ticket_id") in ticket_ids:
                    await store._persist_delete(record["id"])

    @staticmethod
    async def create_sync_run(
        *,
        workspace_id: int,
        project_id: int,
        sprint_id: int,
        status: str = "running",
    ) -> dict:
        now = _now()
        record = {
            "id": SyncRunStore._persist_next_id(),
            "workspace_id": workspace_id,
            "project_id": project_id,
            "sprint_id": sprint_id,
            "status": status,
            "summary": {},
            "error_message": "",
            "created_at": now,
            "started_at": now,
            "finished_at": None,
        }
        return await SyncRunStore._persist_add(record)

    @staticmethod
    async def finish_sync_run(
        sync_run_id: int,
        *,
        status: str,
        summary: Optional[dict] = None,
        error_message: str = "",
    ) -> Optional[dict]:
        return await SyncRunStore.update_fields(
            sync_run_id,
            {
                "status": status,
                "summary": summary or {},
                "error_message": error_message[:2000],
                "finished_at": _now(),
            },
        )

    @staticmethod
    async def audit(
        *,
        workspace_id: int,
        actor_id: int,
        actor_name: str,
        action: str,
        resource_type: str,
        resource_id: Optional[int] = None,
        details: Optional[dict] = None,
    ) -> dict:
        record = {
            "id": AuditLogStore._persist_next_id(),
            "workspace_id": workspace_id,
            "actor_id": actor_id,
            "actor_name": actor_name,
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "details": details or {},
            "created_at": _now(),
        }
        return await AuditLogStore._persist_add(record)

    @staticmethod
    def list_audit_logs(workspace_id: int) -> list[dict]:
        return sorted(
            AuditLogStore.list_by("workspace_id", workspace_id),
            key=lambda item: item.get("created_at", ""),
            reverse=True,
        )

    @staticmethod
    async def add_comment(
        *,
        workspace_id: int,
        ticket_id: int,
        author_id: int,
        author_name: str,
        body: str,
    ) -> dict:
        now = _now()
        record = {
            "id": ReportCommentStore._persist_next_id(),
            "workspace_id": workspace_id,
            "ticket_id": ticket_id,
            "author_id": author_id,
            "author_name": author_name,
            "body": body,
            "mentions": sorted(set(
                token[1:] for token in body.split()
                if token.startswith("@") and len(token) > 1
            )),
            "status": "open",
            "created_at": now,
            "updated_at": now,
        }
        return await ReportCommentStore._persist_add(record)

    @staticmethod
    def list_comments(ticket_id: int, workspace_id: int) -> list[dict]:
        return sorted(
            [
                item for item in ReportCommentStore.list_by("ticket_id", ticket_id)
                if item.get("workspace_id") == workspace_id
            ],
            key=lambda item: item.get("created_at", ""),
        )

    @staticmethod
    async def update_comment_status(
        comment_id: int,
        ticket_id: int,
        workspace_id: int,
        status: str,
    ) -> Optional[dict]:
        comment = ReportCommentStore.get(comment_id)
        if (
            not comment
            or comment.get("ticket_id") != ticket_id
            or comment.get("workspace_id") != workspace_id
        ):
            return None
        return await ReportCommentStore.update_fields(
            comment_id,
            {"status": status, "updated_at": _now()},
        )

    @staticmethod
    async def add_action_item(
        *,
        workspace_id: int,
        ticket_id: int,
        title: str,
        owner: str,
        due_at: Optional[str],
        created_by: int,
    ) -> dict:
        now = _now()
        record = {
            "id": ActionItemStore._persist_next_id(),
            "workspace_id": workspace_id,
            "ticket_id": ticket_id,
            "title": title,
            "owner": owner,
            "due_at": due_at,
            "status": "open",
            "created_by": created_by,
            "created_at": now,
            "updated_at": now,
        }
        return await ActionItemStore._persist_add(record)

    @staticmethod
    def list_action_items(ticket_id: int, workspace_id: int) -> list[dict]:
        return sorted(
            [
                item for item in ActionItemStore.list_by("ticket_id", ticket_id)
                if item.get("workspace_id") == workspace_id
            ],
            key=lambda item: (item.get("status") == "done", item.get("due_at") or "9999"),
        )

    @staticmethod
    async def update_action_item(
        action_item_id: int,
        ticket_id: int,
        workspace_id: int,
        updates: dict,
    ) -> Optional[dict]:
        item = ActionItemStore.get(action_item_id)
        if (
            not item
            or item.get("ticket_id") != ticket_id
            or item.get("workspace_id") != workspace_id
        ):
            return None
        return await ActionItemStore.update_fields(
            action_item_id,
            {**updates, "updated_at": _now()},
        )

    @staticmethod
    async def add_delivery_link(
        *,
        workspace_id: int,
        ticket_id: int,
        provider: str,
        url: str,
        pull_request: str,
        commit_sha: str,
        ci_status: str,
        release_version: str,
        actual_files: list[str],
        created_by: int,
    ) -> dict:
        now = _now()
        record = {
            "id": DeliveryLinkStore._persist_next_id(),
            "workspace_id": workspace_id,
            "ticket_id": ticket_id,
            "provider": provider,
            "url": url,
            "pull_request": pull_request,
            "commit_sha": commit_sha,
            "ci_status": ci_status,
            "release_version": release_version,
            "actual_files": actual_files,
            "created_by": created_by,
            "created_at": now,
            "updated_at": now,
        }
        return await DeliveryLinkStore._persist_add(record)

    @staticmethod
    def list_delivery_links(ticket_id: int, workspace_id: int) -> list[dict]:
        return sorted(
            [
                item for item in DeliveryLinkStore.list_by("ticket_id", ticket_id)
                if item.get("workspace_id") == workspace_id
            ],
            key=lambda item: item.get("created_at", ""),
            reverse=True,
        )
