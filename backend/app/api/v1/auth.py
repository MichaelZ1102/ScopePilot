"""Authentication & workspace management routes."""
from fastapi import APIRouter

router = APIRouter()


@router.post("/login")
async def login():
    """Login with email + password or SSO."""
    return {"message": "Not implemented yet"}


@router.post("/workspaces")
async def create_workspace():
    """Create a new workspace."""
    return {"message": "Not implemented yet"}
