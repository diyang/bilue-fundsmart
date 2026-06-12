from __future__ import annotations

from triage_service.llm_client import acknowledgement_for


def test_acknowledgement_uses_critical_severity_and_flags() -> None:
    draft = acknowledgement_for(
        category="responsible_lending",
        severity="critical",
        routing="responsible_lending_specialist",
        signals=set(),
        flags={"responsible_lending", "AFCA_escalation_risk", "credit_file_risk"},
        preferences=set(),
    )

    assert "specialist review" in draft
    assert "escalation concern" in draft
    assert "credit file concern" in draft
    assert "urgent review" in draft


def test_acknowledgement_uses_high_severity() -> None:
    draft = acknowledgement_for(
        category="collections",
        severity="high",
        routing="collections_escalation",
        signals={"financial_hardship"},
        flags={"collections_contact"},
        preferences={"prefers_message_or_no_phone_contact"},
    )

    assert "collections contact" in draft
    assert "same-day review" in draft
    assert "communication preference" in draft
