"""Report export routes.

Generate and export AI analysis reports as Markdown documents.
All endpoints require a valid Bearer token with workspace access.
"""
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from fastapi.responses import Response

from ...services import get_current_user
from ...services.jira import JiraService, TicketStore
from ..v1.projects import ProjectStore
from scopepilot.analyzer import SprintAnalysis, TicketAnalysis
from scopepilot.report import generate_sprint_report, generate_ticket_report

router = APIRouter()


# ── Helpers ──────────────────────────────────────────────────────────────────


def _build_report(sprint_id: int, token_data: dict) -> str:
    """Reconstruct analysis objects from stored data and generate markdown.

    Steps:
        1. Fetch sprint + project from in-memory stores.
        2. Verify workspace access (404 if sprint/project not found).
        3. Check AI analysis data exists (404 if not yet analysed).
        4. Reconstruct ``SprintAnalysis`` / ``TicketAnalysis`` dataclasses.
        5. Generate sprint overview + individual ticket reports.

    Returns:
        Complete markdown report string.
    """
    sprint = JiraService.get_sprint(sprint_id)
    if sprint is None:
        raise HTTPException(status_code=404, detail="Sprint not found")

    project = ProjectStore.get(sprint["project_id"])
    if project is None or project["workspace_id"] != token_data.get("workspace_id"):
        raise HTTPException(status_code=404, detail="Sprint not found")

    analysis_data = sprint.get("analysis_data")
    if analysis_data is None:
        raise HTTPException(
            status_code=404,
            detail="该 Sprint 尚未进行 AI 分析，请先分析后再导出报告",
        )

    # Reconstruct from stored dicts ──────────────────────────────────────────
    sprint_analysis_dict = analysis_data["sprint_analysis"]
    included_ticket_keys = {
        ticket["key"]
        for ticket in sprint.get("tickets", [])
        if ticket.get("report_included", True)
    }
    ticket_analyses_dicts = [
        ticket_analysis
        for ticket_analysis in analysis_data["ticket_analyses"]
        if ticket_analysis.get("ticket_key") in included_ticket_keys
    ]

    ticket_analyses = [TicketAnalysis(**ta) for ta in ticket_analyses_dicts]

    sprint_analysis = SprintAnalysis(
        sprint_name=sprint_analysis_dict["sprint_name"],
        total_tickets=len(ticket_analyses),
        summary=sprint_analysis_dict.get("summary", ""),
        risk_map=[
            risk
            for risk in sprint_analysis_dict.get("risk_map", [])
            if risk.get("ticket") in included_ticket_keys
        ],
        open_questions=sprint_analysis_dict.get("open_questions", []),
        suggested_execution_order=[
            ticket_key
            for ticket_key in sprint_analysis_dict.get("suggested_execution_order", [])
            if ticket_key in included_ticket_keys
        ],
        ticket_analyses=ticket_analyses,
    )

    # Generate reports ───────────────────────────────────────────────────────
    md_content = generate_sprint_report(sprint_analysis)
    for ta in ticket_analyses:
        if isinstance(ta, TicketAnalysis):
            md_content += "\n\n" + generate_ticket_report(ta)

    return md_content


# ── Routes ───────────────────────────────────────────────────────────────────


@router.get("/{sprint_id}/overview")
async def get_sprint_overview(
    sprint_id: Annotated[int, Path(gt=0)],
    token_data: dict = Depends(get_current_user),
):
    """Get Sprint overview report as Markdown.

    The report includes:
        - Sprint-level summary, risk map, and execution order
        - Individual AI analysis details for every ticket
    """
    md_content = _build_report(sprint_id, token_data)
    return Response(content=md_content, media_type="text/markdown")


@router.get("/{sprint_id}/export")
async def export_report(
    sprint_id: Annotated[int, Path(gt=0)],
    token_data: dict = Depends(get_current_user),
    fmt: Annotated[Literal["md", "pdf"], Query()] = "md",
):
    """Export the sprint report.

    Supported formats:
        - **md** (default) — downloadable Markdown file
        - **pdf** — returns **501 Not Implemented** (planned for Phase 2)
    """
    if fmt == "pdf":
        raise HTTPException(
            status_code=501,
            detail="PDF 导出功能尚未实现，敬请期待",
        )

    md_content = _build_report(sprint_id, token_data)

    # Derive a safe filename from the sprint name
    sprint = JiraService.get_sprint(sprint_id)
    sprint_name = sprint.get("name", f"sprint_{sprint_id}") if sprint else f"sprint_{sprint_id}"
    safe_name = sprint_name.replace(" ", "_").replace("/", "-")

    return Response(
        content=md_content,
        media_type="text/markdown",
        headers={
            "Content-Disposition": f"attachment; filename={safe_name}_report.md",
        },
    )


def _get_report_ticket(sprint_id: int, ticket_id: int, token_data: dict) -> dict:
    sprint = JiraService.get_sprint(sprint_id)
    if sprint is None:
        raise HTTPException(status_code=404, detail="Sprint not found")

    project = ProjectStore.get(sprint["project_id"])
    if project is None or project["workspace_id"] != token_data.get("workspace_id"):
        raise HTTPException(status_code=404, detail="Sprint not found")

    ticket = JiraService.get_ticket(ticket_id)
    if ticket is None or ticket.get("sprint_id") != sprint_id:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


@router.post("/{sprint_id}/tickets/{ticket_id}", status_code=200)
async def include_ticket_in_report(
    sprint_id: Annotated[int, Path(gt=0)],
    ticket_id: Annotated[int, Path(gt=0)],
    token_data: dict = Depends(get_current_user),
):
    """Include one Ticket in Sprint report exports and shared reports."""
    _get_report_ticket(sprint_id, ticket_id, token_data)
    await TicketStore.update_fields(ticket_id, {"report_included": True})
    return {"ticket_id": ticket_id, "report_included": True}


@router.delete("/{sprint_id}/tickets/{ticket_id}", status_code=200)
async def exclude_ticket_from_report(
    sprint_id: Annotated[int, Path(gt=0)],
    ticket_id: Annotated[int, Path(gt=0)],
    token_data: dict = Depends(get_current_user),
):
    """Exclude one Ticket from Sprint report exports and shared reports."""
    _get_report_ticket(sprint_id, ticket_id, token_data)
    await TicketStore.update_fields(ticket_id, {"report_included": False})
    return {"ticket_id": ticket_id, "report_included": False}
