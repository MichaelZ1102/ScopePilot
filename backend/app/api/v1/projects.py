"""Project management routes."""
from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_projects():
    """List all projects."""
    return {"projects": []}


@router.post("/")
async def create_project():
    """Create a new project."""
    return {"message": "Not implemented yet"}


@router.get("/{project_id}")
async def get_project(project_id: int):
    """Get project details."""
    return {"project_id": project_id, "name": "Example"}
