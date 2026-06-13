from __future__ import annotations

import pytest
from pydantic import ValidationError

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
