"""LLM client for synthetic test case generation."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Protocol

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from .prompts import SYNTHETIC_GENERATION_PROMPT
from .schemas import SyntheticBatchOutput, SyntheticGenerationRequest


class SyntheticDataClient(Protocol):
    def generate(self, request: SyntheticGenerationRequest) -> SyntheticBatchOutput:
        """Generate a batch of synthetic triage benchmark cases with an LLM."""


@dataclass(frozen=True)
class OpenAISyntheticDataClient:
    model: str
    reasoning_effort: str | None = "medium"

    def __post_init__(self) -> None:
        kwargs: dict[str, object] = {"model": self.model}
        if self.reasoning_effort:
            kwargs["reasoning_effort"] = self.reasoning_effort
        object.__setattr__(
            self,
            "_model",
            ChatOpenAI(**kwargs).with_structured_output(SyntheticBatchOutput),
        )

    def generate(self, request: SyntheticGenerationRequest) -> SyntheticBatchOutput:
        return self._model.invoke(
            [
                SystemMessage(content=SYNTHETIC_GENERATION_PROMPT),
                HumanMessage(content=request.model_dump_json(indent=2)),
            ]
        )


def client_from_env() -> SyntheticDataClient:
    provider = provider_from_env()
    if provider != "openai":
        raise RuntimeError(
            "Synthetic data generation only supports LLM provider 'openai'. "
            f"Received: {provider!r}."
        )
    model = model_from_env()
    if not model:
        raise RuntimeError(
            "Set SYNTHETIC_DATA_LLM_MODEL or REASONING_LLM_MODEL for synthetic "
            "data generation."
        )
    return OpenAISyntheticDataClient(
        model=model,
        reasoning_effort=(
            os.getenv("SYNTHETIC_DATA_LLM_REASONING_EFFORT")
            or os.getenv("REASONING_LLM_REASONING_EFFORT")
            or "medium"
        ),
    )


def provider_from_env() -> str:
    return os.getenv("SYNTHETIC_DATA_LLM_PROVIDER", "openai").strip().lower()


def model_from_env() -> str | None:
    return os.getenv("SYNTHETIC_DATA_LLM_MODEL") or os.getenv("REASONING_LLM_MODEL")
