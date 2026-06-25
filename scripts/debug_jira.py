"""Debug Jira connection - list boards and find sprints."""
import httpx, os, sys
from dotenv import load_dotenv

load_dotenv()

url = os.getenv('JIRA_URL')
email = os.getenv('JIRA_EMAIL')
token = os.getenv('JIRA_API_TOKEN')

print(f"URL: {url}")
print(f"Email: {email}")

c = httpx.Client(base_url=f'{url}/rest/agile/1.0', auth=(email, token), timeout=30)

# List boards
r = c.get('board', params={'maxResults': 50})
print(f'\n=== Boards (status: {r.status_code}) ===')
if r.status_code == 200:
    for b in r.json().get('values', []):
        print(f'  [{b["id"]}] {b["name"]} (type: {b.get("type","?")})')
else:
    print(r.text[:500])

# Try the LPRO project info via REST API v3
c2 = httpx.Client(auth=(email, token), timeout=30)
r2 = c2.get(f'{url}/rest/api/3/project/LPRO')
print(f'\n=== Project LPRO (status: {r2.status_code}) ===')
if r2.status_code == 200:
    p = r2.json()
    print(f'  Key: {p.get("key")}, Name: {p.get("name")}')
    print(f'  Type: {p.get("projectTypeKey")}')
else:
    print(r2.text[:500])

# Let's also try searching with a broader approach
# Try the LPRO project in the board search
print(f'\n=== Project search ===')
r3 = c.get('board', params={'maxResults': 50, 'projectKeyOrId': 'LPRO'})
print(f'  LPRO boards: status={r3.status_code}')
if r3.status_code == 200:
    for b in r3.json().get('values', []):
        print(f'  [{b["id"]}] {b["name"]}')

c.close()
c2.close()
