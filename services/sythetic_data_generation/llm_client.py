"""LLM client for synthetic test case generation."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from .prompts import SYNTHETIC_GENERATION_PROMPT
from .schemas import SyntheticBatchOutput, SyntheticGenerationRequest

REFERENCE_SAMPLE_CASES_PATH = Path(__file__).with_name("reference") / "sample_cases.jsonl"


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
            build_generation_messages(request)
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


def build_generation_messages(
    request: SyntheticGenerationRequest,
    reference_path: Path = REFERENCE_SAMPLE_CASES_PATH,
) -> list[SystemMessage | HumanMessage]:
    payload: dict[str, object] = {
        "generation_request": request.model_dump(mode="json"),
    }
    if request.include_seed_guidance:
        payload["reference_instruction"] = (
            "Use reference_sample_cases_jsonl as fixed seed examples for style, "
            "metadata shape, and benchmark label conventions. Do not copy them."
        )
        payload["reference_sample_cases_jsonl"] = load_reference_sample_cases_jsonl(reference_path)
    return [
        SystemMessage(content=SYNTHETIC_GENERATION_PROMPT),
        HumanMessage(content=json.dumps(payload, indent=2, ensure_ascii=False)),
    ]


def load_reference_sample_cases_jsonl(path: Path = REFERENCE_SAMPLE_CASES_PATH) -> str:
    if not path.exists():
        raise FileNotFoundError(f"Reference sample cases file not found: {path}")
    rows: list[dict[str, object]] = []
    for line_no, line in enumerate(path.read_text().splitlines(), start=1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSONL at {path}:{line_no}: {exc}") from exc
    if not rows:
        raise ValueError(f"Reference sample cases file is empty: {path}")
    return "\n".join(json.dumps(row, separators=(",", ":"), ensure_ascii=False) for row in rows)
