"""Provider-neutral structured answer generation."""

import json
import logging

from pydantic import ValidationError

from app.core.logging import log_event
from app.rag.generators.base import LLMGenerator, LLMProviderError
from app.rag.prompts.rag_prompt import GroundedPrompt
from app.schemas.chat import GeneratedAnswer

logger = logging.getLogger("app.llm")


async def generate_answer(
    generator: LLMGenerator, prompt: GroundedPrompt
) -> GeneratedAnswer:
    """Call a provider and validate its response against the chat contract."""
    raw_response = await generator.generate(prompt)
    try:
        payload = json.loads(raw_response)
        return GeneratedAnswer.model_validate(payload)
    except (json.JSONDecodeError, ValidationError) as exc:
        log_event(
            logger,
            logging.ERROR,
            "Language model returned an invalid structured answer",
            operation="llm.validate",
            provider=getattr(generator, "provider", None),
            model=getattr(generator, "model_name", None),
            error_code="LLM_PROVIDER_ERROR",
            exception_type=type(exc).__name__,
        )
        raise LLMProviderError(
            "The language model returned an invalid structured answer"
        ) from exc
