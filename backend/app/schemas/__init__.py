"""Pydantic schemas for API request/response validation."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr


# === Auth ===
class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# === Workspace ===
class WorkspaceCreate(BaseModel):
    name: str


class WorkspaceResponse(BaseModel):
    id: int
    name: str
    created_at: datetime

    class Config:
        from_attributes = True


# === User ===
class UserCreate(BaseModel):
    email: str
    name: str
    password: str
    role: str = "member"


class UserResponse(BaseModel):
    id: int
    email: str
    name: str
    role: str

    class Config:
        from_attributes = True


# === Project ===
class ProjectCreate(BaseModel):
    name: str
    jira_url: str
    jira_email: str
    jira_api_token: str
    jira_project_key: str


class ProjectResponse(BaseModel):
    id: int
    name: str
    jira_url: str
    jira_project_key: str
    created_at: datetime

    class Config:
        from_attributes = True


# === Sprint ===
class SprintImportRequest(BaseModel):
    sprint_name: str


class SprintResponse(BaseModel):
    id: int
    name: str
    state: str
    total_tickets: int
    analysis_status: str
    imported_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# === Ticket ===
class TicketResponse(BaseModel):
    id: int
    key: str
    summary: str
    issue_type: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    assignee: Optional[str] = None

    class Config:
        from_attributes = True
