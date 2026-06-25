"""Report export routes."""
from fastapi import APIRouter
from fastapi.responses import FileResponse

router = APIRouter()


@router.get("/{sprint_id}/overview")
async def get_sprint_overview(sprint_id: int):
    """Get Sprint overview report as Markdown."""
    return {"sprint_id": sprint_id, "report": "# Not implemented"}


@router.get("/{sprint_id}/export")
async def export_report(sprint_id: int, fmt: str = "md"):
    """Export report as Markdown or PDF."""
    return {"message": f"Export as {fmt} not implemented yet"}
