from __future__ import annotations

import pytest
from pydantic import ValidationError

from services.sythetic_data_generation.llm_client import (
    build_generation_messages,
    load_reference_sample_cases_jsonl,
)
from services.sythetic_data_generation.schemas import (
    SyntheticGenerationRequest,
    SyntheticTestCase,
)


def test_generation_request_limits_count() -> None:
    with pytest.raises(ValidationError):
        SyntheticGenerationRequest(count=0)

    with pytest.raises(ValidationError):
        SyntheticGenerationRequest(count=51)


def test_synthetic_case_requires_raw_document_shape() -> None:
    with pytest.raises(ValidationError):
        SyntheticTestCase(
            id="SYN-1",
            scenario_type="bad",
            complaint_document="plain text only",
            expected_category="service_error",
            expected_severity="medium",
            expected_routing="frontline_complaints",
            expected_sla="standard_acknowledgement",
        )


def test_reference_sample_cases_are_loaded() -> None:
    reference = load_reference_sample_cases_jsonl()

    assert "SAMPLE-001" in reference
    assert "expected_sla" in reference
    assert "customer_preferences" in reference


def test_generation_messages_include_reference_samples_by_default() -> None:
    messages = build_generation_messages(SyntheticGenerationRequest(count=1))

    assert len(messages) == 2
    assert "reference_sample_cases_jsonl" in messages[1].content
    assert "SAMPLE-001" in messages[1].content


def test_generation_messages_can_omit_reference_samples() -> None:
    messages = build_generation_messages(
        SyntheticGenerationRequest(count=1, include_seed_guidance=False)
    )

    assert "reference_sample_cases_jsonl" not in messages[1].content
    assert "SAMPLE-001" not in messages[1].content
