"""Structured Ticket and Sprint reports assembled from persisted analysis artifacts."""
from datetime import datetime, timezone
from typing import Optional

from ..api.v1.projects import ProjectStore
from .api_test_planner import ApiImpactStore, ApiSpecStore, TestPlanStore
from .codebase import CodeImpactStore, CodeSourceStore, CodebaseService
from .figma import FigmaAnalysisStore
from .jira import JiraService
from .lifecycle import LifecycleService


class ReportingError(Exception):
    """Raised when a report target is missing or inaccessible."""


def _public_api_spec(spec: dict) -> dict:
    return {
        key: value
        for key, value in spec.items()
        if key not in {"raw_spec", "workspace_id"}
    }


def _public_source(source: dict) -> dict:
    return CodebaseService._without_secrets(source)


class ReportingService:
    @staticmethod
    def _resolve_ticket(ticket_id: int, workspace_id: int) -> tuple[dict, dict, dict]:
        ticket = JiraService.get_ticket(ticket_id)
        sprint = JiraService.get_sprint(ticket.get("sprint_id")) if ticket else None
        project = ProjectStore.get(sprint.get("project_id")) if sprint else None
        if not ticket or not sprint or not project or project.get("workspace_id") != workspace_id:
            raise ReportingError("Ticket not found")
        return project, sprint, ticket

    @staticmethod
    def build_ticket_report(
        ticket_id: int,
        workspace_id: int,
        analysis_run_id: Optional[int] = None,
    ) -> dict:
        project, sprint, ticket = ReportingService._resolve_ticket(ticket_id, workspace_id)
        links = LifecycleService.list_artifact_links(ticket_id, workspace_id)
        code_impacts: dict[int, dict] = {}
        code_sources: dict[int, dict] = {}
        api_specs: dict[int, dict] = {}
        api_impacts: dict[int, dict] = {}
        test_plans: dict[int, dict] = {}
        figma_analyses: dict[int, dict] = {}

        for link in links:
            artifact_id = link.get("artifact_id")
            artifact_type = link.get("artifact_type")
            if artifact_type == "code_impact":
                impact = CodeImpactStore.get(artifact_id)
                if impact:
                    code_impacts[artifact_id] = impact
                    source = CodeSourceStore.get(impact.get("code_source_id"))
                    if source and source.get("workspace_id") == workspace_id:
                        code_sources[source["id"]] = _public_source(source)
            elif artifact_type == "code_source":
                source = CodeSourceStore.get(artifact_id)
                if source and source.get("workspace_id") == workspace_id:
                    code_sources[artifact_id] = _public_source(source)
            elif artifact_type == "api_spec":
                spec = ApiSpecStore.get(artifact_id)
                if spec and spec.get("workspace_id") == workspace_id:
                    api_specs[artifact_id] = _public_api_spec(spec)
            elif artifact_type == "api_impact":
                impact = ApiImpactStore.get(artifact_id)
                if impact and impact.get("workspace_id") == workspace_id:
                    api_impacts[artifact_id] = impact
                    spec = ApiSpecStore.get(impact.get("spec_id"))
                    if spec and spec.get("workspace_id") == workspace_id:
                        api_specs[spec["id"]] = _public_api_spec(spec)
            elif artifact_type == "test_plan":
                plan = TestPlanStore.get(artifact_id)
                if plan and plan.get("workspace_id") == workspace_id:
                    test_plans[artifact_id] = plan
                    spec = ApiSpecStore.get(plan.get("spec_id"))
                    if spec and spec.get("workspace_id") == workspace_id:
                        api_specs[spec["id"]] = _public_api_spec(spec)
            elif artifact_type == "figma_analysis":
                analysis = FigmaAnalysisStore.get(artifact_id)
                if analysis and analysis.get("workspace_id") == workspace_id:
                    figma_analyses[artifact_id] = analysis

        for impact in CodeImpactStore.list_by("ticket_id", ticket_id):
            source = CodeSourceStore.get(impact.get("code_source_id"))
            if source and source.get("workspace_id") == workspace_id:
                code_impacts[impact["id"]] = impact
                code_sources[source["id"]] = _public_source(source)
        for plan in TestPlanStore.list_by("workspace_id", workspace_id):
            if ticket_id in plan.get("ticket_ids", []):
                test_plans[plan["id"]] = plan
                spec = ApiSpecStore.get(plan.get("spec_id"))
                if spec:
                    api_specs[spec["id"]] = _public_api_spec(spec)
        for impact in ApiImpactStore.list_by("ticket_id", ticket_id):
            if impact.get("workspace_id") == workspace_id:
                api_impacts[impact["id"]] = impact
                spec = ApiSpecStore.get(impact.get("spec_id"))
                if spec:
                    api_specs[spec["id"]] = _public_api_spec(spec)
        for analysis in FigmaAnalysisStore.list_by("workspace_id", workspace_id):
            if analysis.get("ticket_id") == ticket_id:
                figma_analyses[analysis["id"]] = analysis

        latest_run = LifecycleService.get_latest_analysis_run(ticket_id, workspace_id)
        selected_run = (
            LifecycleService.get_analysis_run(
                analysis_run_id,
                workspace_id,
                ticket_id,
            )
            if analysis_run_id is not None
            else latest_run
        )
        if analysis_run_id is not None and selected_run is None:
            raise ReportingError("Analysis version not found")
        review = LifecycleService.get_review(ticket_id, workspace_id) or {
            "ticket_id": ticket_id,
            "status": "unreviewed",
        }
        analysis = (
            (selected_run or {}).get("result")
            if analysis_run_id is not None
            else ticket.get("analysis_data") or (latest_run or {}).get("result")
        ) or {}
        stale_reasons = []
        if ticket.get("analysis_status") == "stale" or ticket.get("analysis_stale_at"):
            stale_reasons.append("Jira Ticket 或关联资产在分析后发生变化")
        delivery_links = LifecycleService.list_delivery_links(ticket_id, workspace_id)
        latest_impacts_by_source: dict[int, dict] = {}
        for impact in code_impacts.values():
            source_id = impact.get("code_source_id")
            current = latest_impacts_by_source.get(source_id)
            if current is None or impact.get("created_at", "") > current.get("created_at", ""):
                latest_impacts_by_source[source_id] = impact
        predicted_files = {
            item.get("path")
            for impact in latest_impacts_by_source.values()
            for item in impact.get("affected_files") or []
            if item.get("path")
        }
        actual_files = {
            path
            for delivery in delivery_links
            for path in delivery.get("actual_files") or []
        }
        matched_files = sorted(predicted_files & actual_files)
        delivery_comparison = {
            "predicted_files": sorted(predicted_files),
            "actual_files": sorted(actual_files),
            "matched_files": matched_files,
            "unexpected_files": sorted(actual_files - predicted_files),
            "predicted_not_changed": sorted(predicted_files - actual_files),
            "match_rate": round(len(matched_files) / len(predicted_files), 3) if predicted_files else None,
        }

        return {
            "report_type": "ticket",
            "title": f"{ticket.get('key')}: {ticket.get('summary')}",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "project": {
                "id": project["id"],
                "name": project["name"],
                "jira_project_key": project.get("jira_project_key"),
                "jira_url": project.get("jira_url"),
            },
            "sprint": {
                "id": sprint["id"],
                "name": sprint["name"],
                "state": sprint.get("state"),
                "last_synced_at": sprint.get("last_synced_at"),
            },
            "ticket": {
                key: ticket.get(key)
                for key in (
                    "id",
                    "sprint_id",
                    "key",
                    "summary",
                    "description",
                    "issue_type",
                    "status",
                    "priority",
                    "assignee",
                    "labels",
                    "story_points",
                    "acceptance_criteria",
                    "comments",
                    "figma_links",
                    "source_updated_at",
                    "report_included",
                )
            },
            "analysis": analysis,
            "analysis_run": selected_run,
            "is_historical": bool(
                selected_run
                and latest_run
                and selected_run.get("id") != latest_run.get("id")
            ),
            "review": review,
            "collaboration": {
                "comments": LifecycleService.list_comments(ticket_id, workspace_id),
                "action_items": LifecycleService.list_action_items(ticket_id, workspace_id),
                "delivery_links": delivery_links,
                "delivery_comparison": delivery_comparison,
            },
            "is_stale": bool(stale_reasons),
            "stale_reasons": stale_reasons,
            "artifacts": {
                "links": links,
                "code_sources": list(code_sources.values()),
                "code_impacts": sorted(
                    code_impacts.values(),
                    key=lambda item: item.get("created_at", ""),
                    reverse=True,
                ),
                "api_specs": list(api_specs.values()),
                "api_impacts": sorted(
                    api_impacts.values(),
                    key=lambda item: item.get("created_at", ""),
                    reverse=True,
                ),
                "test_plans": list(test_plans.values()),
                "figma_analyses": list(figma_analyses.values()),
            },
        }

    @staticmethod
    def build_sprint_report(sprint_id: int, workspace_id: int) -> dict:
        sprint = JiraService.get_sprint(sprint_id)
        project = ProjectStore.get(sprint.get("project_id")) if sprint else None
        if not sprint or not project or project.get("workspace_id") != workspace_id:
            raise ReportingError("Sprint not found")

        tickets = [
            ticket
            for ticket in sprint.get("tickets", [])
            if ticket.get("report_included", True)
        ]
        ticket_reports = [
            ReportingService.build_ticket_report(ticket["id"], workspace_id)
            for ticket in tickets
        ]
        review_counts = {"unreviewed": 0, "in_review": 0, "approved": 0, "rejected": 0}
        for report in ticket_reports:
            status = report["review"].get("status", "unreviewed")
            review_counts[status] = review_counts.get(status, 0) + 1
        file_to_tickets: dict[str, list[str]] = {}
        for report in ticket_reports:
            ticket_key = report["ticket"].get("key")
            impacts = report.get("artifacts", {}).get("code_impacts", [])
            latest_by_source: dict[int, dict] = {}
            for impact in impacts:
                source_id = impact.get("code_source_id")
                current = latest_by_source.get(source_id)
                if current is None or impact.get("created_at", "") > current.get("created_at", ""):
                    latest_by_source[source_id] = impact
            for impact in latest_by_source.values():
                for item in impact.get("affected_files") or []:
                    file_to_tickets.setdefault(item.get("path"), []).append(ticket_key)
        conflicts = [
            {"path": path, "tickets": sorted(set(ticket_keys))}
            for path, ticket_keys in file_to_tickets.items()
            if len(set(ticket_keys)) > 1
        ]
        execution_order = (
            (sprint.get("analysis_data") or {})
            .get("sprint_analysis", {})
            .get("suggested_execution_order", [])
        )
        dependency_edges = [
            {"from": execution_order[index], "to": execution_order[index + 1], "type": "suggested_order"}
            for index in range(len(execution_order) - 1)
        ]

        return {
            "report_type": "sprint",
            "title": f"Sprint 分析报告: {sprint['name']}",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "project": {
                "id": project["id"],
                "name": project["name"],
                "jira_project_key": project.get("jira_project_key"),
            },
            "sprint": {
                "id": sprint["id"],
                "name": sprint["name"],
                "state": sprint.get("state"),
                "total_tickets": len(ticket_reports),
                "last_synced_at": sprint.get("last_synced_at"),
                "analysis_status": sprint.get("analysis_status"),
            },
            "summary": (sprint.get("analysis_data") or {}).get("sprint_analysis", {}),
            "review_counts": review_counts,
            "stale_ticket_count": sum(1 for report in ticket_reports if report["is_stale"]),
            "dependency_graph": dependency_edges,
            "code_conflicts": conflicts,
            "tickets": ticket_reports,
        }

    @staticmethod
    def render_ticket_markdown(report: dict) -> str:
        ticket = report["ticket"]
        analysis = report.get("analysis") or {}
        review = report.get("review") or {}
        artifacts = report.get("artifacts") or {}
        lines = [
            f"# {ticket.get('key')}: {ticket.get('summary')}",
            "",
            f"- **项目**: {report['project'].get('name')}",
            f"- **Sprint**: {report['sprint'].get('name')}",
            f"- **状态**: {ticket.get('status') or '-'}",
            f"- **优先级**: {ticket.get('priority') or '-'}",
            f"- **负责人**: {ticket.get('assignee') or '-'}",
            f"- **审核状态**: {review.get('status', 'unreviewed')}",
            f"- **分析状态**: {'已过期' if report.get('is_stale') else '有效'}",
            "",
        ]
        if ticket.get("description"):
            lines += ["## 原始需求", ticket["description"], ""]
        lines += ["## 用户目标", analysis.get("business_goal") or "未生成", ""]

        acceptance = ticket.get("acceptance_criteria") or []
        if not acceptance and analysis.get("acceptance_criteria_summary"):
            acceptance = [analysis["acceptance_criteria_summary"]]
        if acceptance:
            lines += ["## 验收标准", *[f"- {item}" for item in acceptance], ""]

        for title, key in (
            ("后端功能点", "backend_features"),
            ("API 候选", "api_candidates"),
            ("数据库变更", "db_changes"),
            ("权限规则", "permission_rules"),
            ("状态流转", "state_transitions"),
            ("校验规则", "validation_rules"),
            ("外部依赖", "external_dependencies"),
            ("待确认问题", "open_questions"),
        ):
            values = analysis.get(key) or []
            if values:
                lines += [f"## {title}", *[f"- {value}" for value in values], ""]

        if analysis.get("implementation_plan"):
            lines += [
                "## 实现计划",
                *[
                    f"{index}. {step}"
                    for index, step in enumerate(analysis["implementation_plan"], 1)
                ],
                "",
            ]
        if analysis.get("score"):
            lines += ["## 复杂度与工作量"]
            for key, value in analysis["score"].items():
                lines.append(f"- **{key}**: {value}")
            lines.append("")
        if analysis.get("evidence"):
            lines += ["## 分析依据"]
            for item in analysis["evidence"]:
                lines.append(
                    f"- **{item.get('type', 'inference')} / {item.get('confidence', 'unknown')}** "
                    f"{item.get('claim', '')} — {item.get('source', '')} {item.get('locator', '')}"
                )
            lines.append("")
        if analysis.get("assumptions"):
            lines += ["## 分析假设", *[f"- {item}" for item in analysis["assumptions"]], ""]

        code_impacts = artifacts.get("code_impacts") or []
        if code_impacts:
            lines += ["## 代码影响"]
            latest_by_source: dict[int, dict] = {}
            for impact in code_impacts:
                source_id = impact.get("code_source_id")
                current = latest_by_source.get(source_id)
                if current is None or impact.get("created_at", "") > current.get("created_at", ""):
                    latest_by_source[source_id] = impact
            for impact in latest_by_source.values():
                lines.append(f"### 代码源 #{impact.get('code_source_id')}")
                lines.append(impact.get("summary") or "")
                for item in impact.get("affected_files") or []:
                    lines.append(
                        f"- `{item.get('path')}` · {item.get('change_type')} "
                        f"· {round(float(item.get('confidence', 0)) * 100)}%"
                    )
                lines.append("")

        api_specs = artifacts.get("api_specs") or []
        api_impacts = artifacts.get("api_impacts") or []
        test_plans = artifacts.get("test_plans") or []
        if api_specs or api_impacts or test_plans:
            lines += ["## API 影响"]
            for spec in api_specs:
                lines.append(
                    f"- **{spec.get('name')}** · v{spec.get('version')} "
                    f"· {spec.get('endpoint_count', 0)} 个端点"
                )
            for plan in test_plans:
                lines.append(
                    f"- 测试计划：{plan.get('title')} "
                    f"· {plan.get('scenario_count', 0)} 个场景"
                )
            for impact in api_impacts:
                for item in impact.get("impacts") or []:
                    lines.append(
                        f"- `{item.get('method')} {item.get('path')}` · "
                        f"{item.get('change_type')} · {item.get('confirmation')}"
                    )
            lines.append("")

        figma_analyses = artifacts.get("figma_analyses") or []
        if figma_analyses:
            lines += ["## Figma 影响"]
            for item in figma_analyses:
                lines.append(
                    f"- **{item.get('file_name')}** · "
                    f"{len(item.get('implications') or [])} 个影响项"
                )
            lines.append("")

        if review.get("comment"):
            lines += ["## 审核意见", review["comment"], ""]
        collaboration = report.get("collaboration") or {}
        action_items = collaboration.get("action_items") or []
        if action_items:
            lines += ["## 待确认事项"]
            for item in action_items:
                marker = "x" if item.get("status") == "done" else " "
                owner = f" · {item.get('owner')}" if item.get("owner") else ""
                due_at = f" · {item.get('due_at')}" if item.get("due_at") else ""
                lines.append(f"- [{marker}] {item.get('title')}{owner}{due_at}")
            lines.append("")
        comments = collaboration.get("comments") or []
        if comments:
            lines += ["## 审核讨论"]
            for comment in comments:
                lines.append(
                    f"- **{comment.get('author_name')}** ({comment.get('status')}): "
                    f"{comment.get('body')}"
                )
            lines.append("")
        delivery_links = collaboration.get("delivery_links") or []
        if delivery_links:
            lines += ["## 开发交付"]
            for item in delivery_links:
                lines.append(
                    f"- [{item.get('provider')}]({item.get('url')}) "
                    f"{item.get('pull_request') or item.get('commit_sha')} "
                    f"· CI {item.get('ci_status')} · Release {item.get('release_version') or '-'}"
                )
            comparison = collaboration.get("delivery_comparison") or {}
            if comparison.get("match_rate") is not None:
                lines.append(f"- **预测/实际文件匹配率**: {round(comparison['match_rate'] * 100)}%")
            lines.append("")
        return "\n".join(lines)

    @staticmethod
    def render_sprint_markdown(report: dict) -> str:
        sprint = report["sprint"]
        summary = report.get("summary") or {}
        lines = [
            f"# Sprint 分析报告: {sprint.get('name')}",
            "",
            f"- **项目**: {report['project'].get('name')}",
            f"- **Ticket 数**: {sprint.get('total_tickets', 0)}",
            f"- **过期分析**: {report.get('stale_ticket_count', 0)}",
            "",
        ]
        if summary.get("summary"):
            lines += ["## Sprint 目标", summary["summary"], ""]
        if summary.get("risk_map"):
            lines += ["## 风险图"]
            for risk in summary["risk_map"]:
                lines.append(
                    f"- **{risk.get('ticket')}** · {risk.get('level')}: "
                    f"{risk.get('description')}"
                )
            lines.append("")
        if summary.get("suggested_execution_order"):
            lines += [
                "## 建议执行顺序",
                *[
                    f"{index}. {key}"
                    for index, key in enumerate(summary["suggested_execution_order"], 1)
                ],
                "",
            ]
        lines += ["---", ""]
        for ticket_report in report.get("tickets") or []:
            lines.append(ReportingService.render_ticket_markdown(ticket_report))
            lines += ["", "---", ""]
        return "\n".join(lines)

    @staticmethod
    def latest_published_snapshot(
        workspace_id: int,
        sprint_id: int,
    ) -> Optional[dict]:
        snapshots = LifecycleService.list_report_snapshots(
            workspace_id,
            sprint_id=sprint_id,
        )
        return next(
            (snapshot for snapshot in snapshots if snapshot.get("status") == "published"),
            None,
        )
