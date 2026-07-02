"""In-app notification and outbound webhook routes."""
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel, Field

from ...services import get_current_user, require_roles
from ...services.notifications import NotificationService

router = APIRouter()


class WebhookCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    provider: Literal["generic", "slack", "teams"] = "generic"
    url: str = Field(pattern=r"^https?://", max_length=1000)
    events: list[str] = Field(default_factory=lambda: ["*"], max_length=100)
    secret: str = Field(default="", max_length=500)


@router.get("/")
async def list_notifications(token_data: dict = Depends(get_current_user)):
    return NotificationService.list_notifications(
        token_data.get("workspace_id"),
        token_data.get("user_id"),
    )


@router.patch("/{notification_id}/read")
async def mark_notification_read(
    notification_id: Annotated[int, Path(gt=0)],
    token_data: dict = Depends(get_current_user),
):
    item = await NotificationService.mark_read(
        notification_id,
        token_data.get("workspace_id"),
    )
    if not item:
        raise HTTPException(status_code=404, detail="Notification not found")
    return item


@router.get("/webhooks")
async def list_webhooks(token_data: dict = Depends(require_roles("admin"))):
    return NotificationService.list_webhooks(token_data.get("workspace_id"))


@router.post("/webhooks", status_code=201)
async def create_webhook(
    data: WebhookCreate,
    token_data: dict = Depends(require_roles("admin")),
):
    return await NotificationService.create_webhook(
        workspace_id=token_data.get("workspace_id"),
        name=data.name,
        provider=data.provider,
        url=data.url,
        events=data.events,
        secret=data.secret,
    )


@router.delete("/webhooks/{webhook_id}", status_code=204)
async def delete_webhook(
    webhook_id: Annotated[int, Path(gt=0)],
    token_data: dict = Depends(require_roles("admin")),
):
    if not await NotificationService.delete_webhook(
        webhook_id,
        token_data.get("workspace_id"),
    ):
        raise HTTPException(status_code=404, detail="Webhook not found")
