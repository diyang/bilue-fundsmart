"""LangGraph orchestration for the standalone triage pipeline."""

from __future__ import annotations

import time
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from pydantic import ValidationError

from .llm_client import TriageClient
from .schemas import (
    ComplaintInput,
    FinalOutput,
    OutputMetadata,
    TriageLLMOutput,
    TriageOutput,
    Version,
)


class ComplaintState(TypedDict, total=False):
    complaint_id: str
    complaint_request: dict[str, Any]
    normalised_complaint: ComplaintInput
    triage_output: TriageOutput
    triage_valid: bool
    triage_validation_errors: list[str]
    critical_risk: bool
    routing_decision: str
    sla_recommendation: str
    acknowledgement_draft: str
    acknowledgement_valid: bool
    acknowledgement_validation_errors: list[str]
    version: Version
    errors: list[str]
    retries: int
    final_output: FinalOutput
    started_at: float


class TriageGraph:
    def __init__(self, client: TriageClient):
        self.client = client
        self.graph = self.build_graph()

    def invoke(self, complaint: dict[str, Any], version: Version = "v2") -> FinalOutput:
        state: ComplaintState = {
            "complaint_id": str(complaint.get("id", "")),
            "complaint_request": complaint,
            "version": version,
            "errors": [],
            "retries": 0,
            "started_at": time.perf_counter(),
        }
        result = self.graph.invoke(state)
        return result["final_output"]

    def build_graph(self):
        builder = StateGraph(ComplaintState)
        builder.add_node("normalise_complaint", self.normalise_complaint)
        builder.add_node("triage_complaint", self.triage_complaint)
        builder.add_node("validate_triage", self.validate_triage)
        builder.add_node("repair_triage", self.repair_triage)
        builder.add_node("risk_safety_check", self.risk_safety_check)
        builder.add_node("set_urgent_escalation_routing", self.set_urgent_escalation_routing)
        builder.add_node("set_standard_routing", self.set_standard_routing)
        builder.add_node("validate_acknowledgement", self.validate_acknowledgement)
        builder.add_node("revise_acknowledgement", self.revise_acknowledgement)
        builder.add_node("save_output", self.save_output)
        builder.add_edge(START, "normalise_complaint")
        builder.add_edge("normalise_complaint", "triage_complaint")
        builder.add_edge("triage_complaint", "validate_triage")
        builder.add_conditional_edges(
            "validate_triage",
            self.route_after_triage_validation,
            {"risk_safety_check": "risk_safety_check", "repair_triage": "repair_triage"},
        )
        builder.add_edge("repair_triage", "validate_triage")
        builder.add_conditional_edges(
            "risk_safety_check",
            self.route_after_risk_check,
            {
                "set_urgent_escalation_routing": "set_urgent_escalation_routing",
                "set_standard_routing": "set_standard_routing",
            },
        )
        builder.add_edge("set_urgent_escalation_routing", "validate_acknowledgement")
        builder.add_edge("set_standard_routing", "validate_acknowledgement")
        builder.add_conditional_edges(
            "validate_acknowledgement",
            self.route_after_acknowledgement_validation,
            {"save_output": "save_output", "revise_acknowledgement": "revise_acknowledgement"},
        )
        builder.add_edge("revise_acknowledgement", "validate_acknowledgement")
        builder.add_edge("save_output", END)
        return builder.compile()

    def normalise_complaint(self, state: ComplaintState) -> dict[str, Any]:
        complaint = ComplaintInput.model_validate(state["complaint_request"])
        return {"normalised_complaint": complaint, "complaint_id": complaint.id}

    def triage_complaint(self, state: ComplaintState) -> dict[str, Any]:
        complaint = state["normalised_complaint"]
        try:
            result = self.client.triage(complaint.complaint_document, state["version"])
            return {
                "triage_output": result.triage,
                "acknowledgement_draft": result.acknowledgement_draft,
            }
        except Exception as exc:
            errors = [*(state.get("errors") or []), str(exc)]
            fallback = TriageLLMOutput(
                triage=TriageOutput(
                    category="unclear_or_other",
                    severity="medium",
                    recommended_routing="frontline_complaints",
                    sla_recommendation="standard_acknowledgement",
                    extracted_metadata=complaint.metadata,
                    complaint_summary="The complaint could not be triaged by the configured LLM client.",
                    reasoning=f"Fallback used after LLM error: {exc}",
                ),
                acknowledgement_draft="Hi, thank you for contacting FundSmart. We have received your complaint and a team member will review it and follow up with next steps.",
            )
            return {
                "triage_output": fallback.triage,
                "acknowledgement_draft": fallback.acknowledgement_draft,
                "errors": errors,
            }

    def validate_triage(self, state: ComplaintState) -> dict[str, Any]:
        try:
            triage = TriageOutput.model_validate(state["triage_output"])
            return {
                "triage_output": triage,
                "triage_valid": True,
                "triage_validation_errors": [],
            }
        except ValidationError as exc:
            return {
                "triage_valid": False,
                "triage_validation_errors": [str(exc)],
            }

    def repair_triage(self, state: ComplaintState) -> dict[str, Any]:
        retries = state.get("retries", 0) + 1
        if retries > 2:
            errors = [*(state.get("errors") or []), "Triage validation failed after retries."]
            return {"triage_valid": True, "retries": retries, "errors": errors}
        return {"retries": retries, **self.triage_complaint(state)}

    def risk_safety_check(self, state: ComplaintState) -> dict[str, Any]:
        triage = state["triage_output"]
        signals = {value.lower() for value in triage.vulnerability_signals}
        flags = {value.lower() for value in triage.regulatory_flags}
        critical = (
            triage.severity == "critical"
            or any("self_harm" in signal for signal in signals)
            or any("identity" in flag or "fraud" in flag for flag in flags)
            or any("responsible_lending" in flag or "afca" in flag.lower() for flag in flags)
        )
        return {"critical_risk": critical}

    def set_urgent_escalation_routing(self, state: ComplaintState) -> dict[str, Any]:
        triage = state["triage_output"]
        routing = triage.recommended_routing
        if any("self_harm" in signal.lower() for signal in triage.vulnerability_signals):
            routing = "vulnerable_customer_team"
        elif triage.category == "fraud_or_identity":
            routing = "legal_compliance_review"
        elif triage.category == "responsible_lending":
            routing = "responsible_lending_specialist"
        triage = triage.model_copy(
            update={"recommended_routing": routing, "sla_recommendation": "urgent_review"}
        )
        return {
            "triage_output": triage,
            "routing_decision": routing,
            "sla_recommendation": "urgent_review",
        }

    def set_standard_routing(self, state: ComplaintState) -> dict[str, Any]:
        triage = state["triage_output"]
        routing = {
            "service_error": "frontline_complaints",
            "fees_charges": "frontline_complaints",
            "financial_hardship": "hardship_team",
            "responsible_lending": "responsible_lending_specialist",
            "collections": "collections_escalation",
            "fraud_or_identity": "legal_compliance_review",
            "unclear_or_other": "frontline_complaints",
        }[triage.category]
        triage = triage.model_copy(update={"recommended_routing": routing})
        return {
            "triage_output": triage,
            "routing_decision": routing,
            "sla_recommendation": triage.sla_recommendation,
        }

    def validate_acknowledgement(self, state: ComplaintState) -> dict[str, Any]:
        draft = state.get("acknowledgement_draft") or ""
        errors: list[str] = []
        lower = draft.lower()
        if len(draft.strip()) < 40:
            errors.append("Acknowledgement is too short.")
        if "received" not in lower:
            errors.append("Acknowledgement does not confirm receipt.")
        if "sorry" not in lower and "understand" not in lower:
            errors.append("Acknowledgement is not empathetic enough.")
        if any(phrase in lower for phrase in ["we will refund", "we accept liability", "we are liable"]):
            errors.append("Acknowledgement may admit liability or promise an outcome.")
        valid = not errors
        return {
            "acknowledgement_valid": valid,
            "acknowledgement_validation_errors": errors,
        }

    def revise_acknowledgement(self, state: ComplaintState) -> dict[str, Any]:
        retries = state.get("retries", 0) + 1
        if retries > 2:
            return {"retries": retries, "acknowledgement_valid": True}
        triage = state["triage_output"]
        draft = (
            "Hi, thank you for contacting FundSmart. We have received your complaint "
            "and I am sorry to hear about your experience. A human team member will "
            f"review it through {triage.recommended_routing} and follow up with next steps. "
            "This acknowledgement does not determine the outcome of the complaint."
        )
        return {"retries": retries, "acknowledgement_draft": draft}

    def save_output(self, state: ComplaintState) -> dict[str, Any]:
        complaint = state["normalised_complaint"]
        output = FinalOutput(
            id=complaint.id,
            triage=state["triage_output"],
            acknowledgement_draft=state["acknowledgement_draft"],
            metadata=OutputMetadata(
                version=state["version"],
                triage_valid=state.get("triage_valid", False),
                acknowledgement_valid=state.get("acknowledgement_valid", False),
                retries=state.get("retries", 0),
                critical_risk=state.get("critical_risk", False),
                errors=state.get("errors", []),
                triage_validation_errors=state.get("triage_validation_errors", []),
                acknowledgement_validation_errors=state.get("acknowledgement_validation_errors", []),
                input_metadata=complaint.metadata,
            ),
        )
        return {"final_output": output}

    def route_after_triage_validation(self, state: ComplaintState) -> str:
        if state.get("triage_valid") or state.get("retries", 0) >= 2:
            return "risk_safety_check"
        return "repair_triage"

    def route_after_risk_check(self, state: ComplaintState) -> str:
        if state.get("critical_risk"):
            return "set_urgent_escalation_routing"
        return "set_standard_routing"

    def route_after_acknowledgement_validation(self, state: ComplaintState) -> str:
        if state.get("acknowledgement_valid") or state.get("retries", 0) >= 2:
            return "save_output"
        return "revise_acknowledgement"
