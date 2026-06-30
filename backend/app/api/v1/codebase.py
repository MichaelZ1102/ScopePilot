"""Codebase routes: manage code sources, scan repos, and analyze code impact."""
from fastapi import APIRouter, Depends, HTTPException
from typing import Optional

from ...schemas import (
    CodeSourceCreate, CodeSourceResponse, CodeSourceDetailResponse,
    RepoSnapshotResponse, CodeImpactResponse,
)
from ...services import get_current_user
from ...services.codebase import CodebaseService, CodebaseError

router = APIRouter()


# ── Code Sources CRUD ─────────────────────────────────────────────────────


@router.get("/")
async def list_sources(token_data: dict = Depends(get_current_user)):
    """List all code sources for the current workspace."""
    return CodebaseService.list_sources(token_data.get("workspace_id"))


@router.post("/", response_model=CodeSourceResponse, status_code=201)
async def create_source(
    data: CodeSourceCreate,
    token_data: dict = Depends(get_current_user),
):
    """Register a new code repository source."""
    return await CodebaseService.create_source(
        data.model_dump(), token_data.get("workspace_id"),
    )


@router.get("/{source_id}", response_model=CodeSourceDetailResponse)
async def get_source(
    source_id: int,
    token_data: dict = Depends(get_current_user),
):
    """Get details of a specific code source."""
    source = CodebaseService.get_source(source_id, token_data.get("workspace_id"))
    if not source:
        raise HTTPException(status_code=404, detail="Code source not found")
    return source


@router.delete("/{source_id}", status_code=204)
async def delete_source(
    source_id: int,
    token_data: dict = Depends(get_current_user),
):
    """Delete a code source and its related data."""
    if not await CodebaseService.delete_source(source_id, token_data.get("workspace_id")):
        raise HTTPException(status_code=404, detail="Code source not found")


@router.post("/{source_id}/scan", response_model=RepoSnapshotResponse)
async def scan_repository(
    source_id: int,
    token_data: dict = Depends(get_current_user),
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
    source_id: int,
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
    source_id: int,
    ticket_id: int,
    sprint_id: int,
    token_data: dict = Depends(get_current_user),
    summary: str = "",
    description: str = "",
):
    """Analyze code impact for a specific ticket within a source repo."""
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
        return impact
    except CodebaseError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/impact/sprint/{sprint_id}", response_model=list[CodeImpactResponse])
async def list_sprint_impacts(
    sprint_id: int,
    token_data: dict = Depends(get_current_user),
):
    """List all code impact analyses for a sprint."""
    return CodebaseService.get_impacts_for_sprint(
        sprint_id, token_data.get("workspace_id"),
    )


@router.get("/impact/ticket/{ticket_id}", response_model=Optional[CodeImpactResponse])
async def get_ticket_impact(
    ticket_id: int,
    token_data: dict = Depends(get_current_user),
):
    """Get code impact for a specific ticket."""
    impact = CodebaseService.get_impact_for_ticket(
        ticket_id, token_data.get("workspace_id"),
    )
    if not impact:
        raise HTTPException(status_code=404, detail="No impact analysis found for this ticket")
    return impact
