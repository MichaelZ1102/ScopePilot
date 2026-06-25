"""AI 分析触发与结果查询路由。"""
from fastapi import APIRouter, Depends, HTTPException

from ...services import get_current_user
from ...services.jira import JiraService
from ...services.analysis import AnalysisService, AnalysisServiceError
from ...schemas import SprintDetailResponse
from ..v1.projects import _projects

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
    description="对指定 Sprint 内的所有 Ticket 执行 AI 批量分析并生成 Sprint 摘要。当前为同步执行。",
)
async def trigger_analysis(
    sprint_id: int,
    token_data: dict = Depends(get_current_user),
):
    """触发 AI 分析管线。

    分析过程**同步**执行（后续阶段将改为后台异步任务）。
    分析完成后会将结果写入内存 sprint 记录并返回完整 sprint 数据。
    """
    _verify_sprint_access(sprint_id, token_data)

    try:
        result = AnalysisService.analyze_sprint(sprint_id)
    except AnalysisServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return SprintDetailResponse(**result)


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

    analysis_data = sprint.get("analysis_data")
    if analysis_data is None:
        raise HTTPException(
            status_code=404,
            detail="该 Sprint 尚未进行 AI 分析。请先调用 POST /api/v1/analysis/sprints/{sprint_id}/analyze",
        )

    return SprintDetailResponse(**sprint)
