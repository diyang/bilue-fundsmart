"""LangGraph orchestration for the standalone triage pipeline."""

from __future__ import annotations

import time
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from .llm_client import TriageClient
from .schemas import ComplaintInput, FinalOutput, OutputMetadata, TriageOutput, Version


class ComplaintState(TypedDict, total=False):
    complaint_id: str
    complaint_request: dict[str, Any]
    normalised_complaint: ComplaintInput
    triage_output: TriageOutput
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
        builder.add_node("calibrate_triage_output", self.calibrate_triage_output)
        builder.add_node("risk_safety_check", self.risk_safety_check)
        builder.add_node("set_urgent_escalation_routing", self.set_urgent_escalation_routing)
        builder.add_node("set_standard_routing", self.set_standard_routing)
        builder.add_node("validate_acknowledgement", self.validate_acknowledgement)
        builder.add_node("revise_acknowledgement", self.revise_acknowledgement)
        builder.add_node("save_output", self.save_output)
        builder.add_edge(START, "normalise_complaint")
        builder.add_edge("normalise_complaint", "triage_complaint")
        builder.add_edge("triage_complaint", "calibrate_triage_output")
        builder.add_edge("calibrate_triage_output", "risk_safety_check")
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
        result = self.client.triage(complaint.complaint_document, state["version"])
        return {
            "triage_output": result.triage,
            "acknowledgement_draft": result.acknowledgement_draft,
        }

    def calibrate_triage_output(self, state: ComplaintState) -> dict[str, Any]:
        """Apply deterministic v2 calibration where routing policy is unambiguous."""
        triage = state["triage_output"]
        if state["version"] != "v2":
            return {"triage_output": triage}

        detected = {value.lower() for value in triage.detected_signals}
        vulnerabilities = {value.lower() for value in triage.vulnerability_signals}
        flags = {value.lower() for value in triage.regulatory_flags}
        category = triage.category
        severity = triage.severity
        sla = triage.sla_recommendation

        has_immediate_safety = self.has_immediate_safety_risk(vulnerabilities | detected)
        has_fraud_identity = category == "fraud_or_identity" or any("identity" in value or "fraud" in value for value in flags | detected)
        has_afca_or_regulator = any("afca" in value or "legal" in value or "regulator" in value for value in flags | detected)
        has_responsible_lending = category == "responsible_lending" or any("responsible_lending" in value for value in flags | detected)
        has_collections_pressure = category == "collections" or any("collection" in value or "workplace_contact" in value for value in detected)
        has_app_or_process_error = any("app" in value or "failed" in value or "error" in value or "not_recognised" in value for value in detected)
        has_duplicate_payment = any("duplicate" in value or "two_" in value or "charged_twice" in value for value in detected)

        if category == "fees_charges" and has_duplicate_payment and has_app_or_process_error:
            category = "service_error"

        if has_immediate_safety or has_fraud_identity or has_afca_or_regulator:
            severity = "critical"
            sla = "urgent_review"
        elif has_responsible_lending:
            severity = "high"
            sla = "same_day_acknowledgement"
        elif has_collections_pressure and not vulnerabilities and not flags:
            severity = "medium"
            sla = "standard_acknowledgement"
        elif severity == "critical":
            severity = "high"
            sla = "same_day_acknowledgement"

        calibrated = triage.model_copy(
            update={
                "category": category,
                "severity": severity,
                "sla_recommendation": sla,
            }
        )
        return {"triage_output": calibrated}

    def risk_safety_check(self, state: ComplaintState) -> dict[str, Any]:
        triage = state["triage_output"]
        signals = {value.lower() for value in triage.vulnerability_signals}
        detected = {value.lower() for value in triage.detected_signals}
        flags = {value.lower() for value in triage.regulatory_flags}
        critical = (
            triage.severity == "critical"
            or self.has_immediate_safety_risk(signals | detected)
            or any("identity" in flag or "fraud" in flag for flag in flags)
            or any("afca" in flag or "legal" in flag or "regulator" in flag for flag in flags)
        )
        return {"critical_risk": critical}

    def set_urgent_escalation_routing(self, state: ComplaintState) -> dict[str, Any]:
        triage = state["triage_output"]
        routing = triage.recommended_routing
        if self.has_immediate_safety_risk(
            {value.lower() for value in triage.vulnerability_signals}
            | {value.lower() for value in triage.detected_signals}
        ):
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

    @staticmethod
    def has_immediate_safety_risk(values: set[str]) -> bool:
        safety_markers = (
            "self_harm",
            "self harm",
            "suicid",
            "not safe",
            "unsafe",
            "keep myself safe",
            "can't keep myself safe",
            "cannot keep myself safe",
            "no way out",
            "end it",
            "ended it",
            "immediate_safety",
            "immediate safety",
        )
        return any(any(marker in value for marker in safety_markers) for value in values)

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
        complaint = state["normalised_complaint"]
        triage = state["triage_output"]
        draft = state.get("acknowledgement_draft") or ""
        judge = self.client.validate_acknowledgement(
            complaint_document=complaint.complaint_document,
            triage=triage,
            acknowledgement_draft=draft,
            version=state["version"],
        )
        hard_errors = self.hard_acknowledgement_errors(draft)
        judge_errors = [
            f"LLM judge issue: {issue}" for issue in judge.issues
        ]
        if not judge.grounded:
            judge_errors.append("LLM judge marked acknowledgement as ungrounded.")
        if not judge.coherent:
            judge_errors.append("LLM judge marked acknowledgement as incoherent.")
        if not judge.safe:
            judge_errors.append("LLM judge marked acknowledgement as unsafe.")
        if judge.revision_guidance:
            judge_errors.append(f"LLM judge revision guidance: {judge.revision_guidance}")
        errors = [*hard_errors, *judge_errors]
        valid = judge.is_valid and judge.grounded and judge.coherent and judge.safe and not hard_errors
        return {
            "acknowledgement_valid": valid,
            "acknowledgement_validation_errors": errors,
        }

    @staticmethod
    def hard_acknowledgement_errors(draft: str) -> list[str]:
        errors: list[str] = []
        lower = draft.lower()
        if len(draft.strip()) < 40:
            errors.append("Acknowledgement is too short.")
        if "received" not in lower:
            errors.append("Acknowledgement does not confirm receipt.")
        prohibited = [
            "we will refund",
            "we will waive",
            "we accept liability",
            "we are liable",
            "we admit",
            "we guarantee",
            "your credit file will be fixed",
            "your credit file will be corrected",
        ]
        if any(phrase in lower for phrase in prohibited):
            errors.append("Acknowledgement may admit liability or promise an outcome.")
        return errors

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
                triage_valid=True,
                acknowledgement_valid=state.get("acknowledgement_valid", False),
                retries=state.get("retries", 0),
                critical_risk=state.get("critical_risk", False),
                errors=state.get("errors", []),
                triage_validation_errors=[],
                acknowledgement_validation_errors=state.get("acknowledgement_validation_errors", []),
                input_metadata=complaint.metadata,
            ),
        )
        return {"final_output": output}

    def route_after_risk_check(self, state: ComplaintState) -> str:
        if state.get("critical_risk"):
            return "set_urgent_escalation_routing"
        return "set_standard_routing"

    def route_after_acknowledgement_validation(self, state: ComplaintState) -> str:
        if state.get("acknowledgement_valid") or state.get("retries", 0) >= 2:
            return "save_output"
        return "revise_acknowledgement"
