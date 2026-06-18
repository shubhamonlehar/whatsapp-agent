from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import models


class CandidateRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_or_create(self, phone: str, name: str | None = None) -> models.Candidate:
        candidate = self.db.scalar(select(models.Candidate).where(models.Candidate.phone == phone))
        if candidate is not None:
            candidate.last_seen_at = models.utcnow()
            if name and candidate.name == "Unknown Candidate":
                candidate.name = name
            return candidate
        candidate = models.Candidate(phone=phone, name=name or f"Candidate {phone[-4:]}")
        self.db.add(candidate)
        self.db.flush()
        return candidate

    def list(self) -> list[models.Candidate]:
        return list(self.db.scalars(select(models.Candidate).order_by(models.Candidate.last_seen_at.desc())))

    def get(self, candidate_id: int) -> models.Candidate | None:
        return self.db.get(models.Candidate, candidate_id)


class MessageRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add_outbound(self, message: models.OutboundMessage) -> models.OutboundMessage:
        self.db.add(message)
        self.db.flush()
        return message

    def get_outbound_by_transaction(self, transaction_id: str) -> models.OutboundMessage | None:
        return self.db.scalar(
            select(models.OutboundMessage).where(models.OutboundMessage.transaction_id == transaction_id)
        )

    def list_outbound(self) -> list[models.OutboundMessage]:
        return list(self.db.scalars(select(models.OutboundMessage).order_by(models.OutboundMessage.created_at.desc())))

    def list_inbound(self, candidate_id: int | None = None) -> list[models.InboundMessage]:
        stmt = select(models.InboundMessage).order_by(models.InboundMessage.created_at.desc())
        if candidate_id is not None:
            stmt = stmt.where(models.InboundMessage.candidate_id == candidate_id)
        return list(self.db.scalars(stmt))

    def add_inbound(self, message: models.InboundMessage) -> models.InboundMessage:
        self.db.add(message)
        self.db.flush()
        return message


class WebhookRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, event: models.WebhookEvent) -> models.WebhookEvent:
        self.db.add(event)
        self.db.flush()
        return event

    def get(self, event_id: int) -> models.WebhookEvent | None:
        return self.db.get(models.WebhookEvent, event_id)

    def list(self) -> list[models.WebhookEvent]:
        return list(self.db.scalars(select(models.WebhookEvent).order_by(models.WebhookEvent.created_at.desc())))


class ScenarioRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list(self) -> list[models.TestScenario]:
        return list(self.db.scalars(select(models.TestScenario).order_by(models.TestScenario.phone.asc())))

    def add(self, scenario: models.TestScenario) -> models.TestScenario:
        self.db.add(scenario)
        self.db.flush()
        return scenario

    def enabled_for_phone(self, phone: str) -> list[models.TestScenario]:
        return list(
            self.db.scalars(
                select(models.TestScenario).where(
                    models.TestScenario.phone == phone,
                    models.TestScenario.enabled.is_(True),
                )
            )
        )


def count(db: Session, model: type[models.Base]) -> int:
    return int(db.scalar(select(func.count()).select_from(model)) or 0)
