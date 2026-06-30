"""Team & billing routes: members, usage, billing tiers, report sharing."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from ...services import get_current_user
from ...services.team import TeamService, TeamError

router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────

class UpgradeRequest(BaseModel):
    tier: str
    payment_token: str = ""


class MemberAddRequest(BaseModel):
    email: str
    name: str
    role: str = "member"


class MemberRoleUpdate(BaseModel):
    role: str


class ShareRequest(BaseModel):
    sprint_id: int
    title: str
    shared_by: str = ""
    expires_in_days: int = 30
    password: str = ""


class ShareAccessRequest(BaseModel):
    password: str = ""


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
    token_data: dict = Depends(get_current_user),
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


# ── Members ───────────────────────────────────────────────────────────────


@router.get("/members")
async def list_members(token_data: dict = Depends(get_current_user)):
    """List all workspace members."""
    return TeamService.list_members(token_data.get("workspace_id"))


@router.post("/members", status_code=201)
async def add_member(
    data: MemberAddRequest,
    token_data: dict = Depends(get_current_user),
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
    member_id: int,
    data: MemberRoleUpdate,
    token_data: dict = Depends(get_current_user),
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
    member_id: int,
    token_data: dict = Depends(get_current_user),
):
    """Remove a member from the workspace."""
    if not await TeamService.remove_member(token_data.get("workspace_id"), member_id):
        raise HTTPException(status_code=404, detail="Member not found")


# ── Report Sharing ────────────────────────────────────────────────────────


@router.post("/share", status_code=201)
async def share_report(
    data: ShareRequest,
    token_data: dict = Depends(get_current_user),
):
    """Create a shareable report link."""
    try:
        return await TeamService.share_report(
            workspace_id=token_data.get("workspace_id"),
            sprint_id=data.sprint_id,
            title=data.title,
            shared_by=data.shared_by or token_data.get("sub", ""),
            expires_in_days=data.expires_in_days,
            password=data.password,
        )
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
        return report
    except TeamError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.delete("/shared/{share_id}", status_code=204)
async def revoke_share(
    share_id: int,
    token_data: dict = Depends(get_current_user),
):
    """Revoke a shared report link."""
    if not await TeamService.revoke_share(token_data.get("workspace_id"), share_id):
        raise HTTPException(status_code=404, detail="Shared report not found")
