"""Inspect Jira response structure for a single ticket."""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv
load_dotenv()

from scopepilot.jira_client import JiraClient, JiraConfig
from scopepilot.jira_client import JiraClient, JiraConfig
from dotenv import load_dotenv
load_dotenv()

config = JiraConfig.from_env()
client = JiraClient(config)

# Get first issue detail
issues = client.get_sprint_issues(3060)
if issues:
    issue = issues[0]
    fields = issue.get("fields", {})
    rendered = issue.get("renderedFields", {})
    
    print(f"=== Issue {issue['key']} ===")
    
    # Available field keys
    print(f"\nFields keys ({len(fields)}):")
    for k in sorted(fields.keys()):
        v = fields[k]
        t = type(v).__name__
        if isinstance(v, (str, int, float, bool)):
            print(f"  {k}: {t} = {repr(v)[:100]}")
        elif isinstance(v, dict):
            print(f"  {k}: {t} with keys {list(v.keys())[:5]}")
        elif isinstance(v, list):
            print(f"  {k}: {t}[{len(v)}]")
        elif v is None:
            print(f"  {k}: None")
        else:
            print(f"  {k}: {t}")
    
    # Check renderedFields
    print(f"\nRenderedFields keys ({len(rendered)}):")
    for k in sorted(rendered.keys()):
        v = rendered[k]
        print(f"  {k}: {type(v).__name__} = {str(v)[:200]}")
    
    # Check description (raw)
    raw_desc = fields.get("description")
    if isinstance(raw_desc, dict):
        print(f"\nRaw description (ADF) - content items: {len(raw_desc.get('content', []))}")
    elif raw_desc:
        print(f"\nRaw description: {str(raw_desc)[:200]}")
    else:
        print(f"\nNo description field")
    
    # Check comments
    comment_field = fields.get("comment")
    if comment_field:
        print(f"\nComments: {json.dumps(comment_field, ensure_ascii=False)[:500]}")
    else:
        print(f"\nNo 'comment' in fields - need to add to field list")
    
    # Extract ticket data and check AC
    td = client.extract_ticket_data(issue)
    print(f"\nExtracted ticket data:")
    print(f"  description length: {len(td.get('description', ''))}")
    print(f"  acceptance_criteria: {td.get('acceptance_criteria', [])}")
    print(f"  figma_links: {td.get('figma_links', [])}")

client.close()
