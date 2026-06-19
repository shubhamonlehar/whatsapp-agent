from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    port: int = 8080
    database_url: str = "sqlite:///./mock_trustsignal.db"
    public_base_url: str = "http://localhost:8080"
    default_sender: str = "9810330589"
    strict_api_key: bool = False
    valid_api_keys: str = "test-api-key"
    valid_senders: str = "9810330589"
    ats_webhook_url: str = "http://localhost:3000/api/webhooks/whatsapp"
    ats_webhook_enabled: bool = True
    ats_webhook_timeout_ms: int = 10000
    ats_webhook_retry_count: int = 3
    ats_webhook_retry_interval_ms: int = 5000
    ats_webhook_auth_header: str = ""
    ats_webhook_auth_token: str = ""
    admin_username: str = "admin"
    admin_password: str = ""
    auth_secret: str = ""
    auto_seed: bool = True
    log_level: str = "INFO"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @property
    def api_keys(self) -> set[str]:
        return {v.strip() for v in self.valid_api_keys.split(",") if v.strip()}

    @property
    def senders(self) -> set[str]:
        return {v.strip() for v in self.valid_senders.split(",") if v.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()
