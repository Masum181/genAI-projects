"""Validated structured output contract for grounded chat generation."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class GeneratedAnswer(BaseModel):
    """Model output references only evidence IDs supplied in its prompt."""

    model_config = ConfigDict(extra="forbid")

    answer: str = Field(min_length=1, max_length=20_000)
    citation_ids: list[str] = Field(default_factory=list, max_length=20)
    status: Literal["answered", "insufficient_evidence", "refused"]
    confidence: float | None = Field(default=None, ge=0, le=1)

    @field_validator("answer")
    @classmethod
    def require_non_whitespace_answer(cls, value: str) -> str:
        answer = value.strip()
        if not answer:
            raise ValueError("Answer must contain non-whitespace characters")
        return answer
