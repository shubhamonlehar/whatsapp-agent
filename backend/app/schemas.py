from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from app.time_utils import india_isoformat


class TrustSignalError(BaseModel):
    code: str
    codeMsg: str
    message: str


class TrustSignalErrorResponse(BaseModel):
    errors: list[TrustSignalError]
    success: bool = False


class IndiaTimeModel(BaseModel):
    @field_serializer("*", check_fields=False, when_used="json")
    def serialize_india_times(self, value: Any) -> Any:
        if isinstance(value, datetime):
            return india_isoformat(value)
        return value


class CandidateOut(IndiaTimeModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    phone: str
    name: str
    current_status: str
    first_seen_at: datetime
    last_seen_at: datetime
    notes: str
    created_at: datetime
    updated_at: datetime


class OutboundMessageOut(IndiaTimeModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    transaction_id: str
    sender: str
    to_phone: str
    endpoint: str
    template_id: str
    message_type: str
    request_payload_json: str
    rendered_preview: str
    status: str
    created_at: datetime
    updated_at: datetime


class InboundMessageOut(IndiaTimeModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    candidate_id: int
    from_phone: str
    message_type: str
    text_body: str
    file_url: str
    file_name: str
    mime_type: str
    webhook_payload_json: str
    created_at: datetime


class UploadedFileOut(IndiaTimeModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    candidate_id: int
    original_filename: str
    stored_filename: str
    mime_type: str
    size_bytes: int
    local_path: str
    public_mock_url: str
    created_at: datetime


class WebhookEventOut(IndiaTimeModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    candidate_id: int | None
    outbound_message_id: int | None
    event_type: str
    webhook_type: str
    payload_json: str
    target_url: str
    response_status: int | None
    response_body: str
    retry_count: int
    created_at: datetime


class ScenarioIn(IndiaTimeModel):
    phone: str
    name: str
    behavior: str
    auto_reply_text: str = ""
    auto_status_flow: str = ""
    delay_seconds: int = 0
    enabled: bool = True


class ScenarioOut(ScenarioIn):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime


class LoginIn(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class ReplyIn(BaseModel):
    text: str = Field(default="YES", min_length=1)
    message_type: str = "text"


class DeleteCandidatesIn(BaseModel):
    ids: list[int] = Field(min_length=1)


class StatusIn(BaseModel):
    status: str = Field(pattern="^(sent|delivered|read|failed|invalid_number)$")


class SettingsPatch(BaseModel):
    ats_webhook_url: str | None = None
    ats_webhook_enabled: bool | None = None
    ats_webhook_retry_count: int | None = None
    ats_webhook_retry_interval_ms: int | None = None
    ats_webhook_timeout_ms: int | None = None
    ats_webhook_auth_header: str | None = None
    ats_webhook_auth_token: str | None = None
    valid_api_keys: str | None = None
    valid_senders: str | None = None
    default_sender: str | None = None
    public_base_url: str | None = None


class DashboardOut(IndiaTimeModel):
    total_candidates: int
    outbound_messages: int
    inbound_messages: int
    cvs_received: int
    delivered: int
    read: int
    failures: int
    webhook_retries: int
    recent_activity: list[dict[str, Any]]
