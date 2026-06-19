import json
import logging
import re
import secrets
from pathlib import Path
from typing import Any

from fastapi import UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import models
from app.config import get_settings
from app.repositories import CandidateRepository, MessageRepository, ScenarioRepository, WebhookRepository
from app.settings_store import allowed_senders, get_runtime_settings, strict_api_key, valid_api_keys
from app.template_mappings import render_template
from app.time_utils import india_isoformat
from app.trustsignal import trustsignal_error
from app.webhooks import customer_response_payload, deliver_event, deliver_event_by_id, status_payload

UPLOAD_DIR = Path("storage/uploads")
ALLOWED_EXTENSIONS = {".pdf", ".doc", ".docx", ".jpg", ".jpeg", ".png"}
MAX_UPLOAD_SIZE = 10 * 1024 * 1024
logger = logging.getLogger("mock_whatsapp.received_messages")


def _transaction_id() -> str:
    return str(17_000_000_000_000_000_000_000_000 + secrets.randbelow(8_000_000_000_000_000_000_000_000))


def normalize_phone(phone: Any) -> str:
    return re.sub(r"[^\d+]", "", str(phone or ""))


def preview_from_payload(payload: dict[str, Any]) -> str:
    if isinstance(payload.get("reply"), dict):
        return str(payload["reply"].get("message") or payload["reply"].get("filename") or "Agent reply")
    rendered_template = render_template(payload.get("template_id"), payload.get("sample"))
    if rendered_template:
        return rendered_template
    sample = payload.get("sample")
    if isinstance(sample, dict):
        if "otp" in sample:
            return f"OTP template: {sample['otp']}"
        if "caption" in sample:
            return str(sample["caption"])
        if "bodyvar" in sample:
            return " ".join(map(str, sample["bodyvar"]))
    if isinstance(payload.get("interactive"), dict):
        body = payload["interactive"].get("body") or {}
        return str(body.get("text") or payload["interactive"].get("type") or "Interactive message")
    return str(payload.get("template_id") or payload.get("message_type") or "WhatsApp template")


def validate_request(db: Session, api_key: str | None, payload: dict[str, Any], require_to: bool = True) -> None:
    if strict_api_key() and not api_key:
        raise trustsignal_error("101", "API_KEY_MISSING", "API Key is required in the request")
    if strict_api_key() and api_key not in valid_api_keys(db):
        raise trustsignal_error("102", "INVALID_API_KEY", "Invalid api key")
    sender = str(payload.get("sender") or "")
    if not sender:
        raise trustsignal_error("113", "SENDERID_MISSING", "Sender is required")
    if sender not in allowed_senders(db):
        raise trustsignal_error("114", "INVALID_SENDERID", "Invalid senderid")
    if require_to and not payload.get("to"):
        raise trustsignal_error("400", "REQUIRED_FIELD_MISSING", "Field 'to' is required")


async def record_send(
    db: Session,
    *,
    endpoint: str,
    payload: dict[str, Any],
    query: dict[str, Any],
    background: Any | None = None,
) -> models.OutboundMessage:
    to_phone = normalize_phone(payload.get("to"))
    candidate = CandidateRepository(db).get_or_create(to_phone)
    txid = _transaction_id()
    message_type = str(payload.get("message_type") or payload.get("type") or "template")
    stored_payload = {"body": payload, "query": query}
    outbound = models.OutboundMessage(
        transaction_id=txid,
        sender=str(payload["sender"]),
        to_phone=to_phone,
        endpoint=endpoint,
        template_id=str(payload.get("template_id") or ""),
        message_type=message_type,
        request_payload_json=json.dumps(stored_payload),
        rendered_preview=preview_from_payload(payload),
        status="sent",
    )
    MessageRepository(db).add_outbound(outbound)
    candidate.current_status = "contacted"
    db.commit()
    await enqueue_status(db, outbound, "sent", background)
    await execute_scenarios(db, outbound, background)
    return outbound


async def record_bulk(
    db: Session,
    *,
    endpoint: str,
    payload: dict[str, Any],
    query: dict[str, Any],
    background: Any | None = None,
) -> list[models.OutboundMessage]:
    validate_request(db, query.get("api_key"), payload, require_to=False)
    receivers = payload.get("receivers")
    if not isinstance(receivers, list) or not receivers:
        raise trustsignal_error("400", "REQUIRED_FIELD_MISSING", "Field 'receivers' is required")
    messages: list[models.OutboundMessage] = []
    for receiver in receivers:
        if not isinstance(receiver, dict) or not receiver.get("to"):
            continue
        merged = {**payload, **receiver, "sender": payload["sender"], "template_id": payload.get("template_id", "")}
        if normalize_phone(merged["to"]).endswith("0004"):
            txid = _transaction_id()
            outbound = models.OutboundMessage(
                transaction_id=txid,
                sender=str(payload["sender"]),
                to_phone=normalize_phone(merged["to"]),
                endpoint=endpoint,
                template_id=str(payload.get("template_id") or ""),
                message_type="template",
                request_payload_json=json.dumps({"body": merged, "query": query}),
                rendered_preview="Invalid number scenario",
                status="invalid_number",
            )
            MessageRepository(db).add_outbound(outbound)
            messages.append(outbound)
            continue
        messages.append(await record_send(db, endpoint=endpoint, payload=merged, query=query, background=background))
    db.commit()
    return messages


async def enqueue_status(
    db: Session,
    outbound: models.OutboundMessage,
    status: str,
    background: Any | None = None,
) -> models.WebhookEvent:
    outbound.status = status
    payload = status_payload(outbound, status)
    event = models.WebhookEvent(
        candidate_id=None,
        outbound_message_id=outbound.id,
        event_type=status,
        webhook_type="whatsapp_template",
        payload_json=json.dumps(payload),
        target_url=str(get_runtime_settings(db)["ats_webhook_url"]),
    )
    WebhookRepository(db).add(event)
    event_id = event.id
    db.commit()
    if background is not None:
        background.add_task(deliver_event_by_id, event_id)
    return event


async def simulate_reply(
    db: Session,
    *,
    candidate_id: int,
    text: str,
    message_type: str = "text",
    background: Any | None = None,
) -> models.InboundMessage:
    candidate = CandidateRepository(db).get(candidate_id)
    if candidate is None:
        raise trustsignal_error("404", "NOT_FOUND", "Candidate not found", 404)
    settings = get_runtime_settings(db)
    payload = customer_response_payload(
        sender=str(settings["default_sender"]),
        from_phone=candidate.phone,
        message_type=message_type,
        text=text,
    )
    logger.info("Generated received message payload=%s", json.dumps(payload, ensure_ascii=False, default=str))
    inbound = models.InboundMessage(
        candidate_id=candidate.id,
        from_phone=candidate.phone,
        message_type=message_type,
        text_body=text,
        webhook_payload_json=json.dumps(payload),
    )
    MessageRepository(db).add_inbound(inbound)
    candidate.current_status = f"replied:{text.lower()[:20]}"
    candidate.last_seen_at = models.utcnow()
    event = models.WebhookEvent(
        candidate_id=candidate.id,
        event_type=message_type,
        webhook_type="customer_response",
        payload_json=json.dumps(payload),
        target_url=str(settings["ats_webhook_url"]),
    )
    WebhookRepository(db).add(event)
    event_id = event.id
    db.commit()
    if background is not None:
        background.add_task(deliver_event_by_id, event_id)
    return inbound


async def upload_candidate_file(
    db: Session,
    *,
    candidate_id: int,
    upload: UploadFile,
    invalid: bool = False,
    background: Any | None = None,
) -> models.UploadedFile:
    candidate = CandidateRepository(db).get(candidate_id)
    if candidate is None:
        raise trustsignal_error("404", "NOT_FOUND", "Candidate not found", 404)
    original = Path(upload.filename or "upload.bin").name
    ext = Path(original).suffix.lower()
    if not invalid and ext not in ALLOWED_EXTENSIONS:
        raise trustsignal_error("415", "UNSUPPORTED_FILE", "Unsupported upload type", 415)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    stored = f"{secrets.token_hex(12)}{ext or '.bin'}"
    local_path = UPLOAD_DIR / stored
    size = 0
    with local_path.open("wb") as out:
        while chunk := await upload.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_UPLOAD_SIZE:
                out.close()
                local_path.unlink(missing_ok=True)
                raise trustsignal_error("413", "UPLOAD_TOO_LARGE", "Upload too large", 413)
            out.write(chunk)
    if invalid and size == 0:
        with local_path.open("wb") as out:
            out.write(b"corrupted mock content")
        size = local_path.stat().st_size
    settings = get_runtime_settings(db)
    public_url = f"{str(settings['public_base_url']).rstrip('/')}/files/{stored}"
    uploaded = models.UploadedFile(
        candidate_id=candidate.id,
        original_filename=original,
        stored_filename=stored,
        mime_type=upload.content_type or "application/octet-stream",
        size_bytes=size,
        local_path=str(local_path),
        public_mock_url=public_url,
    )
    db.add(uploaded)
    payload_type = "image" if ext in {".jpg", ".jpeg", ".png"} else "document"
    payload = customer_response_payload(
        sender=str(settings["default_sender"]),
        from_phone=candidate.phone,
        message_type=payload_type,
        file_url=public_url,
        file_name=original,
        mime_type=upload.content_type or "application/octet-stream",
    )
    logger.info("Generated received file payload=%s", json.dumps(payload, ensure_ascii=False, default=str))
    inbound = models.InboundMessage(
        candidate_id=candidate.id,
        from_phone=candidate.phone,
        message_type=payload_type,
        file_url=public_url,
        file_name=original,
        mime_type=upload.content_type or "application/octet-stream",
        webhook_payload_json=json.dumps(payload),
    )
    MessageRepository(db).add_inbound(inbound)
    candidate.current_status = "cv_received" if payload_type == "document" else "media_received"
    event = models.WebhookEvent(
        candidate_id=candidate.id,
        event_type=payload_type,
        webhook_type="customer_response",
        payload_json=json.dumps(payload),
        target_url=str(settings["ats_webhook_url"]),
    )
    WebhookRepository(db).add(event)
    event_id = event.id
    db.commit()
    if background is not None:
        background.add_task(deliver_event_by_id, event_id)
    return uploaded


def delete_candidates(db: Session, ids: list[int]) -> int:
    if not ids:
        return 0
    candidates = db.scalars(select(models.Candidate).where(models.Candidate.id.in_(ids))).all()
    if not candidates:
        return 0
    found_ids = [c.id for c in candidates]
    phones = [c.phone for c in candidates]
    outbound_ids = [
        m.id for m in db.scalars(select(models.OutboundMessage).where(models.OutboundMessage.to_phone.in_(phones)))
    ]
    db.query(models.WebhookEvent).filter(
        models.WebhookEvent.candidate_id.in_(found_ids) | models.WebhookEvent.outbound_message_id.in_(outbound_ids)
    ).delete(synchronize_session=False)
    db.query(models.OutboundMessage).filter(models.OutboundMessage.to_phone.in_(phones)).delete(synchronize_session=False)
    db.query(models.InboundMessage).filter(models.InboundMessage.candidate_id.in_(found_ids)).delete(synchronize_session=False)
    db.query(models.UploadedFile).filter(models.UploadedFile.candidate_id.in_(found_ids)).delete(synchronize_session=False)
    db.query(models.Candidate).filter(models.Candidate.id.in_(found_ids)).delete(synchronize_session=False)
    db.commit()
    return len(found_ids)


async def replay_webhook(db: Session, event_id: int) -> models.WebhookEvent:
    event = WebhookRepository(db).get(event_id)
    if event is None:
        raise trustsignal_error("404", "NOT_FOUND", "Webhook event not found", 404)
    return await deliver_event(db, event)


async def execute_scenarios(db: Session, outbound: models.OutboundMessage, background: Any | None = None) -> None:
    scenarios = ScenarioRepository(db).enabled_for_phone(outbound.to_phone)
    for scenario in scenarios:
        flow = scenario.auto_status_flow or scenario.behavior
        for status in [s.strip() for s in flow.split("+") if s.strip()]:
            if status in {"delivered", "read", "failed", "invalid_number"}:
                await enqueue_status(db, outbound, status, background)
        behavior = scenario.behavior.lower()
        if "yes" in behavior:
            candidate = CandidateRepository(db).get_or_create(outbound.to_phone)
            await simulate_reply(db, candidate_id=candidate.id, text=scenario.auto_reply_text or "YES", background=background)
        if "cv" in behavior:
            candidate = CandidateRepository(db).get_or_create(outbound.to_phone)
            UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
            fixture = UPLOAD_DIR / "scenario_cv.pdf"
            fixture.write_bytes(b"%PDF-1.4 mock scenario cv")
            public_url = f"{str(get_runtime_settings(db)['public_base_url']).rstrip('/')}/files/{fixture.name}"
            payload = customer_response_payload(
                sender=outbound.sender,
                from_phone=candidate.phone,
                message_type="document",
                file_url=public_url,
                file_name="scenario_cv.pdf",
                mime_type="application/pdf",
            )
            event = models.WebhookEvent(
                candidate_id=candidate.id,
                event_type="document",
                webhook_type="customer_response",
                payload_json=json.dumps(payload),
                target_url=str(get_runtime_settings(db)["ats_webhook_url"]),
            )
            WebhookRepository(db).add(event)
            event_id = event.id
            db.commit()
            if background is not None:
                background.add_task(deliver_event_by_id, event_id)


def copy_seed_upload(name: str) -> str:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    path = UPLOAD_DIR / name
    if not path.exists():
        path.write_bytes(b"%PDF-1.4 mock cv")
    return str(path)


def dashboard(db: Session) -> dict[str, Any]:
    recent_out = db.scalars(select(models.OutboundMessage).order_by(models.OutboundMessage.created_at.desc()).limit(5)).all()
    recent_in = db.scalars(select(models.InboundMessage).order_by(models.InboundMessage.created_at.desc()).limit(5)).all()
    return {
        "total_candidates": int(db.scalar(select(func.count()).select_from(models.Candidate)) or 0),
        "outbound_messages": int(db.scalar(select(func.count()).select_from(models.OutboundMessage)) or 0),
        "inbound_messages": int(db.scalar(select(func.count()).select_from(models.InboundMessage)) or 0),
        "cvs_received": int(db.scalar(select(func.count()).select_from(models.UploadedFile)) or 0),
        "delivered": int(db.scalar(select(func.count()).select_from(models.OutboundMessage).where(models.OutboundMessage.status == "delivered")) or 0),
        "read": int(db.scalar(select(func.count()).select_from(models.OutboundMessage).where(models.OutboundMessage.status == "read")) or 0),
        "failures": int(db.scalar(select(func.count()).select_from(models.OutboundMessage).where(models.OutboundMessage.status.in_(["failed", "invalid_number"]))) or 0),
        "webhook_retries": int(db.scalar(select(func.sum(models.WebhookEvent.retry_count))) or 0),
        "recent_activity": [
            {"kind": "outbound", "phone": m.to_phone, "status": m.status, "created_at": india_isoformat(m.created_at)}
            for m in recent_out
        ]
        + [
            {"kind": "inbound", "phone": m.from_phone, "status": m.message_type, "created_at": india_isoformat(m.created_at)}
            for m in recent_in
        ],
    }
