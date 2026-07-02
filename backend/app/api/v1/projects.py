"""Project management routes - CRUD + Jira config."""
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path

from ...schemas import ProjectCreate, ProjectResponse, ProjectUpdate
from ...services import get_current_user, require_roles
from ...database import SqliteStore
from ...services.jira import JiraService
from ...services.lifecycle import LifecycleService
from ...encryption import encrypt

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
    return [ProjectResponse(**p) for p in ProjectStore.list_by("workspace_id", ws_id)]


@router.post("/", response_model=ProjectResponse, status_code=201)
async def create_project(req: ProjectCreate, token_data: dict = Depends(require_roles("admin"))):
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
    await LifecycleService.audit(
        workspace_id=ws_id,
        actor_id=token_data.get("user_id"),
        actor_name=token_data.get("name", token_data.get("sub", "")),
        action="project.create",
        resource_type="project",
        resource_id=project["id"],
        details={"name": project["name"], "jira_project_key": project["jira_project_key"]},
    )
    return ProjectResponse(**project)


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: Annotated[int, Path(gt=0)], token_data: dict = Depends(get_current_user)):
    """Get project details."""
    ws_id = token_data.get("workspace_id")
    project = ProjectStore.get(project_id)
    if not project or project["workspace_id"] != ws_id:
        raise HTTPException(status_code=404, detail="Project not found")
    return ProjectResponse(**project)


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: Annotated[int, Path(gt=0)], req: ProjectUpdate,
    token_data: dict = Depends(require_roles("admin")),
):
    """Update project configuration."""
    ws_id = token_data.get("workspace_id")
    project = ProjectStore.get(project_id)
    if not project or project["workspace_id"] != ws_id:
        raise HTTPException(status_code=404, detail="Project not found")

    update_data = req.model_dump(exclude_none=True)
    if "jira_api_token" in update_data:
        update_data["jira_api_token"] = encrypt(update_data["jira_api_token"])
    project.update(update_data)
    await ProjectStore.update_fields(project_id, update_data)
    await LifecycleService.audit(
        workspace_id=ws_id,
        actor_id=token_data.get("user_id"),
        actor_name=token_data.get("name", token_data.get("sub", "")),
        action="project.update",
        resource_type="project",
        resource_id=project_id,
        details={"fields": [key for key in update_data if key != "jira_api_token"]},
    )
    return ProjectResponse(**project)


@router.delete("/{project_id}", status_code=204)
async def delete_project(project_id: Annotated[int, Path(gt=0)], token_data: dict = Depends(require_roles("admin"))):
    """Delete a project and cascade-delete its sprints and tickets."""
    ws_id = token_data.get("workspace_id")
    project = ProjectStore.get(project_id)
    if not project or project["workspace_id"] != ws_id:
        raise HTTPException(status_code=404, detail="Project not found")
    from ...services.api_test_planner import ApiTestPlannerService, ApiSpecStore
    from ...services.codebase import CodebaseService, CodeSourceStore
    from ...services.figma import FigmaAnalysisStore, FigmaService
    from ...services.jira import SprintStore, TicketStore

    sprint_ids = {
        sprint["id"] for sprint in SprintStore.list_by("project_id", project_id)
    }
    ticket_ids = {
        ticket["id"]
        for ticket in TicketStore.list_all()
        if ticket.get("sprint_id") in sprint_ids
    }
    for source in list(CodeSourceStore.list_by("workspace_id", ws_id)):
        if source.get("project_id") == project_id:
            await CodebaseService.delete_source(source["id"], ws_id)
    for spec in list(ApiSpecStore.list_by("workspace_id", ws_id)):
        if spec.get("project_id") == project_id:
            await ApiTestPlannerService.delete_spec(spec["id"], ws_id)
    for analysis in list(FigmaAnalysisStore.list_by("workspace_id", ws_id)):
        if analysis.get("project_id") == project_id:
            await FigmaService.delete_analysis(analysis["id"], ws_id)
    await LifecycleService.delete_project_records(project_id, ws_id, ticket_ids)
    await JiraService.delete_project_data(project_id)
    await ProjectStore._persist_delete(project_id)
    await LifecycleService.audit(
        workspace_id=ws_id,
        actor_id=token_data.get("user_id"),
        actor_name=token_data.get("name", token_data.get("sub", "")),
        action="project.delete",
        resource_type="project",
        resource_id=project_id,
        details={"name": project.get("name")},
    )
