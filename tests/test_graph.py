from __future__ import annotations

from services.triage_service.graph import TriageGraph
from services.triage_service.schemas import (
    AcknowledgementJudgeOutput,
    TriageLLMOutput,
    TriageOutput,
)


class StaticTriageClient:
    def __init__(self, triage: TriageOutput):
        self.triage_output = triage

    def triage(self, complaint_document: str, version: str) -> TriageLLMOutput:
        return TriageLLMOutput(
            triage=self.triage_output,
            acknowledgement_draft=(
                "Hi, thank you for contacting FundSmart. We have received your "
                "complaint and I am sorry to hear about your experience. A team "
                "member will review the issue and follow up with next steps."
            ),
        )

    def validate_acknowledgement(
        self,
        complaint_document: str,
        triage: TriageOutput,
        acknowledgement_draft: str,
        version: str,
    ) -> AcknowledgementJudgeOutput:
        return AcknowledgementJudgeOutput(
            is_valid=True,
            grounded=True,
            coherent=True,
            safe=True,
            issues=[],
        )


def invoke_with_triage(triage: TriageOutput):
    graph = TriageGraph(StaticTriageClient(triage))
    return graph.invoke(
        {
            "id": "CASE-1",
            "complaint_document": (
                "**Channel:** Email\n"
                "**Received:** 2026-05-05 18:06 AEST\n"
                "**Customer ID:** CUST-1\n\n"
                "```\nComplaint body.\n```"
            ),
        },
        version="v2",
    )


def test_v2_calibrates_collections_without_risk_to_medium() -> None:
    output = invoke_with_triage(
        TriageOutput(
            category="collections",
            severity="high",
            detected_signals=["collections_contact", "calls_at_work", "payment_dispute"],
            recommended_routing="collections_escalation",
            sla_recommendation="same_day_acknowledgement",
            complaint_summary="Collections contact complaint.",
            reasoning="The complaint is about collections calls.",
        )
    )

    assert output.triage.category == "collections"
    assert output.triage.severity == "medium"
    assert output.triage.recommended_routing == "collections_escalation"
    assert output.triage.sla_recommendation == "standard_acknowledgement"


def test_v2_calibrates_duplicate_payment_app_error_to_service_error() -> None:
    output = invoke_with_triage(
        TriageOutput(
            category="fees_charges",
            severity="medium",
            detected_signals=[
                "duplicate_payment_two_286_same_day",
                "app_showed_first_payment_failed",
                "refund_request",
            ],
            recommended_routing="frontline_complaints",
            sla_recommendation="standard_acknowledgement",
            complaint_summary="Duplicate payment after app failure.",
            reasoning="The complaint is about a duplicate payment.",
        )
    )

    assert output.triage.category == "service_error"
    assert output.triage.severity == "medium"
    assert output.triage.recommended_routing == "frontline_complaints"


def test_v2_calibrates_responsible_lending_without_afca_to_high() -> None:
    output = invoke_with_triage(
        TriageOutput(
            category="responsible_lending",
            severity="critical",
            detected_signals=["responsible_lending", "financial_counsellor", "arrears"],
            regulatory_flags=["responsible_lending_allegation"],
            recommended_routing="responsible_lending_specialist",
            sla_recommendation="urgent_review",
            complaint_summary="Responsible lending complaint without AFCA.",
            reasoning="The customer says the loan should not have been approved.",
        )
    )

    assert output.triage.category == "responsible_lending"
    assert output.triage.severity == "high"
    assert output.triage.recommended_routing == "responsible_lending_specialist"
    assert output.triage.sla_recommendation == "same_day_acknowledgement"


def test_v2_routes_plain_language_self_harm_to_vulnerable_customer_team() -> None:
    output = invoke_with_triage(
        TriageOutput(
            category="financial_hardship",
            severity="high",
            detected_signals=["repayment_pause_request", "collections_contact"],
            vulnerability_signals=[
                "states they are not safe tonight",
                "suicidal thoughts about ending their life",
                "lost job two weeks ago",
            ],
            recommended_routing="hardship_team",
            sla_recommendation="same_day_acknowledgement",
            complaint_summary="Customer is in hardship and has immediate safety risk.",
            reasoning="The customer is in hardship and says they are not safe tonight.",
        )
    )

    assert output.triage.category == "financial_hardship"
    assert output.triage.severity == "critical"
    assert output.triage.recommended_routing == "vulnerable_customer_team"
    assert output.triage.sla_recommendation == "urgent_review"
