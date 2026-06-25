"""Find sprints in all boards - look for LPRO Sprint 0707."""
import httpx, os
from dotenv import load_dotenv

load_dotenv()

url = os.getenv('JIRA_URL')
email = os.getenv('JIRA_EMAIL')
token = os.getenv('JIRA_API_TOKEN')

c = httpx.Client(base_url=f'{url}/rest/agile/1.0', auth=(email, token), timeout=30)

# List all boards and their sprints
boards = [
    (368, "LP board"),
    (381, "Consumer Test"),
    (356, "Lessen360"),
    (375, "Backlog & Sprints"),
]

target = "LPRO Sprint 0707"

for bid, bname in boards:
    r = c.get(f'board/{bid}/sprint', params={'maxResults': 50})
    if r.status_code != 200:
        print(f'[{bid}] {bname}: no sprint access ({r.status_code})')
        continue
    
    sprints = r.json().get('values', [])
    print(f'[{bid}] {bname}: {len(sprints)} sprints')
    for s in sprints:
        sn = s['name']
        match = " <<< MATCH" if target.lower() in sn.lower() else ""
        print(f'  Sprint {s["id"]}: {sn} (state: {s.get("state","?")}){match}')

c.close()
