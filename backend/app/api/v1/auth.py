"""Authentication & workspace management routes."""
from datetime import datetime, timezone
from collections import defaultdict
from time import time
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel

from ...services import (
    hash_password, verify_password, create_access_token,
    decode_access_token, get_current_user, get_current_user_from_cookie,
    blacklist_token, set_token_cookie, clear_token_cookie, COOKIE_NAME,
)
from ...services import security
from ...database import SqliteStore

router = APIRouter()

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
    email: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


class RegisterRequest(BaseModel):
    email: str
    name: str
    password: str
    workspace_name: str = "My Workspace"


class RegisterResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict
    workspace: dict


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
    for u in _users.values():
        email = u.get("email", "")
        if email:
            _users_by_email[email] = u


async def _get_or_create_default_workspace() -> dict:
    if not _workspaces:
        ws_id = WorkspaceStore._persist_next_id()
        ws = {"id": ws_id, "name": "Default Workspace",
              "created_at": datetime.now(timezone.utc).isoformat()}
        await WorkspaceStore._persist_add(ws)
    return list(_workspaces.values())[0]


@router.post("/register")
async def register(req: RegisterRequest, response: Response):
    """Register a new user with workspace."""
    if req.email in _users_by_email:
        raise HTTPException(status_code=400, detail="Email already registered")

    ws = await _get_or_create_default_workspace()
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
    _users_by_email[req.email] = user

    token = create_access_token({"sub": req.email, "user_id": user_id, "workspace_id": ws["id"]})
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

    user = _users_by_email.get(req.email)
    if not user or not verify_password(req.password, user["hashed_password"]):
        _record_login_attempt(client_key)
        raise HTTPException(status_code=401, detail="Invalid email or password")

    _LOGIN_ATTEMPTS.pop(client_key, None)
    token = create_access_token({
        "sub": user["email"],
        "user_id": user["id"],
        "workspace_id": user["workspace_id"],
    })
    set_token_cookie(response, token)  # Set HttpOnly cookie via response parameter
    return LoginResponse(
        access_token=token,
        user={"id": user["id"], "email": user["email"], "name": user["name"], "role": user["role"]},
    )


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
    user = _users_by_email.get(email)
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
    ws = _workspaces.get(ws_id)
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return ws
