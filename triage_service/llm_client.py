"""Swappable LLM clients for the standalone triage pipeline."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Protocol

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from .prompts import get_triage_prompt
from .schemas import (
    ComplaintMetadata,
    SLARecommendation,
    TriageLLMOutput,
    TriageOutput,
    Version,
)


class TriageClient(Protocol):
    def triage(self, complaint_document: str, version: Version) -> TriageLLMOutput:
        """Return structured triage and acknowledgement for complaint_document."""


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
            ChatOpenAI(**kwargs).with_structured_output(TriageLLMOutput),
        )

    def triage(self, complaint_document: str, version: Version) -> TriageLLMOutput:
        return self._model.invoke(
            [
                SystemMessage(content=get_triage_prompt(version)),
                HumanMessage(content=complaint_document),
            ]
        )


class HeuristicTriageClient:
    """Deterministic fallback so the standalone harness runs without API keys."""

    def triage(self, complaint_document: str, version: Version) -> TriageLLMOutput:
        text = complaint_document.lower()
        metadata = extract_metadata(complaint_document)
        vulnerability_signals = vulnerability_for(text)
        regulatory_flags = flags_for(text)
        customer_preferences = preferences_for(text)
        category = category_for(text, vulnerability_signals, regulatory_flags)
        severity = severity_for(text, category, vulnerability_signals, regulatory_flags, version)
        routing = routing_for(category, severity, vulnerability_signals, regulatory_flags)
        sla = sla_for(severity)

        triage = TriageOutput(
            category=category,
            severity=severity,
            vulnerability_signals=sorted(vulnerability_signals),
            regulatory_flags=sorted(regulatory_flags),
            recommended_routing=routing,
            sla_recommendation=sla,
            customer_preferences=sorted(customer_preferences),
            extracted_metadata=metadata,
            complaint_summary=summary_for(category, text),
            reasoning=reasoning_for(category, severity, vulnerability_signals, regulatory_flags),
        )
        return TriageLLMOutput(
            triage=triage,
            acknowledgement_draft=acknowledgement_for(
                category,
                severity,
                routing,
                vulnerability_signals,
                regulatory_flags,
                customer_preferences,
            ),
        )


def client_from_env() -> TriageClient:
    provider = os.getenv("TRIAGE_LLM_PROVIDER", "heuristic").strip().lower()
    if provider == "openai":
        model = os.getenv("TRIAGE_LLM_MODEL")
        if not model:
            raise RuntimeError("Set TRIAGE_LLM_MODEL when TRIAGE_LLM_PROVIDER=openai.")
        return OpenAITriageClient(
            model=model,
            reasoning_effort=os.getenv("TRIAGE_LLM_REASONING_EFFORT", "medium"),
        )
    return HeuristicTriageClient()


def extract_metadata(complaint_document: str) -> ComplaintMetadata:
    fields = {
        "Channel": "channel",
        "Received": "received",
        "Customer ID": "customer_id",
        "Subject": "subject",
        "Thread context": "thread_context",
        "Agent": "agent",
        "Duration": "duration",
        "Note": "note",
    }
    values = {field: None for field in fields.values()}
    header = complaint_document.split("```", 1)[0]
    for line in header.splitlines():
        match = re.fullmatch(r"\*\*(.+?):\*\*\s*(.*)", line)
        if match and match.group(1) in fields:
            values[fields[match.group(1)]] = match.group(2)
    return ComplaintMetadata(**values)


def has_any(text: str, terms: list[str]) -> bool:
    return any(term in text for term in terms)


def vulnerability_for(text: str) -> set[str]:
    signals: set[str] = set()
    if has_any(text, ["keep myself safe", "no way out", "self-harm", "suicide"]):
        signals.add("self_harm_signal")
    if has_any(text, ["lost my job", "pay cut", "lost shifts", "back at work"]):
        signals.add("reduced_income")
    if has_any(text, ["can't afford", "cannot afford", "pause the loan", "repayments smaller", "choose between paying rent"]):
        signals.add("financial_hardship")
    if has_any(text, ["wife moved out", "two kids", "daycare", "seven year old"]):
        signals.add("family_or_dependent_vulnerability")
    if has_any(text, ["surgery", "havent slept", "haven't slept", "2am"]):
        signals.add("health_or_distress_signal")
    if has_any(text, ["english not good", "message me here"]):
        signals.add("communication_need")
    return signals


def flags_for(text: str) -> set[str]:
    flags: set[str] = set()
    if has_any(text, ["responsible lending", "should have got that loan", "should never have been approved", "affordability"]):
        flags.add("responsible_lending")
    if "afca" in text:
        flags.add("AFCA_escalation_risk")
    if has_any(text, ["identity", "never applied", "opened in my name", "used my identity"]):
        flags.add("identity_theft")
    if has_any(text, ["credit file", "bad credit", "late mark"]):
        flags.add("credit_file_risk")
    if has_any(text, ["collections", "calls", "texts saying i am overdue"]):
        flags.add("collections_contact")
    if has_any(text, ["legal", "regulator"]):
        flags.add("legal_or_regulator_escalation")
    return flags


def preferences_for(text: str) -> set[str]:
    preferences: set[str] = set()
    if has_any(text, ["do not want to talk on the phone", "cannot take calls", "message me here", "no phone"]):
        preferences.add("prefers_message_or_no_phone_contact")
    return preferences


def category_for(text: str, signals: set[str], flags: set[str]) -> str:
    if "identity_theft" in flags:
        return "fraud_or_identity"
    if "responsible_lending" in flags:
        return "responsible_lending"
    if "collections_contact" in flags and has_any(text, ["arrangement", "lost my job", "calls", "texts"]):
        return "collections"
    if "financial_hardship" in signals and not has_any(text, ["late fee", "dishonour fee"]):
        return "financial_hardship"
    if has_any(text, ["late fee", "dishonour fee", "charged me twice", "late mark"]):
        return "financial_hardship" if "financial_hardship" in signals else "fees_charges"
    if has_any(text, ["insurance claim", "do not have a loan"]):
        return "unclear_or_other"
    if has_any(text, ["app", "uploaded", "documents", "direct debit", "pay already", "logging me out"]):
        return "service_error"
    return "unclear_or_other"


def severity_for(
    text: str,
    category: str,
    signals: set[str],
    flags: set[str],
    version: Version,
) -> str:
    if (
        "self_harm_signal" in signals
        or "identity_theft" in flags
        or "responsible_lending" in flags
        or "AFCA_escalation_risk" in flags
    ):
        return "critical"
    if category == "unclear_or_other" and has_any(text, ["insurance claim", "do not have a loan"]):
        return "low"
    if category == "service_error" and has_any(text, ["logging me out", "statement"]):
        return "low"
    if signals or category in {"financial_hardship", "collections"}:
        return "high"
    if category in {"fees_charges", "service_error"}:
        return "medium"
    if version == "v1" and has_any(text, ["useless", "senior", "really not happy"]):
        return "high"
    return "medium"


def routing_for(category: str, severity: str, signals: set[str], flags: set[str]) -> str:
    if severity == "critical":
        if "self_harm_signal" in signals:
            return "vulnerable_customer_team"
        if "identity_theft" in flags:
            return "legal_compliance_review"
        if "responsible_lending" in flags or "AFCA_escalation_risk" in flags:
            return "responsible_lending_specialist"
    return {
        "service_error": "frontline_complaints",
        "fees_charges": "frontline_complaints",
        "financial_hardship": "hardship_team",
        "responsible_lending": "responsible_lending_specialist",
        "collections": "collections_escalation",
        "fraud_or_identity": "legal_compliance_review",
        "unclear_or_other": "frontline_complaints",
    }[category]


def sla_for(severity: str) -> SLARecommendation:
    if severity == "critical":
        return "urgent_review"
    if severity == "high":
        return "same_day_acknowledgement"
    return "standard_acknowledgement"


def summary_for(category: str, text: str) -> str:
    if "charged me twice" in text:
        return "The customer says they were charged twice and wants a refund."
    return {
        "service_error": "The customer raises a FundSmart service or process issue.",
        "financial_hardship": "The customer describes financial pressure or asks for repayment support.",
        "responsible_lending": "The customer alleges the loan may have been unaffordable or unsuitable.",
        "collections": "The customer complains about collections contact or a payment arrangement.",
        "fees_charges": "The customer disputes a fee, charge, or payment mark.",
        "fraud_or_identity": "The customer reports possible identity theft or an unauthorised loan.",
        "unclear_or_other": "The complaint is unclear or may relate to the wrong company or product.",
    }[category]


def reasoning_for(category: str, severity: str, signals: set[str], flags: set[str]) -> str:
    parts = [f"Classified as {category} with {severity} severity."]
    if signals:
        parts.append(f"Vulnerability signals: {', '.join(sorted(signals))}.")
    if flags:
        parts.append(f"Regulatory or escalation flags: {', '.join(sorted(flags))}.")
    if not signals and not flags:
        parts.append("No explicit hardship, safety, fraud, responsible lending, AFCA, or legal escalation signal was found.")
    return " ".join(parts)


def acknowledgement_for(
    category: str,
    severity: str,
    routing: str,
    signals: set[str],
    flags: set[str],
    preferences: set[str],
) -> str:
    lines = [
        "Hi, thank you for contacting FundSmart. We have received your complaint and I am sorry to hear about your experience.",
    ]
    if "self_harm_signal" in signals:
        lines.append("Because you mentioned you may not be safe, we will treat this as urgent. If you are in immediate danger, please contact emergency services or crisis support now.")
    elif "identity_theft" in flags or category == "fraud_or_identity":
        lines.append("We will arrange urgent review of the possible unauthorised loan and credit file concern.")
    elif "responsible_lending" in flags or category == "responsible_lending":
        lines.append("We will refer the lending and affordability concerns for specialist review.")
    elif category == "financial_hardship":
        lines.append("We will refer your request to the hardship team so support options can be reviewed.")
    elif "collections_contact" in flags or category == "collections":
        lines.append("We will review the collections contact and payment arrangement concerns you raised.")
    else:
        lines.append("A complaints team member will review the details and follow up with next steps.")

    if "AFCA_escalation_risk" in flags or "legal_or_regulator_escalation" in flags:
        lines.append("We will make sure the escalation concern is included in the review.")
    if "credit_file_risk" in flags:
        lines.append("We will include your credit file concern in the complaint review.")
    if severity == "critical":
        lines.append("This has been marked for urgent review.")
    elif severity == "high":
        lines.append("This has been marked for same-day review by the appropriate team.")

    if preferences:
        lines.append("We will take your stated communication preference into account where possible.")
    lines.append("This acknowledgement does not determine the outcome of the complaint.")
    lines.append(f"Recommended internal routing: {routing}.")
    return " ".join(lines)
