"""Team & billing routes: members, usage, billing tiers, report sharing."""
from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel, Field, field_validator
from typing import Annotated, Literal, Optional

from ...services import get_current_actor, get_current_user, require_roles
from ...services.lifecycle import LifecycleService
from ...services.team import TeamService, TeamError

router = APIRouter()
EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


def _verify_sprint_access(sprint_id: int, workspace_id: int) -> None:
    from ...services.jira import JiraService
    from .projects import _projects

    sprint = JiraService.get_sprint(sprint_id)
    if not sprint:
        raise HTTPException(status_code=404, detail="Sprint not found")

    project = _projects.get(sprint["project_id"])
    if not project or project.get("workspace_id") != workspace_id:
        raise HTTPException(status_code=404, detail="Sprint not found")


# ── Schemas ───────────────────────────────────────────────────────────────

class UpgradeRequest(BaseModel):
    tier: Literal["pro", "enterprise"]
    payment_token: str = Field(default="", max_length=4096)


class MemberAddRequest(BaseModel):
    email: str = Field(pattern=EMAIL_PATTERN, max_length=254)
    name: str = Field(min_length=1, max_length=100)
    role: Literal["admin", "member", "viewer"] = "member"

    @field_validator("email")
    @classmethod
    def _normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class MemberRoleUpdate(BaseModel):
    role: Literal["admin", "member", "viewer"]


class ShareRequest(BaseModel):
    sprint_id: int = Field(gt=0)
    title: str = Field(min_length=1, max_length=200)
    shared_by: str = Field(default="", max_length=254)
    expires_in_days: int = Field(default=30, ge=1, le=365)
    password: str = Field(default="", max_length=256)


class ShareAccessRequest(BaseModel):
    password: str = Field(default="", max_length=256)


# ── Tiers ─────────────────────────────────────────────────────────────────


@router.get("/tiers")
async def list_tiers():
    """List all available billing tiers."""
    return TeamService.list_tiers()


@router.get("/billing")
async def get_billing(token_data: dict = Depends(get_current_user)):
    """Get current workspace billing info."""
    return TeamService.get_workspace_billing(token_data.get("workspace_id"))


@router.post("/billing/upgrade")
async def upgrade_tier(
    data: UpgradeRequest,
    token_data: dict = Depends(require_roles("admin")),
):
    """Upgrade workspace to a paid tier."""
    try:
        return await TeamService.upgrade_tier(
            token_data.get("workspace_id"), data.tier, data.payment_token,
        )
    except TeamError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Usage ─────────────────────────────────────────────────────────────────


@router.get("/usage")
async def get_usage(token_data: dict = Depends(get_current_user)):
    """Get current workspace usage and limits."""
    return await TeamService.get_usage(token_data.get("workspace_id"))


@router.get("/audit-logs")
async def list_audit_logs(
    token_data: dict = Depends(require_roles("admin")),
):
    """List workspace audit events for administrators."""
    return LifecycleService.list_audit_logs(token_data.get("workspace_id"))


# ── Members ───────────────────────────────────────────────────────────────


@router.get("/members")
async def list_members(token_data: dict = Depends(get_current_actor)):
    """List all workspace members."""
    members = TeamService.list_members(token_data.get("workspace_id"))
    if token_data.get("role") == "admin":
        return members
    return [
        {key: value for key, value in member.items() if key != "invite_token"}
        for member in members
    ]


@router.post("/members", status_code=201)
async def add_member(
    data: MemberAddRequest,
    token_data: dict = Depends(require_roles("admin")),
):
    """Add a team member to the workspace."""
    try:
        return await TeamService.add_member(
            workspace_id=token_data.get("workspace_id"),
            email=data.email,
            name=data.name,
            role=data.role,
            invited_by=token_data.get("sub"),
        )
    except TeamError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/members/{member_id}/role")
async def update_member_role(
    member_id: Annotated[int, Path(gt=0)],
    data: MemberRoleUpdate,
    token_data: dict = Depends(require_roles("admin")),
):
    """Change a member's role."""
    member = await TeamService.update_member_role(
        token_data.get("workspace_id"), member_id, data.role,
    )
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    return member


@router.delete("/members/{member_id}", status_code=204)
async def remove_member(
    member_id: Annotated[int, Path(gt=0)],
    token_data: dict = Depends(require_roles("admin")),
):
    """Remove a member from the workspace."""
    if not await TeamService.remove_member(token_data.get("workspace_id"), member_id):
        raise HTTPException(status_code=404, detail="Member not found")


# ── Report Sharing ────────────────────────────────────────────────────────


@router.post("/share", status_code=201)
async def share_report(
    data: ShareRequest,
    token_data: dict = Depends(require_roles("admin", "member")),
):
    """Create a shareable report link."""
    workspace_id = token_data.get("workspace_id")
    _verify_sprint_access(data.sprint_id, workspace_id)
    from ...services.reporting import ReportingService
    snapshot = ReportingService.latest_published_snapshot(workspace_id, data.sprint_id)
    if not snapshot:
        raise HTTPException(
            status_code=409,
            detail="Publish an approved Sprint report before sharing it.",
        )
    try:
        shared = await TeamService.share_report(
            workspace_id=workspace_id,
            sprint_id=data.sprint_id,
            title=data.title,
            shared_by=data.shared_by or token_data.get("sub", ""),
            expires_in_days=data.expires_in_days,
            password=data.password,
            snapshot_id=snapshot["id"],
        )
        await LifecycleService.audit(
            workspace_id=workspace_id,
            actor_id=token_data.get("user_id"),
            actor_name=token_data.get("name", token_data.get("sub", "")),
            action="report.share",
            resource_type="sprint",
            resource_id=data.sprint_id,
            details={"share_id": shared["id"], "snapshot_id": snapshot["id"]},
        )
        return shared
    except TeamError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/shared")
async def list_shared_reports(token_data: dict = Depends(get_current_user)):
    """List all shared reports for the workspace."""
    return TeamService.list_shared_reports(token_data.get("workspace_id"))


@router.get("/shared/history")
async def get_sharing_history(token_data: dict = Depends(get_current_user)):
    """Get sharing history (active + expired)."""
    return TeamService.get_sharing_history(token_data.get("workspace_id"))


@router.post("/shared/access/{share_token}")
async def access_shared_report(
    share_token: str,
    data: ShareAccessRequest = ShareAccessRequest(),
):
    """Access a shared report by token (public endpoint, no auth)."""
    try:
        report = await TeamService.get_shared_report(share_token, data.password)
        if not report:
            raise HTTPException(status_code=404, detail="Shared report not found or expired")
        from ...services.lifecycle import ReportSnapshotStore
        snapshot = ReportSnapshotStore.get(report.get("snapshot_id"))
        if (
            snapshot
            and snapshot.get("workspace_id") == report.get("workspace_id")
            and snapshot.get("status") == "published"
        ):
            report["content"] = snapshot.get("content", "")
            report["report_version"] = snapshot.get("version")
        else:
            report["content"] = ""
            report["content_error"] = "Published report snapshot is unavailable."
        return report
    except TeamError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.delete("/shared/{share_id}", status_code=204)
async def revoke_share(
    share_id: Annotated[int, Path(gt=0)],
    token_data: dict = Depends(require_roles("admin", "member")),
):
    """Revoke a shared report link."""
    if not await TeamService.revoke_share(token_data.get("workspace_id"), share_id):
        raise HTTPException(status_code=404, detail="Shared report not found")
