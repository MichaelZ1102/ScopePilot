"""Jira API client for fetching Sprint and Ticket data."""

import os
from dataclasses import dataclass
from typing import Optional

import httpx


class JiraError(Exception):
    """Base exception for Jira API errors."""


class JiraAuthError(JiraError):
    """Authentication/authorization error."""


class JiraNotFoundError(JiraError):
    """Resource not found."""


@dataclass
class JiraConfig:
    """Jira connection configuration."""
    url: str
    email: str
    api_token: str
    project_key: Optional[str] = None

    @classmethod
    def from_env(cls) -> Optional["JiraConfig"]:
        """Load Jira config from environment variables."""
        url = os.getenv("JIRA_URL")
        email = os.getenv("JIRA_EMAIL")
        api_token = os.getenv("JIRA_API_TOKEN")
        project_key = os.getenv("JIRA_PROJECT_KEY")
        if url and email and api_token:
            return cls(url=url.rstrip("/"), email=email, api_token=api_token, project_key=project_key)
        return None

    @classmethod
    def from_prompt(cls) -> "JiraConfig":
        """Prompt user for Jira configuration (fallback)."""
        import typer
        url = typer.prompt("Jira URL (e.g. https://your-domain.atlassian.net)")
        email = typer.prompt("Jira email")
        api_token = typer.prompt("Jira API token (https://id.atlassian.com/manage/api-tokens)", hide_input=True)
        project_key = typer.prompt("Default project key (optional)", default="")
        return cls(
            url=url.rstrip("/"),
            email=email,
            api_token=api_token,
            project_key=project_key or None,
        )


def _check_response(resp: httpx.Response, path: str) -> dict:
    """Check response status and return JSON or raise appropriate error."""
    if resp.status_code == 401:
        raise JiraAuthError("Jira authentication failed. Check your email and API token.")
    if resp.status_code == 403:
        raise JiraAuthError("Jira permission denied. Check your project access.")
    if resp.status_code == 404:
        raise JiraNotFoundError(f"Jira resource not found: {path}")
    if resp.status_code >= 400:
        raise JiraError(f"Jira API error ({resp.status_code}): {resp.text[:500]}")
    return resp.json()


class JiraClient:
    """Client for Jira REST API (Agile 1.0 + API v3)."""

    def __init__(self, config: JiraConfig):
        self.config = config
        self._client = httpx.Client(
            base_url=f"{config.url}/rest/agile/1.0",
            auth=(config.email, config.api_token),
            headers={"Accept": "application/json"},
            timeout=30.0,
        )
        self._client_api3 = httpx.Client(
            base_url=f"{config.url}/rest/api/3",
            auth=(config.email, config.api_token),
            headers={"Accept": "application/json"},
            timeout=30.0,
        )

    def _get(self, path: str, params: Optional[dict] = None) -> dict:
        """Make a GET request to the Jira Agile API 1.0."""
        try:
            resp = self._client.get(path, params=params)
        except httpx.RequestError as e:
            raise JiraError(f"Jira connection error: {e}") from e
        return _check_response(resp, path)

    def _get_api3(self, path: str, params: Optional[dict] = None) -> dict:
        """Make a GET request to the Jira REST API v3."""
        try:
            resp = self._client_api3.get(path, params=params)
        except httpx.RequestError as e:
            raise JiraError(f"Jira connection error: {e}") from e
        return _check_response(resp, path)

    def find_sprint(self, sprint_name: str) -> Optional[dict]:
        """Find a sprint by name across all boards."""
        boards = self._get("board", params={"maxResults": 100})
        for board in boards.get("values", []):
            # Skip kanban boards — they don't support sprints
            if board.get("type") == "kanban":
                continue
            try:
                sprints = self._get(f"board/{board['id']}/sprint", params={"maxResults": 50})
            except JiraError:
                continue  # Board may not support sprints
            for sprint in sprints.get("values", []):
                if sprint_name.lower() in sprint["name"].lower():
                    return sprint
        return None

    def get_sprint_by_id(self, sprint_id: int) -> dict:
        """Get sprint details by ID."""
        return self._get(f"sprint/{sprint_id}")

    def get_sprint_issues(self, sprint_id: int) -> list[dict]:
        """Get all issues in a sprint."""
        issues = []
        start_at = 0
        max_results = 50

        while True:
            result = self._get_api3(
                "search/jql",
                params={
                    "jql": f"Sprint = {sprint_id} ORDER BY priority DESC, created ASC",
                    "fields": "summary,description,status,assignee,priority,issuetype,labels,attachment,duedate,updated,customfield_10016",
                    "expand": "renderedFields",
                    "startAt": start_at,
                    "maxResults": max_results,
                },
            )
            issues.extend(result.get("issues", []))
            if start_at + max_results >= result.get("total", 0):
                break
            start_at += max_results

        return issues

    def get_issue_detail(self, issue_key: str) -> dict:
        """Get full detail for a single issue."""
        result = self._get_api3(
            f"issue/{issue_key}",
            params={
                "fields": "summary,description,status,assignee,priority,issuetype,labels,attachment,comment,duedate,updated,customfield_10016",
                "expand": "renderedFields",
            },
        )
        return result

    @staticmethod
    def _adf_to_text(adf: dict) -> str:
        """Convert Atlassian Document Format to plain text."""
        if isinstance(adf, str):
            return adf
        if not isinstance(adf, dict):
            return str(adf or "")

        texts = []

        def _walk(node):
            node_type = node.get("type", "")
            content = node.get("content", [])

            if node_type == "text":
                texts.append(node.get("text", ""))
            elif node_type == "hardBreak":
                texts.append("\n")
            elif node_type in ("paragraph", "heading", "listItem", "panel", "blockquote"):
                for child in content:
                    _walk(child)
                texts.append("\n")
            elif node_type in ("orderedList", "bulletList"):
                for child in content:
                    _walk(child)
            elif node_type == "codeBlock":
                for child in content:
                    _walk(child)
                texts.append("\n")
            elif node_type == "doc":
                for child in content:
                    _walk(child)

        _walk(adf)
        return "".join(texts).strip()

    def extract_ticket_data(self, issue: dict) -> dict:
        """Extract structured ticket data from Jira issue response."""
        fields = issue.get("fields", {})
        key = issue.get("key", "")

        # Extract description (rendered HTML if available, else ADF to text)
        rendered = issue.get("renderedFields", {})
        raw_desc = fields.get("description")
        rendered_desc = rendered.get("description")

        if rendered_desc and isinstance(rendered_desc, str):
            # Convert HTML to plain text for analysis
            import re
            desc_text = re.sub(r"<[^>]+>", "", rendered_desc)
            desc_text = desc_text.replace("&nbsp;", " ").replace("&amp;", "&")
        elif isinstance(raw_desc, dict):
            desc_text = self._adf_to_text(raw_desc)
        else:
            desc_text = str(raw_desc or "")

        # Acceptance criteria extraction
        acceptance_criteria = self._extract_ac(desc_text)

        # Figma links
        figma_links = self._extract_figma_links(desc_text)

        return {
            "key": key,
            "summary": fields.get("summary", ""),
            "description": desc_text,
            "acceptance_criteria": acceptance_criteria,
            "figma_links": figma_links,
            "status": fields.get("status", {}).get("name", ""),
            "assignee": fields.get("assignee", {}).get("displayName", "Unassigned"),
            "priority": fields.get("priority", {}).get("name", "Medium"),
            "issue_type": fields.get("issuetype", {}).get("name", ""),
            "labels": fields.get("labels", []),
            "story_points": fields.get("customfield_10016"),
        }

    @staticmethod
    def _extract_ac(description_text: str) -> list[str]:
        """Extract Acceptance Criteria from description text."""
        import re
        if not description_text:
            return []

        ac_list = []
        # Try to find AC section in various formats
        patterns = [
            r"(?:Acceptance Criteria|AC|验收标准)[：:]\s*\n?((?:(?!\n[A-Z]).*\n?)*)",
            r"(?:Given|When|Then)[：:]?\s*(.*?)(?=\n[A-Z]|$)",
        ]

        for pattern in patterns:
            matches = re.findall(pattern, description_text, re.DOTALL | re.IGNORECASE)
            if matches:
                for match in matches:
                    lines = [l.strip("- *").strip() for l in match.strip().split("\n") if l.strip()]
                    ac_list.extend(lines)
                break

        # If no structured AC found, try bullet points after AC header
        if not ac_list:
            lines = description_text.split("\n")
            in_ac = False
            for line in lines:
                if re.match(r"(Acceptance Criteria|AC|验收标准)[：:]", line, re.IGNORECASE):
                    in_ac = True
                    continue
                if in_ac:
                    if line.strip().startswith("-") or line.strip().startswith("*"):
                        ac_list.append(line.strip("- *").strip())
                    elif line.strip() and not line.startswith("#") and not in_ac:
                        break

        return ac_list

    @staticmethod
    def _extract_figma_links(text: str) -> list[str]:
        """Extract Figma URLs from text."""
        import re
        if not text:
            return []
        figma_pattern = r"https://(?:www\.)?figma\.com/[^\s\)\"'<>]+"
        return re.findall(figma_pattern, text)

    def close(self):
        """Close the HTTP client."""
        self._client.close()
        self._client_api3.close()
