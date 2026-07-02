"""Ticket detail & listing routes.

All endpoints require a valid Bearer token and verify workspace access
through the containing sprint/project.
"""
import asyncio
from typing import Annotated, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field

from ...schemas import TicketDetailResponse
from ...services import get_current_actor, get_current_user
from ...services.jira import JiraService, TicketStore
from ...services.lifecycle import LifecycleService
from ...services.reporting import ReportingError, ReportingService
from ...services.pdf_export import markdown_to_pdf
from ...services.notifications import NotificationService
from ..v1.sprints import _get_project

router = APIRouter()


class TicketReviewUpdate(BaseModel):
    status: Literal["unreviewed", "in_review", "approved", "rejected"]
    comment: str = Field(default="", max_length=4000)


class TicketArtifactLinkCreate(BaseModel):
    artifact_type: Literal[
        "code_source",
        "code_impact",
        "api_spec",
        "api_impact",
        "test_plan",
        "figma_analysis",
    ]
    artifact_id: int = Field(gt=0)
    metadata: Optional[dict] = None


class TicketAnalysisRevision(BaseModel):
    business_goal: Optional[str] = Field(default=None, max_length=8000)
    implementation_plan: Optional[list[str]] = Field(default=None, max_length=100)
    open_questions: Optional[list[str]] = Field(default=None, max_length=100)
    assumptions: Optional[list[str]] = Field(default=None, max_length=100)


class ReportCommentCreate(BaseModel):
    body: str = Field(min_length=1, max_length=8000)


class CommentStatusUpdate(BaseModel):
    status: Literal["open", "resolved"]


class ActionItemCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    owner: str = Field(default="", max_length=200)
    due_at: Optional[str] = Field(default=None, max_length=100)


class ActionItemUpdate(BaseModel):
    status: Optional[Literal["open", "done"]] = None
    owner: Optional[str] = Field(default=None, max_length=200)
    due_at: Optional[str] = Field(default=None, max_length=100)


class DeliveryLinkCreate(BaseModel):
    provider: Literal["github", "gitlab", "bitbucket", "other"] = "github"
    url: str = Field(pattern=r"^https?://", max_length=1000)
    pull_request: str = Field(default="", max_length=100)
    commit_sha: str = Field(default="", max_length=100)
    ci_status: str = Field(default="unknown", max_length=50)
    release_version: str = Field(default="", max_length=100)
    actual_files: list[str] = Field(default_factory=list, max_length=2000)


class JiraCommentWriteback(BaseModel):
    body: str = Field(min_length=1, max_length=8000)


class JiraTransitionWriteback(BaseModel):
    transition: str = Field(min_length=1, max_length=200)


class JiraLabelsWriteback(BaseModel):
    labels: list[str] = Field(default_factory=list, max_length=100)


def _ticket_report_response(
    ticket_id: int,
    workspace_id: int,
    analysis_run_id: Optional[int] = None,
) -> dict:
    try:
        return ReportingService.build_ticket_report(
            ticket_id,
            workspace_id,
            analysis_run_id=analysis_run_id,
        )
    except ReportingError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def _ticket_report_export_response(
    ticket_id: int,
    workspace_id: int,
    fmt: Literal["md", "json", "pdf", "jira", "postman"],
) -> Response:
    report = _ticket_report_response(ticket_id, workspace_id)
    ticket_key = report["ticket"].get("key", f"ticket-{ticket_id}").replace("/", "-")
    if fmt == "json":
        import json
        return Response(
            content=json.dumps(report, ensure_ascii=False, indent=2),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename={ticket_key}_report.json"},
        )
    if fmt == "postman":
        import json
        items = []
        for plan in report.get("artifacts", {}).get("test_plans", []):
            for scenario in plan.get("scenarios") or []:
                items.append({
                    "name": scenario.get("scenario_name") or f"{scenario.get('method')} {scenario.get('endpoint')}",
                    "request": {
                        "method": scenario.get("method", "GET"),
                        "header": [],
                        "url": {
                            "raw": f"{{{{baseUrl}}}}{scenario.get('endpoint', '')}",
                            "host": ["{{baseUrl}}"],
                            "path": str(scenario.get("endpoint", "")).strip("/").split("/"),
                        },
                        "body": {
                            "mode": "raw",
                            "raw": json.dumps(scenario.get("test_input") or {}, ensure_ascii=False),
                            "options": {"raw": {"language": "json"}},
                        },
                    },
                    "response": [],
                })
        collection = {
            "info": {
                "name": f"{ticket_key} - ScopePilot",
                "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
            },
            "variable": [{"key": "baseUrl", "value": ""}],
            "item": items,
        }
        return Response(
            content=json.dumps(collection, ensure_ascii=False, indent=2),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename={ticket_key}.postman_collection.json"},
        )
    markdown = ReportingService.render_ticket_markdown(report)
    if fmt == "pdf":
        return Response(
            content=markdown_to_pdf(markdown, report["title"]),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={ticket_key}_report.pdf"},
        )
    if fmt == "jira":
        return Response(
            content=markdown,
            media_type="text/plain",
            headers={"Content-Disposition": f"attachment; filename={ticket_key}_jira_comment.txt"},
        )
    return Response(
        content=markdown,
        media_type="text/markdown",
        headers={"Content-Disposition": f"attachment; filename={ticket_key}_report.md"},
    )


def _get_sprint_or_404(sprint_id: int, token_data: dict) -> dict:
    """Fetch sprint and verify the caller has access to its project."""
    sprint = JiraService.get_sprint(sprint_id)
    if sprint is None:
        raise HTTPException(status_code=404, detail="Sprint not found")
    # Re-use the project access check from sprint routes
    _get_project(sprint["project_id"], token_data)
    return sprint


def _get_ticket_or_404(sprint_id: int, ticket_id: int, token_data: dict) -> tuple[dict, dict]:
    sprint = _get_sprint_or_404(sprint_id, token_data)
    ticket = JiraService.get_ticket(ticket_id)
    if ticket is None or ticket.get("sprint_id") != sprint_id:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return sprint, ticket


def _with_lifecycle(ticket: dict, workspace_id: int) -> dict:
    return {
        **ticket,
        "review_data": LifecycleService.get_review(ticket["id"], workspace_id),
    }


def _validate_artifact(
    artifact_type: str,
    artifact_id: int,
    workspace_id: int,
    project_id: int,
) -> None:
    if artifact_type == "code_source":
        from ...services.codebase import CodebaseService
        artifact = CodebaseService.get_source(artifact_id, workspace_id)
    elif artifact_type == "code_impact":
        from ...services.codebase import CodeImpactStore, CodeSourceStore
        artifact = CodeImpactStore.get(artifact_id)
        source = CodeSourceStore.get(artifact.get("code_source_id")) if artifact else None
        if not source or source.get("workspace_id") != workspace_id:
            artifact = None
    elif artifact_type == "api_spec":
        from ...services.api_test_planner import ApiTestPlannerService
        artifact = ApiTestPlannerService.get_spec(artifact_id, workspace_id)
    elif artifact_type == "api_impact":
        from ...services.api_test_planner import ApiImpactStore
        artifact = ApiImpactStore.get(artifact_id)
        if artifact and artifact.get("workspace_id") != workspace_id:
            artifact = None
    elif artifact_type == "test_plan":
        from ...services.api_test_planner import ApiTestPlannerService
        artifact = ApiTestPlannerService.get_plan(artifact_id, workspace_id)
    else:
        from ...services.figma import FigmaService
        artifact = FigmaService.get_analysis(artifact_id, workspace_id)

    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")
    artifact_project_id = artifact.get("project_id")
    if artifact_project_id is not None and artifact_project_id != project_id:
        raise HTTPException(status_code=400, detail="Artifact belongs to another project")


# ── GET /api/v1/tickets/{sprint_id}/tickets ──────────────────────────────────


@router.get("/{sprint_id}/tickets", response_model=list[TicketDetailResponse])
async def list_tickets(
    sprint_id: Annotated[int, Path(gt=0)],
    token_data: dict = Depends(get_current_user),
):
    """List all tickets in a sprint."""
    _get_sprint_or_404(sprint_id, token_data)
    tickets = JiraService.list_tickets(sprint_id)
    workspace_id = token_data.get("workspace_id")
    return [TicketDetailResponse(**_with_lifecycle(t, workspace_id)) for t in tickets]


# ── GET /api/v1/tickets/{sprint_id}/tickets/{ticket_id} ──────────────────────


@router.get(
    "/{sprint_id}/tickets/{ticket_id}",
    response_model=TicketDetailResponse,
)
async def get_ticket(
    sprint_id: Annotated[int, Path(gt=0)],
    ticket_id: Annotated[int, Path(gt=0)],
    token_data: dict = Depends(get_current_user),
):
    """Get a single ticket detail."""
    _, ticket = _get_ticket_or_404(sprint_id, ticket_id, token_data)
    return TicketDetailResponse(
        **_with_lifecycle(ticket, token_data.get("workspace_id")),
    )


@router.get("/{sprint_id}/tickets/{ticket_id}/analysis-runs")
async def list_ticket_analysis_runs(
    sprint_id: Annotated[int, Path(gt=0)],
    ticket_id: Annotated[int, Path(gt=0)],
    token_data: dict = Depends(get_current_user),
):
    """List immutable analysis versions for a Ticket."""
    _get_ticket_or_404(sprint_id, ticket_id, token_data)
    return LifecycleService.list_analysis_runs(
        workspace_id=token_data.get("workspace_id"),
        ticket_id=ticket_id,
        sprint_id=sprint_id,
    )


@router.post("/{sprint_id}/tickets/{ticket_id}/analysis-runs/{run_id}/archive")
async def archive_ticket_analysis_run(
    sprint_id: Annotated[int, Path(gt=0)],
    ticket_id: Annotated[int, Path(gt=0)],
    run_id: Annotated[int, Path(gt=0)],
    actor: dict = Depends(get_current_actor),
):
    """Archive a historical analysis version without deleting it."""
    if actor.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Only an admin can archive analysis versions")
    _, ticket = _get_ticket_or_404(sprint_id, ticket_id, actor)
    if ticket.get("latest_analysis_run_id") == run_id:
        raise HTTPException(status_code=409, detail="The active analysis version cannot be archived")
    run = await LifecycleService.archive_analysis_run(
        run_id,
        ticket_id,
        actor.get("workspace_id"),
    )
    if not run:
        raise HTTPException(status_code=404, detail="Analysis version not found")
    return run


@router.patch("/{sprint_id}/tickets/{ticket_id}/analysis")
async def revise_ticket_analysis(
    sprint_id: Annotated[int, Path(gt=0)],
    ticket_id: Annotated[int, Path(gt=0)],
    data: TicketAnalysisRevision,
    actor: dict = Depends(get_current_actor),
):
    """Create a human-authored revision without destroying the AI output history."""
    if actor.get("role") == "viewer":
        raise HTTPException(status_code=403, detail="Viewer cannot edit analysis")
    sprint, ticket = _get_ticket_or_404(sprint_id, ticket_id, actor)
    current = ticket.get("analysis_data")
    if not current:
        raise HTTPException(status_code=400, detail="Ticket has no analysis to revise")
    updates = data.model_dump(exclude_none=True)
    revised = {**current, **updates}
    run = await LifecycleService.create_analysis_run(
        workspace_id=actor.get("workspace_id"),
        project_id=sprint["project_id"],
        sprint_id=sprint_id,
        ticket_id=ticket_id,
        analysis_type="ticket",
        result=revised,
        source_versions={
            "base_analysis_run_id": ticket.get("latest_analysis_run_id"),
            "jira_updated_at": ticket.get("source_updated_at"),
        },
        model="human-revision",
        prompt_version="manual",
    )
    await TicketStore.update_fields(
        ticket_id,
        {
            "analysis_data": revised,
            "latest_analysis_run_id": run["id"],
            "analysis_status": "completed",
            "analysis_stale_at": None,
        },
    )
    await LifecycleService.invalidate_review(
        ticket_id,
        actor.get("workspace_id"),
        "分析内容已人工修订，需要重新审核。",
    )
    await LifecycleService.audit(
        workspace_id=actor.get("workspace_id"),
        actor_id=actor.get("user_id"),
        actor_name=actor.get("name", actor.get("sub", "")),
        action="ticket.analysis.revise",
        resource_type="ticket",
        resource_id=ticket_id,
        details={"fields": list(updates)},
    )
    return {"analysis": revised, "analysis_run": run}


@router.get("/{sprint_id}/tickets/{ticket_id}/review")
async def get_ticket_review(
    sprint_id: Annotated[int, Path(gt=0)],
    ticket_id: Annotated[int, Path(gt=0)],
    token_data: dict = Depends(get_current_user),
):
    """Return the current review state for a Ticket."""
    _get_ticket_or_404(sprint_id, ticket_id, token_data)
    return LifecycleService.get_review(
        ticket_id,
        token_data.get("workspace_id"),
    ) or {"ticket_id": ticket_id, "status": "unreviewed"}


@router.put("/{sprint_id}/tickets/{ticket_id}/review")
async def update_ticket_review(
    sprint_id: Annotated[int, Path(gt=0)],
    ticket_id: Annotated[int, Path(gt=0)],
    data: TicketReviewUpdate,
    actor: dict = Depends(get_current_actor),
):
    """Submit, approve, reject, or reset a Ticket analysis review."""
    sprint, ticket = _get_ticket_or_404(sprint_id, ticket_id, actor)
    role = actor.get("role")
    if role == "viewer":
        raise HTTPException(status_code=403, detail="Viewer cannot update reviews")
    if role != "admin" and data.status in {"approved", "rejected"}:
        raise HTTPException(status_code=403, detail="Only an admin can approve or reject")
    if data.status in {"approved", "rejected"} and not ticket.get("analysis_data"):
        raise HTTPException(status_code=400, detail="Ticket has no analysis to review")
    if data.status == "rejected" and not data.comment.strip():
        raise HTTPException(status_code=400, detail="A rejection comment is required")

    review = await LifecycleService.set_review(
        workspace_id=actor.get("workspace_id"),
        project_id=sprint["project_id"],
        sprint_id=sprint_id,
        ticket_id=ticket_id,
        analysis_run_id=ticket.get("latest_analysis_run_id"),
        status=data.status,
        reviewer_id=actor.get("user_id"),
        reviewer_name=actor.get("name", actor.get("sub", "")),
        comment=data.comment.strip(),
    )
    await LifecycleService.audit(
        workspace_id=actor.get("workspace_id"),
        actor_id=actor.get("user_id"),
        actor_name=actor.get("name", actor.get("sub", "")),
        action=f"ticket.review.{data.status}",
        resource_type="ticket",
        resource_id=ticket_id,
        details={"sprint_id": sprint_id, "comment": data.comment.strip()},
    )
    await NotificationService.emit(
        workspace_id=actor.get("workspace_id"),
        event_type=f"review.{data.status}",
        title=f"{ticket['key']} 审核状态更新",
        message=data.comment.strip() or f"审核状态已更新为 {data.status}。",
        resource_type="ticket",
        resource_id=ticket_id,
    )
    return review


@router.get("/{sprint_id}/tickets/{ticket_id}/artifacts")
async def list_ticket_artifacts(
    sprint_id: Annotated[int, Path(gt=0)],
    ticket_id: Annotated[int, Path(gt=0)],
    token_data: dict = Depends(get_current_user),
):
    """List code, API, test-plan, and Figma links attached to a Ticket."""
    _get_ticket_or_404(sprint_id, ticket_id, token_data)
    return LifecycleService.list_artifact_links(
        ticket_id,
        token_data.get("workspace_id"),
    )


@router.post("/{sprint_id}/tickets/{ticket_id}/artifacts", status_code=201)
async def link_ticket_artifact(
    sprint_id: Annotated[int, Path(gt=0)],
    ticket_id: Annotated[int, Path(gt=0)],
    data: TicketArtifactLinkCreate,
    actor: dict = Depends(get_current_actor),
):
    """Attach an existing workspace artifact to a Ticket."""
    if actor.get("role") == "viewer":
        raise HTTPException(status_code=403, detail="Viewer cannot link artifacts")
    sprint, _ = _get_ticket_or_404(sprint_id, ticket_id, actor)
    _validate_artifact(
        data.artifact_type,
        data.artifact_id,
        actor.get("workspace_id"),
        sprint["project_id"],
    )
    link = await LifecycleService.link_artifact(
        workspace_id=actor.get("workspace_id"),
        project_id=sprint["project_id"],
        sprint_id=sprint_id,
        ticket_id=ticket_id,
        artifact_type=data.artifact_type,
        artifact_id=data.artifact_id,
        metadata=data.metadata,
    )
    await LifecycleService.audit(
        workspace_id=actor.get("workspace_id"),
        actor_id=actor.get("user_id"),
        actor_name=actor.get("name", actor.get("sub", "")),
        action="ticket.artifact.link",
        resource_type="ticket",
        resource_id=ticket_id,
        details={"artifact_type": data.artifact_type, "artifact_id": data.artifact_id},
    )
    return link


@router.delete("/{sprint_id}/tickets/{ticket_id}/artifacts/{link_id}", status_code=204)
async def unlink_ticket_artifact(
    sprint_id: Annotated[int, Path(gt=0)],
    ticket_id: Annotated[int, Path(gt=0)],
    link_id: Annotated[int, Path(gt=0)],
    actor: dict = Depends(get_current_actor),
):
    """Remove a Ticket-to-artifact association without deleting the artifact."""
    if actor.get("role") == "viewer":
        raise HTTPException(status_code=403, detail="Viewer cannot unlink artifacts")
    _get_ticket_or_404(sprint_id, ticket_id, actor)
    removed = await LifecycleService.unlink_artifact(
        link_id,
        ticket_id,
        actor.get("workspace_id"),
    )
    if not removed:
        raise HTTPException(status_code=404, detail="Artifact link not found")


@router.get("/{sprint_id}/tickets/{ticket_id}/comments")
async def list_report_comments(
    sprint_id: Annotated[int, Path(gt=0)],
    ticket_id: Annotated[int, Path(gt=0)],
    token_data: dict = Depends(get_current_user),
):
    _get_ticket_or_404(sprint_id, ticket_id, token_data)
    return LifecycleService.list_comments(ticket_id, token_data.get("workspace_id"))


@router.post("/{sprint_id}/tickets/{ticket_id}/comments", status_code=201)
async def add_report_comment(
    sprint_id: Annotated[int, Path(gt=0)],
    ticket_id: Annotated[int, Path(gt=0)],
    data: ReportCommentCreate,
    actor: dict = Depends(get_current_actor),
):
    if actor.get("role") == "viewer":
        raise HTTPException(status_code=403, detail="Viewer cannot comment")
    _get_ticket_or_404(sprint_id, ticket_id, actor)
    return await LifecycleService.add_comment(
        workspace_id=actor.get("workspace_id"),
        ticket_id=ticket_id,
        author_id=actor.get("user_id"),
        author_name=actor.get("name", actor.get("sub", "")),
        body=data.body.strip(),
    )


@router.patch("/{sprint_id}/tickets/{ticket_id}/comments/{comment_id}")
async def update_report_comment(
    sprint_id: Annotated[int, Path(gt=0)],
    ticket_id: Annotated[int, Path(gt=0)],
    comment_id: Annotated[int, Path(gt=0)],
    data: CommentStatusUpdate,
    actor: dict = Depends(get_current_actor),
):
    if actor.get("role") == "viewer":
        raise HTTPException(status_code=403, detail="Viewer cannot update comments")
    _get_ticket_or_404(sprint_id, ticket_id, actor)
    comment = await LifecycleService.update_comment_status(
        comment_id,
        ticket_id,
        actor.get("workspace_id"),
        data.status,
    )
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    return comment


@router.get("/{sprint_id}/tickets/{ticket_id}/action-items")
async def list_action_items(
    sprint_id: Annotated[int, Path(gt=0)],
    ticket_id: Annotated[int, Path(gt=0)],
    token_data: dict = Depends(get_current_user),
):
    _get_ticket_or_404(sprint_id, ticket_id, token_data)
    return LifecycleService.list_action_items(ticket_id, token_data.get("workspace_id"))


@router.post("/{sprint_id}/tickets/{ticket_id}/action-items", status_code=201)
async def add_action_item(
    sprint_id: Annotated[int, Path(gt=0)],
    ticket_id: Annotated[int, Path(gt=0)],
    data: ActionItemCreate,
    actor: dict = Depends(get_current_actor),
):
    if actor.get("role") == "viewer":
        raise HTTPException(status_code=403, detail="Viewer cannot create action items")
    _get_ticket_or_404(sprint_id, ticket_id, actor)
    return await LifecycleService.add_action_item(
        workspace_id=actor.get("workspace_id"),
        ticket_id=ticket_id,
        title=data.title.strip(),
        owner=data.owner.strip(),
        due_at=data.due_at,
        created_by=actor.get("user_id"),
    )


@router.patch("/{sprint_id}/tickets/{ticket_id}/action-items/{action_item_id}")
async def update_action_item(
    sprint_id: Annotated[int, Path(gt=0)],
    ticket_id: Annotated[int, Path(gt=0)],
    action_item_id: Annotated[int, Path(gt=0)],
    data: ActionItemUpdate,
    actor: dict = Depends(get_current_actor),
):
    if actor.get("role") == "viewer":
        raise HTTPException(status_code=403, detail="Viewer cannot update action items")
    _get_ticket_or_404(sprint_id, ticket_id, actor)
    item = await LifecycleService.update_action_item(
        action_item_id,
        ticket_id,
        actor.get("workspace_id"),
        data.model_dump(exclude_none=True),
    )
    if not item:
        raise HTTPException(status_code=404, detail="Action item not found")
    return item


@router.get("/{sprint_id}/tickets/{ticket_id}/delivery-links")
async def list_delivery_links(
    sprint_id: Annotated[int, Path(gt=0)],
    ticket_id: Annotated[int, Path(gt=0)],
    token_data: dict = Depends(get_current_user),
):
    _get_ticket_or_404(sprint_id, ticket_id, token_data)
    return LifecycleService.list_delivery_links(ticket_id, token_data.get("workspace_id"))


@router.post("/{sprint_id}/tickets/{ticket_id}/delivery-links", status_code=201)
async def add_delivery_link(
    sprint_id: Annotated[int, Path(gt=0)],
    ticket_id: Annotated[int, Path(gt=0)],
    data: DeliveryLinkCreate,
    actor: dict = Depends(get_current_actor),
):
    if actor.get("role") == "viewer":
        raise HTTPException(status_code=403, detail="Viewer cannot add delivery links")
    _get_ticket_or_404(sprint_id, ticket_id, actor)
    link = await LifecycleService.add_delivery_link(
        workspace_id=actor.get("workspace_id"),
        ticket_id=ticket_id,
        provider=data.provider,
        url=data.url,
        pull_request=data.pull_request,
        commit_sha=data.commit_sha,
        ci_status=data.ci_status,
        release_version=data.release_version,
        actual_files=data.actual_files,
        created_by=actor.get("user_id"),
    )
    await LifecycleService.audit(
        workspace_id=actor.get("workspace_id"),
        actor_id=actor.get("user_id"),
        actor_name=actor.get("name", actor.get("sub", "")),
        action="ticket.delivery.link",
        resource_type="ticket",
        resource_id=ticket_id,
        details={"delivery_link_id": link["id"], "provider": link["provider"]},
    )
    return link


@router.post("/{sprint_id}/tickets/{ticket_id}/jira/comment")
async def writeback_jira_comment(
    sprint_id: Annotated[int, Path(gt=0)],
    ticket_id: Annotated[int, Path(gt=0)],
    data: JiraCommentWriteback,
    actor: dict = Depends(get_current_actor),
):
    if actor.get("role") == "viewer":
        raise HTTPException(status_code=403, detail="Viewer cannot write to Jira")
    sprint, ticket = _get_ticket_or_404(sprint_id, ticket_id, actor)
    project = _get_project(sprint["project_id"], actor)
    client = JiraService.create_client(project)
    try:
        result = await asyncio.to_thread(client.add_issue_comment, ticket["key"], data.body.strip())
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await LifecycleService.audit(
        workspace_id=actor.get("workspace_id"),
        actor_id=actor.get("user_id"),
        actor_name=actor.get("name", actor.get("sub", "")),
        action="jira.comment.writeback",
        resource_type="ticket",
        resource_id=ticket_id,
        details={"ticket_key": ticket["key"]},
    )
    return result


@router.post("/{sprint_id}/tickets/{ticket_id}/jira/transition")
async def writeback_jira_transition(
    sprint_id: Annotated[int, Path(gt=0)],
    ticket_id: Annotated[int, Path(gt=0)],
    data: JiraTransitionWriteback,
    actor: dict = Depends(get_current_actor),
):
    if actor.get("role") == "viewer":
        raise HTTPException(status_code=403, detail="Viewer cannot write to Jira")
    sprint, ticket = _get_ticket_or_404(sprint_id, ticket_id, actor)
    project = _get_project(sprint["project_id"], actor)
    client = JiraService.create_client(project)
    try:
        result = await asyncio.to_thread(
            client.transition_issue,
            ticket["key"],
            data.transition.strip(),
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return result


@router.put("/{sprint_id}/tickets/{ticket_id}/jira/labels")
async def writeback_jira_labels(
    sprint_id: Annotated[int, Path(gt=0)],
    ticket_id: Annotated[int, Path(gt=0)],
    data: JiraLabelsWriteback,
    actor: dict = Depends(get_current_actor),
):
    if actor.get("role") == "viewer":
        raise HTTPException(status_code=403, detail="Viewer cannot write to Jira")
    sprint, ticket = _get_ticket_or_404(sprint_id, ticket_id, actor)
    project = _get_project(sprint["project_id"], actor)
    client = JiraService.create_client(project)
    try:
        result = await asyncio.to_thread(
            client.update_issue_labels,
            ticket["key"],
            data.labels,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await TicketStore.update_fields(ticket_id, {"labels": data.labels})
    return result


@router.get("/{sprint_id}/tickets/{ticket_id}/report")
async def get_ticket_report(
    sprint_id: Annotated[int, Path(gt=0)],
    ticket_id: Annotated[int, Path(gt=0)],
    token_data: dict = Depends(get_current_user),
):
    """Return the complete structured report for one Ticket."""
    _get_ticket_or_404(sprint_id, ticket_id, token_data)
    return _ticket_report_response(ticket_id, token_data.get("workspace_id"))


@router.get("/{sprint_id}/tickets/{ticket_id}/report/export")
async def export_ticket_report(
    sprint_id: Annotated[int, Path(gt=0)],
    ticket_id: Annotated[int, Path(gt=0)],
    fmt: Annotated[Literal["md", "json", "pdf", "jira", "postman"], Query()] = "md",
    token_data: dict = Depends(get_current_actor),
):
    """Download a Ticket report as Markdown or JSON."""
    _get_ticket_or_404(sprint_id, ticket_id, token_data)
    await LifecycleService.audit(
        workspace_id=token_data.get("workspace_id"),
        actor_id=token_data.get("user_id"),
        actor_name=token_data.get("name", token_data.get("sub", "")),
        action="report.export",
        resource_type="ticket",
        resource_id=ticket_id,
        details={"format": fmt},
    )
    return _ticket_report_export_response(
        ticket_id,
        token_data.get("workspace_id"),
        fmt,
    )


@router.get("/{ticket_id}/report")
async def get_ticket_report_by_id(
    ticket_id: Annotated[int, Path(gt=0)],
    analysis_run_id: Annotated[Optional[int], Query(gt=0)] = None,
    token_data: dict = Depends(get_current_user),
):
    """Return a complete Ticket report using the stable Ticket URL."""
    return _ticket_report_response(
        ticket_id,
        token_data.get("workspace_id"),
        analysis_run_id,
    )


@router.get("/{ticket_id}/report/export")
async def export_ticket_report_by_id(
    ticket_id: Annotated[int, Path(gt=0)],
    fmt: Annotated[Literal["md", "json", "pdf", "jira", "postman"], Query()] = "md",
    token_data: dict = Depends(get_current_actor),
):
    """Download a Ticket report from its stable Ticket URL."""
    await LifecycleService.audit(
        workspace_id=token_data.get("workspace_id"),
        actor_id=token_data.get("user_id"),
        actor_name=token_data.get("name", token_data.get("sub", "")),
        action="report.export",
        resource_type="ticket",
        resource_id=ticket_id,
        details={"format": fmt},
    )
    return _ticket_report_export_response(
        ticket_id,
        token_data.get("workspace_id"),
        fmt,
    )
