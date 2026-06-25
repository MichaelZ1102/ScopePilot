"""Quick test: analyze 3 high-priority tickets individually."""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv
load_dotenv()

from scopepilot.ai import create_provider
from scopepilot.analyzer import AnalysisPipeline

provider = create_provider()
pipeline = AnalysisPipeline(provider)

# 3 high-priority tickets
tickets = [
    {"key": "LP-2139", "summary": "[Live] Lessen Quote and Lessen HVAC Recurrent Wo missing handling for voided WO",
     "description": "When a WO is voided after a Lessen Quote or Lessen HVAC Recurrent work order is created but before completion, the system does not properly handle the voided state.", "acceptance_criteria": [], "issue_type": "Bug", "priority": "Escalated"},
    {"key": "LP-2142", "summary": "Edit Form causes unexpected error after data update",
     "description": "After updating form data, clicking edit on the form causes an unexpected error on the UI.", "acceptance_criteria": [], "issue_type": "Bug", "priority": "Escalated"},
    {"key": "LP-2147", "summary": "[LIVE] Requesting password reset for another account triggers session logout",
     "description": "When an active user clicks send reset password to a different account, it logs out active Session of current user.", "acceptance_criteria": [], "issue_type": "Bug", "priority": "Escalated"},
]

for td in tickets:
    print(f"\n{'='*50}")
    print(f"Analyzing {td['key']}...")
    result = pipeline.analyze_ticket(td)
    d = result.to_dict()
    print(f"  Business Goal: {d.get('business_goal', '')[:80]}...")
    print(f"  Backend Features: {len(d.get('backend_features', []))}")
    print(f"  Score: {d.get('score', {}).get('overall', 'N/A')}/10")
    for f in d.get('backend_features', []):
        print(f"    - {f}")
    if d.get('open_questions'):
        print(f"  Open Questions:")
        for q in d['open_questions']:
            print(f"    ❓ {q}")
    print(f"  Implementation Steps: {len(d.get('implementation_plan', []))}")

print("\n✅ Done!")
