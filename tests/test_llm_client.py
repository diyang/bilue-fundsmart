from __future__ import annotations

import pytest

import services.triage_service.llm_client as llm_client


def test_client_from_env_requires_model(monkeypatch) -> None:
    monkeypatch.delenv("TRIAGE_LLM_MODEL", raising=False)
    monkeypatch.delenv("REASONING_LLM_MODEL", raising=False)

    with pytest.raises(RuntimeError, match="requires an LLM"):
        llm_client.client_from_env()


def test_client_from_env_builds_openai_client(monkeypatch) -> None:
    captured: dict[str, str | None] = {}

    class FakeOpenAIClient:
        def __init__(self, model: str, reasoning_effort: str | None = None):
            captured["model"] = model
            captured["reasoning_effort"] = reasoning_effort

    monkeypatch.setattr(llm_client, "OpenAITriageClient", FakeOpenAIClient)
    monkeypatch.setenv("TRIAGE_LLM_MODEL", "gpt-test")
    monkeypatch.setenv("TRIAGE_LLM_REASONING_EFFORT", "low")

    client = llm_client.client_from_env()

    assert isinstance(client, FakeOpenAIClient)
    assert captured == {"model": "gpt-test", "reasoning_effort": "low"}
