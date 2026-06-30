"""Auth service: JWT tokens, password hashing, login/register logic."""
import json
from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import jwt, JWTError
import bcrypt as _bcrypt
from fastapi import Depends, HTTPException, status, Request
from fastapi.responses import Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from ..config import settings
from ..database import SqliteStore, _get_conn

security = HTTPBearer(auto_error=False)

# Persistent blacklist store
class BlacklistStore(SqliteStore):
    _entity_name = "token_blacklist"
    _store: dict[int, dict] = {}
    _next_id: int = 1


_blacklisted_tokens: set[str] = set()


def _load_blacklist():
    """Load blacklisted tokens from SQLite into memory set."""
    BlacklistStore._load_all_at_startup()
    _blacklisted_tokens.clear()
    for record in BlacklistStore._store.values():
        token = record.get("token")
        if token:
            _blacklisted_tokens.add(token)


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return _bcrypt.hashpw(password.encode(), _bcrypt.gensalt()).decode()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return _bcrypt.checkpw(plain_password.encode(), hashed_password.encode())


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=settings.access_token_expire_minutes))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    """Decode and validate a JWT token."""
    if token in _blacklisted_tokens:
        raise HTTPException(status_code=401, detail="Token has been revoked")
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)):
    """Dependency: extract and validate current user from Bearer token."""
    if credentials is not None:
        return decode_access_token(credentials.credentials)
    raise HTTPException(status_code=401, detail="Not authenticated")


async def get_current_user_from_cookie(request: Request):
    """Dependency: extract and validate current user from HttpOnly cookie (web frontend)."""
    token = request.cookies.get(COOKIE_NAME)
    if token:
        return decode_access_token(token)
    # Fallback: try Authorization header (for API clients)
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return decode_access_token(auth[7:])
    raise HTTPException(status_code=401, detail="Not authenticated")


# ── HttpOnly Cookie helpers ───────────────────────────────────────────────

COOKIE_NAME = "access_token"


def set_token_cookie(response: Response, token: str, max_age: int = None):
    """Set HttpOnly cookie with JWT token (login/register response)."""
    if max_age is None:
        max_age = settings.access_token_expire_minutes * 60
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=max_age,
        expires=max_age,
        httponly=True,
        samesite="lax",
        secure=False,  # Set True in production with HTTPS
        path="/",
    )


def clear_token_cookie(response: Response):
    """Clear the access_token cookie (logout)."""
    response.delete_cookie(
        key=COOKIE_NAME,
        path="/",
        httponly=True,
        samesite="lax",
    )


def get_token_from_cookie(request: Request) -> Optional[str]:
    """Extract JWT from cookie if present."""
    return request.cookies.get(COOKIE_NAME)


async def blacklist_token(token: str):
    """Add token to blacklist (for logout) and persist."""
    if token not in _blacklisted_tokens:
        _blacklisted_tokens.add(token)
        record = {"id": BlacklistStore._persist_next_id(), "token": token}
        await BlacklistStore._persist_add(record)
