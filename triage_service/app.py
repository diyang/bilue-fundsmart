"""FastAPI entrypoint for the standalone FundSmart triage service."""

from __future__ import annotations

import logging
import os
import time
from contextlib import asynccontextmanager
from typing import Any
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException, Query, status
from pydantic import BaseModel, Field

from .db import (
    AsyncTriageReviewStore,
    AsyncTriageRunStore,
    TriageDatabase,
    database_url_from_env,
)
from .graph import TriageGraph
from .llm_client import client_from_env
from .schemas import (
    ComplaintInput,
    FinalOutput,
    TriageReviewRequest,
    TriageReviewResponse,
    TriageRunResponse,
    Version,
)

logging.basicConfig(
    level=os.getenv("TRIAGE_SERVICE_LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)

triage_graph: TriageGraph | None = None
triage_database: TriageDatabase | None = None
triage_run_store: AsyncTriageRunStore | None = None
triage_review_store: AsyncTriageReviewStore | None = None


class HealthResponse(BaseModel):
    status: str
    provider: str
    database_enabled: bool
    default_version: Version = "v2"


class TriageResponse(FinalOutput):
    run_id: UUID | None = None
    latency_seconds: float = Field(ge=0.0)


def parse_version(version: str) -> Version:
    if version not in {"v1", "v2"}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="version must be v1 or v2",
        )
    return version  # type: ignore[return-value]


@asynccontextmanager
async def lifespan(_: FastAPI):
    global triage_graph, triage_database, triage_run_store, triage_review_store
    started = time.perf_counter()
    provider = os.getenv("TRIAGE_LLM_PROVIDER", "heuristic")
    logger.info("Starting triage service provider=%s", provider)
    triage_graph = TriageGraph(client_from_env())
    database_url = database_url_from_env()
    if database_url:
        triage_database = TriageDatabase(database_url)
        if os.getenv("TRIAGE_DATABASE_AUTO_CREATE", "false").lower() in {
            "1",
            "true",
            "yes",
        }:
            await triage_database.create_schema()
        triage_run_store = AsyncTriageRunStore(triage_database.async_session_factory)
        triage_review_store = AsyncTriageReviewStore(
            triage_database.async_session_factory
        )
        logger.info("Triage database persistence enabled")
    else:
        logger.info("Triage database persistence disabled; no database URL configured")
    logger.info("Started triage service elapsed_seconds=%.3f", time.perf_counter() - started)
    try:
        yield
    finally:
        logger.info("Stopping triage service")
        triage_graph = None
        triage_run_store = None
        triage_review_store = None
        if triage_database is not None:
            await triage_database.aclose()
            triage_database = None


app = FastAPI(
    title="FundSmart Triage Service",
    version="0.1.0",
    description=(
        "Single-turn complaint triage and acknowledgement drafting service. "
        "The service uses request.complaint_document as the LLM pipeline input."
    ),
    lifespan=lifespan,
)


def require_api_key(authorization: str | None = Header(default=None)) -> None:
    api_key = os.getenv("TRIAGE_SERVICE_API_KEY")
    if not api_key:
        return
    if authorization != f"Bearer {api_key}":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid bearer token.",
        )


def require_graph() -> TriageGraph:
    if triage_graph is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Triage graph has not started.",
        )
    return triage_graph


def require_run_store() -> AsyncTriageRunStore:
    if triage_run_store is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Triage database is not configured.",
        )
    return triage_run_store


def require_review_store() -> AsyncTriageReviewStore:
    if triage_review_store is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Triage database is not configured.",
        )
    return triage_review_store


@app.get("/")
def root() -> dict[str, Any]:
    return {
        "service": "fundsmart-triage",
        "status": "ok",
        "health": "/health",
        "triage": "/triage",
        "triage_runs": "/triage-runs",
    }


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        provider=os.getenv("TRIAGE_LLM_PROVIDER", "heuristic"),
        database_enabled=triage_run_store is not None,
    )


@app.post(
    "/triage",
    response_model=TriageResponse,
    dependencies=[Depends(require_api_key)],
)
async def triage(
    request: ComplaintInput,
    version: str = Query(default="v2", description="Pipeline version: v1 or v2."),
    graph: TriageGraph = Depends(require_graph),
) -> TriageResponse:
    """Triage one complaint. Only request.complaint_document is sent into the pipeline."""
    started = time.perf_counter()
    request_payload = request.model_dump(mode="json")
    output = graph.invoke(request_payload, version=parse_version(version))
    latency_seconds = time.perf_counter() - started
    run_id = None
    if triage_run_store is not None:
        run = await triage_run_store.create(
            request=request_payload,
            output=output,
            latency_seconds=latency_seconds,
        )
        run_id = run.run_id
    return TriageResponse(
        **output.model_dump(mode="json"),
        run_id=run_id,
        latency_seconds=latency_seconds,
    )


@app.get(
    "/triage-runs",
    response_model=list[TriageRunResponse],
    dependencies=[Depends(require_api_key)],
)
async def list_triage_runs(
    limit: int = Query(default=50, ge=1, le=200),
    store: AsyncTriageRunStore = Depends(require_run_store),
) -> list[TriageRunResponse]:
    return await store.list_recent(limit=limit)


@app.get(
    "/triage-runs/{run_id}",
    response_model=TriageRunResponse,
    dependencies=[Depends(require_api_key)],
)
async def get_triage_run(
    run_id: UUID,
    store: AsyncTriageRunStore = Depends(require_run_store),
) -> TriageRunResponse:
    run = await store.get(run_id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Triage run not found.",
        )
    return run


@app.post(
    "/triage-runs/{run_id}/review",
    response_model=TriageReviewResponse,
    dependencies=[Depends(require_api_key)],
)
async def upsert_triage_review(
    run_id: UUID,
    request: TriageReviewRequest,
    store: AsyncTriageReviewStore = Depends(require_review_store),
) -> TriageReviewResponse:
    return await store.upsert(run_id, request)
