"""AI-powered analysis pipeline for Sprint and Ticket analysis."""

import json
import logging
from dataclasses import dataclass
from typing import Optional

from .ai import AIProvider, create_provider

logger = logging.getLogger(__name__)


SYSTEM_PROMPT_TICKET = """你是资深后端 Tech Lead。请分析下面的 Jira ticket，输出结构化 JSON。

目标：
1. 总结业务目标。
2. 拆解 Acceptance Criteria。
3. 识别后端功能点。
4. 判断是否涉及 API、DB、权限、状态流、校验逻辑、外部依赖。
5. 找出需求不清晰的问题。
6. 给出复杂度和风险评分。

限制：
- 不要编造 ticket 中不存在的业务规则。
- 如果信息不足，放入 open_questions。
- 输出必须是合法 JSON。"""

SYSTEM_PROMPT_TICKET_BATCH = """你是资深后端 Tech Lead。请分析下面的多个 Jira tickets，**对每个 ticket 分别输出结构化 JSON，放在一个 JSON 数组中**。

每个 ticket 分析目标：
1. 总结业务目标。
2. 拆解 Acceptance Criteria。
3. 识别后端功能点。
4. 判断是否涉及 API、DB、权限、状态流、校验逻辑、外部依赖。
5. 找出需求不清晰的问题。
6. 给出复杂度和风险评分。

限制：
- 不要编造 ticket 中不存在的业务规则。
- 如果信息不足，放入 open_questions。
- **输出必须是合法 JSON 数组**，元素对应各个 ticket。
- 保持 JSON 数组顺序与输入一致。"""

SYSTEM_PROMPT_SPRINT = """你是资深后端 Tech Lead。请分析整个 Sprint 的 tickets，输出结构化 JSON。

目标：
1. 汇总迭代业务目标。
2. 识别跨 ticket 依赖。
3. 识别高风险 ticket。
4. 推荐执行顺序。
5. 生成 Sprint 级别的风险报告。

限制：
- 基于各个 ticket 的分析结果，不要编造不存在的信息。
- 输出必须是合法 JSON。"""


@dataclass
class TicketAnalysis:
    """Analysis result for a single ticket."""
    ticket_key: str
    summary: str
    business_goal: str = ""
    acceptance_criteria_summary: str = ""
    backend_features: list = None
    api_candidates: list = None
    db_changes: list = None
    permission_rules: list = None
    state_transitions: list = None
    validation_rules: list = None
    external_dependencies: list = None
    open_questions: list = None
    score: dict = None
    code_impact: dict = None
    implementation_plan: list = None
    api_tests: list = None
    comments: list = None

    def to_dict(self) -> dict:
        return {
            "ticket_key": self.ticket_key,
            "summary": self.summary,
            "business_goal": self.business_goal,
            "acceptance_criteria_summary": self.acceptance_criteria_summary,
            "backend_features": self.backend_features or [],
            "api_candidates": self.api_candidates or [],
            "db_changes": self.db_changes or [],
            "permission_rules": self.permission_rules or [],
            "state_transitions": self.state_transitions or [],
            "validation_rules": self.validation_rules or [],
            "external_dependencies": self.external_dependencies or [],
            "open_questions": self.open_questions or [],
            "score": self.score or {},
            "code_impact": self.code_impact or {},
            "implementation_plan": self.implementation_plan or [],
            "api_tests": self.api_tests or [],
            "comments": self.comments or [],
        }


@dataclass
class SprintAnalysis:
    """Analysis result for a full sprint."""
    sprint_name: str
    total_tickets: int
    summary: str = ""
    risk_map: list = None
    open_questions: list = None
    suggested_execution_order: list = None
    ticket_analyses: list = None

    def to_dict(self) -> dict:
        return {
            "sprint_name": self.sprint_name,
            "total_tickets": self.total_tickets,
            "summary": self.summary,
            "risk_map": self.risk_map or [],
            "open_questions": self.open_questions or [],
            "suggested_execution_order": self.suggested_execution_order or [],
            "ticket_analyses": [t.to_dict() if isinstance(t, TicketAnalysis) else t for t in (self.ticket_analyses or [])],
        }


def _parse_ticket_result(ticket_key: str, summary: str, result: dict, comments: list = None) -> TicketAnalysis:
    """Parse a single AI result dict into TicketAnalysis."""
    return TicketAnalysis(
        ticket_key=ticket_key,
        summary=summary,
        business_goal=result.get("business_goal", ""),
        acceptance_criteria_summary=result.get("acceptance_criteria_summary", ""),
        backend_features=result.get("backend_features", []),
        api_candidates=result.get("api_candidates", []),
        db_changes=result.get("db_changes", []),
        permission_rules=result.get("permission_rules", []),
        state_transitions=result.get("state_transitions", []),
        validation_rules=result.get("validation_rules", []),
        external_dependencies=result.get("external_dependencies", []),
        open_questions=result.get("open_questions", []),
        score=result.get("score", {}),
        code_impact=result.get("code_impact", {}),
        implementation_plan=result.get("implementation_plan", []),
        api_tests=result.get("api_tests", []),
        comments=comments or [],
    )


class AnalysisPipeline:
    """AI analysis pipeline for Sprint and Ticket analysis."""

    def __init__(self, provider: Optional[AIProvider] = None):
        self.provider = provider or create_provider()

    def analyze_ticket(self, ticket_data: dict) -> TicketAnalysis:
        """Analyze a single ticket using AI."""
        ticket_key = ticket_data["key"]
        summary = ticket_data["summary"]
        description = ticket_data.get("description", "")
        acceptance_criteria = ticket_data.get("acceptance_criteria", [])
        comments = ticket_data.get("comments", [])

        ac_text = "\n".join(f"- {ac}" for ac in acceptance_criteria[:20]) if acceptance_criteria else "No explicit AC provided."

        # Include comments as context
        comments_text = ""
        if comments:
            parts = []
            for c in comments[:8]:  # limit to 8 most recent
                parts.append(f"[{c['author']}]: {c['body'][:300]}")
            comments_text = "\n".join(parts) if parts else ""

        user_prompt = f"""## Ticket: {ticket_key}
## Summary: {summary}
## Description:
{description[:3000]}

## Acceptance Criteria:
{ac_text}

## Comments:
{comments_text if comments_text else "No comments available."}

Please analyze this ticket and return the structured JSON result."""

        try:
            result = self.provider.chat_json(SYSTEM_PROMPT_TICKET, user_prompt)
            return _parse_ticket_result(ticket_key, summary, result, comments)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI response for {ticket_key}: {e}")
            return TicketAnalysis(
                ticket_key=ticket_key,
                summary=summary,
                open_questions=["AI analysis failed to produce valid JSON. Please retry."],
            )
        except Exception as e:
            logger.error(f"AI analysis failed for {ticket_key}: {e}")
            return TicketAnalysis(
                ticket_key=ticket_key,
                summary=summary,
                open_questions=[f"AI analysis error: {str(e)}"],
            )

    def analyze_tickets_batch(self, tickets_data: list[dict], batch_size: int = 5) -> list[TicketAnalysis]:
        """Analyze multiple tickets in batches, each batch sends one AI call."""
        all_results = []

        for i in range(0, len(tickets_data), batch_size):
            batch = tickets_data[i:i + batch_size]
            logger.info(f"Analyzing batch {i // batch_size + 1}: tickets {batch[0]['key']}..{batch[-1]['key']}")

            # Build batch prompt
            sections = []
            for td in batch:
                key = td["key"]
                summary = td["summary"]
                description = (td.get("description", "") or "")[:2000]
                ac = td.get("acceptance_criteria", [])
                ac_text = "\n".join(f"- {a}" for a in ac[:10]) if ac else "None"
                sections.append(f"""### Ticket: {key}
**Summary**: {summary}
**Description**:
{description}
**Acceptance Criteria**:
{ac_text}
---""")

            user_prompt = "Please analyze the following tickets and return a JSON array of analysis results:\n\n" + "\n".join(sections)

            try:
                raw_result = self.provider._parse_json(
                    self.provider.chat(SYSTEM_PROMPT_TICKET_BATCH, user_prompt)
                )

                # Handle both list and single-dict responses
                if isinstance(raw_result, list):
                    results_list = raw_result
                elif isinstance(raw_result, dict):
                    # Try common wrapping keys
                    for key in ("results", "analyses", "tickets", "data"):
                        if key in raw_result and isinstance(raw_result[key], list):
                            results_list = raw_result[key]
                            break
                    else:
                        results_list = [raw_result]
                else:
                    results_list = []

                for j, td in enumerate(batch):
                    if j < len(results_list) and isinstance(results_list[j], dict):
                        result = results_list[j]
                        all_results.append(_parse_ticket_result(
                            td["key"], td["summary"], result
                        ))
                    else:
                        all_results.append(TicketAnalysis(
                            ticket_key=td["key"],
                            summary=td["summary"],
                            open_questions=["AI batch analysis did not return result for this ticket."],
                        ))

            except Exception as e:
                logger.error(f"Batch analysis failed for {batch[0]['key']}..{batch[-1]['key']}: {e}")
                for td in batch:
                    all_results.append(TicketAnalysis(
                        ticket_key=td["key"],
                        summary=td["summary"],
                        open_questions=[f"Batch analysis error: {str(e)}"],
                    ))

        return all_results

    def analyze_sprint(self, sprint_name: str, ticket_analyses: list[TicketAnalysis]) -> SprintAnalysis:
        """Generate sprint-level analysis from individual ticket analyses."""
        analyses_json = json.dumps(
            [t.to_dict() for t in ticket_analyses],
            ensure_ascii=False,
            indent=2,
        )

        user_prompt = f"""## Sprint: {sprint_name}
## Total Tickets: {len(ticket_analyses)}

## Ticket Analyses:
{analyses_json}

Please generate the sprint-level analysis (summary, risk map, execution order, open questions)."""

        try:
            result = self.provider.chat_json(SYSTEM_PROMPT_SPRINT, user_prompt)
            return SprintAnalysis(
                sprint_name=sprint_name,
                total_tickets=len(ticket_analyses),
                summary=result.get("summary", ""),
                risk_map=result.get("risk_map", []),
                open_questions=result.get("open_questions", []),
                suggested_execution_order=result.get("suggested_execution_order", []),
                ticket_analyses=ticket_analyses,
            )
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI response for sprint: {e}")
            return SprintAnalysis(
                sprint_name=sprint_name,
                total_tickets=len(ticket_analyses),
                open_questions=["Sprint analysis failed to produce valid JSON. Please retry."],
                ticket_analyses=ticket_analyses,
            )
        except Exception as e:
            logger.error(f"AI analysis failed for sprint: {e}")
            return SprintAnalysis(
                sprint_name=sprint_name,
                total_tickets=len(ticket_analyses),
                open_questions=[f"Sprint AI analysis error: {str(e)}"],
                ticket_analyses=ticket_analyses,
            )
