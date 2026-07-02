"""In-app notifications and outbound webhook delivery."""
import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone
from typing import Optional

import httpx

from ..database import SqliteStore
from ..encryption import decrypt, encrypt

logger = logging.getLogger(__name__)


class NotificationStore(SqliteStore):
    _entity_name = "notifications"
    _store: dict[int, dict] = {}
    _next_id: int = 1


class WebhookSubscriptionStore(SqliteStore):
    _entity_name = "webhook_subscriptions"
    _store: dict[int, dict] = {}
    _next_id: int = 1


class NotificationService:
    @staticmethod
    async def emit(
        *,
        workspace_id: int,
        event_type: str,
        title: str,
        message: str,
        resource_type: str,
        resource_id: Optional[int] = None,
        user_id: Optional[int] = None,
        details: Optional[dict] = None,
    ) -> dict:
        now = datetime.now(timezone.utc).isoformat()
        record = {
            "id": NotificationStore._persist_next_id(),
            "workspace_id": workspace_id,
            "user_id": user_id,
            "event_type": event_type,
            "title": title,
            "message": message,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "details": details or {},
            "is_read": False,
            "created_at": now,
        }
        await NotificationStore._persist_add(record)
        await NotificationService._dispatch_webhooks(record)
        return record

    @staticmethod
    def list_notifications(workspace_id: int, user_id: Optional[int] = None) -> list[dict]:
        return sorted(
            [
                item for item in NotificationStore.list_by("workspace_id", workspace_id)
                if item.get("user_id") in {None, user_id}
            ],
            key=lambda item: item.get("created_at", ""),
            reverse=True,
        )

    @staticmethod
    async def mark_read(notification_id: int, workspace_id: int) -> Optional[dict]:
        item = NotificationStore.get(notification_id)
        if not item or item.get("workspace_id") != workspace_id:
            return None
        return await NotificationStore.update_fields(notification_id, {"is_read": True})

    @staticmethod
    async def create_webhook(
        *,
        workspace_id: int,
        name: str,
        provider: str,
        url: str,
        events: list[str],
        secret: str,
    ) -> dict:
        now = datetime.now(timezone.utc).isoformat()
        record = {
            "id": WebhookSubscriptionStore._persist_next_id(),
            "workspace_id": workspace_id,
            "name": name,
            "provider": provider,
            "url": url,
            "events": events,
            "secret": encrypt(secret) if secret else "",
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        }
        await WebhookSubscriptionStore._persist_add(record)
        return NotificationService._public_webhook(record)

    @staticmethod
    def list_webhooks(workspace_id: int) -> list[dict]:
        return [
            NotificationService._public_webhook(item)
            for item in WebhookSubscriptionStore.list_by("workspace_id", workspace_id)
        ]

    @staticmethod
    async def delete_webhook(webhook_id: int, workspace_id: int) -> bool:
        item = WebhookSubscriptionStore.get(webhook_id)
        if not item or item.get("workspace_id") != workspace_id:
            return False
        return await WebhookSubscriptionStore._persist_delete(webhook_id)

    @staticmethod
    def _public_webhook(item: dict) -> dict:
        return {key: value for key, value in item.items() if key != "secret"}

    @staticmethod
    async def _dispatch_webhooks(notification: dict) -> None:
        subscriptions = [
            item for item in WebhookSubscriptionStore.list_by(
                "workspace_id",
                notification["workspace_id"],
            )
            if item.get("is_active", True)
            and (
                not item.get("events")
                or notification["event_type"] in item.get("events", [])
                or "*" in item.get("events", [])
            )
        ]
        if not subscriptions:
            return
        event_payload = {
            "event": notification["event_type"],
            "title": notification["title"],
            "message": notification["message"],
            "resource": {
                "type": notification["resource_type"],
                "id": notification.get("resource_id"),
            },
            "details": notification.get("details", {}),
            "created_at": notification["created_at"],
        }
        async with httpx.AsyncClient(timeout=8.0) as client:
            for subscription in subscriptions:
                provider = subscription.get("provider", "generic").lower()
                if provider == "slack":
                    payload = {
                        "text": (
                            f"*{notification['title']}*\n"
                            f"{notification['message']}"
                        ),
                    }
                elif provider == "teams":
                    payload = {
                        "@type": "MessageCard",
                        "@context": "https://schema.org/extensions",
                        "summary": notification["title"],
                        "themeColor": "2563EB",
                        "title": notification["title"],
                        "text": notification["message"],
                    }
                else:
                    payload = event_payload
                body = json.dumps(payload, ensure_ascii=False).encode()
                headers = {"Content-Type": "application/json", "User-Agent": "ScopePilot/0.6"}
                if subscription.get("secret"):
                    try:
                        secret = decrypt(subscription["secret"])
                        headers["X-ScopePilot-Signature"] = hmac.new(
                            secret.encode(),
                            body,
                            hashlib.sha256,
                        ).hexdigest()
                    except Exception:
                        logger.warning("Unable to sign webhook %s", subscription["id"])
                try:
                    response = await client.post(subscription["url"], content=body, headers=headers)
                    if response.status_code >= 400:
                        logger.warning(
                            "Webhook %s returned %s",
                            subscription["id"],
                            response.status_code,
                        )
                except Exception as exc:
                    logger.warning("Webhook %s failed: %s", subscription["id"], exc)
