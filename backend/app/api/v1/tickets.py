"""Ticket detail & listing routes.

All endpoints require a valid Bearer token and verify workspace access
through the containing sprint/project.
"""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path

from ...schemas import TicketDetailResponse
from ...services import get_current_user
from ...services.jira import JiraService
from ..v1.sprints import _get_project

router = APIRouter()


def _get_sprint_or_404(sprint_id: int, token_data: dict) -> dict:
    """Fetch sprint and verify the caller has access to its project."""
    sprint = JiraService.get_sprint(sprint_id)
    if sprint is None:
        raise HTTPException(status_code=404, detail="Sprint not found")
    # Re-use the project access check from sprint routes
    _get_project(sprint["project_id"], token_data)
    return sprint


# ── GET /api/v1/tickets/{sprint_id}/tickets ──────────────────────────────────


@router.get("/{sprint_id}/tickets", response_model=list[TicketDetailResponse])
async def list_tickets(
    sprint_id: Annotated[int, Path(gt=0)],
    token_data: dict = Depends(get_current_user),
):
    """List all tickets in a sprint."""
    _get_sprint_or_404(sprint_id, token_data)
    tickets = JiraService.list_tickets(sprint_id)
    return [TicketDetailResponse(**t) for t in tickets]


# ── GET /api/v1/tickets/{sprint_id}/tickets/{ticket_id} ──────────────────────


@router.get(
    "/{sprint_id}/tickets/{ticket_id}",
    response_model=TicketDetailResponse,
)
async def get_ticket(
    sprint_id: Annotated[int, Path(gt=0)],
    ticket_id: Annotated[int, Path(gt=0)],
    token_data: dict = Depends(get_current_user),
):
    """Get a single ticket detail."""
    _get_sprint_or_404(sprint_id, token_data)

    ticket = JiraService.get_ticket(ticket_id)
    if ticket is None or ticket["sprint_id"] != sprint_id:
        raise HTTPException(status_code=404, detail="Ticket not found")

    return TicketDetailResponse(**ticket)
