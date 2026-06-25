"""Check tickets that have descriptions + comments."""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv
load_dotenv()

from scopepilot.jira_client import JiraClient, JiraConfig

config = JiraConfig.from_env()
client = JiraClient(config)

issues = client.get_sprint_issues(3060)

print(f"Total tickets: {len(issues)}")

# Count tickets with descriptions
with_desc = 0
with_comments = 0
with_attachments = 0

for issue in issues:
    td = client.extract_ticket_data(issue)
    if td["description"].strip():
        with_desc += 1
        print(f"\n{'='*50}")
        print(f"{td['key']}: {td['summary'][:60]}")
        print(f"  Description: {td['description'][:300]}")
        print(f"  AC: {td['acceptance_criteria']}")
        if td.get("comments"):
            print(f"  Comments ({len(td['comments'])}):")
            for c in td["comments"][:2]:
                print(f"    [{c['author']}] {c['body'][:200]}")
    if td.get("comments"):
        with_comments += 1
    if td.get("figma_links"):
        with_attachments += 1

print(f"\n{'='*50}")
print(f"Summary: {len(issues)} tickets")
print(f"  With description: {with_desc}")
print(f"  With comments: {with_comments}")
print(f"  With figma links: {with_attachments}")

client.close()
