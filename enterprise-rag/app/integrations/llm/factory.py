"""Construct a configured LLM provider without leaking provider details."""

from functools import lru_cache

from app.core.config import settings
from app.rag.generators.base import LLMGenerator, LLMProviderError
from app.rag.generators.providers.gemini_provider import GeminiGenerator
from app.rag.generators.providers.ollama_provider import OllamaGenerator
from app.rag.generators.providers.openai_provider import OpenAIGenerator


@lru_cache(maxsize=1)
def create_llm_generator() -> LLMGenerator:
    """Create the configured generation provider or fail with actionable context."""
    providers = {
        "ollama": OllamaGenerator,
        "openai": OpenAIGenerator,
        "gemini": GeminiGenerator,
    }
    try:
        provider = providers[settings.llm.provider]
    except KeyError as exc:
        raise LLMProviderError(
            f"Unsupported LLM provider: {settings.llm.provider!r}"
        ) from exc
    return provider()


async def close_llm_generator() -> None:
    """Release a cached provider client during application shutdown."""
    if create_llm_generator.cache_info().currsize:
        await create_llm_generator().close()
        create_llm_generator.cache_clear()
