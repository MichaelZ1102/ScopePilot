"""Figma integration routes: read designs, analyze, generate backend implications."""
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel, Field

from ...services import get_current_user
from ...services.figma import FigmaService, FigmaError

router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────

class FigmaAnalyzeRequest(BaseModel):
    figma_url: str = Field(pattern=r"^https?://(www\.)?figma\.com/", max_length=1000)
    figma_token: str = Field(min_length=1, max_length=4096)
    ticket_summary: str = Field(default="", max_length=4000)


class FigmaAnalysisResponse(BaseModel):
    id: int
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
    token_data: dict = Depends(get_current_user),
):
    """Analyze a Figma design URL and generate backend implications."""
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

    # Save
    analysis = {
        "figma_url": data.figma_url,
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

    saved = await FigmaService.save_analysis(analysis, token_data.get("workspace_id"))
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
    token_data: dict = Depends(get_current_user),
):
    """Delete a Figma analysis."""
    if not await FigmaService.delete_analysis(analysis_id, token_data.get("workspace_id")):
        raise HTTPException(status_code=404, detail="Analysis not found")
