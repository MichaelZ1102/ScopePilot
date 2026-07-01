"""AI 分析触发与结果查询路由。"""
import asyncio
import logging
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Path

from ...services import get_current_user
from ...services.jira import JiraService, SprintStore, _sprints
from ...services.analysis import AnalysisService, AnalysisServiceError
from ...schemas import SprintDetailResponse
from ..v1.projects import _projects

logger = logging.getLogger(__name__)
router = APIRouter()


def _verify_sprint_access(sprint_id: int, token_data: dict) -> dict:
    """校验 sprint 是否存在且属于当前用户的 workspace。"""
    sprint = JiraService.get_sprint(sprint_id)
    if sprint is None:
        raise HTTPException(status_code=404, detail="Sprint 不存在")

    project = _projects.get(sprint["project_id"])
    if project is None:
        raise HTTPException(status_code=404, detail="Sprint 不存在")
    if project["workspace_id"] != token_data.get("workspace_id"):
        raise HTTPException(status_code=404, detail="Sprint 不存在")

    return sprint


@router.post(
    "/sprints/{sprint_id}/analyze",
    response_model=SprintDetailResponse,
    summary="触发 AI 分析",
    description="对指定 Sprint 内的所有 Ticket 执行 AI 批量分析并生成 Sprint 摘要。后台异步执行。",
)
async def trigger_analysis(
    sprint_id: Annotated[int, Path(gt=0)],
    background_tasks: BackgroundTasks,
    token_data: dict = Depends(get_current_user),
):
    """触发 AI 分析管线（后台异步执行）。"""
    _verify_sprint_access(sprint_id, token_data)

    # 如果已在分析中则跳过
    if _sprints.get(sprint_id, {}).get("analysis_status") == "running":
        raise HTTPException(status_code=409, detail="该 Sprint 正在分析中")

    # 标记为"运行中"并立即返回
    job = await AnalysisService.create_job(sprint_id, token_data.get("workspace_id"))
    await SprintStore.update_fields(
        sprint_id,
        {"analysis_status": "running", "latest_analysis_job_id": job["id"]},
    )

    # 后台异步执行分析
    background_tasks.add_task(_run_analysis_background, sprint_id, job["id"])

    return SprintDetailResponse(**_sprints[sprint_id])


def _run_analysis_background(sprint_id: int, job_id: int):
    """后台运行 AI 分析（在 executor 线程中执行）。"""
    try:
        asyncio.run(AnalysisService.update_job(job_id, "running"))
        asyncio.run(AnalysisService.analyze_sprint(sprint_id))
        asyncio.run(AnalysisService.update_job(job_id, "done"))
        logger.info("Sprint %d AI 分析完成", sprint_id)
    except AnalysisServiceError as exc:
        asyncio.run(AnalysisService.update_job(job_id, "failed", str(exc)))
        pass  # analyze_sprint already sets status=done/failed and persists


@router.get(
    "/sprints/{sprint_id}/analysis",
    response_model=SprintDetailResponse,
    summary="获取分析结果",
    description="获取指定 Sprint 已有的 AI 分析结果。若尚未分析则返回 404。",
)
async def get_analysis(
    sprint_id: Annotated[int, Path(gt=0)],
    token_data: dict = Depends(get_current_user),
):
    """获取已存储的 AI 分析结果。"""
    sprint = _verify_sprint_access(sprint_id, token_data)
    status = sprint.get("analysis_status")

    if status == "running":
        raise HTTPException(status_code=202, detail="该 Sprint 正在分析中，请稍后查询")

    analysis_data = sprint.get("analysis_data")
    if analysis_data is None or status == "failed":
        raise HTTPException(
            status_code=404,
            detail="该 Sprint 尚未进行 AI 分析。请先调用 POST /api/v1/analysis/sprints/{sprint_id}/analyze",
        )

    return SprintDetailResponse(**sprint)


@router.post(
    "/sprints/{sprint_id}/tickets/{ticket_id}/analyze",
    summary="重新分析单个 Ticket",
)
async def analyze_ticket(
    sprint_id: Annotated[int, Path(gt=0)],
    ticket_id: Annotated[int, Path(gt=0)],
    token_data: dict = Depends(get_current_user),
):
    """Run AI analysis for one Ticket and replace its previous result."""
    sprint = _verify_sprint_access(sprint_id, token_data)
    ticket = JiraService.get_ticket(ticket_id)
    if ticket is None or ticket.get("sprint_id") != sprint["id"]:
        raise HTTPException(status_code=404, detail="Ticket 不存在")

    try:
        analysis_result = await AnalysisService.analyze_ticket(sprint_id, ticket_id)
        return {
            "ticket_id": ticket_id,
            "ticket_key": ticket["key"],
            "analysis": analysis_result,
        }
    except AnalysisServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
