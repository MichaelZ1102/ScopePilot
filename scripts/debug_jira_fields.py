"""Debug: Test what Jira description field looks like."""
import httpx, os, json
from dotenv import load_dotenv

load_dotenv()

url = os.getenv('JIRA_URL')
email = os.getenv('JIRA_EMAIL')
token = os.getenv('JIRA_API_TOKEN')

c = httpx.Client(
    base_url=f'{url}/rest/api/3',
    auth=(email, token),
    headers={"Accept": "application/json"},
    timeout=30
)

# Get a single issue
r = c.get('search/jql', params={
    'jql': 'Sprint = 3060 ORDER BY priority DESC',
    'fields': 'summary,description,status,assignee,priority,issuetype',
    'expand': 'renderedFields',
    'maxResults': 1
})

data = r.json()
if data.get('issues'):
    issue = data['issues'][0]
    fields = issue['fields']
    rendered = issue.get('renderedFields', {})
    
    print(f"Issue: {issue['key']}")
    print(f"\nfields['description'] type: {type(fields.get('description'))}")
    desc = fields.get('description')
    if isinstance(desc, dict):
        print(f"A+D format keys: {list(desc.keys())}")
        print(f"A+D content: {json.dumps(desc, indent=2)[:500]}")
    else:
        print(f"description: {str(desc)[:200]}")
    
    rendered_desc = rendered.get('description')
    print(f"\nrenderedFields['description'] type: {type(rendered_desc)}")
    print(f"renderedFields['description']: {str(rendered_desc)[:200]}")
else:
    print(f"No issues found. Status: {r.status_code}")
    print(r.text[:300])

c.close()
