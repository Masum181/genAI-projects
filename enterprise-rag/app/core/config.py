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
    secret_key: str = "change-this-secret-before-deployment"
    service_name: str = "api"
    log_level: str = "INFO"
    log_format: str = "json"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7


class DatabaseSettings(_EnvironmentSettings):
    """PostgreSQL connection settings."""

    model_config = SettingsConfigDict(
        env_file=".env", env_prefix="DATABASE_", extra="ignore"
    )
    POSTGRES_DB: str  = "enterprise_rag"
    POSTGRES_USER:str = "postgres"
    POSTGRES_PASSWORD:str = "131192113"
    POSTGES_PORT:str = "5432"
    POSTGRES_HOST:str = "localhost"
    @property
    def url(self) -> str:
        return (
                f"postgresql+asyncpg://"
                f"{self.POSTGRES_USER}:"
                f"{self.POSTGRES_PASSWORD}@"
                f"{self.POSTGRES_HOST}:"
                f"{self.POSTGES_PORT}/"
                f"{self.POSTGRES_DB}"
            )
    # url: str = "postgresql+asyncpg://app:change-me@localhost:5432/enterprise_rag"
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
    ACCESS_KEY: str = "replace-me"
    SECRET_KEY: str = "replace-me"
    secure: bool = False
    region: str = "us-east-1"
    max_upload_bytes: int = 25 * 1024 * 1024


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
    timeout_seconds: float = Field(default=60.0, gt=0)
    max_output_tokens: int = Field(default=2048, gt=0, le=8192)


class RAGSettings(_EnvironmentSettings):
    """Retrieval, reranking, and context limits."""

    model_config = SettingsConfigDict(
        env_file=".env", env_prefix="RAG_", extra="ignore"
    )

    candidate_limit: int = Field(default=40, gt=0, le=500)
    result_limit: int = Field(default=8, gt=0, le=100)
    context_token_limit: int = Field(default=6000, gt=512, le=100_000)
    reranker_model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"


class Settings(BaseModel):
    """Application settings grouped by their owning subsystem."""

    app: AppSettings = Field(default_factory=AppSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    qdrant: QdrantSettings = Field(default_factory=QdrantSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)
    embedding: EmbeddingSettings = Field(default_factory=EmbeddingSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    rag: RAGSettings = Field(default_factory=RAGSettings)


@lru_cache
def get_settings() -> Settings:
    """Return one cached settings object for this process."""
    return Settings()


settings = get_settings()
