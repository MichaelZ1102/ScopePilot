"""Sprint import, listing & detail routes.

All endpoints require a valid Bearer token.  The token provides the
``workspace_id`` which is used to scope projects and sprints.
"""
from fastapi import APIRouter, Depends, HTTPException

from ...schemas import SprintImportRequest, SprintResponse, SprintDetailResponse
from ...services import get_current_user
from ...services.jira import JiraService, JiraServiceError
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
    token_data: dict = Depends(get_current_user),
):
    """Import a Sprint (and its tickets) from Jira.

    The calling user's token must belong to the same workspace as the
    referenced project.
    """
    project = _get_project(req.project_id, token_data)

    try:
        result = await JiraService.import_sprint(project, req.sprint_name, ws_id)
    except JiraServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return SprintDetailResponse(**result)


# ── GET /api/v1/sprints ──────────────────────────────────────────────────────


@router.get("/", response_model=list[SprintResponse])
async def list_sprints(
    project_id: int,
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
    sprint_id: int,
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
