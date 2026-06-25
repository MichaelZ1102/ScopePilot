"""AI 分析服务 - 封装 CLI 的分析管线供 Web API 使用。

将 scopepilot.analyzer 中的 AnalysisPipeline 集成到后端服务层，
支持触发式 Sprint 分析和查询已有分析结果。
"""
import logging
from typing import Optional

from scopepilot.analyzer import AnalysisPipeline
from scopepilot.ai import create_provider, AIError

from .jira import JiraService, _sprints

logger = logging.getLogger(__name__)


class AnalysisServiceError(Exception):
    """分析服务基础异常。"""


class AnalysisService:
    """AI 分析服务，对 Sprint 内的所有 Ticket 执行批量分析和 Sprint 摘要生成。"""

    @staticmethod
    def analyze_sprint(sprint_id: int) -> dict:
        """对指定 sprint 运行 AI 分析管线。

        步骤:
          1. 通过 JiraService 获取 sprint 及对应 tickets
          2. 从环境变量创建 AI provider
          3. 使用 AnalysisPipeline 对 tickets 做批量分析
          4. 生成 sprint 级别的摘要
          5. 将分析结果写入内存 sprint 记录
          6. 返回带分析数据的 sprint dict

        Args:
            sprint_id: 内部 sprint ID.

        Returns:
            包含 ``analysis_data`` 和 ``analysis_status`` 的 sprint dict.

        Raises:
            AnalysisServiceError: sprint 不存在、无 ticket、或 AI 分析失败。
        """
        # 1. 获取 sprint + tickets
        sprint = JiraService.get_sprint(sprint_id)
        if sprint is None:
            raise AnalysisServiceError(f"Sprint {sprint_id} 不存在")

        tickets = sprint.get("tickets", [])
        if not tickets:
            raise AnalysisServiceError(f"Sprint {sprint_id} 没有需要分析的 ticket")

        # 标记为"运行中"
        _sprints[sprint_id]["analysis_status"] = "running"

        try:
            # 2-3. 创建 provider 和 pipeline
            provider = create_provider()
            pipeline = AnalysisPipeline(provider=provider)

            # 4. 批量分析 ticket
            logger.info(
                "正在分析 Sprint「%s」的 %d 个 ticket …",
                sprint["name"], len(tickets),
            )
            ticket_analyses = pipeline.analyze_tickets_batch(tickets)

            # 5. 生成 sprint 摘要
            logger.info(
                "正在生成 Sprint「%s」的分析摘要 …", sprint["name"],
            )
            sprint_analysis = pipeline.analyze_sprint(
                sprint["name"], ticket_analyses,
            )

            # 组装分析数据
            analysis_data = {
                "sprint_analysis": sprint_analysis.to_dict(),
                "ticket_analyses": [ta.to_dict() for ta in ticket_analyses],
            }

            # 6. 持久化到内存 sprint 记录
            _sprints[sprint_id]["analysis_data"] = analysis_data
            _sprints[sprint_id]["analysis_status"] = "done"

            return {
                **sprint,
                "analysis_data": analysis_data,
                "analysis_status": "done",
            }

        except AIError as exc:
            _sprints[sprint_id]["analysis_status"] = "failed"
            logger.error("Sprint %d AI 分析失败: %s", sprint_id, exc)
            raise AnalysisServiceError(f"AI 分析失败: {exc}") from exc

        except Exception as exc:
            _sprints[sprint_id]["analysis_status"] = "failed"
            logger.exception("Sprint %d 分析过程出现未预期错误", sprint_id)
            raise AnalysisServiceError(f"分析失败: {exc}") from exc

    @staticmethod
    def get_analysis(sprint_id: int) -> Optional[dict]:
        """获取 sprint 已有的分析结果。

        Args:
            sprint_id: 内部 sprint ID.

        Returns:
            带 ``analysis_data`` 的 sprint dict，若 sprint 不存在或未分析过返回 *None*。
        """
        sprint = JiraService.get_sprint(sprint_id)
        if sprint is None:
            return None
        if sprint.get("analysis_data") is None:
            return None
        return sprint
