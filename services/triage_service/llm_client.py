"""LLM client for the standalone triage pipeline."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Protocol

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from .prompts import ACKNOWLEDGEMENT_JUDGE_PROMPT, get_triage_prompt
from .schemas import AcknowledgementJudgeOutput, TriageLLMOutput, TriageOutput, Version

LLMUsage = dict[str, Any]


class TriageClient(Protocol):
    def triage(
        self, complaint_document: str, version: Version
    ) -> tuple[TriageLLMOutput, LLMUsage]:
        """Return structured triage output and token usage for complaint_document."""

    def validate_acknowledgement(
        self,
        complaint_document: str,
        triage: TriageOutput,
        acknowledgement_draft: str,
        version: Version,
    ) -> tuple[AcknowledgementJudgeOutput, LLMUsage]:
        """Judge acknowledgement quality and return token usage."""


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
            ChatOpenAI(**kwargs).with_structured_output(
                TriageLLMOutput, include_raw=True
            ),
        )
        object.__setattr__(
            self,
            "_acknowledgement_judge_model",
            ChatOpenAI(**kwargs).with_structured_output(
                AcknowledgementJudgeOutput, include_raw=True
            ),
        )

    def triage(
        self, complaint_document: str, version: Version
    ) -> tuple[TriageLLMOutput, LLMUsage]:
        result = self._model.invoke(
            [
                SystemMessage(content=get_triage_prompt(version)),
                HumanMessage(content=complaint_document),
            ]
        )
        return self._parsed_with_usage(result, "triage")

    def validate_acknowledgement(
        self,
        complaint_document: str,
        triage: TriageOutput,
        acknowledgement_draft: str,
        version: Version,
    ) -> tuple[AcknowledgementJudgeOutput, LLMUsage]:
        judge_input = {
            "version": version,
            "complaint_document": complaint_document,
            "triage": triage.model_dump(mode="json"),
            "acknowledgement_draft": acknowledgement_draft,
        }
        result = self._acknowledgement_judge_model.invoke(
            [
                SystemMessage(content=ACKNOWLEDGEMENT_JUDGE_PROMPT),
                HumanMessage(content=json.dumps(judge_input, ensure_ascii=False)),
            ]
        )
        return self._parsed_with_usage(result, "acknowledgement_judge")

    @staticmethod
    def _parsed_with_usage(result: Any, call_name: str) -> tuple[Any, LLMUsage]:
        if not isinstance(result, dict) or "parsed" not in result:
            return result, {"call": call_name}

        if result.get("parsing_error") is not None:
            raise RuntimeError(
                f"{call_name} structured output parsing failed: "
                f"{result['parsing_error']}"
            )

        parsed = result.get("parsed")
        if parsed is None:
            raise RuntimeError(f"{call_name} structured output returned no parsed value.")

        return parsed, OpenAITriageClient._extract_token_usage(result.get("raw"), call_name)

    @staticmethod
    def _extract_token_usage(raw_message: Any, call_name: str) -> LLMUsage:
        usage_metadata = getattr(raw_message, "usage_metadata", None) or {}
        response_metadata = getattr(raw_message, "response_metadata", None) or {}
        token_usage = response_metadata.get("token_usage") or {}

        input_tokens = (
            usage_metadata.get("input_tokens")
            or token_usage.get("input_tokens")
            or token_usage.get("prompt_tokens")
            or 0
        )
        output_tokens = (
            usage_metadata.get("output_tokens")
            or token_usage.get("output_tokens")
            or token_usage.get("completion_tokens")
            or 0
        )
        total_tokens = (
            usage_metadata.get("total_tokens")
            or token_usage.get("total_tokens")
            or (input_tokens + output_tokens)
        )
        usage: LLMUsage = {
            "call": call_name,
            "input_tokens": int(input_tokens or 0),
            "output_tokens": int(output_tokens or 0),
            "total_tokens": int(total_tokens or 0),
        }
        for detail_key in ("input_token_details", "output_token_details"):
            detail_value = usage_metadata.get(detail_key)
            if isinstance(detail_value, dict):
                usage[detail_key] = detail_value
        return usage


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
