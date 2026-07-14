"""AI 分析触发与结果查询路由。"""
import asyncio
import logging
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Path

from ...services import get_current_user, require_roles
from ...services.jira import JiraService, SprintStore, _sprints
from ...services.lifecycle import LifecycleService
from ...services.notifications import NotificationService
from ...services.analysis import AnalysisJobStore, AnalysisService, AnalysisServiceError
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


@router.get("/jobs")
async def list_analysis_jobs(
    token_data: dict = Depends(get_current_user),
):
    """List analysis jobs for the current workspace."""
    return AnalysisService.list_jobs(token_data.get("workspace_id"))


@router.get("/jobs/{job_id}")
async def get_analysis_job(
    job_id: Annotated[int, Path(gt=0)],
    token_data: dict = Depends(get_current_user),
):
    job = AnalysisService.get_job(job_id, token_data.get("workspace_id"))
    if not job:
        raise HTTPException(status_code=404, detail="Analysis job not found")
    return job


@router.post("/jobs/{job_id}/cancel")
async def cancel_analysis_job(
    job_id: Annotated[int, Path(gt=0)],
    token_data: dict = Depends(require_roles("admin", "member")),
):
    job = await AnalysisService.request_cancel(job_id, token_data.get("workspace_id"))
    if not job:
        raise HTTPException(status_code=409, detail="Analysis job cannot be cancelled")
    return job


@router.post("/jobs/{job_id}/retry", status_code=201)
async def retry_analysis_job(
    job_id: Annotated[int, Path(gt=0)],
    background_tasks: BackgroundTasks,
    token_data: dict = Depends(require_roles("admin", "member")),
):
    previous = AnalysisService.get_job(job_id, token_data.get("workspace_id"))
    if not previous:
        raise HTTPException(status_code=404, detail="Analysis job not found")
    if previous.get("status") not in {"failed", "cancelled"}:
        raise HTTPException(status_code=409, detail="Only failed or cancelled jobs can be retried")
    sprint_id = previous["sprint_id"]
    _verify_sprint_access(sprint_id, token_data)
    job = await AnalysisService.create_job(sprint_id, token_data.get("workspace_id"))
    await SprintStore.update_fields(
        sprint_id,
        {"analysis_status": "running", "latest_analysis_job_id": job["id"]},
    )
    background_tasks.add_task(
        _run_analysis_background,
        sprint_id,
        job["id"],
        token_data.get("workspace_id"),
    )
    await LifecycleService.audit(
        workspace_id=token_data.get("workspace_id"),
        actor_id=token_data.get("user_id"),
        actor_name=token_data.get("name", token_data.get("sub", "")),
        action="analysis.sprint.start",
        resource_type="sprint",
        resource_id=sprint_id,
        details={"job_id": job["id"]},
    )
    return job


@router.post(
    "/sprints/{sprint_id}/analyze",
    response_model=SprintDetailResponse,
    summary="触发 AI 分析",
    description="对指定 Sprint 内的所有 Ticket 执行 AI 批量分析并生成 Sprint 摘要。后台异步执行。",
)
async def trigger_analysis(
    sprint_id: Annotated[int, Path(gt=0)],
    background_tasks: BackgroundTasks,
    token_data: dict = Depends(require_roles("admin", "member")),
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
    background_tasks.add_task(
        _run_analysis_background,
        sprint_id,
        job["id"],
        token_data.get("workspace_id"),
    )

    return SprintDetailResponse(**_sprints[sprint_id])


def _run_analysis_background(sprint_id: int, job_id: int, workspace_id: int):
    """后台运行 AI 分析（在 executor 线程中执行）。"""
    try:
        asyncio.run(AnalysisService.update_job(job_id, "running"))
        job = AnalysisJobStore.get(job_id)
        if job and job.get("cancel_requested"):
            asyncio.run(AnalysisService.update_job(job_id, "cancelled"))
            asyncio.run(SprintStore.update_fields(
                sprint_id,
                {"analysis_status": _analysis_status_after_cancel(sprint_id)},
            ))
            return
        asyncio.run(AnalysisService.analyze_sprint(sprint_id, workspace_id, job_id))
        asyncio.run(AnalysisService.update_job(job_id, "done"))
        asyncio.run(NotificationService.emit(
            workspace_id=workspace_id,
            event_type="analysis.completed",
            title="Sprint 分析完成",
            message=f"Sprint #{sprint_id} 的分析任务已完成。",
            resource_type="sprint",
            resource_id=sprint_id,
            details={"job_id": job_id},
        ))
        logger.info("Sprint %d AI 分析完成", sprint_id)
    except AnalysisServiceError as exc:
        status = "cancelled" if str(exc) == "Analysis cancelled" else "failed"
        asyncio.run(AnalysisService.update_job(job_id, status, str(exc)))
        if status == "cancelled":
            asyncio.run(SprintStore.update_fields(
                sprint_id,
                {"analysis_status": _analysis_status_after_cancel(sprint_id)},
            ))
        asyncio.run(NotificationService.emit(
            workspace_id=workspace_id,
            event_type=f"analysis.{status}",
            title="Sprint 分析已取消" if status == "cancelled" else "Sprint 分析失败",
            message=str(exc),
            resource_type="sprint",
            resource_id=sprint_id,
            details={"job_id": job_id},
        ))
        pass  # analyze_sprint already sets status=done/failed and persists


def _analysis_status_after_cancel(sprint_id: int) -> str:
    """Restore a truthful Sprint state when a background analysis is cancelled."""
    sprint = JiraService.get_sprint(sprint_id) or {}
    if sprint.get("analysis_data"):
        return "done"
    if any(ticket.get("analysis_data") for ticket in JiraService.list_tickets(sprint_id)):
        return "partial"
    return "pending"


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
    token_data: dict = Depends(require_roles("admin", "member")),
):
    """Run AI analysis for one Ticket and replace its previous result."""
    sprint = _verify_sprint_access(sprint_id, token_data)
    ticket = JiraService.get_ticket(ticket_id)
    if ticket is None or ticket.get("sprint_id") != sprint["id"]:
        raise HTTPException(status_code=404, detail="Ticket 不存在")

    try:
        analysis_result = await AnalysisService.analyze_ticket(
            sprint_id,
            ticket_id,
            token_data.get("workspace_id"),
        )
        await LifecycleService.audit(
            workspace_id=token_data.get("workspace_id"),
            actor_id=token_data.get("user_id"),
            actor_name=token_data.get("name", token_data.get("sub", "")),
            action="analysis.ticket.complete",
            resource_type="ticket",
            resource_id=ticket_id,
            details={"sprint_id": sprint_id},
        )
        await NotificationService.emit(
            workspace_id=token_data.get("workspace_id"),
            event_type="analysis.ticket.completed",
            title=f"{ticket['key']} 分析完成",
            message="Ticket 分析结果已更新，等待审核。",
            resource_type="ticket",
            resource_id=ticket_id,
        )
        return {
            "ticket_id": ticket_id,
            "ticket_key": ticket["key"],
            "analysis": analysis_result,
        }
    except AnalysisServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
