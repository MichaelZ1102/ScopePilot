"""Figma integration routes: read designs, analyze, generate backend implications."""
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel, Field

from ...services import get_current_user, require_roles
from ...services.figma import FigmaService, FigmaError
from ...services.jira import JiraService, TicketStore
from ...services.lifecycle import LifecycleService
from ...services.notifications import NotificationService
from ..v1.projects import ProjectStore

router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────

class FigmaAnalyzeRequest(BaseModel):
    figma_url: str = Field(pattern=r"^https?://(www\.)?figma\.com/", max_length=1000)
    figma_token: str = Field(min_length=1, max_length=4096)
    ticket_summary: str = Field(default="", max_length=4000)
    project_id: Optional[int] = Field(default=None, gt=0)
    ticket_id: Optional[int] = Field(default=None, gt=0)
    figma_node_id: str = Field(default="", max_length=200)


class FigmaAnalysisResponse(BaseModel):
    id: int
    project_id: Optional[int] = None
    ticket_id: Optional[int] = None
    figma_node_id: str = ""
    version: int = 1
    previous_analysis_id: Optional[int] = None
    last_modified: str = ""
    changes: Optional[dict] = None
    figma_url: str
    file_name: str
    frame_count: int
    text_node_count: int
    implications: list[dict]
    ai_used: bool
    created_at: str
    design_tokens: Optional[dict] = None
    frames: Optional[list[dict]] = None


# ── Routes ────────────────────────────────────────────────────────────────


@router.post("/analyze", response_model=FigmaAnalysisResponse)
async def analyze_figma_design(
    data: FigmaAnalyzeRequest,
    token_data: dict = Depends(require_roles("admin", "member")),
):
    """Analyze a Figma design URL and generate backend implications."""
    workspace_id = token_data.get("workspace_id")
    project_id = data.project_id
    sprint_id = None
    if project_id is not None:
        project = ProjectStore.get(project_id)
        if not project or project.get("workspace_id") != workspace_id:
            raise HTTPException(status_code=404, detail="Project not found")
    if data.ticket_id is not None:
        ticket = JiraService.get_ticket(data.ticket_id)
        sprint = JiraService.get_sprint(ticket.get("sprint_id")) if ticket else None
        project = ProjectStore.get(sprint.get("project_id")) if sprint else None
        if not ticket or not sprint or not project or project.get("workspace_id") != workspace_id:
            raise HTTPException(status_code=404, detail="Ticket not found")
        if project_id is not None and sprint.get("project_id") != project_id:
            raise HTTPException(status_code=400, detail="Ticket belongs to another project")
        project_id = sprint.get("project_id")
        sprint_id = sprint.get("id")

    # Parse URL
    parsed = FigmaService.parse_figma_url(data.figma_url)
    if not parsed:
        raise HTTPException(status_code=400, detail="Invalid Figma URL format")

    try:
        # Fetch file info from Figma API
        file_info = await FigmaService.fetch_file_info(
            parsed["file_key"], data.figma_token,
        )
    except FigmaError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Extract design data
    document = file_info.get("document", {})
    frames = FigmaService.extract_frames(document)
    texts = FigmaService.extract_text_nodes(document)
    tokens = FigmaService.extract_design_tokens(document)

    # Generate implications
    ai_provider = None
    try:
        from scopepilot.ai import create_provider
        ai_provider = create_provider()
    except Exception:
        pass

    implications_data = FigmaService.generate_implications(
        frames, texts, tokens, data.ticket_summary, ai_provider,
    )
    previous_candidates = [
        item for item in FigmaService.list_analyses(workspace_id)
        if item.get("file_key") == parsed["file_key"]
        and item.get("ticket_id") == data.ticket_id
    ]
    previous = max(
        previous_candidates,
        key=lambda item: item.get("created_at", ""),
        default=None,
    )
    previous_frames = {
        item.get("id"): item
        for item in (previous or {}).get("frames", [])
        if item.get("id")
    }
    current_frames = {
        item.get("id"): item
        for item in frames[:30]
        if item.get("id")
    }
    changes = {
        "added_frames": [
            item.get("name") for frame_id, item in current_frames.items()
            if frame_id not in previous_frames
        ],
        "removed_frames": [
            item.get("name") for frame_id, item in previous_frames.items()
            if frame_id not in current_frames
        ],
        "changed_frames": [
            item.get("name") for frame_id, item in current_frames.items()
            if frame_id in previous_frames and item != previous_frames[frame_id]
        ],
    } if previous else {"added_frames": [], "removed_frames": [], "changed_frames": []}

    # Save
    analysis = {
        "figma_url": data.figma_url,
        "project_id": project_id,
        "ticket_id": data.ticket_id,
        "figma_node_id": data.figma_node_id,
        "version": (previous or {}).get("version", 0) + 1,
        "previous_analysis_id": (previous or {}).get("id"),
        "changes": changes,
        "file_key": parsed["file_key"],
        "file_name": file_info.get("name", "Unknown"),
        "last_modified": file_info.get("last_modified", ""),
        "frame_count": implications_data["frame_count"],
        "text_node_count": implications_data["text_node_count"],
        "implications": implications_data["implications"],
        "ai_used": implications_data["ai_used"],
        "design_tokens": tokens,
        "frames": frames[:30],  # cap for response size
    }

    saved = await FigmaService.save_analysis(analysis, workspace_id)
    if data.ticket_id is not None and project_id is not None and sprint_id is not None:
        await LifecycleService.link_artifact(
            workspace_id=workspace_id,
            project_id=project_id,
            sprint_id=sprint_id,
            ticket_id=data.ticket_id,
            artifact_type="figma_analysis",
            artifact_id=saved["id"],
            metadata={"figma_node_id": data.figma_node_id},
        )
        await LifecycleService.invalidate_review(
            data.ticket_id,
            workspace_id,
            "Figma 影响分析已更新，需要重新审核。",
        )
        ticket = TicketStore.get(data.ticket_id)
        source_changed = bool(
            previous
            and (
                previous.get("last_modified") != saved.get("last_modified")
                or any(changes.values())
            )
        )
        if ticket and ticket.get("analysis_data") and source_changed:
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc).isoformat()
            await TicketStore.update_fields(
                data.ticket_id,
                {
                    "analysis_status": "stale",
                    "analysis_stale_at": now,
                    "updated_at": now,
                },
            )
            await NotificationService.emit(
                workspace_id=workspace_id,
                event_type="analysis.stale",
                title=f"{ticket.get('key', data.ticket_id)} 分析已过期",
                message="关联 Figma 文件版本发生变化。",
                resource_type="ticket",
                resource_id=data.ticket_id,
                details={"source": "figma", "analysis_id": saved["id"]},
            )
    saved["design_tokens"] = tokens
    return saved


@router.get("/analyses", response_model=list[FigmaAnalysisResponse])
async def list_analyses(token_data: dict = Depends(get_current_user)):
    """List all Figma design analyses."""
    return FigmaService.list_analyses(token_data.get("workspace_id"))


@router.get("/analyses/{analysis_id}", response_model=FigmaAnalysisResponse)
async def get_analysis(
    analysis_id: Annotated[int, Path(gt=0)],
    token_data: dict = Depends(get_current_user),
):
    """Get a specific Figma analysis."""
    analysis = FigmaService.get_analysis(analysis_id, token_data.get("workspace_id"))
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return analysis


@router.delete("/analyses/{analysis_id}", status_code=204)
async def delete_analysis(
    analysis_id: Annotated[int, Path(gt=0)],
    token_data: dict = Depends(require_roles("admin", "member")),
):
    """Delete a Figma analysis."""
    if not await FigmaService.delete_analysis(analysis_id, token_data.get("workspace_id")):
        raise HTTPException(status_code=404, detail="Analysis not found")
