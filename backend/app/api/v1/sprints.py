"""Sprint import, listing & detail routes.

All endpoints require a valid Bearer token.  The token provides the
``workspace_id`` which is used to scope projects and sprints.
"""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query

from ...schemas import SprintImportRequest, SprintResponse, SprintDetailResponse
from ...services import get_current_user, require_roles
from ...services.jira import JiraService, JiraServiceError
from ...services.notifications import NotificationService
from ..v1.projects import _projects  # in-memory project store

router = APIRouter()


# ── Helpers ──────────────────────────────────────────────────────────────────


def _get_project(project_id: int, token_data: dict) -> dict:
    """Look up a project, verifying it belongs to the caller's workspace."""
    project = _projects.get(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if project["workspace_id"] != token_data.get("workspace_id"):
        raise HTTPException(status_code=403, detail="Access denied")
    return project


# ── POST /api/v1/sprints/import ──────────────────────────────────────────────


@router.post("/import", response_model=SprintDetailResponse, status_code=201)
async def import_sprint(
    req: SprintImportRequest,
    token_data: dict = Depends(require_roles("admin", "member")),
):
    """Import a Sprint (and its tickets) from Jira.

    The calling user's token must belong to the same workspace as the
    referenced project.
    """
    project = _get_project(req.project_id, token_data)
    ws_id = token_data.get("workspace_id")

    try:
        result = await JiraService.import_sprint(project, req.sprint_name, ws_id)
    except JiraServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return SprintDetailResponse(**result)


# ── GET /api/v1/sprints ──────────────────────────────────────────────────────


@router.get("/", response_model=list[SprintResponse])
async def list_sprints(
    project_id: Annotated[int, Query(gt=0)],
    token_data: dict = Depends(get_current_user),
):
    """List all sprints belonging to a project."""
    # Verify project exists and is accessible
    _get_project(project_id, token_data)

    sprints = JiraService.list_sprints(project_id)
    # Return without the nested tickets for list view
    return [SprintResponse(**{k: v for k, v in s.items() if k != "tickets"})
            for s in sprints]


# ── GET /api/v1/sprints/{sprint_id} ──────────────────────────────────────────


@router.get("/{sprint_id}", response_model=SprintDetailResponse)
async def get_sprint(
    sprint_id: Annotated[int, Path(gt=0)],
    token_data: dict = Depends(get_current_user),
):
    """Get full sprint details including imported tickets."""
    sprint = JiraService.get_sprint(sprint_id)
    if sprint is None:
        raise HTTPException(status_code=404, detail="Sprint not found")

    # Verify project access
    try:
        _get_project(sprint["project_id"], token_data)
    except HTTPException:
        raise HTTPException(status_code=404, detail="Sprint not found")

    return SprintDetailResponse(**sprint)


@router.post("/{sprint_id}/sync")
async def sync_sprint(
    sprint_id: Annotated[int, Path(gt=0)],
    token_data: dict = Depends(require_roles("admin", "member")),
):
    """Synchronize an imported Sprint with Jira without creating duplicates."""
    sprint = JiraService.get_sprint(sprint_id)
    if sprint is None:
        raise HTTPException(status_code=404, detail="Sprint not found")
    project = _get_project(sprint["project_id"], token_data)
    try:
        result = await JiraService.sync_sprint(
            sprint_id,
            project,
            token_data.get("workspace_id"),
        )
        summary = result.get("summary", {})
        if summary.get("added") or summary.get("updated") or summary.get("removed"):
            await NotificationService.emit(
                workspace_id=token_data.get("workspace_id"),
                event_type="jira.sync.changed",
                title=f"{sprint['name']} 已同步",
                message=(
                    f"新增 {len(summary.get('added', []))}，"
                    f"更新 {len(summary.get('updated', []))}，"
                    f"移除 {len(summary.get('removed', []))}。"
                ),
                resource_type="sprint",
                resource_id=sprint_id,
                details=summary,
            )
        return result
    except JiraServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
