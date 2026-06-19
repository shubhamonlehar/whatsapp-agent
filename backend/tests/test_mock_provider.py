import json
import os
import sys
import asyncio
from io import BytesIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

os.environ["AUTO_SEED"] = "false"
os.environ["ATS_WEBHOOK_ENABLED"] = "false"
os.environ["STRICT_API_KEY"] = "true"
os.environ["VALID_API_KEYS"] = "test-api-key"
os.environ["VALID_SENDERS"] = "9810330589"
os.environ["ADMIN_PASSWORD"] = "test-admin-pass"
os.environ["DATABASE_URL"] = "sqlite:///./test_mock_trustsignal.db"

test_db = ROOT / "test_mock_trustsignal.db"
if test_db.exists():
    test_db.unlink()

from fastapi.testclient import TestClient  # noqa: E402

from app import models  # noqa: E402
from app.db import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.webhooks import deliver_event_by_id, webhook_auth_headers  # noqa: E402

Base.metadata.create_all(bind=engine)

client = TestClient(app)

# The /mock/* control surface now requires an admin bearer token. Authenticate once
# and attach the token to every request this client makes.
_token = client.post("/auth/login", json={"username": "admin", "password": "test-admin-pass"}).json()["token"]
client.headers.update({"Authorization": f"Bearer {_token}"})


def send_payload(to: str = "919100000001") -> dict[str, str]:
    return {"sender": "9810330589", "to": to, "template_id": "cv_request"}


def test_webhook_auth_headers_adds_lovable_bearer_prefix() -> None:
    headers = webhook_auth_headers({"ats_webhook_auth_token": "secret-token"})
    assert headers == {"Authorization": "Bearer secret-token"}


def test_webhook_auth_headers_does_not_double_prefix_bearer() -> None:
    headers = webhook_auth_headers(
        {"ats_webhook_auth_header": "Authorization", "ats_webhook_auth_token": "Bearer secret-token"}
    )
    assert headers == {"Authorization": "Bearer secret-token"}


def test_mock_surface_requires_admin_token() -> None:
    anon = TestClient(app)
    assert anon.get("/mock/dashboard").status_code == 401


def test_login_issues_token_and_rejects_bad_credentials() -> None:
    bad = client.post("/auth/login", json={"username": "admin", "password": "wrong"})
    assert bad.status_code == 401
    good = client.post("/auth/login", json={"username": "admin", "password": "test-admin-pass"})
    assert good.status_code == 200
    assert good.json()["token"]


def test_message_send_generates_trustsignal_response_and_webhook() -> None:
    response = client.post("/api/v1/whatsapp/single?api_key=test-api-key", json=send_payload())
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["message"] == "Request process successfully"
    assert body["results"]["transaction_id"]

    logs = client.get("/mock/webhook-events").json()
    assert logs[0]["webhook_type"] == "whatsapp_template"
    payload = json.loads(logs[0]["payload_json"])
    assert payload["value"]["statuses"][0]["status"] == "sent"


def test_mock_api_timestamps_are_serialized_in_india_time() -> None:
    client.post("/api/v1/whatsapp/single?api_key=test-api-key", json=send_payload("919100000055"))

    message = next(item for item in client.get("/mock/messages").json() if item["to_phone"] == "919100000055")
    assert message["created_at"].endswith("+05:30")

    candidate = next(item for item in client.get("/mock/candidates").json() if item["phone"] == "919100000055")
    assert candidate["last_seen_at"].endswith("+05:30")

    detail = client.get(f"/mock/candidates/{candidate['id']}").json()
    assert detail["candidate"]["created_at"].endswith("+05:30")

    dashboard = client.get("/mock/dashboard").json()
    recent = [item for item in dashboard["recent_activity"] if item["phone"] == "919100000055"]
    assert recent
    assert recent[0]["created_at"].endswith("+05:30")


def test_template_id_renders_preview_from_mapping() -> None:
    payload = {
        "body": {
            "sender": "9810330589",
            "to": "919100000123",
            "template_id": "candidate_cv_reqquest_18bva1mbdlo8c907",
            "sample": {"bodyvar": ["Ravi", "Software Engineer", "Noida"]},
        }
    }
    response = client.post("/api/v1/whatsapp/single?api_key=test-api-key", json=payload)
    assert response.status_code == 200

    messages = client.get("/mock/messages").json()
    stored = next(message for message in messages if message["to_phone"] == "919100000123")
    assert stored["rendered_preview"] == (
        "Candidate CV Request Template : Hi Ravi, thanks for your interest in the Software Engineer role at Noida."
    )


def test_received_duplicate_interview_reminder_template_id_renders_preview() -> None:
    payload = {
        "body": {
            "sender": "9810330589",
            "to": "919100000124",
            "template_id": "duplicate_interview_reminder_yeaygobldbvb2m1z",
            "sample": {"bodyvar": ["Priyanka", "Software Engineer", "Myna"]},
        }
    }
    response = client.post("/api/v1/whatsapp/single?api_key=test-api-key", json=payload)
    assert response.status_code == 200

    messages = client.get("/mock/messages").json()
    stored = next(message for message in messages if message["to_phone"] == "919100000124")
    assert stored["rendered_preview"] == (
        "Hi Priyanka, a quick reminder - your interview for Software Engineer at Myna starts in 30 minutes."
    )


def test_unknown_candidate_is_created() -> None:
    client.post("/api/v1/whatsapp/single?api_key=test-api-key", json=send_payload("919100000099"))
    candidates = client.get("/mock/candidates").json()
    assert any(candidate["phone"] == "919100000099" for candidate in candidates)


def test_candidate_reply_generates_customer_response_webhook() -> None:
    candidate = client.get("/mock/candidates").json()[0]
    response = client.post(f"/mock/candidates/{candidate['id']}/reply", json={"text": "YES"})
    assert response.status_code == 200
    logs = client.get("/mock/webhook-events").json()
    assert any(event["webhook_type"] == "customer_response" and event["event_type"] == "text" for event in logs)


def test_cv_upload_generates_document_webhook() -> None:
    candidate = client.get("/mock/candidates").json()[0]
    files = {"file": ("resume.pdf", BytesIO(b"%PDF-1.4"), "application/pdf")}
    response = client.post(f"/mock/candidates/{candidate['id']}/upload-cv", files=files)
    assert response.status_code == 200
    assert response.json()["file"]["public_mock_url"].endswith(".pdf")


def test_invalid_sender() -> None:
    payload = send_payload()
    payload["sender"] = "bad"
    response = client.post("/api/v1/whatsapp/single?api_key=test-api-key", json=payload)
    assert response.status_code == 400
    assert response.json()["errors"][0]["codeMsg"] == "INVALID_SENDERID"


def test_invalid_api_key() -> None:
    response = client.post("/api/v1/whatsapp/single?api_key=wrong", json=send_payload())
    assert response.status_code == 400
    assert response.json()["errors"][0]["codeMsg"] == "INVALID_API_KEY"


def test_webhook_retry_endpoint() -> None:
    client.post("/api/v1/whatsapp/single?api_key=test-api-key", json=send_payload("919100000077"))
    event = client.get("/mock/webhook-events").json()[0]
    response = client.post(f"/mock/webhook-events/{event['id']}/retry")
    assert response.status_code == 200
    assert response.json()["success"] is True


def test_scenario_execution() -> None:
    client.post(
        "/mock/scenarios",
        json={
            "phone": "919100000088",
            "name": "Auto read yes",
            "behavior": "yes",
            "auto_reply_text": "YES",
            "auto_status_flow": "delivered+read",
            "enabled": True,
        },
    )
    client.post("/api/v1/whatsapp/single?api_key=test-api-key", json=send_payload("919100000088"))
    logs = client.get("/mock/webhook-events").json()
    assert any(event["event_type"] == "read" for event in logs)
    assert any(event["webhook_type"] == "customer_response" for event in logs)


def test_bulk_delete_removes_candidate_and_related_rows() -> None:
    client.post("/api/v1/whatsapp/single?api_key=test-api-key", json=send_payload("919100000201"))
    candidate = next(item for item in client.get("/mock/candidates").json() if item["phone"] == "919100000201")
    client.post(f"/mock/candidates/{candidate['id']}/reply", json={"text": "YES"})

    response = client.post("/mock/candidates/bulk-delete", json={"ids": [candidate["id"]]})
    assert response.status_code == 200
    assert response.json()["deleted"] == 1

    phones = [item["phone"] for item in client.get("/mock/candidates").json()]
    assert "919100000201" not in phones
    detail = client.get(f"/mock/candidates/{candidate['id']}")
    assert detail.status_code == 404


def test_invalid_json_body() -> None:
    response = client.post(
        "/api/v1/whatsapp/single?api_key=test-api-key",
        data="{bad-json",
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 400
    assert response.json()["errors"][0]["codeMsg"] == "INVALID_JSON_BODY"


def test_background_webhook_delivery_uses_fresh_session() -> None:
    with SessionLocal() as db:
        event = models.WebhookEvent(
            event_type="text",
            webhook_type="customer_response",
            payload_json=json.dumps({"ok": True}),
            target_url="",
        )
        db.add(event)
        db.flush()
        event_id = event.id
        db.commit()

    asyncio.run(deliver_event_by_id(event_id))

    with SessionLocal() as db:
        stored = db.get(models.WebhookEvent, event_id)
        assert stored is not None
        assert stored.response_body == "Webhook delivery disabled or URL empty; event stored for replay."
