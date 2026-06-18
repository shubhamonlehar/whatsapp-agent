import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.services import copy_seed_upload
from app.webhooks import customer_response_payload, status_payload


def seed_if_empty(db: Session) -> None:
    if db.scalar(select(models.Candidate).limit(1)) is not None:
        return

    candidates: list[models.Candidate] = []
    for i in range(10):
        phone = f"91000000{i + 1:02d}"
        candidate = models.Candidate(phone=phone, name=f"Candidate {i + 1}", current_status="new")
        db.add(candidate)
        candidates.append(candidate)
    db.flush()

    statuses = ["delivered"] * 5 + ["read"] * 3 + ["failed"] * 2 + ["sent"] * 10
    for i in range(20):
        candidate = candidates[i % len(candidates)]
        msg = models.OutboundMessage(
            transaction_id=f"1731449582893088309917895172025{i:05d}",
            sender="9810330589",
            to_phone=candidate.phone,
            endpoint="single",
            template_id="mock_recruitment_template",
            message_type="template",
            request_payload_json=json.dumps({"sender": "9810330589", "to": candidate.phone}),
            rendered_preview="Please share your updated CV.",
            status=statuses[i],
        )
        db.add(msg)
        db.flush()
        event_payload = status_payload(msg, statuses[i])
        db.add(
            models.WebhookEvent(
                outbound_message_id=msg.id,
                event_type=statuses[i],
                webhook_type="whatsapp_template",
                payload_json=json.dumps(event_payload),
                target_url="http://localhost:3000/api/webhooks/whatsapp",
            )
        )

    replies = ["YES", "NO", "RESCHEDULE", "CALL_ME", "Random question", "STOP", "YES", "NO", "Shared CV", "Interested"]
    for i, text in enumerate(replies):
        candidate = candidates[i % len(candidates)]
        payload = customer_response_payload(sender="9810330589", from_phone=candidate.phone, message_type="text", text=text)
        db.add(
            models.InboundMessage(
                candidate_id=candidate.id,
                from_phone=candidate.phone,
                message_type="text",
                text_body=text,
                webhook_payload_json=json.dumps(payload),
            )
        )
        db.add(
            models.WebhookEvent(
                candidate_id=candidate.id,
                event_type="text",
                webhook_type="customer_response",
                payload_json=json.dumps(payload),
                target_url="http://localhost:3000/api/webhooks/whatsapp",
            )
        )

    for i in range(5):
        candidate = candidates[i]
        stored = f"seed_cv_{i + 1}.pdf"
        path = copy_seed_upload(stored)
        public_url = f"http://localhost:8080/files/{stored}"
        db.add(
            models.UploadedFile(
                candidate_id=candidate.id,
                original_filename=f"candidate_{i + 1}_resume.pdf",
                stored_filename=stored,
                mime_type="application/pdf",
                size_bytes=24,
                local_path=path,
                public_mock_url=public_url,
            )
        )
    db.add_all(
        [
            models.TestScenario(
                phone="9100000001", name="Delivered", behavior="delivered", auto_status_flow="delivered"
            ),
            models.TestScenario(
                phone="9100000002", name="Delivered + Read", behavior="delivered+read", auto_status_flow="delivered+read"
            ),
            models.TestScenario(
                phone="9100000003", name="Delivered + Read + YES", behavior="yes", auto_reply_text="YES", auto_status_flow="delivered+read"
            ),
            models.TestScenario(
                phone="9100000004", name="Invalid Number", behavior="invalid_number", auto_status_flow="invalid_number"
            ),
            models.TestScenario(phone="9100000005", name="Upload CV", behavior="upload_cv"),
        ]
    )
    db.commit()
