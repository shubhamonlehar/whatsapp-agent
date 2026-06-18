from typing import Any

from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.models import AppSetting


SETTING_KEYS = {
    "ats_webhook_url",
    "ats_webhook_enabled",
    "ats_webhook_retry_count",
    "ats_webhook_retry_interval_ms",
    "ats_webhook_timeout_ms",
    "ats_webhook_auth_header",
    "ats_webhook_auth_token",
    "valid_api_keys",
    "valid_senders",
    "default_sender",
    "public_base_url",
}


def get_runtime_settings(db: Session) -> dict[str, Any]:
    env = get_settings()
    values: dict[str, Any] = {
        "ats_webhook_url": env.ats_webhook_url,
        "ats_webhook_enabled": env.ats_webhook_enabled,
        "ats_webhook_retry_count": env.ats_webhook_retry_count,
        "ats_webhook_retry_interval_ms": env.ats_webhook_retry_interval_ms,
        "ats_webhook_timeout_ms": env.ats_webhook_timeout_ms,
        "ats_webhook_auth_header": env.ats_webhook_auth_header,
        "ats_webhook_auth_token": env.ats_webhook_auth_token,
        "valid_api_keys": env.valid_api_keys,
        "valid_senders": env.valid_senders,
        "default_sender": env.default_sender,
        "public_base_url": env.public_base_url,
    }
    for setting in db.query(AppSetting).all():
        values[setting.key] = setting.value
    for key in ("ats_webhook_enabled",):
        values[key] = str(values[key]).lower() in {"1", "true", "yes", "on"}
    for key in ("ats_webhook_retry_count", "ats_webhook_retry_interval_ms", "ats_webhook_timeout_ms"):
        values[key] = int(values[key])
    return values


def patch_runtime_settings(db: Session, patch: dict[str, Any]) -> dict[str, Any]:
    for key, value in patch.items():
        if key not in SETTING_KEYS or value is None:
            continue
        setting = db.get(AppSetting, key) or AppSetting(key=key)
        setting.value = str(value)
        db.add(setting)
    db.commit()
    return get_runtime_settings(db)


def allowed_senders(db: Session) -> set[str]:
    values = get_runtime_settings(db)
    return {v.strip() for v in str(values["valid_senders"]).split(",") if v.strip()}


def valid_api_keys(db: Session) -> set[str]:
    values = get_runtime_settings(db)
    return {v.strip() for v in str(values["valid_api_keys"]).split(",") if v.strip()}


def strict_api_key() -> bool:
    settings: Settings = get_settings()
    return settings.strict_api_key
