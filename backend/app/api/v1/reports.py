"""Report export routes.

Generate and export AI analysis reports as Markdown documents.
All endpoints require a valid Bearer token with workspace access.
"""
import csv
import html
import io
import json
from typing import Annotated, Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException, Path, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field

from ...services import get_current_actor, get_current_user, require_roles
from ...services.jira import JiraService, TicketStore
from ...services.lifecycle import LifecycleService
from ...services.reporting import ReportingError, ReportingService
from ...services.pdf_export import markdown_to_pdf
from ...services.notifications import NotificationService
from ...encryption import decrypt
from ..v1.projects import ProjectStore

router = APIRouter()


class ConfluencePublishRequest(BaseModel):
    space_key: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=200)
    parent_page_id: str = Field(default="", max_length=100)


# ── Helpers ──────────────────────────────────────────────────────────────────


def _build_report(sprint_id: int, token_data: dict) -> str:
    """Build the current aggregated Sprint report as Markdown."""
    try:
        report = ReportingService.build_sprint_report(
            sprint_id,
            token_data.get("workspace_id"),
        )
        return ReportingService.render_sprint_markdown(report)
    except ReportingError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ── Routes ───────────────────────────────────────────────────────────────────


@router.get("/")
async def list_report_snapshots(
    token_data: dict = Depends(get_current_user),
):
    """List published and archived report snapshots in the workspace."""
    return LifecycleService.list_report_snapshots(token_data.get("workspace_id"))


@router.post("/snapshots/{snapshot_id}/archive")
async def archive_report_snapshot(
    snapshot_id: Annotated[int, Path(gt=0)],
    actor: dict = Depends(require_roles("admin")),
):
    """Archive a published report version without deleting its immutable content."""
    snapshot = await LifecycleService.archive_report_snapshot(
        snapshot_id,
        actor.get("workspace_id"),
    )
    if not snapshot:
        raise HTTPException(status_code=404, detail="Report snapshot not found")
    await LifecycleService.audit(
        workspace_id=actor.get("workspace_id"),
        actor_id=actor.get("user_id"),
        actor_name=actor.get("name", actor.get("sub", "")),
        action="report.archive",
        resource_type="report_snapshot",
        resource_id=snapshot_id,
        details={"sprint_id": snapshot.get("sprint_id"), "version": snapshot.get("version")},
    )
    return snapshot


@router.get("/{sprint_id}/structured")
async def get_structured_sprint_report(
    sprint_id: Annotated[int, Path(gt=0)],
    token_data: dict = Depends(get_current_user),
):
    """Return a Sprint report with all Ticket analysis artifacts."""
    try:
        return ReportingService.build_sprint_report(
            sprint_id,
            token_data.get("workspace_id"),
        )
    except ReportingError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{sprint_id}/publish", status_code=201)
async def publish_sprint_report(
    sprint_id: Annotated[int, Path(gt=0)],
    actor: dict = Depends(get_current_actor),
):
    """Publish an immutable Sprint report snapshot after approval checks."""
    if actor.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Only an admin can publish reports")
    try:
        report = ReportingService.build_sprint_report(
            sprint_id,
            actor.get("workspace_id"),
        )
    except ReportingError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    unapproved = [
        item["ticket"].get("key")
        for item in report["tickets"]
        if item.get("review", {}).get("status") != "approved"
    ]
    stale = [
        item["ticket"].get("key")
        for item in report["tickets"]
        if item.get("is_stale")
    ]
    if unapproved:
        raise HTTPException(
            status_code=409,
            detail={"message": "All included Tickets must be approved", "tickets": unapproved},
        )
    if stale:
        raise HTTPException(
            status_code=409,
            detail={"message": "Stale Ticket analyses cannot be published", "tickets": stale},
        )

    snapshot = await LifecycleService.create_report_snapshot(
        workspace_id=actor.get("workspace_id"),
        project_id=report["project"]["id"],
        sprint_id=sprint_id,
        ticket_id=None,
        report_type="sprint",
        title=report["title"],
        content=ReportingService.render_sprint_markdown(report),
        structured_content=report,
        created_by=actor.get("user_id"),
    )
    await LifecycleService.audit(
        workspace_id=actor.get("workspace_id"),
        actor_id=actor.get("user_id"),
        actor_name=actor.get("name", actor.get("sub", "")),
        action="report.publish",
        resource_type="sprint",
        resource_id=sprint_id,
        details={"snapshot_id": snapshot["id"], "version": snapshot["version"]},
    )
    await NotificationService.emit(
        workspace_id=actor.get("workspace_id"),
        event_type="report.published",
        title=f"{report['sprint']['name']} 报告已发布",
        message=f"报告版本 v{snapshot['version']} 已生成。",
        resource_type="sprint",
        resource_id=sprint_id,
        details={"snapshot_id": snapshot["id"], "version": snapshot["version"]},
    )
    return snapshot


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


@router.post("/{sprint_id}/confluence", status_code=201)
async def publish_to_confluence(
    sprint_id: Annotated[int, Path(gt=0)],
    data: ConfluencePublishRequest,
    actor: dict = Depends(require_roles("admin", "member")),
):
    """Publish the current report to Confluence Cloud using project credentials."""
    try:
        report = ReportingService.build_sprint_report(sprint_id, actor.get("workspace_id"))
    except ReportingError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    project = ProjectStore.get(report["project"]["id"])
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    markdown = ReportingService.render_sprint_markdown(report)
    payload = {
        "type": "page",
        "title": data.title,
        "space": {"key": data.space_key},
        "body": {
            "storage": {
                "value": f"<pre>{html.escape(markdown)}</pre>",
                "representation": "storage",
            },
        },
    }
    if data.parent_page_id:
        payload["ancestors"] = [{"id": data.parent_page_id}]
    try:
        token = decrypt(project["jira_api_token"])
        async with httpx.AsyncClient(
            auth=(project["jira_email"], token),
            timeout=20.0,
        ) as client:
            response = await client.post(
                f"{project['jira_url'].rstrip('/')}/wiki/rest/api/content",
                json=payload,
                headers={"Accept": "application/json", "Content-Type": "application/json"},
            )
        if response.status_code >= 400:
            raise HTTPException(
                status_code=400,
                detail=f"Confluence publish failed: {response.status_code} {response.text[:300]}",
            )
        result = response.json()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await LifecycleService.audit(
        workspace_id=actor.get("workspace_id"),
        actor_id=actor.get("user_id"),
        actor_name=actor.get("name", actor.get("sub", "")),
        action="report.confluence.publish",
        resource_type="sprint",
        resource_id=sprint_id,
        details={"confluence_page_id": result.get("id"), "space_key": data.space_key},
    )
    return result


@router.get("/{sprint_id}/export")
async def export_report(
    sprint_id: Annotated[int, Path(gt=0)],
    token_data: dict = Depends(get_current_actor),
    fmt: Annotated[Literal["md", "pdf", "json", "csv", "jira"], Query()] = "md",
):
    """Export the sprint report.

    Supported formats:
        - **md** (default) — downloadable Markdown file
        - **pdf** — downloadable PDF document
    """
    try:
        structured = ReportingService.build_sprint_report(
            sprint_id,
            token_data.get("workspace_id"),
        )
    except ReportingError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    md_content = ReportingService.render_sprint_markdown(structured)
    await LifecycleService.audit(
        workspace_id=token_data.get("workspace_id"),
        actor_id=token_data.get("user_id"),
        actor_name=token_data.get("name", token_data.get("sub", "")),
        action="report.export",
        resource_type="sprint",
        resource_id=sprint_id,
        details={"format": fmt},
    )

    # Derive a safe filename from the sprint name
    sprint = JiraService.get_sprint(sprint_id)
    sprint_name = sprint.get("name", f"sprint_{sprint_id}") if sprint else f"sprint_{sprint_id}"
    safe_name = sprint_name.replace(" ", "_").replace("/", "-")

    if fmt == "pdf":
        return Response(
            content=markdown_to_pdf(md_content, f"{sprint_name} Report"),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={safe_name}_report.pdf",
            },
        )
    if fmt == "json":
        return Response(
            content=json.dumps(structured, ensure_ascii=False, indent=2),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename={safe_name}_report.json"},
        )
    if fmt == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "ticket_key", "summary", "status", "priority", "assignee",
            "review_status", "analysis_stale", "complexity", "estimated_effort",
        ])
        for item in structured["tickets"]:
            ticket = item["ticket"]
            score = item.get("analysis", {}).get("score", {})
            writer.writerow([
                ticket.get("key"),
                ticket.get("summary"),
                ticket.get("status"),
                ticket.get("priority"),
                ticket.get("assignee"),
                item.get("review", {}).get("status"),
                item.get("is_stale"),
                score.get("overall"),
                score.get("estimated_effort"),
            ])
        return Response(
            content="\ufeff" + output.getvalue(),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename={safe_name}_report.csv"},
        )
    if fmt == "jira":
        return Response(
            content=md_content,
            media_type="text/plain",
            headers={"Content-Disposition": f"attachment; filename={safe_name}_jira_comment.txt"},
        )
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
    token_data: dict = Depends(require_roles("admin", "member")),
):
    """Include one Ticket in Sprint report exports and shared reports."""
    _get_report_ticket(sprint_id, ticket_id, token_data)
    await TicketStore.update_fields(ticket_id, {"report_included": True})
    return {"ticket_id": ticket_id, "report_included": True}


@router.delete("/{sprint_id}/tickets/{ticket_id}", status_code=200)
async def exclude_ticket_from_report(
    sprint_id: Annotated[int, Path(gt=0)],
    ticket_id: Annotated[int, Path(gt=0)],
    token_data: dict = Depends(require_roles("admin", "member")),
):
    """Exclude one Ticket from Sprint report exports and shared reports."""
    _get_report_ticket(sprint_id, ticket_id, token_data)
    await TicketStore.update_fields(ticket_id, {"report_included": False})
    return {"ticket_id": ticket_id, "report_included": False}
