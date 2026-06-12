"""Database access for persisted triage runs."""

from __future__ import annotations

import logging
import os
from datetime import datetime
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from .models import Base, TRIAGE_SCHEMA, TriageReview, TriageRun
from .schemas import FinalOutput, TriageReviewRequest, TriageReviewResponse, TriageRunResponse

logger = logging.getLogger(__name__)


def db_uuid(value: UUID | str | None) -> str | None:
    if value is None:
        return None
    return str(value)


def database_url_from_env() -> str | None:
    return os.getenv("TRIAGE_DATABASE_URL") or os.getenv("DATABASE_URL")


def normalize_database_url(url: str) -> str:
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


class TriageDatabase:
    def __init__(self, url: str):
        self.url = url
        self.async_engine = create_async_engine(normalize_database_url(url), future=True)
        self.async_session_factory = async_sessionmaker(
            bind=self.async_engine,
            autoflush=False,
            expire_on_commit=False,
        )
        logger.info("Initialized triage database engine")

    async def aclose(self) -> None:
        await self.async_engine.dispose()
        logger.info("Closed triage database engine")

    async def create_schema(self) -> None:
        async with self.async_engine.begin() as connection:
            await connection.execute(
                text(f"CREATE SCHEMA IF NOT EXISTS {TRIAGE_SCHEMA}")
            )
            await connection.run_sync(Base.metadata.create_all)
        logger.info("Ensured triage database schema exists")

    def langgraph_database_url(self) -> str:
        value = self.url.replace("postgresql+psycopg://", "postgresql://", 1)
        return self.with_search_path(value, TRIAGE_SCHEMA)

    @staticmethod
    def with_search_path(url: str, schema: str) -> str:
        parts = urlsplit(url)
        query = dict(parse_qsl(parts.query, keep_blank_values=True))
        query.setdefault("options", f"-csearch_path={schema},public")
        return urlunsplit(
            (parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment)
        )


class AsyncTriageRunStore:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self.session_factory = session_factory

    async def create(
        self,
        request: dict,
        output: FinalOutput,
        latency_seconds: float,
    ) -> TriageRunResponse:
        async with self.session_factory() as session, session.begin():
            run = TriageRun(
                complaint_id=output.id,
                version=output.metadata.version,
                complaint_document=request["complaint_document"],
                source=request.get("source"),
                scenario_type=request.get("scenario_type"),
                input_metadata_json=request.get("metadata") or {},
                output_json=output.model_dump(mode="json"),
                triage_json=output.triage.model_dump(mode="json"),
                acknowledgement_draft=output.acknowledgement_draft,
                output_metadata_json={
                    **output.metadata.model_dump(mode="json"),
                    "latency_seconds": latency_seconds,
                },
            )
            session.add(run)
            await session.flush()
            await session.refresh(run)
            logger.info(
                "Created triage run run_id=%s complaint_id=%s version=%s",
                run.run_id,
                run.complaint_id,
                run.version,
            )
            return self._response(run)

    async def get(self, run_id: UUID) -> TriageRunResponse | None:
        async with self.session_factory() as session:
            run = await session.get(TriageRun, db_uuid(run_id))
            return self._response(run) if run is not None else None

    async def list_recent(self, limit: int = 50) -> list[TriageRunResponse]:
        async with self.session_factory() as session:
            statement = (
                select(TriageRun)
                .order_by(TriageRun.created_at.desc())
                .limit(limit)
            )
            runs = (await session.scalars(statement)).all()
            return [self._response(run) for run in runs]

    def _response(self, run: TriageRun) -> TriageRunResponse:
        return TriageRunResponse(
            run_id=run.run_id,
            complaint_id=run.complaint_id,
            version=run.version,
            complaint_document=run.complaint_document,
            source=run.source,
            scenario_type=run.scenario_type,
            input_metadata=run.input_metadata_json or {},
            output=run.output_json,
            triage=run.triage_json,
            acknowledgement_draft=run.acknowledgement_draft,
            output_metadata=run.output_metadata_json or {},
            created_at=run.created_at,
        )


class AsyncTriageReviewStore:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self.session_factory = session_factory

    async def upsert(
        self,
        run_id: UUID,
        request: TriageReviewRequest,
    ) -> TriageReviewResponse:
        async with self.session_factory() as session, session.begin():
            review = await session.get(TriageReview, db_uuid(run_id))
            if review is None:
                review = TriageReview(run_id=db_uuid(run_id))
                session.add(review)
            review.reviewer = request.reviewer
            review.status = request.status
            review.final_category = request.final_category
            review.final_severity = request.final_severity
            review.final_routing = request.final_routing
            review.edited_acknowledgement = request.edited_acknowledgement
            review.comments = request.comments
            review.review_metadata_json = request.metadata
            review.updated_at = func.now()
            await session.flush()
            await session.refresh(review)
            logger.info("Upserted triage review run_id=%s status=%s", run_id, review.status)
            return self._response(review)

    async def get(self, run_id: UUID) -> TriageReviewResponse | None:
        async with self.session_factory() as session:
            review = await session.get(TriageReview, db_uuid(run_id))
            return self._response(review) if review is not None else None

    def _response(self, review: TriageReview) -> TriageReviewResponse:
        return TriageReviewResponse(
            run_id=review.run_id,
            reviewer=review.reviewer,
            status=review.status,
            final_category=review.final_category,
            final_severity=review.final_severity,
            final_routing=review.final_routing,
            edited_acknowledgement=review.edited_acknowledgement,
            comments=review.comments,
            metadata=review.review_metadata_json or {},
            created_at=review.created_at,
            updated_at=review.updated_at,
        )
