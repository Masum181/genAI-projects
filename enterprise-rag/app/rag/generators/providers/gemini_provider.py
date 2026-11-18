"""Google Gemini generation provider with JSON-constrained output."""

import logging
import time

from app.core.config import settings
from app.core.logging import log_event
from app.rag.generators.base import LLMProviderError
from app.rag.prompts.rag_prompt import GroundedPrompt

logger = logging.getLogger("app.llm.gemini")


class GeminiGenerator:
    provider = "gemini"

    def __init__(self) -> None:
        if not settings.llm.gemini_api_key:
            raise LLMProviderError("LLM_GEMINI_API_KEY is required for Gemini")
        try:
            from google import genai
            from google.genai import types
            from google.genai.errors import APIError
        except ImportError as exc:
            raise LLMProviderError(
                "Install the project's AI extra to use the Gemini provider"
            ) from exc
        self.model_name = settings.llm.model_name
        self.api_error = APIError
        self._types = types
        self.client = genai.Client(api_key=settings.llm.gemini_api_key)

    async def close(self) -> None:
        await self.client.aio.aclose()

    async def generate(self, prompt: GroundedPrompt) -> str:
        started = time.perf_counter()
        log_event(
            logger,
            logging.INFO,
            "Gemini generation started",
            operation="llm.generate",
            provider="gemini",
            model=self.model_name,
        )
        try:
            response = await self.client.aio.models.generate_content(
                model=self.model_name,
                contents=prompt.user,
                config=self._types.GenerateContentConfig(
                    response_mime_type="application/json",
                    system_instruction=prompt.system,
                    temperature=0,
                    max_output_tokens=settings.llm.max_output_tokens,
                ),
            )
        except self.api_error as exc:
            log_event(
                logger,
                logging.ERROR,
                "Gemini generation failed",
                operation="llm.generate",
                provider="gemini",
                model=self.model_name,
                duration_ms=round((time.perf_counter() - started) * 1000),
                http_status=getattr(exc, "code", None),
                error_code="LLM_PROVIDER_ERROR",
                exception_type=type(exc).__name__,
            )
            raise LLMProviderError("Gemini generation request failed") from exc
        if not response.text:
            raise LLMProviderError("Gemini returned an empty response")
        log_event(
            logger,
            logging.INFO,
            "Gemini generation completed",
            operation="llm.generate",
            provider="gemini",
            model=self.model_name,
            duration_ms=round((time.perf_counter() - started) * 1000),
            status="succeeded",
        )
        return response.text
