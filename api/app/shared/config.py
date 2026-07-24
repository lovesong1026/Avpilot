"""Environment-backed application settings."""

from functools import lru_cache
from urllib.parse import quote_plus

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Avpilot"
    app_env: str = "development"
    app_debug: bool = True
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    cors_origins: str = "http://localhost:5173"

    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "avpilot"
    postgres_password: str = "avpilot"
    postgres_db: str = "avpilot"
    postgres_pool_size: int = 10
    postgres_max_overflow: int = 20

    elasticsearch_url: str = "http://localhost:19200"
    elasticsearch_request_timeout: float = 10.0
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "avpilot-neo4j"
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"
    health_check_timeout_seconds: float = 3.0
    storage_path: str = "storage"
    max_upload_size_mb: int = 25

    jwt_secret: str = "development-only-change-me-please"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 30

    dashscope_api_key: str = ""
    bailian_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    bailian_chat_model: str = "qwen-plus"
    bailian_vision_model: str = "qwen-vl-plus"
    bailian_embedding_model: str = "text-embedding-v4"
    bailian_embedding_dimensions: int = 1024
    bailian_rerank_model: str = "qwen3-rerank"
    bailian_workspace_id: str = ""
    bailian_rerank_base_url: str = ""
    agent_mode: str = "auto"
    agent_max_steps: int = 4
    agent_tool_timeout_seconds: float = 30.0
    agent_react_model: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def database_url(self) -> str:
        user = quote_plus(self.postgres_user)
        password = quote_plus(self.postgres_password)
        return (
            f"postgresql+asyncpg://{user}:{password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
