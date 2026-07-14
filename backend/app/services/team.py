"""Team and billing service - workspace tiers, usage limits, team members, report sharing.

Phase 5: In-memory store persisted to local JSON via SqliteStore.
"""
import asyncio
import json
import secrets
import hashlib
import bcrypt as _bcrypt
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from ..database import SqliteStore

logger = __import__("logging").getLogger(__name__)


class TeamMemberStore(SqliteStore):
    _entity_name = "team_members"
    _store: dict[int, dict] = {}
    _next_id: int = 1


class UsageRecordStore(SqliteStore):
    _entity_name = "usage_records"
    _store: dict[int, dict] = {}
    _next_id: int = 1


class SharedReportStore(SqliteStore):
    _entity_name = "shared_reports"
    _store: dict[int, dict] = {}
    _next_id: int = 1


class BillingStore(SqliteStore):
    _entity_name = "billing"
    _store: dict[int, dict] = {}
    _next_id: int = 1


_team_members = TeamMemberStore._store
_usage_records = UsageRecordStore._store
_shared_reports = SharedReportStore._store
_billing: dict[int, dict] = BillingStore._store
_workspace_member_locks: dict[int, asyncio.Lock] = {}


class TeamError(Exception):
    """Base exception for team/billing service."""


TIERS = {
    "free": {
        "name": "Free", "price_monthly": 0, "max_members": 2, "max_projects": 3,
        "max_analyses_per_month": 10, "max_repo_scans": 2, "max_api_specs": 3,
        "max_figma_analyses": 3, "report_sharing": False, "export_formats": ["md"],
        "ai_analysis": True, "support": "community",
    },
    "pro": {
        "name": "Pro", "price_monthly": 29, "max_members": 10, "max_projects": 20,
        "max_analyses_per_month": 100, "max_repo_scans": 20, "max_api_specs": 20,
        "max_figma_analyses": 20, "report_sharing": True,
        "export_formats": ["md", "pdf", "postman"], "ai_analysis": True, "support": "email",
    },
    "enterprise": {
        "name": "Enterprise", "price_monthly": 99, "max_members": 999, "max_projects": 999,
        "max_analyses_per_month": 9999, "max_repo_scans": 999, "max_api_specs": 999,
        "max_figma_analyses": 999, "report_sharing": True,
        "export_formats": ["md", "pdf", "postman", "jira"],
        "ai_analysis": True, "support": "priority",
    },
}


def _load_custom_tiers():
    """Override hardcoded tiers with values from ~/.scopepilot/tiers.json if present."""
    tiers_path = Path.home() / ".scopepilot" / "tiers.json"
    if not tiers_path.exists():
        return
    try:
        custom = json.loads(tiers_path.read_text(encoding="utf-8"))
        if isinstance(custom, dict):
            TIERS.update(custom)
            logger.info("Loaded custom tiers from %s", tiers_path)
    except Exception as exc:
        logger.warning("Failed to load custom tiers from %s: %s", tiers_path, exc)


_load_custom_tiers()


class TeamService:
    """Service for team management, billing, usage tracking, and report sharing."""

    @staticmethod
    def _get_billing_entry(workspace_id: int) -> Optional[dict]:
        return BillingStore.get(workspace_id) or BillingStore.find_by("workspace_id", workspace_id)

    @staticmethod
    def _get_usage_record(workspace_id: int) -> Optional[dict]:
        return UsageRecordStore.get(workspace_id) or UsageRecordStore.find_by("workspace_id", workspace_id)

    @staticmethod
    def _active_member_count(workspace_id: int) -> int:
        return sum(
            1
            for member in TeamMemberStore.list_by("workspace_id", workspace_id)
            if member.get("status", "active") == "active"
        )

    @staticmethod
    def _workspace_member_lock(workspace_id: int) -> asyncio.Lock:
        lock = _workspace_member_locks.get(workspace_id)
        if lock is None:
            lock = asyncio.Lock()
            _workspace_member_locks[workspace_id] = lock
        return lock

    @staticmethod
    def _find_member_user(workspace_id: int, member: dict) -> Optional[dict]:
        from ..api.v1.auth import UserStore

        email = member.get("email", "").strip().lower()
        user = UserStore.find_by("email", email)
        if user and user.get("workspace_id") == workspace_id:
            return user
        return None

    @staticmethod
    def _active_admin_count(workspace_id: int) -> int:
        """Count administrators who can currently authenticate to the workspace."""
        from ..api.v1.auth import UserStore

        return sum(
            1
            for user in UserStore.list_by("workspace_id", workspace_id)
            if user.get("role") == "admin"
        )

    @staticmethod
    def _is_actor_member(
        member: dict,
        user: Optional[dict],
        actor_user_id: Optional[int],
        actor_email: str,
    ) -> bool:
        if user and actor_user_id is not None and user.get("id") == actor_user_id:
            return True
        normalized_actor_email = actor_email.strip().lower()
        return bool(
            normalized_actor_email
            and member.get("email", "").strip().lower() == normalized_actor_email
        )

    @staticmethod
    async def _restore_store_record(store, record: dict) -> None:
        """Best-effort compensation when a multi-store member write fails."""
        try:
            if store.get(record["id"]):
                await store.update_fields(record["id"], record)
            else:
                await store._persist_add(record)
        except Exception:
            logger.exception("Failed to restore %s record %s", store._entity_name, record["id"])

    # ── Workspace Billing ─────────────────────────────────────────────────

    @classmethod
    def get_workspace_billing(cls, workspace_id: int) -> dict:
        entry = cls._get_billing_entry(workspace_id) or {}
        tier_name = entry.get("tier", "free")
        return {"workspace_id": workspace_id, "tier": tier_name,
                "tier_info": TIERS[tier_name], "features": cls._get_enabled_features(tier_name)}

    @classmethod
    async def upgrade_tier(cls, workspace_id: int, tier: str, payment_token: str = "") -> dict:
        if tier not in TIERS:
            raise TeamError(f"Invalid tier: {tier}. Choose from: {', '.join(TIERS.keys())}")
        if tier == "free":
            raise TeamError("Free tier is the default. Use 'pro' or 'enterprise'.")
        entry = cls._get_billing_entry(workspace_id)
        if entry is None:
            entry = {"id": workspace_id, "workspace_id": workspace_id}
            await BillingStore._persist_add(entry)
        entry["tier"] = tier
        await BillingStore.update_fields(entry["id"], {"tier": tier})
        return {"workspace_id": workspace_id, "tier": tier, "tier_info": TIERS[tier],
                "features": cls._get_enabled_features(tier),
                "message": f"Upgraded to {TIERS[tier]['name']} tier successfully."}

    @staticmethod
    def _get_enabled_features(tier: str) -> dict:
        info = TIERS.get(tier, TIERS["free"])
        return {"max_members": info["max_members"], "max_projects": info["max_projects"],
                "max_analyses_per_month": info["max_analyses_per_month"],
                "report_sharing": info["report_sharing"],
                "export_formats": info["export_formats"], "ai_analysis": info["ai_analysis"],
                "support": info["support"]}

    @classmethod
    def list_tiers(cls) -> list[dict]:
        return [{"id": k, **v} for k, v in TIERS.items()]

    # ── Usage Tracking ────────────────────────────────────────────────────

    @classmethod
    async def _ensure_usage_record(cls, workspace_id: int) -> dict:
        usage = cls._get_usage_record(workspace_id)
        if not usage:
            now = datetime.now(timezone.utc)
            usage = {
                "workspace_id": workspace_id,
                "period_start": now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat(),
                "period_end": (now.replace(day=1) + timedelta(days=32)).replace(day=1).isoformat(),
                "analyses_run": 0, "repo_scans": 0, "api_specs_imported": 0,
                "figma_analyses": 0, "members_active": 0, "projects_count": 0, "sprints_imported": 0,
            }
            usage["id"] = workspace_id
            await UsageRecordStore._persist_add(usage)
        return usage

    @classmethod
    async def sync_members_active(cls, workspace_id: int) -> int:
        """Keep active-member usage aligned with canonical team membership."""
        usage = await cls._ensure_usage_record(workspace_id)
        active_count = cls._active_member_count(workspace_id)
        if usage.get("members_active") != active_count:
            await UsageRecordStore.update_fields(
                usage["id"], {"members_active": active_count},
            )
        return active_count

    @classmethod
    async def get_usage(cls, workspace_id: int) -> dict:
        usage = await cls._ensure_usage_record(workspace_id)
        await cls.sync_members_active(workspace_id)

        tier_info = TIERS["free"]
        entry = cls._get_billing_entry(workspace_id) or {}
        tier_name = entry.get("tier", "free")
        if tier_name in TIERS:
            tier_info = TIERS[tier_name]
        return {
            "current": usage,
            "limits": {"max_members": tier_info["max_members"],
                       "max_projects": tier_info["max_projects"],
                       "max_analyses_per_month": tier_info["max_analyses_per_month"],
                       "max_repo_scans": tier_info["max_repo_scans"],
                       "max_api_specs": tier_info["max_api_specs"],
                       "max_figma_analyses": tier_info["max_figma_analyses"]},
        }

    @classmethod
    async def increment_usage(cls, workspace_id: int, metric: str, amount: int = 1):
        usage = (await cls.get_usage(workspace_id))["current"]
        if metric in usage:
            usage[metric] += amount
            if usage[metric] < 0:
                usage[metric] = 0
            await UsageRecordStore.update_fields(usage["id"], {})

    @classmethod
    async def check_usage_limit(cls, workspace_id: int, metric: str) -> tuple[bool, str]:
        usage_data = await cls.get_usage(workspace_id)
        current = usage_data["current"].get(metric, 0)
        metric_to_limit = {"analyses_run": "max_analyses_per_month", "repo_scans": "max_repo_scans",
                           "api_specs_imported": "max_api_specs", "figma_analyses": "max_figma_analyses",
                           "members_active": "max_members", "projects_count": "max_projects"}
        limit_key = metric_to_limit.get(metric)
        if limit_key and limit_key in usage_data["limits"]:
            if current >= usage_data["limits"][limit_key]:
                return False, f"Usage limit reached for {metric} ({current}/{usage_data['limits'][limit_key]})"
        return True, ""

    # ── Team Members ──────────────────────────────────────────────────────

    @classmethod
    def list_members(cls, workspace_id: int) -> list[dict]:
        return TeamMemberStore.list_by("workspace_id", workspace_id)

    @classmethod
    async def add_member(cls, workspace_id: int, email: str, name: str, role: str = "member", invited_by: Optional[str] = None) -> dict:
        allowed, reason = await cls.check_usage_limit(workspace_id, "members_active")
        if not allowed:
            raise TeamError(reason + ". Upgrade your plan to add more members.")
        existing = [m for m in TeamMemberStore.list_by("workspace_id", workspace_id) if m["email"] == email]
        if existing:
            raise TeamError(f"Member {email} already exists in this workspace.")

        existing_member = next(
            (
                item for item in TeamMemberStore.list_by("workspace_id", workspace_id)
                if item.get("email", "").lower() == email.lower()
            ),
            None,
        )
        if existing_member:
            raise TeamError("A member with this email already exists.")
        from ..api.v1.auth import UserStore
        user = UserStore.find_by("email", email.lower())
        if user and user.get("workspace_id") != workspace_id:
            raise TeamError("This email belongs to another workspace.")
        if user:
            await UserStore.update_fields(user["id"], {"role": role, "name": name})
        now = datetime.now(timezone.utc).isoformat()
        member = {"id": TeamMemberStore._persist_next_id(), "workspace_id": workspace_id,
                  "email": email.lower(), "name": name, "role": role,
                  "status": "active" if user else "invited",
                  "invite_token": "" if user else secrets.token_urlsafe(24),
                  "invited_by": invited_by or "",
                  "invited_at": now,
                  "joined_at": now if user else None}
        await TeamMemberStore._persist_add(member)
        await cls.sync_members_active(workspace_id)
        return member

    @classmethod
    async def update_member_role(
        cls,
        workspace_id: int,
        member_id: int,
        role: str,
        actor_user_id: Optional[int] = None,
        actor_email: str = "",
    ) -> Optional[dict]:
        if role not in ("admin", "member", "viewer"):
            raise TeamError(f"Invalid role: {role}")

        async with cls._workspace_member_lock(workspace_id):
            member = TeamMemberStore.get(member_id)
            if not member or member.get("workspace_id") != workspace_id:
                return None

            from ..api.v1.auth import UserStore

            user = cls._find_member_user(workspace_id, member)
            is_self = cls._is_actor_member(
                member, user, actor_user_id, actor_email,
            )
            if is_self and role != "admin":
                raise TeamError("不能更改自己的管理员角色，请先由另一名管理员接管。")
            if (
                user
                and user.get("role") == "admin"
                and role != "admin"
                and cls._active_admin_count(workspace_id) <= 1
            ):
                raise TeamError("工作区必须至少保留一名可登录的管理员。")

            previous_member = dict(member)
            previous_user = dict(user) if user else None
            if member.get("role") == role and (not user or user.get("role") == role):
                return member

            try:
                if user:
                    updated_user = await UserStore.update_fields(user["id"], {"role": role})
                    if not updated_user:
                        raise RuntimeError("User record disappeared during role update")
                updated_member = await TeamMemberStore.update_fields(member_id, {"role": role})
                if not updated_member:
                    raise RuntimeError("Team member disappeared during role update")
                return updated_member
            except Exception as exc:
                await cls._restore_store_record(TeamMemberStore, previous_member)
                if previous_user:
                    await cls._restore_store_record(UserStore, previous_user)
                raise TeamError("团队角色更新失败，已撤销本次变更。") from exc

    @classmethod
    async def remove_member(
        cls,
        workspace_id: int,
        member_id: int,
        actor_user_id: Optional[int] = None,
        actor_email: str = "",
    ) -> bool:
        async with cls._workspace_member_lock(workspace_id):
            member = TeamMemberStore.get(member_id)
            if not member or member.get("workspace_id") != workspace_id:
                return False

            from ..api.v1.auth import UserStore

            user = cls._find_member_user(workspace_id, member)
            if cls._is_actor_member(member, user, actor_user_id, actor_email):
                raise TeamError("不能移除自己的工作区账号。")
            if (
                user
                and user.get("role") == "admin"
                and cls._active_admin_count(workspace_id) <= 1
            ):
                raise TeamError("工作区必须至少保留一名可登录的管理员。")

            previous_member = dict(member)
            previous_user = dict(user) if user else None
            try:
                if user and not await UserStore._persist_delete(user["id"]):
                    raise RuntimeError("User record disappeared during member removal")
                if not await TeamMemberStore._persist_delete(member_id):
                    raise RuntimeError("Team member disappeared during member removal")
            except Exception as exc:
                await cls._restore_store_record(TeamMemberStore, previous_member)
                if previous_user:
                    await cls._restore_store_record(UserStore, previous_user)
                raise TeamError("成员移除失败，已撤销本次变更。") from exc

            await cls.sync_members_active(workspace_id)
            return True

    # ── Report Sharing ────────────────────────────────────────────────────

    @classmethod
    async def share_report(cls, workspace_id: int, sprint_id: int, title: str,
                     shared_by: str = "", expires_in_days: int = 30, password: str = "",
                     snapshot_id: Optional[int] = None) -> dict:
        entry = cls._get_billing_entry(workspace_id) or {}
        tier_name = entry.get("tier", "free")
        tier_info = TIERS.get(tier_name, TIERS["free"])
        if not tier_info["report_sharing"]:
            raise TeamError("Report sharing is not available on the Free tier. Upgrade to Pro.")

        share_token = secrets.token_urlsafe(16)
        now = datetime.now(timezone.utc)
        share = {"id": SharedReportStore._persist_next_id(), "workspace_id": workspace_id,
                 "sprint_id": sprint_id, "title": title, "shared_by": shared_by,
                 "snapshot_id": snapshot_id,
                 "share_token": share_token, "view_count": 0,
                 "is_password_protected": bool(password),
                 "password_hash": cls._hash_password(password) if password else "",
                 "created_at": now.isoformat(), "expires_at": (now + timedelta(days=expires_in_days)).isoformat(),
                 "is_active": True}
        await SharedReportStore._persist_add(share)
        return {k: v for k, v in share.items() if k != "password_hash"}

    @staticmethod
    def _hash_password(password: str) -> str:
        return _bcrypt.hashpw(password.encode(), _bcrypt.gensalt()).decode()

    @staticmethod
    def _verify_password(password: str, password_hash: str) -> tuple[bool, str]:
        if password_hash.startswith("$2"):
            return _bcrypt.checkpw(password.encode(), password_hash.encode()), ""

        legacy_hash = hashlib.sha256(password.encode()).hexdigest()
        if legacy_hash == password_hash:
            return True, TeamService._hash_password(password)
        return False, ""

    @classmethod
    def list_shared_reports(cls, workspace_id: int) -> list[dict]:
        return [{k: v for k, v in r.items() if k != "password_hash"}
                for r in SharedReportStore.list_by("workspace_id", workspace_id)]

    @classmethod
    async def get_shared_report(cls, share_token: str, password: str = "") -> Optional[dict]:
        share = SharedReportStore.find_by("share_token", share_token)
        if not share or not share.get("is_active", True):
            return None
        if share.get("expires_at") and share["expires_at"] < datetime.now(timezone.utc).isoformat():
            return None
        if share.get("is_password_protected") and share.get("password_hash"):
            if not password:
                raise TeamError("This report is password protected.")
            valid, migrated_hash = cls._verify_password(password, share["password_hash"])
            if not valid:
                raise TeamError("Invalid password.")
            if migrated_hash:
                share["password_hash"] = migrated_hash
                await SharedReportStore.update_fields(share["id"], {"password_hash": migrated_hash})
        share["view_count"] = share.get("view_count", 0) + 1
        await SharedReportStore.update_fields(share["id"], {"view_count": share["view_count"]})
        return {k: v for k, v in share.items() if k != "password_hash"}

    @classmethod
    async def revoke_share(cls, workspace_id: int, share_id: int) -> bool:
        share = SharedReportStore.get(share_id)
        if share and share["workspace_id"] == workspace_id:
            share["is_active"] = False
            await SharedReportStore.update_fields(share_id, {"is_active": False})
            return True
        return False

    @classmethod
    def get_sharing_history(cls, workspace_id: int) -> list[dict]:
        return [{k: v for k, v in s.items() if k != "password_hash"}
                for s in SharedReportStore.list_by("workspace_id", workspace_id)]
