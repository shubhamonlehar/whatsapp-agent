"""initial schema

Revision ID: 20260607_0001
Revises:
Create Date: 2026-06-07
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260607_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "candidates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("phone", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("current_status", sa.String(length=64), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_candidates_phone", "candidates", ["phone"], unique=True)
    op.create_table(
        "outbound_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("transaction_id", sa.String(length=80), nullable=False),
        sa.Column("sender", sa.String(length=32), nullable=False),
        sa.Column("to_phone", sa.String(length=32), nullable=False),
        sa.Column("endpoint", sa.String(length=80), nullable=False),
        sa.Column("template_id", sa.String(length=160), nullable=False),
        sa.Column("message_type", sa.String(length=80), nullable=False),
        sa.Column("request_payload_json", sa.Text(), nullable=False),
        sa.Column("rendered_preview", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_outbound_messages_transaction_id", "outbound_messages", ["transaction_id"], unique=True)
    op.create_index("ix_outbound_messages_sender", "outbound_messages", ["sender"])
    op.create_index("ix_outbound_messages_to_phone", "outbound_messages", ["to_phone"])
    op.create_index("ix_outbound_messages_status", "outbound_messages", ["status"])
    op.create_table(
        "inbound_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("candidate_id", sa.Integer(), sa.ForeignKey("candidates.id"), nullable=False),
        sa.Column("from_phone", sa.String(length=32), nullable=False),
        sa.Column("message_type", sa.String(length=40), nullable=False),
        sa.Column("text_body", sa.Text(), nullable=False),
        sa.Column("file_url", sa.Text(), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=120), nullable=False),
        sa.Column("webhook_payload_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_inbound_messages_from_phone", "inbound_messages", ["from_phone"])
    op.create_table(
        "uploaded_files",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("candidate_id", sa.Integer(), sa.ForeignKey("candidates.id"), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("stored_filename", sa.String(length=255), nullable=False, unique=True),
        sa.Column("mime_type", sa.String(length=120), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("local_path", sa.Text(), nullable=False),
        sa.Column("public_mock_url", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "webhook_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("candidate_id", sa.Integer(), sa.ForeignKey("candidates.id"), nullable=True),
        sa.Column("outbound_message_id", sa.Integer(), sa.ForeignKey("outbound_messages.id"), nullable=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("webhook_type", sa.String(length=64), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("target_url", sa.Text(), nullable=False),
        sa.Column("response_status", sa.Integer(), nullable=True),
        sa.Column("response_body", sa.Text(), nullable=False),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_webhook_events_event_type", "webhook_events", ["event_type"])
    op.create_index("ix_webhook_events_webhook_type", "webhook_events", ["webhook_type"])
    op.create_table(
        "test_scenarios",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("phone", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("behavior", sa.String(length=80), nullable=False),
        sa.Column("auto_reply_text", sa.Text(), nullable=False),
        sa.Column("auto_status_flow", sa.Text(), nullable=False),
        sa.Column("delay_seconds", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_test_scenarios_phone", "test_scenarios", ["phone"])
    op.create_table(
        "app_settings",
        sa.Column("key", sa.String(length=120), primary_key=True),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("app_settings")
    op.drop_table("test_scenarios")
    op.drop_table("webhook_events")
    op.drop_table("uploaded_files")
    op.drop_table("inbound_messages")
    op.drop_table("outbound_messages")
    op.drop_table("candidates")
