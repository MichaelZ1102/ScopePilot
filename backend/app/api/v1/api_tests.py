"""API Test Plan routes: import OpenAPI specs, generate test plans, export."""
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel, Field

from ...services import get_current_user, require_roles
from ...services.api_test_planner import ApiTestPlannerService, ApiTestPlanError
from ...services.jira import JiraService
from ...services.lifecycle import LifecycleService
from ..v1.projects import ProjectStore

router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────

class SpecImportUrl(BaseModel):
    url: str = Field(pattern=r"^https?://", max_length=1000)
    name: str = Field(min_length=1, max_length=120)
    project_id: Optional[int] = Field(default=None, gt=0)
    service_name: str = Field(default="", max_length=120)


class SpecImportContent(BaseModel):
    content: str = Field(min_length=1, max_length=2_000_000)
    name: str = Field(min_length=1, max_length=120)
    source: str = Field(default="inline", min_length=1, max_length=500)
    project_id: Optional[int] = Field(default=None, gt=0)
    service_name: str = Field(default="", max_length=120)


class SpecResponse(BaseModel):
    id: int
    project_id: Optional[int] = None
    service_name: str = ""
    name: str
    title: str
    version: str
    source: str
    endpoint_count: int
    revision: int = 1
    previous_spec_id: Optional[int] = None
    changes: Optional[dict] = None
    created_at: str


class TestPlanGenerate(BaseModel):
    focus_tags: Optional[list[str]] = Field(default=None, max_length=50)
    ticket_ids: Optional[list[int]] = Field(default=None, max_length=100)


class TestPlanResponse(BaseModel):
    id: int
    spec_id: int
    project_id: Optional[int] = None
    ticket_ids: list[int] = Field(default_factory=list)
    title: str
    base_url: str
    endpoints_analyzed: int
    scenario_count: int
    coverage_summary: dict
    created_at: str
    scenarios: Optional[list[dict]] = None


class ExportMarkdownResponse(BaseModel):
    markdown: str
    filename: str


class ExportPostmanResponse(BaseModel):
    collection: dict


# ── Routes ────────────────────────────────────────────────────────────────


@router.post("/specs/from-url", response_model=SpecResponse, status_code=201)
async def import_spec_from_url(
    data: SpecImportUrl,
    token_data: dict = Depends(require_roles("admin", "member")),
):
    """Import an OpenAPI spec from a URL."""
    if data.project_id is not None:
        project = ProjectStore.get(data.project_id)
        if not project or project.get("workspace_id") != token_data.get("workspace_id"):
            raise HTTPException(status_code=404, detail="Project not found")
    try:
        spec = await ApiTestPlannerService.create_spec_from_url(
            url=data.url, name=data.name,
            workspace_id=token_data.get("workspace_id"),
            project_id=data.project_id,
            service_name=data.service_name,
        )
        return spec
    except ApiTestPlanError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/specs/from-content", response_model=SpecResponse, status_code=201)
async def import_spec_from_content(
    data: SpecImportContent,
    token_data: dict = Depends(require_roles("admin", "member")),
):
    """Import an OpenAPI spec from pasted content."""
    if data.project_id is not None:
        project = ProjectStore.get(data.project_id)
        if not project or project.get("workspace_id") != token_data.get("workspace_id"):
            raise HTTPException(status_code=404, detail="Project not found")
    try:
        spec = await ApiTestPlannerService.create_spec_from_content(
            content=data.content, name=data.name, source=data.source,
            workspace_id=token_data.get("workspace_id"),
            project_id=data.project_id,
            service_name=data.service_name,
        )
        return spec
    except ApiTestPlanError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/specs")
async def list_specs(token_data: dict = Depends(get_current_user)):
    """List all imported API specs."""
    return ApiTestPlannerService.list_specs(token_data.get("workspace_id"))


@router.get("/specs/{spec_id}", response_model=SpecResponse)
async def get_spec(spec_id: Annotated[int, Path(gt=0)], token_data: dict = Depends(get_current_user)):
    """Get a specific API spec with its endpoints."""
    spec = ApiTestPlannerService.get_spec(spec_id, token_data.get("workspace_id"))
    if not spec:
        raise HTTPException(status_code=404, detail="API spec not found")
    return spec


@router.post("/specs/{spec_id}/impact/{ticket_id}", status_code=201)
async def analyze_ticket_api_impact(
    spec_id: Annotated[int, Path(gt=0)],
    ticket_id: Annotated[int, Path(gt=0)],
    token_data: dict = Depends(require_roles("admin", "member")),
):
    """Compare one Ticket's API candidates with an imported OpenAPI spec."""
    ticket = JiraService.get_ticket(ticket_id)
    sprint = JiraService.get_sprint(ticket.get("sprint_id")) if ticket else None
    project = ProjectStore.get(sprint.get("project_id")) if sprint else None
    if not ticket or not sprint or not project or project.get("workspace_id") != token_data.get("workspace_id"):
        raise HTTPException(status_code=404, detail="Ticket not found")
    try:
        impact = await ApiTestPlannerService.analyze_ticket_impact(
            spec_id,
            ticket,
            sprint,
            token_data.get("workspace_id"),
        )
        await LifecycleService.link_artifact(
            workspace_id=token_data.get("workspace_id"),
            project_id=sprint["project_id"],
            sprint_id=sprint["id"],
            ticket_id=ticket_id,
            artifact_type="api_impact",
            artifact_id=impact["id"],
            metadata={"spec_id": spec_id, "spec_version": impact.get("spec_version")},
        )
        await LifecycleService.invalidate_review(
            ticket_id,
            token_data.get("workspace_id"),
            "API 影响核验结果已更新，需要重新审核。",
        )
        return impact
    except ApiTestPlanError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/impacts/ticket/{ticket_id}")
async def list_ticket_api_impacts(
    ticket_id: Annotated[int, Path(gt=0)],
    token_data: dict = Depends(get_current_user),
):
    """List OpenAPI comparison results for a Ticket."""
    return ApiTestPlannerService.list_ticket_impacts(
        ticket_id,
        token_data.get("workspace_id"),
    )


@router.delete("/specs/{spec_id}", status_code=204)
async def delete_spec(spec_id: Annotated[int, Path(gt=0)], token_data: dict = Depends(require_roles("admin", "member"))):
    """Delete an API spec and related test plans."""
    if not await ApiTestPlannerService.delete_spec(spec_id, token_data.get("workspace_id")):
        raise HTTPException(status_code=404, detail="API spec not found")


@router.post("/specs/{spec_id}/generate", response_model=TestPlanResponse, status_code=201)
async def generate_test_plan(
    spec_id: Annotated[int, Path(gt=0)],
    data: TestPlanGenerate = TestPlanGenerate(),
    token_data: dict = Depends(require_roles("admin", "member")),
):
    """Generate an AI-powered test plan from a spec."""
    spec = ApiTestPlannerService.get_spec(spec_id, token_data.get("workspace_id"))
    if not spec:
        raise HTTPException(status_code=404, detail="API spec not found")
    linked_tickets: list[tuple[dict, dict]] = []
    for ticket_id in data.ticket_ids or []:
        ticket = JiraService.get_ticket(ticket_id)
        sprint = JiraService.get_sprint(ticket.get("sprint_id")) if ticket else None
        if not ticket or not sprint:
            raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found")
        project = ProjectStore.get(sprint.get("project_id"))
        if not project or project.get("workspace_id") != token_data.get("workspace_id"):
            raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found")
        if spec.get("project_id") is not None and spec.get("project_id") != sprint.get("project_id"):
            raise HTTPException(status_code=400, detail=f"Ticket {ticket_id} belongs to another project")
        linked_tickets.append((sprint, ticket))
    try:
        plan = await ApiTestPlannerService.generate_test_plan(
            spec_id=spec_id,
            workspace_id=token_data.get("workspace_id"),
            focus_tags=data.focus_tags,
            ticket_ids=data.ticket_ids,
        )
        for sprint, ticket in linked_tickets:
            await LifecycleService.link_artifact(
                workspace_id=token_data.get("workspace_id"),
                project_id=sprint["project_id"],
                sprint_id=sprint["id"],
                ticket_id=ticket["id"],
                artifact_type="test_plan",
                artifact_id=plan["id"],
                metadata={"spec_id": spec_id},
            )
            await LifecycleService.invalidate_review(
                ticket["id"],
                token_data.get("workspace_id"),
                "API 测试计划已更新，需要重新审核。",
            )
        return plan
    except ApiTestPlanError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/plans", response_model=list[TestPlanResponse])
async def list_plans(token_data: dict = Depends(get_current_user)):
    """List all generated test plans."""
    return ApiTestPlannerService.list_plans(token_data.get("workspace_id"))


@router.get("/plans/{plan_id}", response_model=TestPlanResponse)
async def get_plan(plan_id: Annotated[int, Path(gt=0)], token_data: dict = Depends(get_current_user)):
    """Get a test plan with all scenarios."""
    plan = ApiTestPlannerService.get_plan(plan_id, token_data.get("workspace_id"))
    if not plan:
        raise HTTPException(status_code=404, detail="Test plan not found")
    return plan


@router.get("/plans/{plan_id}/export/markdown", response_model=ExportMarkdownResponse)
async def export_plan_markdown(
    plan_id: Annotated[int, Path(gt=0)],
    token_data: dict = Depends(get_current_user),
):
    """Export a test plan as Markdown."""
    try:
        md = ApiTestPlannerService.export_markdown(plan_id, token_data.get("workspace_id"))
        plan = ApiTestPlannerService.get_plan(plan_id, token_data.get("workspace_id"))
        return {
            "markdown": md,
            "filename": f"test-plan-{plan_id}.md",
        }
    except ApiTestPlanError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/plans/{plan_id}/export/postman", response_model=ExportPostmanResponse)
async def export_plan_postman(
    plan_id: Annotated[int, Path(gt=0)],
    token_data: dict = Depends(get_current_user),
):
    """Export a test plan as Postman collection."""
    try:
        collection = ApiTestPlannerService.export_postman(
            plan_id, token_data.get("workspace_id"),
        )
        return {"collection": collection}
    except ApiTestPlanError as e:
        raise HTTPException(status_code=404, detail=str(e))
