"""Sprint import & analysis routes."""
from fastapi import APIRouter

router = APIRouter()


@router.post("/import")
async def import_sprint():
    """Import a Sprint from Jira."""
    return {"message": "Not implemented yet"}


@router.get("/{sprint_id}")
async def get_sprint(sprint_id: int):
    """Get sprint analysis results."""
    return {"sprint_id": sprint_id, "status": "pending"}
