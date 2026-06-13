"""LLM client for the standalone triage pipeline."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Protocol

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from .prompts import ACKNOWLEDGEMENT_JUDGE_PROMPT, get_triage_prompt
from .schemas import AcknowledgementJudgeOutput, TriageLLMOutput, TriageOutput, Version


class TriageClient(Protocol):
    def triage(self, complaint_document: str, version: Version) -> TriageLLMOutput:
        """Return structured triage and acknowledgement for complaint_document."""

    def validate_acknowledgement(
        self,
        complaint_document: str,
        triage: TriageOutput,
        acknowledgement_draft: str,
        version: Version,
    ) -> AcknowledgementJudgeOutput:
        """Judge acknowledgement groundedness, coherence, and safety."""


@dataclass(frozen=True)
class OpenAITriageClient:
    model: str
    reasoning_effort: str | None = "medium"

    def __post_init__(self) -> None:
        kwargs: dict[str, object] = {"model": self.model}
        if self.reasoning_effort:
            kwargs["reasoning_effort"] = self.reasoning_effort
        object.__setattr__(
            self,
            "_model",
            ChatOpenAI(**kwargs).with_structured_output(TriageLLMOutput),
        )
        object.__setattr__(
            self,
            "_acknowledgement_judge_model",
            ChatOpenAI(**kwargs).with_structured_output(AcknowledgementJudgeOutput),
        )

    def triage(self, complaint_document: str, version: Version) -> TriageLLMOutput:
        return self._model.invoke(
            [
                SystemMessage(content=get_triage_prompt(version)),
                HumanMessage(content=complaint_document),
            ]
        )

    def validate_acknowledgement(
        self,
        complaint_document: str,
        triage: TriageOutput,
        acknowledgement_draft: str,
        version: Version,
    ) -> AcknowledgementJudgeOutput:
        judge_input = {
            "version": version,
            "complaint_document": complaint_document,
            "triage": triage.model_dump(mode="json"),
            "acknowledgement_draft": acknowledgement_draft,
        }
        return self._acknowledgement_judge_model.invoke(
            [
                SystemMessage(content=ACKNOWLEDGEMENT_JUDGE_PROMPT),
                HumanMessage(content=json.dumps(judge_input, ensure_ascii=False)),
            ]
        )


def client_from_env() -> TriageClient:
    model = model_from_env()
    if not model:
        raise RuntimeError(
            "Set TRIAGE_LLM_MODEL or REASONING_LLM_MODEL for triage_service. "
            "The triage service requires an LLM."
        )
    return OpenAITriageClient(
        model=model,
        reasoning_effort=(
            os.getenv("TRIAGE_LLM_REASONING_EFFORT")
            or os.getenv("REASONING_LLM_REASONING_EFFORT")
            or "medium"
        ),
    )


def provider_from_env() -> str:
    return "openai"


def model_from_env() -> str | None:
    return os.getenv("TRIAGE_LLM_MODEL") or os.getenv("REASONING_LLM_MODEL")
