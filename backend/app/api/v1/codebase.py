"""Codebase routes: manage code sources, scan repos, and analyze code impact."""
from fastapi import APIRouter, Depends, HTTPException, Path, Query
from typing import Annotated, Optional

from ...schemas import (
    CodeSourceCreate, CodeSourceResponse, CodeSourceDetailResponse,
    RepoSnapshotResponse, CodeImpactResponse,
)
from ...services import get_current_user, require_roles
from ...services.codebase import CodebaseService, CodebaseError
from ...services.jira import JiraService
from ...services.lifecycle import LifecycleService
from ..v1.projects import _projects

router = APIRouter()


# ── Code Sources CRUD ─────────────────────────────────────────────────────


@router.get("/")
async def list_sources(
    project_id: Annotated[Optional[int], Query(gt=0)] = None,
    token_data: dict = Depends(get_current_user),
):
    """List code sources in the workspace, optionally scoped to one project."""
    return CodebaseService.list_sources(token_data.get("workspace_id"), project_id)


@router.post("/", response_model=CodeSourceResponse, status_code=201)
async def create_source(
    data: CodeSourceCreate,
    token_data: dict = Depends(require_roles("admin", "member")),
):
    """Register a new code repository source."""
    if data.project_id is not None:
        project = _projects.get(data.project_id)
        if not project or project.get("workspace_id") != token_data.get("workspace_id"):
            raise HTTPException(status_code=404, detail="Project not found")
    source_data = data.model_dump()
    source_data["repo_url"] = source_data["repo_url"].strip()
    source_data["default_branch"] = source_data["default_branch"].strip()
    try:
        CodebaseService.validate_source_config(source_data)
        return await CodebaseService.create_source(
            source_data, token_data.get("workspace_id"),
        )
    except CodebaseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{source_id}", response_model=CodeSourceDetailResponse)
async def get_source(
    source_id: Annotated[int, Path(gt=0)],
    token_data: dict = Depends(get_current_user),
):
    """Get details of a specific code source."""
    source = CodebaseService.get_source(source_id, token_data.get("workspace_id"))
    if not source:
        raise HTTPException(status_code=404, detail="Code source not found")
    return source


@router.delete("/{source_id}", status_code=204)
async def delete_source(
    source_id: Annotated[int, Path(gt=0)],
    token_data: dict = Depends(require_roles("admin", "member")),
):
    """Delete a code source and its related data."""
    if not await CodebaseService.delete_source(source_id, token_data.get("workspace_id")):
        raise HTTPException(status_code=404, detail="Code source not found")


@router.post("/{source_id}/scan", response_model=RepoSnapshotResponse)
async def scan_repository(
    source_id: Annotated[int, Path(gt=0)],
    token_data: dict = Depends(require_roles("admin", "member")),
):
    """Trigger a scan of the repository."""
    try:
        snapshot = await CodebaseService.scan_repository(
            source_id, token_data.get("workspace_id"),
        )
        return snapshot
    except CodebaseError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{source_id}/snapshot", response_model=Optional[RepoSnapshotResponse])
async def get_latest_snapshot(
    source_id: Annotated[int, Path(gt=0)],
    token_data: dict = Depends(get_current_user),
):
    """Get the latest repository snapshot."""
    snapshot = CodebaseService.get_latest_snapshot(
        source_id, token_data.get("workspace_id"),
    )
    if not snapshot:
        raise HTTPException(status_code=404, detail="No snapshot found. Scan the repo first.")
    return snapshot


# ── Code Impact Analysis ──────────────────────────────────────────────────


@router.post("/{source_id}/impact/{ticket_id}", response_model=CodeImpactResponse)
async def analyze_code_impact(
    source_id: Annotated[int, Path(gt=0)],
    ticket_id: Annotated[int, Path(gt=0)],
    sprint_id: Annotated[int, Query(gt=0)],
    token_data: dict = Depends(require_roles("admin", "member")),
    summary: str = "",
    description: str = "",
):
    """Analyze code impact for a specific ticket within a source repo."""
    ticket = JiraService.get_ticket(ticket_id)
    sprint = JiraService.get_sprint(sprint_id)
    if not ticket or not sprint or ticket.get("sprint_id") != sprint_id:
        raise HTTPException(status_code=404, detail="Ticket not found")
    project = _projects.get(sprint.get("project_id"))
    if not project or project.get("workspace_id") != token_data.get("workspace_id"):
        raise HTTPException(status_code=404, detail="Ticket not found")
    source = CodebaseService.get_source(source_id, token_data.get("workspace_id"))
    if not source:
        raise HTTPException(status_code=404, detail="Code source not found")
    if source.get("project_id") != sprint.get("project_id"):
        raise HTTPException(status_code=400, detail="Code source belongs to another project")
    try:
        snapshot = CodebaseService.get_latest_snapshot(
            source_id, token_data.get("workspace_id"),
        )
        impact = await CodebaseService.analyze_impact(
            source_id=source_id,
            ticket_id=ticket_id,
            sprint_id=sprint_id,
            workspace_id=token_data.get("workspace_id"),
            ticket_summary=summary,
            ticket_description=description,
            snapshot=snapshot,
        )
        await LifecycleService.link_artifact(
            workspace_id=token_data.get("workspace_id"),
            project_id=sprint["project_id"],
            sprint_id=sprint_id,
            ticket_id=ticket_id,
            artifact_type="code_impact",
            artifact_id=impact["id"],
            metadata={
                "code_source_id": source_id,
                "commit_sha": (snapshot or {}).get("commit_sha"),
            },
        )
        await LifecycleService.invalidate_review(
            ticket_id,
            token_data.get("workspace_id"),
            "代码影响分析已更新，需要重新审核。",
        )
        return impact
    except CodebaseError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/impact/sprint/{sprint_id}", response_model=list[CodeImpactResponse])
async def list_sprint_impacts(
    sprint_id: Annotated[int, Path(gt=0)],
    token_data: dict = Depends(get_current_user),
):
    """List all code impact analyses for a sprint."""
    return CodebaseService.get_impacts_for_sprint(
        sprint_id, token_data.get("workspace_id"),
    )


@router.get("/impact/ticket/{ticket_id}", response_model=Optional[CodeImpactResponse])
async def get_ticket_impact(
    ticket_id: Annotated[int, Path(gt=0)],
    token_data: dict = Depends(get_current_user),
):
    """Get code impact for a specific ticket."""
    impact = CodebaseService.get_impact_for_ticket(
        ticket_id, token_data.get("workspace_id"),
    )
    if not impact:
        raise HTTPException(status_code=404, detail="No impact analysis found for this ticket")
    return impact
