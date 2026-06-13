"""FastAPI entrypoint for synthetic FundSmart triage test generation."""

from __future__ import annotations

import json
import logging
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, status

from .llm_client import SyntheticDataClient, client_from_env, model_from_env, provider_from_env
from .schemas import (
    HealthResponse,
    SyntheticGenerationRequest,
    SyntheticGenerationResponse,
    SyntheticTestCase,
)

load_dotenv(Path(__file__).with_name(".env"), override=False)

logging.basicConfig(
    level=os.getenv("SYNTHETIC_DATA_SERVICE_LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)

synthetic_data_client: SyntheticDataClient | None = None


@asynccontextmanager
async def lifespan(_: FastAPI):
    global synthetic_data_client
    started = time.perf_counter()
    logger.info("Starting synthetic data generation service provider=%s", provider_from_env())
    synthetic_data_client = client_from_env()
    logger.info(
        "Started synthetic data generation service elapsed_seconds=%.3f",
        time.perf_counter() - started,
    )
    try:
        yield
    finally:
        logger.info("Stopping synthetic data generation service")
        synthetic_data_client = None


app = FastAPI(
    title="FundSmart Synthetic Data Generation Service",
    version="0.1.0",
    description=(
        "Batch synthetic complaint test-case generation service for the FundSmart "
        "triage benchmark."
    ),
    lifespan=lifespan,
)


def require_api_key(authorization: str | None = Header(default=None)) -> None:
    api_key = os.getenv("SYNTHETIC_DATA_SERVICE_API_KEY")
    if not api_key:
        return
    if authorization != f"Bearer {api_key}":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid bearer token.",
        )


def require_client() -> SyntheticDataClient:
    if synthetic_data_client is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Synthetic data generation client has not started.",
        )
    return synthetic_data_client


@app.get("/")
def root() -> dict[str, Any]:
    return {
        "service": "fundsmart-synthetic-data-generation",
        "status": "ok",
        "health": "/health",
        "generate": "/generate",
    }


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        provider=provider_from_env(),
        model=model_from_env(),
    )


@app.post(
    "/generate",
    response_model=SyntheticGenerationResponse,
    dependencies=[Depends(require_api_key)],
)
async def generate(
    request: SyntheticGenerationRequest,
    client: SyntheticDataClient = Depends(require_client),
) -> SyntheticGenerationResponse:
    started = time.perf_counter()
    output = client.generate(request)
    if len(output.cases) != request.count:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "Synthetic data client returned "
                f"{len(output.cases)} cases, expected {request.count}."
            ),
        )
    cases = [
        case.model_copy(update={"id": f"{request.id_prefix}-{index:03d}", "source": "synthetic"})
        for index, case in enumerate(output.cases, start=1)
    ]
    jsonl = combined_jsonl(cases)
    complaints_jsonl = synthetic_complaints_jsonl(cases)
    labels_jsonl = gold_labels_jsonl(cases)
    notes_md = synthetic_generation_notes_md(output.generation_notes, cases)
    return SyntheticGenerationResponse(
        cases=cases,
        generation_notes=output.generation_notes,
        requested_count=request.count,
        generated_count=len(cases),
        jsonl=jsonl if request.output_mode in {"combined", "both"} else "",
        synthetic_complaints_jsonl=(
            complaints_jsonl if request.output_mode in {"split", "both"} else ""
        ),
        gold_labels_jsonl=(
            labels_jsonl if request.output_mode in {"split", "both"} else ""
        ),
        synthetic_generation_notes_md=(
            notes_md if request.output_mode in {"split", "both"} else ""
        ),
        provider=provider_from_env(),
        model=model_from_env(),
        latency_seconds=time.perf_counter() - started,
    )


def as_jsonl(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return ""
    return "\n".join(json.dumps(row, separators=(",", ":")) for row in rows) + "\n"


def combined_jsonl(cases: list[SyntheticTestCase]) -> str:
    return as_jsonl([case.model_dump(mode="json") for case in cases])


def synthetic_complaints_jsonl(cases: list[SyntheticTestCase]) -> str:
    rows: list[dict[str, Any]] = []
    for case in cases:
        metadata = case.metadata
        row: dict[str, Any] = {
            "id": case.id,
            "channel": metadata.channel,
            "received": metadata.received,
            "customer_id": metadata.customer_id,
            "message": extract_body(case.complaint_document),
        }
        if metadata.subject is not None:
            row["subject"] = metadata.subject
        if metadata.thread_context is not None:
            row["thread_context"] = metadata.thread_context
        if metadata.agent is not None:
            row["agent"] = metadata.agent
        if metadata.duration is not None:
            row["duration"] = metadata.duration
        if metadata.note is not None:
            row["note"] = metadata.note
        rows.append(row)
    return as_jsonl(rows)


def gold_labels_jsonl(cases: list[SyntheticTestCase]) -> str:
    return as_jsonl(
        [
            {
                "id": case.id,
                "expected_category": case.expected_category,
                "expected_severity": case.expected_severity,
                "expected_routing": case.expected_routing,
                "expected_sla": case.expected_sla,
                "scenario_tags": case.scenario_tags,
                "expected_signals": case.expected_signals,
                "expected_preferences": case.expected_preferences,
                "forbidden_signals": case.forbidden_signals,
                "must_detect": case.must_detect,
                "must_not_detect": case.must_not_detect,
                "customer_preferences": case.customer_preferences,
            }
            for case in cases
        ]
    )


def synthetic_generation_notes_md(
    generation_notes: str,
    cases: list[SyntheticTestCase],
) -> str:
    scenario_lines = "\n".join(
        f"- {case.id}: {case.scenario_type} ({case.expected_category}, {case.expected_severity})"
        for case in cases
    )
    return (
        "# Synthetic Data Generation Notes\n\n"
        "Generated using a coverage-matrix approach based on the seed complaints "
        "and synthetic test case generation spec.\n\n"
        "## Generator Notes\n\n"
        f"{generation_notes}\n\n"
        "## Generated Coverage\n\n"
        f"{scenario_lines}\n"
    )


def extract_body(complaint_document: str) -> str:
    parts = complaint_document.split("```", 2)
    if len(parts) >= 3:
        return parts[1].strip()
    return complaint_document.strip()
