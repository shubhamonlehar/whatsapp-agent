import asyncio
import json
import logging
import uuid
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app import models
from app.db import SessionLocal
from app.settings_store import get_runtime_settings
from app.time_utils import india_wall_clock_timestamp

logger = logging.getLogger(__name__)


def webhook_auth_headers(settings: dict[str, Any]) -> dict[str, str]:
    auth_token = str(settings.get("ats_webhook_auth_token") or "").strip()
    if not auth_token:
        return {}

    auth_header = str(settings.get("ats_webhook_auth_header") or "").strip() or "Authorization"
    if auth_header.lower() == "authorization" and not auth_token.lower().startswith("bearer "):
        auth_token = f"Bearer {auth_token}"
    return {auth_header: auth_token}


def wamid() -> str:
    return "wamid." + uuid.uuid4().hex


def status_payload(message: models.OutboundMessage, status: str) -> dict[str, Any]:
    status_item: dict[str, Any] = {
        "id": wamid(),
        "status": "failed" if status == "invalid_number" else status,
        "timestamp": india_wall_clock_timestamp(),
        "recipient_id": message.to_phone,
        "biz_opaque_callback_data": json.dumps(
            {
                "source": "api/partners",
                "mobileno": message.to_phone,
                "templateid": message.template_id,
                "sent_master_uuid": message.transaction_id,
            }
        ),
    }
    if status == "delivered":
        status_item["conversation"] = {"id": uuid.uuid4().hex, "origin": {"type": "utility"}}
        status_item["pricing"] = {"billable": True, "pricing_model": "CBP", "category": "utility"}
    if status in {"failed", "invalid_number"}:
        status_item["errors"] = [
            {
                "code": 131026,
                "title": "Message undeliverable",
                "message": "Message undeliverable",
                "error_data": {"details": "Message Undeliverable."},
            }
        ]
    return {
        "value": {
            "messaging_product": "whatsapp",
            "metadata": {"display_phone_number": message.sender, "phone_number_id": "349984148202356"},
            "statuses": [status_item],
        },
        "field": "messages",
        "template_id": message.template_id,
        "webhook_type": "whatsapp_template",
        "transaction_id": message.transaction_id,
    }


def customer_response_payload(
    *,
    sender: str,
    from_phone: str,
    message_type: str,
    text: str = "",
    file_url: str = "",
    file_name: str = "",
    mime_type: str = "",
) -> dict[str, Any]:
    msg: dict[str, Any] = {"from": from_phone, "id": wamid(), "timestamp": india_wall_clock_timestamp(), "type": message_type}
    if message_type == "text":
        msg["text"] = {"body": text}
    elif message_type == "button_reply":
        msg["type"] = "button"
        msg["button"] = {"payload": text, "text": text}
    elif message_type == "interactive_reply":
        msg["type"] = "interactive"
        msg["interactive"] = {
            "type": "button_reply",
            "button_reply": {"id": text.lower().replace(" ", "_"), "title": text},
        }
    elif message_type in {"image", "document"}:
        msg[message_type] = {
            "mime_type": mime_type or ("application/pdf" if message_type == "document" else "image/jpeg"),
            "sha256": uuid.uuid4().hex,
            "id": uuid.uuid4().hex,
        }
        if message_type == "document":
            msg["document"]["filename"] = file_name or "candidate_cv.pdf"
    payload: dict[str, Any] = {
        "value": {
            "messaging_product": "whatsapp",
            "metadata": {"display_phone_number": sender, "phone_number_id": "349984148202356"},
            "contacts": [{"profile": {"name": f"Candidate {from_phone[-4:]}"}, "wa_id": from_phone}],
            "messages": [msg],
        },
        "field": "messages",
        "webhook_type": "customer_response",
        "transaction_id": msg["id"],
    }
    if file_url:
        payload["fileurl"] = file_url
    return payload


async def deliver_event(db: Session, event: models.WebhookEvent) -> models.WebhookEvent:
    settings = get_runtime_settings(db)
    target_url = str(settings["ats_webhook_url"])
    event.target_url = target_url
    if not settings["ats_webhook_enabled"] or not target_url:
        event.response_status = None
        event.response_body = "Webhook delivery disabled or URL empty; event stored for replay."
        db.commit()
        return event

    headers = webhook_auth_headers(settings)

    retry_count = int(settings["ats_webhook_retry_count"])
    timeout = int(settings["ats_webhook_timeout_ms"]) / 1000
    interval = int(settings["ats_webhook_retry_interval_ms"]) / 1000
    payload = json.loads(event.payload_json)

    for attempt in range(retry_count + 1):
        event.retry_count = attempt
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(target_url, json=payload, headers=headers)
            event.response_status = response.status_code
            event.response_body = response.text[:4000]
            db.commit()
            if response.status_code < 500:
                return event
        except httpx.HTTPError as exc:
            event.response_status = None
            event.response_body = str(exc)
            db.commit()
            logger.warning("Webhook delivery failed: %s", exc)
        if attempt < retry_count:
            await asyncio.sleep(interval)
    return event


async def deliver_event_by_id(event_id: int) -> None:
    with SessionLocal() as db:
        event = db.get(models.WebhookEvent, event_id)
        if event is None:
            logger.warning("Webhook event %s was not found for background delivery", event_id)
            return
        await deliver_event(db, event)
