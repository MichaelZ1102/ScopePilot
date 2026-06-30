"""Project management routes - CRUD + Jira config."""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException

from ...schemas import ProjectCreate, ProjectResponse, ProjectUpdate
from ...services import get_current_user
from ...database import SqliteStore
from ...services.jira import JiraService
from ...encryption import encrypt, decrypt

router = APIRouter()


# --- Persisted store ---
class ProjectStore(SqliteStore):
    _entity_name = "projects"
    _store: dict[int, dict] = {}
    _next_id: int = 1


_projects = ProjectStore._store
_next_id = ProjectStore._next_id


@router.get("/", response_model=list[ProjectResponse])
async def list_projects(token_data: dict = Depends(get_current_user)):
    """List all projects in current workspace."""
    ws_id = token_data.get("workspace_id")
    return [
        ProjectResponse(**p) for p in _projects.values()
        if p["workspace_id"] == ws_id
    ]


@router.post("/", response_model=ProjectResponse, status_code=201)
async def create_project(req: ProjectCreate, token_data: dict = Depends(get_current_user)):
    """Create a new project with Jira configuration."""
    ws_id = token_data.get("workspace_id")
    if not req.jira_url or not req.jira_email or not req.jira_api_token:
        raise HTTPException(status_code=400, detail="Jira configuration is required")

    project = {
        "id": ProjectStore._persist_next_id(),
        "name": req.name,
        "jira_url": req.jira_url.rstrip("/"),
        "jira_email": req.jira_email,
        "jira_api_token": encrypt(req.jira_api_token),
        "jira_project_key": req.jira_project_key,
        "workspace_id": ws_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await ProjectStore._persist_add(project)
    return ProjectResponse(**project)


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: int, token_data: dict = Depends(get_current_user)):
    """Get project details."""
    ws_id = token_data.get("workspace_id")
    project = _projects.get(project_id)
    if not project or project["workspace_id"] != ws_id:
        raise HTTPException(status_code=404, detail="Project not found")
    return ProjectResponse(**project)


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: int, req: ProjectUpdate,
    token_data: dict = Depends(get_current_user),
):
    """Update project configuration."""
    ws_id = token_data.get("workspace_id")
    project = _projects.get(project_id)
    if not project or project["workspace_id"] != ws_id:
        raise HTTPException(status_code=404, detail="Project not found")

    update_data = req.model_dump(exclude_none=True)
    if "jira_api_token" in update_data:
        update_data["jira_api_token"] = encrypt(update_data["jira_api_token"])
    project.update(update_data)
    await ProjectStore._persist_update(project_id, update_data)
    return ProjectResponse(**project)


@router.delete("/{project_id}", status_code=204)
async def delete_project(project_id: int, token_data: dict = Depends(get_current_user)):
    """Delete a project and cascade-delete its sprints and tickets."""
    ws_id = token_data.get("workspace_id")
    project = _projects.get(project_id)
    if not project or project["workspace_id"] != ws_id:
        raise HTTPException(status_code=404, detail="Project not found")
    # Cascade delete sprints and tickets
    await JiraService.delete_project_data(project_id)
    await ProjectStore._persist_delete(project_id)
