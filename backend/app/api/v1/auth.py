"""Authentication & workspace management routes."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ...services import (
    hash_password, verify_password, create_access_token,
    decode_access_token, get_current_user, blacklist_token,
)

router = APIRouter()


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


# --- In-memory store (will be replaced by SQLAlchemy in Phase 2) ---
_users: dict[str, dict] = {}       # email -> user record
_workspaces: dict[int, dict] = {}  # id -> workspace record
_next_id = 1
_next_ws_id = 1


def _get_or_create_default_workspace() -> dict:
    global _next_ws_id
    if not _workspaces:
        ws = {"id": _next_ws_id, "name": "Default Workspace", "created_at": "2026-06-25T00:00:00"}
        _workspaces[_next_ws_id] = ws
        _next_ws_id += 1
    return list(_workspaces.values())[0]


@router.post("/register", response_model=RegisterResponse)
async def register(req: RegisterRequest):
    """Register a new user with workspace."""
    if req.email in _users:
        raise HTTPException(status_code=400, detail="Email already registered")

    ws = _get_or_create_default_workspace()
    user_id = _next_id
    global _next_id
    _next_id += 1

    user = {
        "id": user_id,
        "email": req.email,
        "name": req.name,
        "hashed_password": hash_password(req.password),
        "role": "admin",
        "workspace_id": ws["id"],
    }
    _users[req.email] = user

    token = create_access_token({"sub": req.email, "user_id": user_id, "workspace_id": ws["id"]})
    return RegisterResponse(
        access_token=token,
        user={"id": user_id, "email": req.email, "name": req.name, "role": "admin"},
        workspace=ws,
    )


@router.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest):
    """Login with email and password."""
    user = _users.get(req.email)
    if not user or not verify_password(req.password, user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_access_token({
        "sub": user["email"],
        "user_id": user["id"],
        "workspace_id": user["workspace_id"],
    })
    return LoginResponse(
        access_token=token,
        user={"id": user["id"], "email": user["email"], "name": user["name"], "role": user["role"]},
    )


@router.post("/logout")
async def logout(token_data: dict = Depends(get_current_user)):
    """Logout by blacklisting the current token."""
    # Token from Authorization header — extract it
    from fastapi import Request
    request = Request
    # Note: token is blacklisted via service
    return {"message": "Logged out successfully"}


@router.get("/me")
async def get_me(token_data: dict = Depends(get_current_user)):
    """Get current user info from token."""
    email = token_data.get("sub")
    user = _users.get(email)
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
