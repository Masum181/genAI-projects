"""Local Ollama chat-completion provider."""

import asyncio
import json
import logging
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.core.config import settings
from app.core.logging import log_event
from app.rag.generators.base import LLMProviderError
from app.rag.prompts.rag_prompt import GroundedPrompt

logger = logging.getLogger("app.llm.ollama")


class OllamaGenerator:
    provider = "ollama"

    def __init__(self) -> None:
        self.model_name = settings.llm.model_name
        self.base_url = settings.llm.base_url.rstrip("/")

    async def close(self) -> None:
        """Ollama requests do not retain a client connection."""

    async def generate(self, prompt: GroundedPrompt) -> str:
        return await asyncio.to_thread(self._generate, prompt)

    def _generate(self, prompt: GroundedPrompt) -> str:
        started = time.perf_counter()
        log_event(
            logger,
            logging.INFO,
            "Ollama generation started",
            operation="llm.generate",
            provider="ollama",
            model=self.model_name,
            base_url=self.base_url,
        )
        body = json.dumps(
            {
                "model": self.model_name,
                "messages": [
                    {"role": "system", "content": prompt.system},
                    {"role": "user", "content": prompt.user},
                ],
                "stream": False,
                "format": "json",
                "options": {
                    "temperature": 0,
                    "num_predict": settings.llm.max_output_tokens,
                },
            }
        ).encode("utf-8")
        request = Request(
            f"{self.base_url}/api/chat",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=settings.llm.timeout_seconds) as response:
                http_status = getattr(response, "status", 200)
                response_body = response.read(4_000_001)
            if len(response_body) > 4_000_000:
                raise LLMProviderError("Ollama response exceeded the size limit")
            result = json.loads(response_body.decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            log_event(
                logger,
                logging.ERROR,
                "Ollama generation failed",
                operation="llm.generate",
                provider="ollama",
                model=self.model_name,
                http_status=getattr(exc, "code", None),
                duration_ms=round((time.perf_counter() - started) * 1000),
                error_code="LLM_PROVIDER_ERROR",
                exception_type=type(exc).__name__,
            )
            raise LLMProviderError("Ollama generation request failed") from exc
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            log_event(
                logger,
                logging.ERROR,
                "Ollama returned invalid JSON",
                operation="llm.parse",
                provider="ollama",
                model=self.model_name,
                error_code="LLM_PROVIDER_ERROR",
            )
            raise LLMProviderError("Ollama returned an invalid response") from exc
        if not isinstance(result, dict):
            raise LLMProviderError("Ollama returned an invalid response")
        message = result.get("message")
        text = message.get("content") if isinstance(message, dict) else None
        if not isinstance(text, str) or not text.strip():
            raise LLMProviderError("Ollama returned an empty response")
        log_event(
            logger,
            logging.INFO,
            "Ollama generation completed",
            operation="llm.generate",
            provider="ollama",
            model=self.model_name,
            http_status=http_status,
            duration_ms=round((time.perf_counter() - started) * 1000),
            status="succeeded",
        )
        return text
