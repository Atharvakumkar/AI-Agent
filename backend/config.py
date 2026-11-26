from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "SentinelAI"
    app_env: str = "development"
    host: str = "127.0.0.1"
    port: int = 8000
    frontend_origin: str = "http://localhost:5173"

    database_url: str = "sqlite:///./sentinelai.db"

    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"

    poll_interval_seconds: float = 2.0
    cpu_warning_threshold: float = 75.0
    cpu_critical_threshold: float = 90.0
    memory_warning_threshold: float = 80.0
    memory_critical_threshold: float = 92.0
    disk_warning_threshold: float = 80.0
    disk_critical_threshold: float = 90.0
    alert_cooldown_seconds: int = 120

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()