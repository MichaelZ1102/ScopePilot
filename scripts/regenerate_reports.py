"""Quick fix: regenerate sprint overview using existing ticket data."""
import json, sys, os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv
load_dotenv()

from scopepilot.jira_client import JiraClient, JiraConfig
from scopepilot.analyzer import AnalysisPipeline
from scopepilot.report import save_reports

# 1. Fetch sprint data
config = JiraConfig.from_env()
client = JiraClient(config)
issues = client.get_sprint_issues(3060)
tickets_data = [client.extract_ticket_data(i) for i in issues]
client.close()

# 2. Analyze tickets (individual, with JSON mode)
pipeline = AnalysisPipeline()
ticket_analyses = []
for td in tickets_data:
    if not td.get("description","").strip() and not td.get("comments"):
        continue
    try:
        analysis = pipeline.analyze_ticket(td)
        ticket_analyses.append(analysis)
        print(f"  ✓ {td['key']}")
    except Exception as e:
        print(f"  ⚠️ {td['key']}: {e}")

# 3. Sprint-level analysis (using condensed summary)
sprint_analysis = pipeline.analyze_sprint("LPRO Sprint 0707", ticket_analyses)

# 4. Save reports
output_dir = "reports/lpro-sprint-0707"
save_reports(sprint_analysis, output_dir, "zh-CN")
print(f"\n✅ Done! Reports saved to {output_dir}/")
print(f"   Sprint summary: {sprint_analysis.summary[:100]}...")
print(f"   Risk items: {len(sprint_analysis.risk_map or [])}")
print(f"   Execution order: {len(sprint_analysis.suggested_execution_order or [])}")
