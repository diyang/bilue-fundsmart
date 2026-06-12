"""Pydantic schemas for the FundSmart triage pipeline."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

Category = Literal[
    "service_error",
    "financial_hardship",
    "responsible_lending",
    "collections",
    "fees_charges",
    "fraud_or_identity",
    "unclear_or_other",
]
Severity = Literal["low", "medium", "high", "critical"]
Routing = Literal[
    "frontline_complaints",
    "hardship_team",
    "responsible_lending_specialist",
    "collections_escalation",
    "vulnerable_customer_team",
    "legal_compliance_review",
]
SLARecommendation = Literal[
    "standard_acknowledgement",
    "same_day_acknowledgement",
    "urgent_review",
]
Version = Literal["v1", "v2"]


class ComplaintMetadata(BaseModel):
    channel: str | None = None
    received: str | None = None
    customer_id: str | None = None
    subject: str | None = None
    thread_context: str | None = None
    agent: str | None = None
    duration: str | None = None
    note: str | None = None


class ComplaintInput(BaseModel):
    id: str
    complaint_document: str
    source: str | None = None
    scenario_type: str | None = None
    metadata: ComplaintMetadata = Field(default_factory=ComplaintMetadata)

    @model_validator(mode="after")
    def require_complaint_document(self) -> ComplaintInput:
        if not self.complaint_document.strip():
            raise ValueError(
                "complaint_document is required because it is the LLM input."
            )
        return self


class TriageOutput(BaseModel):
    category: Category
    severity: Severity
    vulnerability_signals: list[str] = Field(default_factory=list)
    regulatory_flags: list[str] = Field(default_factory=list)
    recommended_routing: Routing
    sla_recommendation: SLARecommendation
    customer_preferences: list[str] = Field(default_factory=list)
    extracted_metadata: ComplaintMetadata = Field(default_factory=ComplaintMetadata)
    complaint_summary: str
    reasoning: str


class TriageLLMOutput(BaseModel):
    triage: TriageOutput
    acknowledgement_draft: str


class OutputMetadata(BaseModel):
    version: Version
    triage_valid: bool
    acknowledgement_valid: bool
    retries: int = 0
    critical_risk: bool = False
    errors: list[str] = Field(default_factory=list)
    triage_validation_errors: list[str] = Field(default_factory=list)
    acknowledgement_validation_errors: list[str] = Field(default_factory=list)
    input_metadata: ComplaintMetadata = Field(default_factory=ComplaintMetadata)


class FinalOutput(BaseModel):
    id: str
    triage: TriageOutput
    acknowledgement_draft: str
    metadata: OutputMetadata


class TriageRunResponse(BaseModel):
    run_id: UUID
    complaint_id: str
    version: Version
    complaint_document: str
    source: str | None = None
    scenario_type: str | None = None
    input_metadata: dict[str, Any] = Field(default_factory=dict)
    output: dict[str, Any]
    triage: dict[str, Any]
    acknowledgement_draft: str
    output_metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


ReviewStatus = Literal["accepted", "edited", "rejected"]


class TriageReviewRequest(BaseModel):
    reviewer: str = Field(min_length=1)
    status: ReviewStatus
    final_category: Category | None = None
    final_severity: Severity | None = None
    final_routing: Routing | None = None
    edited_acknowledgement: str | None = None
    comments: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class TriageReviewResponse(TriageReviewRequest):
    run_id: UUID
    created_at: datetime
    updated_at: datetime


JsonDict = dict[str, Any]
