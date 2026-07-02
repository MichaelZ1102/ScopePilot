"""Startup loader — loads persisted data into all in-memory stores.

Called once at backend startup (from main.py) to restore data
from SQLite so nothing is lost across restarts.
Also handles migration from old JSON files to SQLite.
"""
import json
import logging
from pathlib import Path

from .database import SqliteStore, DB_DIR, DB_PATH

logger = logging.getLogger(__name__)


def _migrate_from_json(entity_name: str, store_cls: type) -> bool:
    """Migrate data from old JSON file to SQLite if SQLite is empty."""
    # Check if SQLite already has data for this entity
    from .database import _load_all, _init_table
    _init_table(entity_name)
    existing = _load_all(entity_name)
    if existing:
        return False  # Already migrated

    # Check for old JSON file
    json_path = DB_DIR / "data" / f"{entity_name}.json"
    if not json_path.exists():
        return False

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        records = data.get("records", [])
        next_id = data.get("next_id", 1)

        if not records:
            return False

        # Load into store
        store_cls._store.clear()
        for rec in records:
            rid = rec.get("id")
            if rid is not None:
                store_cls._store[rid] = rec
        store_cls._next_id = next_id
        for rid, rec in store_cls._store.items():
            _init_table(entity_name)
            from .database import _upsert
            _upsert(entity_name, rid, {k: v for k, v in rec.items() if k != "id"})

        # Clean up JSON file
        json_path.unlink()
        logger.info(f"Migrated {len(records)} records from {json_path.name} to SQLite")
        return True
    except Exception as e:
        logger.warning(f"Migration failed for {entity_name}: {e}")
        return False


def load_persisted_data():
    """Load all SqliteStore-backed data from SQLite into memory."""
    from .services.jira import SprintStore, TicketStore
    from .services.analysis import AnalysisJobStore
    from .services.lifecycle import (
        AnalysisRunStore,
        TicketReviewStore,
        TicketArtifactLinkStore,
        ReportSnapshotStore,
        SyncRunStore,
        AuditLogStore,
        ReportCommentStore,
        ActionItemStore,
        DeliveryLinkStore,
    )
    from .services.codebase import CodeSourceStore, RepoSnapshotStore, CodeImpactStore
    from .services.api_test_planner import ApiImpactStore, ApiSpecStore, TestPlanStore
    from .services.figma import FigmaAnalysisStore
    from .services.team import TeamMemberStore, UsageRecordStore, SharedReportStore, BillingStore
    from .services.notifications import NotificationStore, WebhookSubscriptionStore
    from .api.v1.projects import ProjectStore
    from .api.v1.auth import UserStore, WorkspaceStore

    stores = [
        ("sprints", SprintStore), ("tickets", TicketStore),
        ("analysis_jobs", AnalysisJobStore),
        ("analysis_runs", AnalysisRunStore),
        ("ticket_reviews", TicketReviewStore),
        ("ticket_artifact_links", TicketArtifactLinkStore),
        ("report_snapshots", ReportSnapshotStore),
        ("sync_runs", SyncRunStore),
        ("audit_logs", AuditLogStore),
        ("report_comments", ReportCommentStore),
        ("action_items", ActionItemStore),
        ("delivery_links", DeliveryLinkStore),
        ("code_sources", CodeSourceStore), ("repo_snapshots", RepoSnapshotStore),
        ("code_impacts", CodeImpactStore),
        ("api_specs", ApiSpecStore), ("test_plans", TestPlanStore),
        ("api_impacts", ApiImpactStore),
        ("figma_analyses", FigmaAnalysisStore),
        ("team_members", TeamMemberStore), ("usage_records", UsageRecordStore),
        ("billing", BillingStore),
        ("shared_reports", SharedReportStore),
        ("notifications", NotificationStore),
        ("webhook_subscriptions", WebhookSubscriptionStore),
        ("projects", ProjectStore),
        ("auth_users", UserStore), ("auth_workspaces", WorkspaceStore),
    ]

    migrated_count = 0
    for entity_name, store_cls in stores:
        # Try to migrate from old JSON
        if _migrate_from_json(entity_name, store_cls):
            migrated_count += 1
        else:
            # Normal SQLite load
            store_cls._load_all_at_startup()

    if migrated_count:
        logger.info(f"Migrated {migrated_count} entities from JSON to SQLite")

    # Backfill workspace owners created before team membership was persisted.
    from .database import _upsert
    existing_member_emails = {
        (member.get("workspace_id"), member.get("email", "").lower())
        for member in TeamMemberStore.list_all()
    }
    for user in UserStore.list_all():
        identity = (user.get("workspace_id"), user.get("email", "").lower())
        if identity in existing_member_emails:
            continue
        member_id = TeamMemberStore._persist_next_id()
        member = {
            "id": member_id,
            "workspace_id": user.get("workspace_id"),
            "email": user.get("email", "").lower(),
            "name": user.get("name", ""),
            "role": user.get("role", "viewer"),
            "status": "active",
            "invite_token": "",
            "invited_by": "",
            "invited_at": "",
            "joined_at": "",
        }
        TeamMemberStore._store[member_id] = member
        _upsert(
            TeamMemberStore._entity_name,
            member_id,
            {key: value for key, value in member.items() if key != "id"},
        )
        existing_member_emails.add(identity)

    # Rebuild email index for auth
    from .api.v1.auth import _rebuild_email_index
    _rebuild_email_index()

    # Load token blacklist
    from .services import _load_blacklist
    _load_blacklist()

    logger.info(f"All persisted data loaded (SQLite: {DB_PATH})")
