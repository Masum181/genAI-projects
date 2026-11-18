"""OpenAI chat-completions provider with JSON-constrained output."""

import logging
import time

from app.core.config import settings
from app.core.logging import log_event
from app.rag.generators.base import LLMProviderError
from app.rag.prompts.rag_prompt import GroundedPrompt

logger = logging.getLogger("app.llm.openai")


class OpenAIGenerator:
    provider = "openai"

    def __init__(self) -> None:
        if not settings.llm.openai_api_key:
            raise LLMProviderError("LLM_OPENAI_API_KEY is required for OpenAI")
        try:
            from openai import APIError, AsyncOpenAI
        except ImportError as exc:
            raise LLMProviderError(
                "Install the project's AI extra to use the OpenAI provider"
            ) from exc
        self.api_error = APIError
        self.model_name = settings.llm.model_name
        self.client = AsyncOpenAI(
            api_key=settings.llm.openai_api_key,
            timeout=settings.llm.timeout_seconds,
            max_retries=2,
        )

    async def close(self) -> None:
        await self.client.close()

    async def generate(self, prompt: GroundedPrompt) -> str:
        started = time.perf_counter()
        log_event(
            logger,
            logging.INFO,
            "OpenAI generation started",
            operation="llm.generate",
            provider="openai",
            model=self.model_name,
        )
        try:
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": prompt.system},
                    {"role": "user", "content": prompt.user},
                ],
                response_format={"type": "json_object"},
                temperature=0,
                max_tokens=settings.llm.max_output_tokens,
            )
        except self.api_error as exc:
            log_event(
                logger,
                logging.ERROR,
                "OpenAI generation failed",
                operation="llm.generate",
                provider="openai",
                model=self.model_name,
                duration_ms=round((time.perf_counter() - started) * 1000),
                http_status=getattr(exc, "status_code", None),
                error_code="LLM_PROVIDER_ERROR",
                exception_type=type(exc).__name__,
            )
            raise LLMProviderError("OpenAI generation request failed") from exc
        text = response.choices[0].message.content
        if not text:
            raise LLMProviderError("OpenAI returned an empty response")
        usage = getattr(response, "usage", None)
        log_event(
            logger,
            logging.INFO,
            "OpenAI generation completed",
            operation="llm.generate",
            provider="openai",
            model=self.model_name,
            duration_ms=round((time.perf_counter() - started) * 1000),
            input_tokens=getattr(usage, "prompt_tokens", None),
            output_tokens=getattr(usage, "completion_tokens", None),
            status="succeeded",
        )
        return text
