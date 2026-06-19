import json
import logging
from datetime import datetime
from typing import Any

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from app import models
from app.db import get_db
from app.repositories import CandidateRepository, MessageRepository, ScenarioRepository, WebhookRepository
from app.auth import check_credentials, create_token
from app.schemas import (
    CandidateOut,
    DashboardOut,
    DeleteCandidatesIn,
    LoginIn,
    ReplyIn,
    ScenarioIn,
    ScenarioOut,
    SettingsPatch,
    StatusIn,
    OutboundMessageOut,
    UploadedFileOut,
    WebhookEventOut,
)
from app.services import dashboard, delete_candidates, record_bulk, record_send, replay_webhook, simulate_reply, upload_candidate_file, validate_request
from app.settings_store import get_runtime_settings, patch_runtime_settings
from app.time_utils import india_isoformat
from app.trustsignal import success_bulk, success_indicator, success_single, trustsignal_error
from app.webhooks import webhook_auth_headers

router = APIRouter()
logger = logging.getLogger("mock_whatsapp.requests")


def masked_query(request: Request) -> dict[str, Any]:
    values = dict(request.query_params.multi_items())
    if "api_key" in values:
        values["api_key"] = "***"
    return values


async def json_body(request: Request) -> dict[str, Any]:
    try:
        body = await request.json()
    except Exception as exc:
        raise trustsignal_error("400", "INVALID_JSON_BODY", "Invalid JSON body") from exc
    if not isinstance(body, dict):
        raise trustsignal_error("400", "INVALID_JSON_BODY", "JSON body must be an object")
    if not body.get("sender") and isinstance(body.get("body"), dict):
        body = body["body"]
    logger.info(
        "Received %s %s query=%s payload=%s",
        request.method,
        request.url.path,
        masked_query(request),
        json.dumps(body, ensure_ascii=False, default=str),
    )
    return body


def query_dict(request: Request) -> dict[str, Any]:
    return dict(request.query_params.multi_items())


def public_settings(settings: dict[str, Any]) -> dict[str, Any]:
    values = dict(settings)
    if values.get("ats_webhook_auth_token"):
        values["ats_webhook_auth_token"] = "***"
        values["ats_webhook_auth_token_masked"] = "***"
    return values


@router.get("/health")
def health(db: Session = Depends(get_db)) -> dict[str, Any]:
    return {"status": "ok", "provider": "mock-trustsignal-whatsapp", "settings": public_settings(get_runtime_settings(db))}


@router.post("/auth/login")
def login(body: LoginIn) -> dict[str, Any]:
    if not check_credentials(body.username, body.password):
        raise trustsignal_error("401", "INVALID_CREDENTIALS", "Invalid username or password", 401)
    return {"success": True, "token": create_token(body.username), "username": body.username}


@router.post("/api/v1/whatsapp/single")
async def whatsapp_single(
    request: Request,
    background: BackgroundTasks,
    api_key: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    payload = await json_body(request)
    validate_request(db, api_key, payload)
    message = await record_send(db, endpoint="single", payload=payload, query=query_dict(request), background=background)
    return success_single(message.to_phone, message.transaction_id)


@router.post("/api/v1/whatsapp/otp")
async def whatsapp_otp(
    request: Request,
    background: BackgroundTasks,
    api_key: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    payload = await json_body(request)
    validate_request(db, api_key, payload)
    message = await record_send(db, endpoint="otp", payload=payload, query=query_dict(request), background=background)
    return success_single(message.to_phone, message.transaction_id)


@router.post("/api/v1/whatsapp/agent-reply")
async def whatsapp_agent_reply(
    request: Request,
    background: BackgroundTasks,
    api_key: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    payload = await json_body(request)
    validate_request(db, api_key, payload)
    message = await record_send(db, endpoint="agent-reply", payload=payload, query=query_dict(request), background=background)
    return success_single(message.to_phone, message.transaction_id)


@router.post("/api/v1/whatsapp/bulk")
async def whatsapp_bulk(
    request: Request,
    background: BackgroundTasks,
    api_key: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    payload = await json_body(request)
    messages = await record_bulk(db, endpoint="bulk", payload=payload, query=query_dict(request), background=background)
    return success_bulk(
        [
            {"to": msg.to_phone, "transaction_id": msg.transaction_id, "status": msg.status}
            for msg in messages
        ]
    )


@router.post("/api/v1/whatsapp/typing-indicator")
async def typing_indicator(request: Request, api_key: str | None = Query(default=None)) -> dict[str, Any]:
    _ = api_key
    body = await json_body(request)
    if not body.get("message_id"):
        raise trustsignal_error("400", "REQUIRED_FIELD_MISSING", "Field 'message_id' is required")
    return success_indicator()


@router.post("/api/v1/whatsapp/mark-read")
async def mark_read(request: Request, api_key: str | None = Query(default=None)) -> dict[str, Any]:
    _ = api_key
    body = await json_body(request)
    if not body.get("message_id"):
        raise trustsignal_error("400", "REQUIRED_FIELD_MISSING", "Field 'message_id' is required")
    return success_indicator()


@router.get("/mock/dashboard", response_model=DashboardOut)
def mock_dashboard(db: Session = Depends(get_db)) -> dict[str, Any]:
    return dashboard(db)


@router.get("/mock/messages", response_model=list[OutboundMessageOut])
def mock_messages(db: Session = Depends(get_db)) -> list[models.OutboundMessage]:
    return MessageRepository(db).list_outbound()


@router.get("/mock/candidates", response_model=list[CandidateOut])
def mock_candidates(db: Session = Depends(get_db)) -> list[models.Candidate]:
    return CandidateRepository(db).list()


@router.post("/mock/candidates/bulk-delete")
def mock_delete_candidates(body: DeleteCandidatesIn, db: Session = Depends(get_db)) -> dict[str, Any]:
    deleted = delete_candidates(db, body.ids)
    return {"success": True, "deleted": deleted}


@router.get("/mock/candidates/{candidate_id}")
def mock_candidate_detail(candidate_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    candidate = CandidateRepository(db).get(candidate_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail="Candidate not found")
    inbound = MessageRepository(db).list_inbound(candidate_id)
    outbound = [m for m in MessageRepository(db).list_outbound() if m.to_phone == candidate.phone]
    files = db.query(models.UploadedFile).filter(models.UploadedFile.candidate_id == candidate.id).all()
    events = db.query(models.WebhookEvent).filter(models.WebhookEvent.candidate_id == candidate.id).all()
    return jsonable_encoder(
        {"candidate": candidate, "inbound": inbound, "outbound": outbound, "files": files, "webhook_events": events},
        custom_encoder={datetime: india_isoformat},
    )


@router.post("/mock/candidates/{candidate_id}/reply")
async def mock_reply(
    candidate_id: int,
    reply: ReplyIn,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    inbound = await simulate_reply(
        db, candidate_id=candidate_id, text=reply.text, message_type=reply.message_type, background=background
    )
    return {"success": True, "inbound_message_id": inbound.id}


@router.post("/mock/candidates/{candidate_id}/upload-cv")
async def mock_upload_cv(
    candidate_id: int,
    background: BackgroundTasks,
    file: UploadFile = File(...),
    invalid: bool = False,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    uploaded = await upload_candidate_file(db, candidate_id=candidate_id, upload=file, invalid=invalid, background=background)
    return {"success": True, "file": UploadedFileOut.model_validate(uploaded).model_dump(mode="json")}


@router.post("/mock/messages/{transaction_id}/status")
async def mock_message_status(
    transaction_id: str,
    status: StatusIn,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    message = MessageRepository(db).get_outbound_by_transaction(transaction_id)
    if message is None:
        raise HTTPException(status_code=404, detail="Message not found")
    from app.services import enqueue_status

    event = await enqueue_status(db, message, status.status, background)
    return {"success": True, "event_id": event.id}


@router.post("/mock/messages/{transaction_id}/replay-webhook")
async def mock_message_replay(transaction_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    message = MessageRepository(db).get_outbound_by_transaction(transaction_id)
    if message is None or not message.webhook_events:
        raise HTTPException(status_code=404, detail="Webhook not found")
    event = await replay_webhook(db, message.webhook_events[-1].id)
    return {"success": True, "event": WebhookEventOut.model_validate(event).model_dump(mode="json")}


@router.get("/mock/webhook-events", response_model=list[WebhookEventOut])
def mock_webhook_events(db: Session = Depends(get_db)) -> list[models.WebhookEvent]:
    return WebhookRepository(db).list()


@router.post("/mock/webhook-events/{event_id}/retry")
async def mock_webhook_retry(event_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    event = await replay_webhook(db, event_id)
    return {"success": True, "event": WebhookEventOut.model_validate(event).model_dump(mode="json")}


@router.post("/mock/scenarios", response_model=ScenarioOut)
def mock_add_scenario(scenario: ScenarioIn, db: Session = Depends(get_db)) -> models.TestScenario:
    created = ScenarioRepository(db).add(models.TestScenario(**scenario.model_dump()))
    db.commit()
    return created


@router.get("/mock/scenarios", response_model=list[ScenarioOut])
def mock_list_scenarios(db: Session = Depends(get_db)) -> list[models.TestScenario]:
    return ScenarioRepository(db).list()


@router.get("/mock/settings")
def mock_get_settings(db: Session = Depends(get_db)) -> dict[str, Any]:
    settings = public_settings(get_runtime_settings(db))
    if "valid_api_keys" in settings:
        settings["valid_api_keys_masked"] = ",".join("***" for _ in str(settings["valid_api_keys"]).split(",") if _)
    return settings


@router.patch("/mock/settings")
def mock_patch_settings(patch: SettingsPatch, db: Session = Depends(get_db)) -> dict[str, Any]:
    return patch_runtime_settings(db, patch.model_dump(exclude_none=True))


@router.post("/mock/settings/test-ats-connection")
async def test_ats_connection(db: Session = Depends(get_db)) -> dict[str, Any]:
    settings = get_runtime_settings(db)
    url = str(settings["ats_webhook_url"])
    if not url:
        return {"success": False, "status": None, "body": "ATS_WEBHOOK_URL is empty"}
    payload = {"webhook_type": "connection_test", "success": True, "message": "Mock WhatsApp Provider test"}
    try:
        async with httpx.AsyncClient(timeout=int(settings["ats_webhook_timeout_ms"]) / 1000) as client:
            response = await client.post(url, json=payload, headers=webhook_auth_headers(settings))
        return {"success": response.status_code < 500, "status": response.status_code, "body": response.text}
    except httpx.HTTPError as exc:
        return {"success": False, "status": None, "body": str(exc)}
