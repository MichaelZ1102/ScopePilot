"""AI 分析触发与结果查询路由。"""
import asyncio
import logging
from fastapi import APIRouter, Depends, HTTPException

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
    sprint_id: int,
    token_data: dict = Depends(get_current_user),
):
    """触发 AI 分析管线（后台异步执行）。"""
    _verify_sprint_access(sprint_id, token_data)

    # 如果已在分析中则跳过
    if _sprints.get(sprint_id, {}).get("analysis_status") == "running":
        raise HTTPException(status_code=409, detail="该 Sprint 正在分析中")

    # 标记为"运行中"并立即返回
    await SprintStore._persist_update(sprint_id, {"analysis_status": "running"})

    # 后台异步执行分析
    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, _run_analysis_background, sprint_id)

    return SprintDetailResponse(**_sprints[sprint_id])


def _run_analysis_background(sprint_id: int):
    """后台运行 AI 分析（在 executor 线程中执行）。"""
    try:
        asyncio.run(AnalysisService.analyze_sprint(sprint_id))
        logger.info("Sprint %d AI 分析完成", sprint_id)
    except AnalysisServiceError:
        pass  # analyze_sprint already sets status=done/failed and persists


@router.get(
    "/sprints/{sprint_id}/analysis",
    response_model=SprintDetailResponse,
    summary="获取分析结果",
    description="获取指定 Sprint 已有的 AI 分析结果。若尚未分析则返回 404。",
)
async def get_analysis(
    sprint_id: int,
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
