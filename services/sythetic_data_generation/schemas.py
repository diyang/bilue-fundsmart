"""Pydantic schemas for synthetic FundSmart complaint test generation."""

from __future__ import annotations

from typing import Literal

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


class ComplaintMetadata(BaseModel):
    channel: str | None = None
    received: str | None = None
    customer_id: str | None = None
    subject: str | None = None
    thread_context: str | None = None
    agent: str | None = None
    duration: str | None = None
    note: str | None = None


class SyntheticTestCase(BaseModel):
    id: str = Field(min_length=1)
    source: Literal["synthetic"] = "synthetic"
    scenario_type: str = Field(min_length=1)
    complaint_document: str = Field(min_length=1)
    metadata: ComplaintMetadata = Field(default_factory=ComplaintMetadata)
    expected_category: Category
    expected_severity: Severity
    expected_routing: Routing
    expected_sla: Literal[
        "standard_acknowledgement",
        "same_day_acknowledgement",
        "urgent_review",
    ]
    scenario_tags: list[str] = Field(default_factory=list)
    expected_signals: list[str] = Field(default_factory=list)
    expected_preferences: list[str] = Field(default_factory=list)
    forbidden_signals: list[str] = Field(default_factory=list)
    must_detect: list[str] = Field(default_factory=list)
    must_not_detect: list[str] = Field(default_factory=list)
    customer_preferences: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def complaint_document_contains_markdown_input(self) -> SyntheticTestCase:
        if "**Channel:**" not in self.complaint_document:
            raise ValueError("complaint_document must include a markdown Channel header.")
        if "```" not in self.complaint_document:
            raise ValueError("complaint_document must include a fenced complaint body.")
        return self


class SyntheticGenerationRequest(BaseModel):
    count: int = Field(default=10, ge=1, le=50)
    id_prefix: str = Field(default="SYN-GEN", min_length=1, max_length=24)
    scenario_focus: list[str] = Field(
        default_factory=list,
        description=(
            "Optional scenario shapes to emphasize, such as subtle_hardship, "
            "self_harm_signal, wrong_company_or_product, or multi_issue_complaint."
        ),
    )
    category_focus: list[Category] = Field(default_factory=list)
    include_seed_guidance: bool = True
    coverage_matrix: bool = Field(
        default=True,
        description="Prefer broad coverage-matrix generation over random generic complaints.",
    )
    output_mode: Literal["combined", "split", "both"] = Field(
        default="both",
        description=(
            "combined returns the current benchmark JSONL shape. split also returns "
            "synthetic_complaints.jsonl and gold_labels.jsonl style content."
        ),
    )
    notes: str | None = Field(
        default=None,
        description="Optional extra generation instructions for this batch.",
    )


class SyntheticBatchOutput(BaseModel):
    cases: list[SyntheticTestCase]
    generation_notes: str


class SyntheticGenerationResponse(SyntheticBatchOutput):
    requested_count: int
    generated_count: int
    jsonl: str
    synthetic_complaints_jsonl: str
    gold_labels_jsonl: str
    synthetic_generation_notes_md: str
    provider: str
    model: str | None = None
    latency_seconds: float = Field(ge=0.0)


class HealthResponse(BaseModel):
    status: str
    provider: str
    model: str | None = None
