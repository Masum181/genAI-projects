"""Provider-neutral interface for grounded answer generation."""

from typing import Protocol

from app.rag.prompts.rag_prompt import GroundedPrompt


class LLMGenerator(Protocol):
    """Contract shared by hosted and local language model providers."""

    provider: str
    model_name: str

    async def generate(self, prompt: GroundedPrompt) -> str:
        """Generate an answer from an already constructed prompt."""

    async def close(self) -> None:
        """Release provider client resources."""


class LLMProviderError(RuntimeError):
    """A provider is unavailable or returned an unusable response."""
