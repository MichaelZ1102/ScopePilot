"""Test a single AI analysis call."""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv
load_dotenv()

from scopepilot.ai import create_provider
from scopepilot.analyzer import AnalysisPipeline

provider = create_provider()
pipeline = AnalysisPipeline(provider)

ticket = {
    "key": "LP-2139",
    "summary": "[Live] Lessen Quote and Lessen HVAC Recurrent Wo missing handling for voided WO",
    "description": "Issue Description:\nWhen a WO is voided after a Lessen Quote or Lessen HVAC Recurrent work order is created but before completion, the system does not properly handle the voided state.",
    "acceptance_criteria": [],
    "figma_links": [],
    "status": "Stage Confirmed, Waiting Testing Pool",
    "assignee": "Developer",
    "priority": "Escalated",
    "issue_type": "Bug",
    "labels": [],
}

print("Calling AI...")
result = pipeline.analyze_ticket(ticket)
print(f"Result: {json.dumps(result.to_dict(), ensure_ascii=False, indent=2)[:500]}")
