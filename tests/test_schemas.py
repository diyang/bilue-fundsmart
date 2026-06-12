from __future__ import annotations

import pytest
from pydantic import ValidationError

from triage_service.schemas import ComplaintInput, TriageOutput


def test_complaint_input_requires_complaint_document() -> None:
    with pytest.raises(ValidationError):
        ComplaintInput(id="CASE-1", complaint_document="")


def test_triage_output_rejects_unknown_category() -> None:
    with pytest.raises(ValidationError):
        TriageOutput(
            category="bad_category",
            severity="medium",
            recommended_routing="frontline_complaints",
            sla_recommendation="standard_acknowledgement",
            complaint_summary="summary",
            reasoning="reasoning",
        )
