"""Authentication & workspace management routes."""
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from time import time
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel, Field, field_validator

from ...services import (
    hash_password, verify_password, create_access_token,
    decode_access_token, get_current_user, get_current_user_from_cookie,
    blacklist_token, set_token_cookie, clear_token_cookie, COOKIE_NAME,
)
from ...services import security
from ...database import SqliteStore

router = APIRouter()
EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"

# --- Lightweight in-memory login rate limiter ---
_LOGIN_ATTEMPTS: dict[str, list[float]] = defaultdict(list)
_LOGIN_WINDOW_SECONDS = 60
_LOGIN_MAX_ATTEMPTS = 8


def _is_login_rate_limited(client_key: str) -> bool:
    now = time()
    attempts = _LOGIN_ATTEMPTS[client_key]
    _LOGIN_ATTEMPTS[client_key] = [t for t in attempts if now - t < _LOGIN_WINDOW_SECONDS]
    return len(_LOGIN_ATTEMPTS[client_key]) >= _LOGIN_MAX_ATTEMPTS


def _record_login_attempt(client_key: str) -> None:
    _LOGIN_ATTEMPTS[client_key].append(time())


# --- Request/Response schemas ---
class LoginRequest(BaseModel):
    email: str = Field(pattern=EMAIL_PATTERN, max_length=254)
    password: str = Field(min_length=1, max_length=256)

    @field_validator("email")
    @classmethod
    def _normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


class RegisterRequest(BaseModel):
    email: str = Field(pattern=EMAIL_PATTERN, max_length=254)
    name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=8, max_length=256)
    workspace_name: str = Field(default="My Workspace", min_length=1, max_length=100)

    @field_validator("email")
    @classmethod
    def _normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class RegisterResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict
    workspace: dict


class AcceptInviteRequest(BaseModel):
    email: str = Field(pattern=EMAIL_PATTERN, max_length=254)
    invite_token: str = Field(min_length=1, max_length=500)
    name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=8, max_length=256)

    @field_validator("email")
    @classmethod
    def _normalize_invite_email(cls, value: str) -> str:
        return value.strip().lower()


# --- Persisted stores ---
class UserStore(SqliteStore):
    _entity_name = "auth_users"
    _store: dict[int, dict] = {}
    _next_id: int = 1


class WorkspaceStore(SqliteStore):
    _entity_name = "auth_workspaces"
    _store: dict[int, dict] = {}
    _next_id: int = 1


_users_by_email: dict[str, dict] = {}
_users: dict[int, dict] = UserStore._store
_workspaces: dict[int, dict] = WorkspaceStore._store


def _rebuild_email_index():
    _users_by_email.clear()
    for u in UserStore.list_all():
        email = u.get("email", "").strip().lower()
        if email:
            u["email"] = email
            _users_by_email[email] = u


def _find_user_by_email(email: str) -> dict | None:
    normalized = email.strip().lower()
    return UserStore.find_by("email", normalized)


async def _create_workspace(name: str) -> dict:
    ws_id = WorkspaceStore._persist_next_id()
    ws = {
        "id": ws_id,
        "name": name.strip() or "My Workspace",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await WorkspaceStore._persist_add(ws)
    return ws


@router.post("/register")
async def register(req: RegisterRequest, response: Response):
    """Register a new user with workspace."""
    if _find_user_by_email(req.email):
        raise HTTPException(status_code=400, detail="Email already registered")

    ws = await _create_workspace(req.workspace_name)
    user_id = UserStore._persist_next_id()

    user = {
        "id": user_id,
        "email": req.email,
        "name": req.name,
        "hashed_password": hash_password(req.password),
        "role": "admin",
        "workspace_id": ws["id"],
    }
    await UserStore._persist_add(user)
    from ...services.team import TeamMemberStore, UsageRecordStore
    now = datetime.now(timezone.utc).isoformat()
    await TeamMemberStore._persist_add({
        "id": TeamMemberStore._persist_next_id(),
        "workspace_id": ws["id"],
        "email": req.email,
        "name": req.name,
        "role": "admin",
        "status": "active",
        "invite_token": "",
        "invited_by": "",
        "invited_at": now,
        "joined_at": now,
    })
    await UsageRecordStore._persist_add({
        "id": ws["id"],
        "workspace_id": ws["id"],
        "period_start": datetime.now(timezone.utc).replace(
            day=1,
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        ).isoformat(),
        "period_end": (
            datetime.now(timezone.utc).replace(day=1) + timedelta(days=32)
        ).replace(day=1).isoformat(),
        "analyses_run": 0,
        "repo_scans": 0,
        "api_specs_imported": 0,
        "figma_analyses": 0,
        "members_active": 1,
        "projects_count": 0,
        "sprints_imported": 0,
    })

    token = create_access_token({
        "sub": req.email,
        "user_id": user_id,
        "workspace_id": ws["id"],
        "role": "admin",
        "name": req.name,
    })
    set_token_cookie(response, token)  # Set HttpOnly cookie via response parameter
    return RegisterResponse(
        access_token=token,
        user={"id": user_id, "email": req.email, "name": req.name, "role": "admin"},
        workspace=ws,
    )


@router.post("/login")
async def login(req: LoginRequest, request: Request, response: Response):
    """Login with email and password."""
    client_key = request.client.host if request.client else "unknown"
    if _is_login_rate_limited(client_key):
        raise HTTPException(status_code=429, detail="Too many login attempts. Please try again later.")

    user = _find_user_by_email(req.email)
    if not user or not verify_password(req.password, user["hashed_password"]):
        _record_login_attempt(client_key)
        raise HTTPException(status_code=401, detail="Invalid email or password")

    _LOGIN_ATTEMPTS.pop(client_key, None)
    token = create_access_token({
        "sub": user["email"],
        "user_id": user["id"],
        "workspace_id": user["workspace_id"],
        "role": user["role"],
        "name": user["name"],
    })
    set_token_cookie(response, token)  # Set HttpOnly cookie via response parameter
    return LoginResponse(
        access_token=token,
        user={"id": user["id"], "email": user["email"], "name": user["name"], "role": user["role"]},
    )


@router.post("/accept-invite")
async def accept_invite(
    req: AcceptInviteRequest,
    response: Response,
):
    """Accept a workspace invitation and create a login account."""
    from ...services.team import TeamMemberStore
    member = next(
        (
            item for item in TeamMemberStore.list_all()
            if item.get("email", "").lower() == req.email
            and item.get("invite_token") == req.invite_token
            and item.get("status") == "invited"
        ),
        None,
    )
    if not member:
        raise HTTPException(status_code=404, detail="Invitation not found or already used")
    if _find_user_by_email(req.email):
        raise HTTPException(status_code=400, detail="Email already registered")
    user_id = UserStore._persist_next_id()
    user = {
        "id": user_id,
        "email": req.email,
        "name": req.name,
        "hashed_password": hash_password(req.password),
        "role": member["role"],
        "workspace_id": member["workspace_id"],
    }
    await UserStore._persist_add(user)
    _users_by_email[req.email] = user
    await TeamMemberStore.update_fields(
        member["id"],
        {
            "name": req.name,
            "status": "active",
            "invite_token": "",
            "joined_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    token = create_access_token({
        "sub": req.email,
        "user_id": user_id,
        "workspace_id": member["workspace_id"],
        "role": member["role"],
        "name": req.name,
    })
    set_token_cookie(response, token)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user_id,
            "email": req.email,
            "name": req.name,
            "role": member["role"],
        },
    }


@router.post("/logout")
async def logout(request: Request, response: Response):
    """Logout: blacklist token and clear cookie."""
    # Extract token from cookie or Authorization header to blacklist it
    raw_token = request.cookies.get(COOKIE_NAME)
    if raw_token:
        await blacklist_token(raw_token)
    clear_token_cookie(response)
    return {"message": "Logged out successfully"}


@router.get("/me")
async def get_me(token_data: dict = Depends(get_current_user_from_cookie)):
    """Get current user info from token (cookie or Bearer)."""
    email = token_data.get("sub")
    user = _find_user_by_email(email or "")
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "id": user["id"],
        "email": user["email"],
        "name": user["name"],
        "role": user["role"],
        "workspace_id": user["workspace_id"],
    }


# --- Workspace routes ---
@router.get("/workspace")
async def get_workspace(token_data: dict = Depends(get_current_user)):
    """Get current workspace info."""
    ws_id = token_data.get("workspace_id")
    ws = WorkspaceStore.get(ws_id)
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return ws
