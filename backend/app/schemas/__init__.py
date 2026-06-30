"""Pydantic schemas for API request/response validation."""
from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


# === Auth ===
class LoginRequest(BaseModel):
    email: str = Field(pattern=EMAIL_PATTERN, max_length=254)
    password: str = Field(min_length=1, max_length=256)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# === Workspace ===
class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class WorkspaceResponse(BaseModel):
    id: int
    name: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# === User ===
class UserCreate(BaseModel):
    email: str = Field(pattern=EMAIL_PATTERN, max_length=254)
    name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=8, max_length=256)
    role: Literal["admin", "member", "viewer"] = "member"


class UserResponse(BaseModel):
    id: int
    email: str
    name: str
    role: str

    model_config = ConfigDict(from_attributes=True)


# === Project ===
class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    jira_url: str = Field(pattern=r"^https?://", max_length=500)
    jira_email: str = Field(pattern=EMAIL_PATTERN, max_length=254)
    jira_api_token: str = Field(min_length=1, max_length=4096)
    jira_project_key: str = Field(min_length=1, max_length=50)

    @field_validator("jira_url")
    @classmethod
    def _strip_jira_url(cls, value: str) -> str:
        return value.strip().rstrip("/")


class ProjectResponse(BaseModel):
    id: int
    name: str
    jira_url: str
    jira_project_key: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    jira_url: Optional[str] = Field(default=None, pattern=r"^https?://", max_length=500)
    jira_email: Optional[str] = Field(default=None, pattern=EMAIL_PATTERN, max_length=254)
    jira_api_token: Optional[str] = Field(default=None, min_length=1, max_length=4096)
    jira_project_key: Optional[str] = Field(default=None, min_length=1, max_length=50)

    @field_validator("jira_url")
    @classmethod
    def _strip_optional_jira_url(cls, value: Optional[str]) -> Optional[str]:
        return value.strip().rstrip("/") if value else value


# === Sprint ===
class SprintImportRequest(BaseModel):
    project_id: int = Field(gt=0)
    sprint_name: str = Field(min_length=1, max_length=200)


class SprintResponse(BaseModel):
    id: int
    name: str
    state: str
    total_tickets: int
    analysis_status: str
    imported_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class SprintDetailResponse(SprintResponse):
    """Sprint including project_id, dates, ticket list, and optional AI analysis data."""
    project_id: int
    jira_sprint_id: int
    started_at: Optional[str] = None
    ended_at: Optional[str] = None
    tickets: list["TicketDetailResponse"] = []
    analysis_data: Optional[dict] = Field(
        default=None,
        description="AI 分析结果，包含 sprint_analysis 和 ticket_analyses",
    )


# === Ticket ===
class TicketResponse(BaseModel):
    id: int
    key: str
    summary: str
    issue_type: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    assignee: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class TicketDetailResponse(TicketResponse):
    """Detailed ticket with description, acceptance criteria, etc."""
    sprint_id: int
    description: Optional[str] = None
    labels: Optional[list[str]] = None
    story_points: Optional[int] = None
    acceptance_criteria: Optional[list[str]] = None
    comments: Optional[list[dict]] = None
    figma_links: Optional[list[str]] = None
    created_at: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# === Code Source ===
class CodeSourceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    provider: Literal["github", "gitlab", "bitbucket", "local"] = "github"
    repo_url: str = Field(min_length=1, max_length=1000)
    default_branch: str = Field(default="main", min_length=1, max_length=120)
    access_token: str = Field(default="", max_length=4096)


class CodeSourceResponse(BaseModel):
    id: int
    name: str
    provider: str
    repo_url: str
    default_branch: str
    last_scanned_at: Optional[datetime] = None
    scan_status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CodeSourceDetailResponse(CodeSourceResponse):
    project_id: Optional[int] = None
    webhook_secret: Optional[str] = None
    updated_at: Optional[datetime] = None


# === Repo Snapshot ===
class RepoSnapshotResponse(BaseModel):
    id: int
    code_source_id: int
    branch: str
    commit_sha: Optional[str] = None
    file_tree: Optional[dict] = None
    language_breakdown: Optional[dict] = None
    total_files: int
    total_lines: int
    scanned_at: datetime

    model_config = ConfigDict(from_attributes=True)


# === Code Impact ===
class CodeImpactResponse(BaseModel):
    id: int
    code_source_id: int
    ticket_id: int
    sprint_id: int
    affected_files: Optional[list[dict]] = None
    summary: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
