"""API Test Plan routes: import OpenAPI specs, generate test plans, export."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from ...services import get_current_user
from ...services.api_test_planner import ApiTestPlannerService, ApiTestPlanError

router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────

class SpecImportUrl(BaseModel):
    url: str
    name: str


class SpecImportContent(BaseModel):
    content: str
    name: str
    source: str = "inline"


class SpecResponse(BaseModel):
    id: int
    name: str
    title: str
    version: str
    source: str
    endpoint_count: int
    created_at: str


class TestPlanGenerate(BaseModel):
    focus_tags: Optional[list[str]] = None


class TestPlanResponse(BaseModel):
    id: int
    spec_id: int
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
    token_data: dict = Depends(get_current_user),
):
    """Import an OpenAPI spec from a URL."""
    try:
        spec = await ApiTestPlannerService.create_spec_from_url(
            url=data.url, name=data.name,
            workspace_id=token_data.get("workspace_id"),
        )
        return spec
    except ApiTestPlanError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/specs/from-content", response_model=SpecResponse, status_code=201)
async def import_spec_from_content(
    data: SpecImportContent,
    token_data: dict = Depends(get_current_user),
):
    """Import an OpenAPI spec from pasted content."""
    try:
        spec = await ApiTestPlannerService.create_spec_from_content(
            content=data.content, name=data.name, source=data.source,
            workspace_id=token_data.get("workspace_id"),
        )
        return spec
    except ApiTestPlanError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/specs")
async def list_specs(token_data: dict = Depends(get_current_user)):
    """List all imported API specs."""
    return ApiTestPlannerService.list_specs(token_data.get("workspace_id"))


@router.get("/specs/{spec_id}", response_model=SpecResponse)
async def get_spec(spec_id: int, token_data: dict = Depends(get_current_user)):
    """Get a specific API spec with its endpoints."""
    spec = ApiTestPlannerService.get_spec(spec_id, token_data.get("workspace_id"))
    if not spec:
        raise HTTPException(status_code=404, detail="API spec not found")
    return spec


@router.delete("/specs/{spec_id}", status_code=204)
async def delete_spec(spec_id: int, token_data: dict = Depends(get_current_user)):
    """Delete an API spec and related test plans."""
    if not await ApiTestPlannerService.delete_spec(spec_id, token_data.get("workspace_id")):
        raise HTTPException(status_code=404, detail="API spec not found")


@router.post("/specs/{spec_id}/generate", response_model=TestPlanResponse, status_code=201)
async def generate_test_plan(
    spec_id: int,
    data: TestPlanGenerate = TestPlanGenerate(),
    token_data: dict = Depends(get_current_user),
):
    """Generate an AI-powered test plan from a spec."""
    try:
        plan = await ApiTestPlannerService.generate_test_plan(
            spec_id=spec_id,
            workspace_id=token_data.get("workspace_id"),
            focus_tags=data.focus_tags,
        )
        return plan
    except ApiTestPlanError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/plans", response_model=list[TestPlanResponse])
async def list_plans(token_data: dict = Depends(get_current_user)):
    """List all generated test plans."""
    return ApiTestPlannerService.list_plans(token_data.get("workspace_id"))


@router.get("/plans/{plan_id}", response_model=TestPlanResponse)
async def get_plan(plan_id: int, token_data: dict = Depends(get_current_user)):
    """Get a test plan with all scenarios."""
    plan = ApiTestPlannerService.get_plan(plan_id, token_data.get("workspace_id"))
    if not plan:
        raise HTTPException(status_code=404, detail="Test plan not found")
    return plan


@router.get("/plans/{plan_id}/export/markdown", response_model=ExportMarkdownResponse)
async def export_plan_markdown(
    plan_id: int,
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
    plan_id: int,
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
