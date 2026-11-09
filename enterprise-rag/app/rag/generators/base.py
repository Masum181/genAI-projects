"""Provider-neutral interface for grounded answer generation."""

from typing import Protocol


class LLMGenerator(Protocol):
    """Contract shared by hosted and local language model providers."""

    async def generate(self, prompt: str) -> str:
        """Generate an answer from an already constructed prompt."""
