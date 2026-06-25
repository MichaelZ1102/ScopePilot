"""
验证脚本：用模拟数据验证 ScopePilot CLI 完整管线
Inspect the src directory structure
"""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from scopepilot.analyzer import AnalysisPipeline, TicketAnalysis, SprintAnalysis
from scopepilot.ai import OpenAILikeProvider
from scopepilot.report import save_reports

def mock_ai():
    """Use a mock provider that returns structured data without API calls."""
    from unittest.mock import MagicMock
    
    provider = MagicMock()
    provider.chat_json.return_value = {
        "business_goal": "实现订单导出功能，允许有权限的用户根据筛选条件导出订单数据",
        "acceptance_criteria_summary": "用户可根据状态筛选订单并导出，无权限用户不能导出",
        "backend_features": [
            "订单列表查询支持 status 筛选",
            "新增订单导出 API",
            "导出逻辑复用订单筛选条件",
            "增加订单导出权限校验"
        ],
        "api_candidates": ["GET /orders", "GET /orders/export"],
        "db_changes": ["orders 表新增 export_count 字段（可选）"],
        "permission_rules": ["需要订单导出权限: order:export"],
        "state_transitions": [],
        "validation_rules": ["导出数量上限校验", "导出频率限制"],
        "external_dependencies": ["CSV 生成库"],
        "open_questions": ["导出字段是否固定？", "最大导出数量是多少？"],
        "score": {
            "business_complexity": 2,
            "technical_complexity": 3,
            "code_impact": 3,
            "dependency_risk": 2,
            "test_cost": 3,
            "uncertainty": 2,
            "overall": 3,
            "estimated_effort": "1-2 days",
            "risk_level": "medium"
        },
        "code_impact": {
            "likely_modules": ["OrderController", "OrderService", "OrderRepository", "PermissionService"],
            "likely_files": ["src/order/order.controller.ts", "src/order/order.service.ts"],
            "database_impact": ["orders table"],
            "confidence": "medium"
        },
        "implementation_plan": [
            "确认订单导出字段和最大导出数量",
            "检查现有订单查询 API 是否已支持 status 筛选",
            "新增 GET /orders/export API",
            "复用订单查询条件构建导出数据集",
            "增加订单导出权限校验",
            "实现 CSV 文件生成逻辑",
            "补充导出失败场景处理",
            "准备 API 测试用例"
        ],
        "api_tests": [
            {
                "name": "有权限用户导出订单成功",
                "method": "GET",
                "path": "/orders/export",
                "expected_status": 200,
                "assertions": ["Content-Type 为 text/csv", "导出内容符合筛选条件"]
            },
            {
                "name": "无权限用户导出订单失败",
                "method": "GET",
                "path": "/orders/export",
                "expected_status": 403
            },
            {
                "name": "筛选结果为空时导出空 CSV",
                "method": "GET",
                "path": "/orders/export?status=cancelled",
                "expected_status": 200,
                "assertions": ["CSV 表头存在", "数据行为空"]
            }
        ]
    }
    return provider

def test_full_pipeline():
    """Test the full analysis and report pipeline with mock data."""
    print("=" * 60)
    print("ScopePilot Pipeline 验证")
    print("=" * 60)
    
    # Step 1: Create mock provider
    print("\n[1/4] 初始化 AI Provider (Mock)...")
    provider = mock_ai()
    pipeline = AnalysisPipeline(provider)
    print("  ✓ Mock provider ready")
    
    # Step 2: Simulate ticket data (like JiraClient.extract_ticket_data would return)
    print("\n[2/4] 模拟 Ticket 数据...")
    mock_tickets = [
        {
            "key": "LPRO-123",
            "summary": "用户可以导出订单列表",
            "description": "用户需要能够根据订单状态、客户、时间范围筛选订单，并导出筛选结果为 CSV 文件。",
            "acceptance_criteria": [
                "有订单导出权限的用户可以导出当前筛选结果",
                "没有权限的用户不能导出",
                "当筛选结果为空时，导出空 CSV"
            ],
            "figma_links": [],
            "status": "To Do",
            "assignee": "Developer A",
            "priority": "High",
            "issue_type": "Story",
        },
        {
            "key": "LPRO-124",
            "summary": "订单详情页增加审批操作",
            "description": "用户在订单详情页可以对订单提交审批，审批流程需要校验用户权限。",
            "acceptance_criteria": [
                "有审批权限的用户可以看到审批按钮",
                "提交审批后订单状态变为 Pending Approval",
                "无权限用户看不到审批按钮"
            ],
            "figma_links": [],
            "status": "To Do",
            "assignee": "Developer B",
            "priority": "Medium",
            "issue_type": "Story",
        },
        {
            "key": "LPRO-125",
            "summary": "优化订单查询接口性能",
            "description": "当前订单列表查询在大数据量下响应缓慢，需要优化分页和索引。",
            "acceptance_criteria": [
                "订单列表页 page size 为 20",
                "支持游标分页",
                "响应时间 < 500ms"
            ],
            "figma_links": [],
            "status": "To Do",
            "assignee": "Developer A",
            "priority": "Low",
            "issue_type": "Task",
        }
    ]
    print(f"  ✓ {len(mock_tickets)} tickets simulated")
    
    # Step 3: Run analysis
    print("\n[3/4] 运行 AI 分析管线...")
    ticket_analyses = []
    for td in mock_tickets:
        print(f"  → 分析 {td['key']}...", end=" ")
        analysis = pipeline.analyze_ticket(td)
        ticket_analyses.append(analysis)
        print(f"✓ 评分: {analysis.score.get('overall', 'N/A')}/10")
    
    sprint_analysis = pipeline.analyze_sprint("LPRO Sprint 0707", ticket_analyses)
    print(f"  → Sprint 分析完成: {len(sprint_analysis.ticket_analyses)} tickets")
    
    # Step 4: Generate reports
    print("\n[4/4] 生成报告并保存...")
    output_dir = "reports/test-verification"
    save_reports(sprint_analysis, output_dir, "zh-CN")
    
    print("\n" + "=" * 60)
    print("验证完成! ✅")
    print("报告文件:")
    print(f"  📄 {output_dir}/sprint-overview.md")
    print(f"  📄 {output_dir}/api-test-plan.md")
    print(f"  📄 {output_dir}/open-questions.md")
    print(f"  📁 {output_dir}/tickets/ (3 files)")
    print("=" * 60)

if __name__ == "__main__":
    test_full_pipeline()
