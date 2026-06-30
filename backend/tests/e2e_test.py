"""ScopePilot end-to-end test flow."""
import httpx, json, sys, time

BASE = "http://localhost:8000/api/v1"
errors = []
passes = 0

def check(ok: bool, msg: str, detail: str = ""):
    global passes
    tag = "✅" if ok else "❌"
    print(f"  {tag} {msg}")
    if ok: passes += 1
    else: errors.append((msg, detail[:150] if detail else ""))

def step(n: int, name: str):
    print(f"\n[{n}] {name}")

# Wait for server
for _ in range(5):
    try:
        r = httpx.get("http://localhost:8000/health", timeout=3)
        if r.status_code == 200: break
    except: time.sleep(1)

# ── 1. Auth ──
step(1, "Auth - Register/Login")

# Try register, fallback to login if user exists
r = httpx.post(f"{BASE}/auth/register", json={"email":"demo@test.com","name":"Demo","password":"demo123"})
if r.status_code == 400:
    r = httpx.post(f"{BASE}/auth/login", json={"email":"demo@test.com","password":"demo123"})
    check(r.status_code == 200, "Login (user existed)")
else:
    check(r.status_code == 200, "Register new user", r.text[:80])

token = r.json()["access_token"]
h = {"Authorization": f"Bearer {token}"}

r = httpx.post(f"{BASE}/auth/register", json={"email":"demo@test.com","name":"Dup","password":"demo123"})
check(r.status_code == 400, "Duplicate blocked")

r = httpx.get(f"{BASE}/auth/me", headers=h)
check(r.status_code == 200 and r.json().get("email")=="demo@test.com", "GET /me")

r = httpx.get(f"{BASE}/auth/me", headers={"Authorization": "Bearer badtoken"})
check(r.status_code == 401, "Bad token→401")

# ── 2. Projects ──
step(2, "Projects CRUD")

r = httpx.get(f"{BASE}/projects/", headers=h)
check(r.status_code == 200, "List projects")

r = httpx.post(f"{BASE}/projects/", json={
    "name":"Demo Project","jira_url":"https://j.atlassian.net",
    "jira_email":"e@e.com","jira_api_token":"t","jira_project_key":"D"}, headers=h)
check(r.status_code in (200,201), "Create project", r.text[:80])
pid = r.json().get("id", 1)

r = httpx.get(f"{BASE}/projects/{pid}", headers=h)
check(r.status_code == 200, "Get project")

r = httpx.put(f"{BASE}/projects/{pid}", json={"name":"Updated"}, headers=h)
check(r.status_code == 200 and r.json()["name"]=="Updated", "Update project")

r = httpx.delete(f"{BASE}/projects/{pid}", headers=h)
check(r.status_code == 204, "Delete project")

r = httpx.get(f"{BASE}/projects/{pid}", headers=h)
check(r.status_code == 404, "Deleted→404")

# ── 3. API Test Plans ──
step(3, "API Test Plans")

spec = '''{"openapi":"3.0.0","info":{"title":"E2E API","version":"1.0"},
"paths":{"/ping":{"get":{"summary":"Ping","responses":{"200":{"description":"OK"}}}}}}'''

r = httpx.post(f"{BASE}/api-tests/specs/from-content", json={"content":spec,"name":"E2E Spec"}, headers=h)
check(r.status_code in (200,201), "Import spec", r.text[:80])
spec_id = r.json().get("id")

r = httpx.get(f"{BASE}/api-tests/specs", headers=h)
check(r.status_code == 200, "List specs")

r = httpx.post(f"{BASE}/api-tests/specs/{spec_id}/generate", json={"focus_tags":[]}, headers=h)
check(r.status_code in (200,201), "Generate test plan", r.text[:80])
plan_id = r.json().get("id")

r = httpx.get(f"{BASE}/api-tests/plans/{plan_id}", headers=h)
check(r.status_code == 200, "Get plan details")

r = httpx.get(f"{BASE}/api-tests/plans/{plan_id}/export/markdown", headers=h)
check(r.status_code == 200, "Export Markdown")

r = httpx.get(f"{BASE}/api-tests/plans/{plan_id}/export/postman", headers=h)
check(r.status_code == 200, "Export Postman")

# ── 4. Codebase ──
step(4, "Codebase")

r = httpx.post(f"{BASE}/code-sources/", json={"name":"E2E Repo","repo_url":"https://github.com/user/repo"}, headers=h)
check(r.status_code in (200,201), "Create source", r.text[:80])
sid = r.json().get("id")

r = httpx.get(f"{BASE}/code-sources/", headers=h)
check(r.status_code == 200, "List sources")

r = httpx.get(f"{BASE}/code-sources/{sid}", headers=h)
check(r.status_code == 200, "Get source")

r = httpx.delete(f"{BASE}/code-sources/{sid}", headers=h)
check(r.status_code == 204, "Delete source")

# ── 5. Figma ──
step(5, "Figma")

r = httpx.post(f"{BASE}/figma/analyze", json={"figma_url":"https://google.com","figma_token":"t"}, headers=h)
check(r.status_code == 400, "Invalid Figma URL→400")

# ── 6. Team ──
step(6, "Team & Billing")

r = httpx.get(f"{BASE}/team/tiers")
check(r.status_code == 200 and len(r.json())==3, "List tiers (Free/Pro/Enterprise)")

r = httpx.get(f"{BASE}/team/billing", headers=h)
check(r.status_code == 200, "Billing info")

r = httpx.get(f"{BASE}/team/usage", headers=h)
check(r.status_code == 200, "Usage info")

r = httpx.get(f"{BASE}/team/members", headers=h)
check(r.status_code == 200, "Members list")

r = httpx.post(f"{BASE}/team/members", json={"email":"alice@test.com","name":"Alice"}, headers=h)
check(r.status_code in (200,201), "Add member", r.text[:80])

r = httpx.post(f"{BASE}/team/billing/upgrade", json={"tier":"pro"}, headers=h)
check(r.status_code == 200, "Upgrade to Pro")

r = httpx.post(f"{BASE}/team/share", json={"sprint_id":1,"title":"E2E Report"}, headers=h)
check(r.status_code in (200,201), "Share report", r.text[:80])
share_id = r.json().get("id")

r = httpx.delete(f"{BASE}/team/shared/{share_id}", headers=h)
check(r.status_code == 204, "Revoke share")

# ── 7. Frontend ──
step(7, "Frontend Static Files")

r = httpx.get("http://localhost:8000/")
check(r.status_code == 200 and "html" in r.text.lower(), "Frontend index.html")

# ── 8. OpenAPI docs ──
step(8, "API Docs")

r = httpx.get("http://localhost:8000/openapi.json")
check(r.status_code == 200 and "openapi" in r.text, "OpenAPI schema")

r = httpx.get("http://localhost:8000/docs")
check(r.status_code == 200 and "html" in r.text.lower(), "Swagger UI")

# ── Summary ──
print(f"\n{'='*50}")
print(f"RESULTS: {passes} passed, {len(errors)} failed out of {passes+len(errors)} tests")
if errors:
    print(f"\nFAILURES:")
    for msg, detail in errors:
        print(f"  ❌ {msg}")
        if detail: print(f"     {detail}")
else:
    print("🏆 ALL TESTS PASSED!")
