"""Read-only local data consistency checks for ScopePilot.

This script inspects the SQLite database under ~/.scopepilot/scopepilot.db.
It does not modify data.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DB_PATH = Path.home() / ".scopepilot" / "scopepilot.db"
TABLES = [
    "auth_users",
    "auth_workspaces",
    "projects",
    "sprints",
    "tickets",
    "team_members",
    "usage_records",
    "billing",
    "shared_reports",
    "code_sources",
    "repo_snapshots",
    "code_impacts",
    "api_specs",
    "test_plans",
]


def _read_env_value(path: Path, key: str) -> str:
    if not path.exists():
        return ""
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        if name.strip() == key:
            return value.strip().strip('"').strip("'")
    return ""


def _secret_key() -> str:
    return (
        os.environ.get("SECRET_KEY", "")
        or _read_env_value(ROOT / "backend" / ".env", "SECRET_KEY")
        or _read_env_value(ROOT / ".env", "SECRET_KEY")
    )


def _load_table(conn: sqlite3.Connection, table: str) -> list[dict[str, Any]]:
    try:
        rows = conn.execute(f'SELECT id, data FROM "{table}"').fetchall()
    except sqlite3.OperationalError:
        return []

    records: list[dict[str, Any]] = []
    for row_id, raw_data in rows:
        try:
            record = json.loads(raw_data)
        except json.JSONDecodeError:
            record = {"_decode_error": True, "_raw": raw_data}
        record["id"] = row_id
        records.append(record)
    return records


def _load_data() -> dict[str, list[dict[str, Any]]]:
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Database not found: {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    try:
        return {table: _load_table(conn, table) for table in TABLES}
    finally:
        conn.close()


def _workspace_id(record: dict[str, Any]) -> int | None:
    value = record.get("workspace_id", record.get("id"))
    return value if isinstance(value, int) else None


def _build_fernet():
    secret = _secret_key()
    if not secret:
        return None, "SECRET_KEY not found; encrypted token verification skipped"
    try:
        from cryptography.fernet import Fernet
    except Exception as exc:  # pragma: no cover - optional local dependency
        return None, f"cryptography unavailable; encrypted token verification skipped ({exc})"

    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest())
    return Fernet(key), ""


def _check_tokens(data: dict[str, list[dict[str, Any]]], issues: list[str], notes: list[str]) -> None:
    fernet, note = _build_fernet()
    if note:
        notes.append(note)

    token_fields = [
        ("projects", "jira_api_token"),
        ("code_sources", "access_token"),
    ]
    for table, field in token_fields:
        for record in data[table]:
            token = record.get(field) or ""
            if not token:
                continue
            if not isinstance(token, str):
                issues.append(f"{table}#{record['id']} has non-string {field}")
                continue
            if not token.startswith("gAAAA"):
                issues.append(f"{table}#{record['id']} has a token that does not look encrypted")
                continue
            if fernet is None:
                continue
            try:
                fernet.decrypt(token.encode())
            except Exception:
                issues.append(f"{table}#{record['id']} has an encrypted token that cannot be decrypted")


def _check_relations(data: dict[str, list[dict[str, Any]]], issues: list[str]) -> None:
    workspace_ids = {record["id"] for record in data["auth_workspaces"]}
    project_ids = {record["id"] for record in data["projects"]}
    sprint_ids = {record["id"] for record in data["sprints"]}
    code_source_ids = {record["id"] for record in data["code_sources"]}
    api_spec_ids = {record["id"] for record in data["api_specs"]}

    for table in ["auth_users", "projects", "team_members", "usage_records", "billing", "shared_reports"]:
        for record in data[table]:
            ws_id = _workspace_id(record)
            if ws_id is not None and workspace_ids and ws_id not in workspace_ids:
                issues.append(f"{table}#{record['id']} references missing workspace {ws_id}")

    for sprint in data["sprints"]:
        project_id = sprint.get("project_id")
        if project_id not in project_ids:
            issues.append(f"sprints#{sprint['id']} references missing project {project_id}")

    for ticket in data["tickets"]:
        sprint_id = ticket.get("sprint_id")
        if sprint_id not in sprint_ids:
            issues.append(f"tickets#{ticket['id']} references missing sprint {sprint_id}")

    for share in data["shared_reports"]:
        sprint_id = share.get("sprint_id")
        if sprint_id not in sprint_ids:
            issues.append(f"shared_reports#{share['id']} references missing sprint {sprint_id}")

    for source in data["code_sources"]:
        project_id = source.get("project_id")
        if project_id and project_id not in project_ids:
            issues.append(f"code_sources#{source['id']} references missing project {project_id}")

    for snapshot in data["repo_snapshots"]:
        source_id = snapshot.get("code_source_id")
        if source_id not in code_source_ids:
            issues.append(f"repo_snapshots#{snapshot['id']} references missing code source {source_id}")

    for impact in data["code_impacts"]:
        source_id = impact.get("code_source_id")
        if source_id not in code_source_ids:
            issues.append(f"code_impacts#{impact['id']} references missing code source {source_id}")

    for plan in data["test_plans"]:
        spec_id = plan.get("spec_id")
        if spec_id not in api_spec_ids:
            issues.append(f"test_plans#{plan['id']} references missing API spec {spec_id}")


def _check_uniqueness(data: dict[str, list[dict[str, Any]]], issues: list[str]) -> None:
    emails = [str(user.get("email", "")).strip().lower() for user in data["auth_users"]]
    duplicates = [email for email, count in Counter(emails).items() if email and count > 1]
    for email in duplicates:
        issues.append(f"auth_users has duplicate normalized email: {email}")

    members_by_workspace: dict[int, list[str]] = defaultdict(list)
    for member in data["team_members"]:
        ws_id = member.get("workspace_id")
        email = str(member.get("email", "")).strip().lower()
        if isinstance(ws_id, int) and email:
            members_by_workspace[ws_id].append(email)
    for ws_id, emails_for_ws in members_by_workspace.items():
        for email, count in Counter(emails_for_ws).items():
            if count > 1:
                issues.append(f"team_members in workspace {ws_id} has duplicate email: {email}")


def _check_usage_counts(data: dict[str, list[dict[str, Any]]], issues: list[str]) -> None:
    active_members = Counter(
        member.get("workspace_id")
        for member in data["team_members"]
        if member.get("status", "active") == "active"
    )
    projects = Counter(project.get("workspace_id") for project in data["projects"])
    sprints_by_workspace: Counter[int | None] = Counter()
    project_workspace = {project["id"]: project.get("workspace_id") for project in data["projects"]}
    for sprint in data["sprints"]:
        sprints_by_workspace[project_workspace.get(sprint.get("project_id"))] += 1

    for usage in data["usage_records"]:
        ws_id = _workspace_id(usage)
        if ws_id is None:
            continue
        expected = {
            "members_active": active_members[ws_id],
            "projects_count": projects[ws_id],
            "sprints_imported": sprints_by_workspace[ws_id],
        }
        for field, actual_expected in expected.items():
            actual = usage.get(field, 0)
            if actual != actual_expected:
                issues.append(
                    f"usage_records#{usage['id']} {field}={actual}, expected {actual_expected}"
                )


def main() -> int:
    try:
        data = _load_data()
    except FileNotFoundError as exc:
        print(exc)
        return 1

    issues: list[str] = []
    notes: list[str] = []

    _check_uniqueness(data, issues)
    _check_relations(data, issues)
    _check_usage_counts(data, issues)
    _check_tokens(data, issues, notes)

    print(f"Database: {DB_PATH}")
    print("Records:")
    for table in TABLES:
        print(f"  {table}: {len(data[table])}")

    if notes:
        print("\nNotes:")
        for note in notes:
            print(f"  - {note}")

    if issues:
        print("\nIssues:")
        for issue in issues:
            print(f"  - {issue}")
        return 2

    print("\nNo consistency issues found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
