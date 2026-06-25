"""Project management routes - CRUD + Jira config."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from ...services import get_current_user

router = APIRouter()


# --- Schemas ---
class ProjectCreate(BaseModel):
    name: str
    jira_url: str
    jira_email: str
    jira_api_token: str
    jira_project_key: str


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    jira_url: Optional[str] = None
    jira_email: Optional[str] = None
    jira_api_token: Optional[str] = None
    jira_project_key: Optional[str] = None


class ProjectResponse(BaseModel):
    id: int
    name: str
    jira_url: str
    jira_project_key: str
    workspace_id: int
    created_at: str

    class Config:
        from_attributes = True


# --- In-memory store ---
_projects: dict[int, dict] = {}
_next_id = 1


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
    global _next_id

    ws_id = token_data.get("workspace_id")
    if not req.jira_url or not req.jira_email or not req.jira_api_token:
        raise HTTPException(status_code=400, detail="Jira configuration is required")

    project = {
        "id": _next_id,
        "name": req.name,
        "jira_url": req.jira_url.rstrip("/"),
        "jira_email": req.jira_email,
        "jira_api_token": req.jira_api_token,
        "jira_project_key": req.jira_project_key,
        "workspace_id": ws_id,
        "created_at": "2026-06-25T00:00:00",
    }
    _projects[_next_id] = project
    _next_id += 1

    return ProjectResponse(**project)


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: int, token_data: dict = Depends(get_current_user)):
    """Get project details."""
    project = _projects.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return ProjectResponse(**project)


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: int, req: ProjectUpdate,
    token_data: dict = Depends(get_current_user),
):
    """Update project configuration."""
    project = _projects.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    update_data = req.model_dump(exclude_none=True)
    project.update(update_data)
    return ProjectResponse(**project)


@router.delete("/{project_id}", status_code=204)
async def delete_project(project_id: int, token_data: dict = Depends(get_current_user)):
    """Delete a project."""
    if project_id not in _projects:
        raise HTTPException(status_code=404, detail="Project not found")
    del _projects[project_id]
