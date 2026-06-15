from __future__ import annotations

from fastapi.testclient import TestClient

import services.triage_service.app as app_module
from services.triage_service.schemas import (
    AcknowledgementJudgeOutput,
    TriageLLMOutput,
    TriageOutput,
)


class FakeTriageClient:
    def triage(self, complaint_document: str, version: str):
        return (
            TriageLLMOutput(
                triage=TriageOutput(
                    category="fees_charges",
                    severity="medium",
                    detected_signals=["duplicate_charge", "refund_request"],
                    recommended_routing="frontline_complaints",
                    sla_recommendation="standard_acknowledgement",
                    extracted_metadata={
                        "channel": "Email",
                        "received": "2026-04-18 09:12 AEST",
                        "customer_id": "CUST-1",
                    },
                    complaint_summary="The customer says they were charged twice.",
                    reasoning="The complaint disputes a duplicate charge.",
                ),
                acknowledgement_draft=(
                    "Hi, thank you for contacting FundSmart. We have received your "
                    "complaint and I am sorry to hear about your experience. A team "
                    "member will review the issue and follow up with next steps."
                ),
            ),
            {
                "call": "triage",
                "input_tokens": 10,
                "output_tokens": 20,
                "total_tokens": 30,
            },
        )

    def validate_acknowledgement(
        self,
        complaint_document: str,
        triage: TriageOutput,
        acknowledgement_draft: str,
        version: str,
    ):
        return (
            AcknowledgementJudgeOutput(
                is_valid=True,
                grounded=True,
                coherent=True,
                safe=True,
                issues=[],
            ),
            {
                "call": "acknowledgement_judge",
                "input_tokens": 5,
                "output_tokens": 6,
                "total_tokens": 11,
            },
        )


def install_fake_llm(monkeypatch) -> None:
    monkeypatch.setattr(app_module, "client_from_env", lambda: FakeTriageClient())


def test_health_endpoint(monkeypatch) -> None:
    install_fake_llm(monkeypatch)
    with TestClient(app_module.app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["provider"] == "openai"


def test_triage_endpoint_uses_complaint_document(monkeypatch) -> None:
    install_fake_llm(monkeypatch)
    request = {
        "id": "CASE-1",
        "complaint_document": (
            "**Channel:** Email\n"
            "**Received:** 2026-04-18 09:12 AEST\n"
            "**Customer ID:** CUST-1\n\n"
            "```\nYou charged me twice this month. Fix it and refund me.\n```"
        ),
    }

    with TestClient(app_module.app) as client:
        response = client.post("/triage", json=request)

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "CASE-1"
    assert body["triage"]["category"] == "fees_charges"
    assert body["triage"]["detected_signals"] == ["duplicate_charge", "refund_request"]
    assert body["metadata"]["version"] == "v2"
    assert body["metadata"]["token_usage"]["totals"]["total_tokens"] == 41
    assert "triage_complaint" in body["metadata"]["step_latency_seconds"]
    assert body["metadata"]["step_invocation_counts"]["validate_acknowledgement"] == 1
