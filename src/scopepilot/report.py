"""Markdown report generation for sprint and ticket analysis."""

import os
from datetime import datetime
from typing import Optional

from .analyzer import SprintAnalysis, TicketAnalysis


def _score_to_emoji(overall: int) -> str:
    """Convert score to emoji indicator."""
    if overall <= 2:
        return "🟢"
    elif overall <= 4:
        return "🟡"
    else:
        return "🔴"


def _risk_to_badge(risk_level: str) -> str:
    """Convert risk level to badge."""
    risk_level = (risk_level or "").lower()
    if risk_level == "low":
        return "🟢 Low"
    elif risk_level == "medium":
        return "🟡 Medium"
    elif risk_level == "high":
        return "🔴 High"
    elif risk_level == "critical":
        return "🔥 Critical"
    return "⚪ Unknown"


def generate_ticket_report(ticket: TicketAnalysis, language: str = "zh-CN") -> str:
    """Generate a Markdown report for a single ticket analysis."""
    if language == "zh-CN":
        lines = [
            f"# {ticket.ticket_key}: {ticket.summary}",
            "",
            "## 📋 基本信息",
            f"- **Ticket**: {ticket.ticket_key}",
            f"- **Summary**: {ticket.summary}",
            "",
        ]

        if ticket.business_goal:
            lines += [
                "## 🎯 业务目标",
                ticket.business_goal,
                "",
            ]

        if ticket.backend_features:
            lines += [
                "## 🔧 后端功能点",
            ]
            for f in ticket.backend_features:
                lines.append(f"- {f}")
            lines.append("")

        if ticket.api_candidates:
            lines += [
                "## 🌐 API 候选",
            ]
            for api in ticket.api_candidates:
                lines.append(f"- `{api}`")
            lines.append("")

        if ticket.db_changes:
            lines += [
                "## 🗄️ 数据库变更",
            ]
            for db in ticket.db_changes:
                lines.append(f"- {db}")
            lines.append("")

        if ticket.permission_rules:
            lines += [
                "## 🔐 权限规则",
            ]
            for p in ticket.permission_rules:
                lines.append(f"- {p}")
            lines.append("")

        if ticket.state_transitions:
            lines += [
                "## 🔄 状态流转",
            ]
            for s in ticket.state_transitions:
                lines.append(f"- {s}")
            lines.append("")

        if ticket.validation_rules:
            lines += [
                "## ✅ 校验规则",
            ]
            for v in ticket.validation_rules:
                lines.append(f"- {v}")
            lines.append("")

        if ticket.external_dependencies:
            lines += [
                "## 📦 外部依赖",
            ]
            for d in ticket.external_dependencies:
                lines.append(f"- {d}")
            lines.append("")

        if ticket.score:
            score = ticket.score
            overall = score.get("overall", 0)
            effort = score.get("estimated_effort", "")
            lines += [
                "## 📊 评分",
                f"- **综合复杂度**: {overall}/10 {_score_to_emoji(overall)}",
                f"- **预估工作量**: {effort}",
            ]
            for dim in ["business_complexity", "technical_complexity", "code_impact",
                         "dependency_risk", "test_cost", "uncertainty"]:
                val = score.get(dim)
                if val is not None:
                    dim_name = {
                        "business_complexity": "业务复杂度",
                        "technical_complexity": "技术复杂度",
                        "code_impact": "代码影响范围",
                        "dependency_risk": "外部依赖风险",
                        "test_cost": "测试成本",
                        "uncertainty": "需求不确定性",
                    }.get(dim, dim)
                    lines.append(f"  - {dim_name}: {val}/10")
            lines.append("")

        if ticket.implementation_plan:
            lines += [
                "## 📝 开发执行计划",
            ]
            for i, step in enumerate(ticket.implementation_plan, 1):
                lines.append(f"{i}. {step}")
            lines.append("")

        if ticket.api_tests:
            lines += [
                "## 🧪 API 测试计划",
            ]
            for test in ticket.api_tests:
                name = test.get("name", "")
                method = test.get("method", "GET")
                path = test.get("path", "")
                expected = test.get("expected_status", 200)
                assertions = test.get("assertions", [])
                lines.append(f"### {name}")
                lines.append(f"- **Method**: `{method}`")
                lines.append(f"- **Path**: `{path}`")
                lines.append(f"- **Expected Status**: {expected}")
                if assertions:
                    lines.append("- **Assertions**:")
                    for a in assertions:
                        lines.append(f"  - {a}")
                lines.append("")
            lines.append("")

        if ticket.open_questions:
            lines += [
                "## ❓ 待确认问题",
            ]
            for q in ticket.open_questions:
                lines.append(f"- {q}")
            lines.append("")

    else:
        # English version
        lines = [
            f"# {ticket.ticket_key}: {ticket.summary}",
            "",
            "## 📋 Summary",
            f"- **Ticket**: {ticket.ticket_key}",
            f"- **Summary**: {ticket.summary}",
            "",
        ]
        if ticket.business_goal:
            lines += ["## 🎯 Business Goal", ticket.business_goal, ""]
        if ticket.backend_features:
            lines += ["## 🔧 Backend Features"] + [f"- {f}" for f in ticket.backend_features] + [""]
        if ticket.api_candidates:
            lines += ["## 🌐 API Candidates"] + [f"- `{api}`" for api in ticket.api_candidates] + [""]
        if ticket.db_changes:
            lines += ["## 🗄️ Database Changes"] + [f"- {db}" for db in ticket.db_changes] + [""]
        if ticket.permission_rules:
            lines += ["## 🔐 Permission Rules"] + [f"- {p}" for p in ticket.permission_rules] + [""]
        if ticket.implementation_plan:
            lines += ["## 📝 Implementation Plan"] + [f"{i}. {step}" for i, step in enumerate(ticket.implementation_plan, 1)] + [""]
        if ticket.api_tests:
            lines += ["## 🧪 API Test Plan"]
            for test in ticket.api_tests:
                name = test.get("name", "")
                method = test.get("method", "GET")
                path = test.get("path", "")
                lines.append(f"### {name}")
                lines.append(f"- **Method**: `{method}`")
                lines.append(f"- **Path**: `{path}`")
                lines.append(f"- **Expected Status**: {test.get('expected_status', 200)}")
                if test.get("assertions"):
                    lines.append("- **Assertions**:")
                    for a in test["assertions"]:
                        lines.append(f"  - {a}")
                lines.append("")
        if ticket.open_questions:
            lines += ["## ❓ Open Questions"] + [f"- {q}" for q in ticket.open_questions] + [""]

    return "\n".join(lines)


def generate_sprint_report(sprint: SprintAnalysis, language: str = "zh-CN") -> str:
    """Generate a Markdown report for the full sprint analysis."""
    if language == "zh-CN":
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        lines = [
            f"# Sprint 分析报告: {sprint.sprint_name}",
            f"生成时间: {now}",
            "",
            "## 📊 概览",
            f"- **Sprint**: {sprint.sprint_name}",
            f"- **Ticket 数**: {sprint.total_tickets}",
            "",
        ]

        if sprint.summary:
            lines += [
                "## 🎯 Sprint 业务目标汇总",
                sprint.summary,
                "",
            ]

        if sprint.risk_map:
            lines += [
                "## ⚠️ 风险图",
            ]
            for risk in sprint.risk_map:
                level = risk.get("level", "")
                ticket = risk.get("ticket", "")
                description = risk.get("description", "")
                badge = _risk_to_badge(level)
                lines.append(f"- **{ticket}** ({badge}): {description}")
            lines.append("")

        if sprint.suggested_execution_order:
            lines += [
                "## 📋 建议执行顺序",
            ]
            for i, ticket_key in enumerate(sprint.suggested_execution_order, 1):
                lines.append(f"{i}. {ticket_key}")
            lines.append("")

        if sprint.open_questions:
            lines += [
                "## ❓ 待确认问题",
            ]
            for q in sprint.open_questions:
                lines.append(f"- {q}")
            lines.append("")

        lines += [
            "---",
            "## 📄 Ticket 详情",
            "",
        ]

    else:
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        lines = [
            f"# Sprint Analysis Report: {sprint.sprint_name}",
            f"Generated: {now}",
            "",
            "## 📊 Overview",
            f"- **Sprint**: {sprint.sprint_name}",
            f"- **Total Tickets**: {sprint.total_tickets}",
            "",
        ]
        if sprint.summary:
            lines += ["## 🎯 Sprint Summary", sprint.summary, ""]
        if sprint.risk_map:
            lines += ["## ⚠️ Risk Map"]
            for risk in sprint.risk_map:
                level = risk.get("level", "")
                ticket = risk.get("ticket", "")
                description = risk.get("description", "")
                badge = _risk_to_badge(level)
                lines.append(f"- **{ticket}** ({badge}): {description}")
            lines.append("")
        if sprint.suggested_execution_order:
            lines += ["## 📋 Suggested Execution Order"]
            for i, ticket_key in enumerate(sprint.suggested_execution_order, 1):
                lines.append(f"{i}. {ticket_key}")
            lines.append("")
        if sprint.open_questions:
            lines += ["## ❓ Open Questions"] + [f"- {q}" for q in sprint.open_questions] + [""]
        lines += ["---", "## 📄 Ticket Details", ""]

    return "\n".join(lines)


def generate_api_test_plan(sprint: SprintAnalysis, language: str = "zh-CN") -> str:
    """Generate a combined API test plan from all tickets."""
    if language == "zh-CN":
        lines = [
            f"# API 测试计划: {sprint.sprint_name}",
            "",
        ]
    else:
        lines = [
            f"# API Test Plan: {sprint.sprint_name}",
            "",
        ]

    all_tests = []
    for ta in (sprint.ticket_analyses or []):
        if isinstance(ta, TicketAnalysis) and ta.api_tests:
            all_tests.append((ta.ticket_key, ta.summary, ta.api_tests))

    if not all_tests:
        if language == "zh-CN":
            lines.append("暂无 API 测试用例。")
        else:
            lines.append("No API test cases generated.")
        return "\n".join(lines)

    for ticket_key, summary, tests in all_tests:
        if language == "zh-CN":
            lines.append(f"## {ticket_key}: {summary}")
        else:
            lines.append(f"## {ticket_key}: {summary}")

        for test in tests:
            name = test.get("name", "")
            method = test.get("method", "GET")
            path = test.get("path", "")
            expected = test.get("expected_status", 200)
            assertions = test.get("assertions", [])
            lines.append(f"### {name}")
            lines.append(f"- **Method**: `{method}`")
            lines.append(f"- **Path**: `{path}`")
            lines.append(f"- **Expected Status**: {expected}")
            if assertions:
                if language == "zh-CN":
                    lines.append("- **断言**:")
                else:
                    lines.append("- **Assertions**:")
                for a in assertions:
                    lines.append(f"  - {a}")
            lines.append("")

    return "\n".join(lines)


def generate_open_questions(sprint: SprintAnalysis, language: str = "zh-CN") -> str:
    """Generate open questions report."""
    if language == "zh-CN":
        lines = [
            f"# 待确认问题: {sprint.sprint_name}",
            "",
        ]
    else:
        lines = [
            f"# Open Questions: {sprint.sprint_name}",
            "",
        ]

    all_questions = []
    for ta in (sprint.ticket_analyses or []):
        if isinstance(ta, TicketAnalysis) and ta.open_questions:
            all_questions.append((ta.ticket_key, ta.summary, ta.open_questions))

    if not all_questions:
        if language == "zh-CN":
            lines.append("暂无待确认问题。")
        else:
            lines.append("No open questions.")
        return "\n".join(lines)

    for ticket_key, summary, questions in all_questions:
        if language == "zh-CN":
            lines.append(f"## {ticket_key}: {summary}")
        else:
            lines.append(f"## {ticket_key}: {summary}")
        for q in questions:
            lines.append(f"- ❓ {q}")
        lines.append("")

    return "\n".join(lines)


def save_reports(sprint: SprintAnalysis, output_dir: str, language: str = "zh-CN"):
    """Save all reports to the output directory."""
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(os.path.join(output_dir, "tickets"), exist_ok=True)

    # Sprint overview
    sprint_report = generate_sprint_report(sprint, language)
    sprint_path = os.path.join(output_dir, "sprint-overview.md")
    with open(sprint_path, "w", encoding="utf-8") as f:
        f.write(sprint_report)
    print(f"  ✓ {sprint_path}")

    # API test plan
    api_plan = generate_api_test_plan(sprint, language)
    api_path = os.path.join(output_dir, "api-test-plan.md")
    with open(api_path, "w", encoding="utf-8") as f:
        f.write(api_plan)
    print(f"  ✓ {api_path}")

    # Open questions
    questions = generate_open_questions(sprint, language)
    questions_path = os.path.join(output_dir, "open-questions.md")
    with open(questions_path, "w", encoding="utf-8") as f:
        f.write(questions)
    print(f"  ✓ {questions_path}")

    # Individual ticket reports
    for ta in (sprint.ticket_analyses or []):
        if isinstance(ta, TicketAnalysis):
            ticket_report = generate_ticket_report(ta, language)
            safe_key = ta.ticket_key.replace("/", "-")
            ticket_path = os.path.join(output_dir, "tickets", f"{safe_key}.md")
            with open(ticket_path, "w", encoding="utf-8") as f:
                f.write(ticket_report)
            print(f"  ✓ {ticket_path}")

    print(f"\n✅ All reports saved to {output_dir}/")
