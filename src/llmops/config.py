from enum import StrEnum

from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(StrEnum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class ObservabilityBackendType(StrEnum):
    LANGFUSE = "langfuse"
    NOOP = "noop"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", ".env.secrets"),
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # App
    app_env: Environment = Environment.DEVELOPMENT
    app_debug: bool = False
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    # Database
    database_url: str = "postgresql+asyncpg://llmops:llmops@localhost:5432/llmops"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # LLM Providers
    anthropic_api_key: str = ""
    gemini_api_key: str = ""

    # Langfuse
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "http://localhost:3000"

    # Observability
    observability_backend: ObservabilityBackendType = ObservabilityBackendType.LANGFUSE

    # Auth
    api_keys: str = ""  # comma-separated

    # Rate Limiting
    rate_limit_requests_per_minute: int = 60

    @property
    def api_key_list(self) -> list[str]:
        return [k.strip() for k in self.api_keys.split(",") if k.strip()]

    @property
    def is_development(self) -> bool:
        return self.app_env == Environment.DEVELOPMENT


settings = Settings()
