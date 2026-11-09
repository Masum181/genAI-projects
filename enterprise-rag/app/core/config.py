"""Environment-backed settings grouped by infrastructure responsibility."""

from functools import lru_cache

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class _EnvironmentSettings(BaseSettings):
    """Load a settings group from the root environment file and process env."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


class AppSettings(_EnvironmentSettings):
    """Application identity and HTTP behavior."""

    model_config = SettingsConfigDict(
        env_file=".env", env_prefix="APP_", extra="ignore"
    )

    name: str = "Enterprise Knowledge Intelligence Platform"
    version: str = "0.1.0"
    environment: str = "development"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"


class DatabaseSettings(_EnvironmentSettings):
    """PostgreSQL connection settings."""

    model_config = SettingsConfigDict(
        env_file=".env", env_prefix="DATABASE_", extra="ignore"
    )

    url: str = "postgresql+asyncpg://app:change-me@localhost:5432/enterprise_rag"
    echo: bool = False


class QdrantSettings(_EnvironmentSettings):
    """Qdrant vector database connection settings."""

    model_config = SettingsConfigDict(
        env_file=".env", env_prefix="QDRANT_", extra="ignore"
    )

    url: str = "http://localhost:6333"
    api_key: str | None = None
    collection_name: str = "document_chunks"


class RedisSettings(_EnvironmentSettings):
    """Redis connection settings for Celery and cache integrations."""

    model_config = SettingsConfigDict(
        env_file=".env", env_prefix="REDIS_", extra="ignore"
    )

    url: str = "redis://localhost:6379/0"


class StorageSettings(_EnvironmentSettings):
    """S3-compatible object storage settings."""

    model_config = SettingsConfigDict(
        env_file=".env", env_prefix="STORAGE_", extra="ignore"
    )

    endpoint_url: str = "http://localhost:9000"
    bucket: str = "enterprise-rag-documents"
    access_key: str = "replace-me"
    secret_key: str = "replace-me"
    secure: bool = False


class EmbeddingSettings(_EnvironmentSettings):
    """Embedding model selection and vector dimensions."""

    model_config = SettingsConfigDict(
        env_file=".env", env_prefix="EMBEDDING_", extra="ignore"
    )

    provider: str = "sentence_transformers"
    model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    dimensions: int = 384


class LLMSettings(_EnvironmentSettings):
    """Default language model provider and optional provider credentials."""

    model_config = SettingsConfigDict(
        env_file=".env", env_prefix="LLM_", extra="ignore"
    )

    provider: str = "ollama"
    model_name: str = "llama3.1"
    base_url: str = "http://localhost:11434"
    openai_api_key: str | None = None
    gemini_api_key: str | None = None


class Settings(BaseModel):
    """Application settings grouped by their owning subsystem."""

    app: AppSettings = Field(default_factory=AppSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    qdrant: QdrantSettings = Field(default_factory=QdrantSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)
    embedding: EmbeddingSettings = Field(default_factory=EmbeddingSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)


@lru_cache
def get_settings() -> Settings:
    """Return one cached settings object for this process."""
    return Settings()


settings = get_settings()
