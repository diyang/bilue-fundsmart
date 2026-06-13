"""SQLAlchemy models for persisted triage runs and human review."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from uuid_utils import uuid7

TRIAGE_SCHEMA = "triage_service"


class Base(DeclarativeBase):
    pass


class TriageRun(Base):
    __tablename__ = "triage_runs"
    __table_args__ = (
        Index("idx_triage_runs_complaint_id", "complaint_id"),
        Index("idx_triage_runs_created_at", "created_at"),
        Index("idx_triage_runs_version_created", "version", "created_at"),
        {"schema": TRIAGE_SCHEMA},
    )

    run_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid7,
    )
    complaint_id: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[str] = mapped_column(Text, nullable=False)
    complaint_document: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str | None] = mapped_column(Text)
    scenario_type: Mapped[str | None] = mapped_column(Text)
    input_metadata_json: Mapped[dict[str, object]] = mapped_column(
        "input_metadata",
        JSONB,
        server_default="{}",
        nullable=False,
    )
    output_json: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    triage_json: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    acknowledgement_draft: Mapped[str] = mapped_column(Text, nullable=False)
    output_metadata_json: Mapped[dict[str, object]] = mapped_column(
        "output_metadata",
        JSONB,
        server_default="{}",
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class TriageReview(Base):
    __tablename__ = "triage_reviews"
    __table_args__ = (
        CheckConstraint(
            "status in ('accepted', 'edited', 'rejected')",
            name="ck_triage_reviews_status",
        ),
        Index("idx_triage_reviews_status_updated", "status", "updated_at"),
        {"schema": TRIAGE_SCHEMA},
    )

    run_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(
            f"{TRIAGE_SCHEMA}.triage_runs.run_id",
            ondelete="CASCADE",
        ),
        primary_key=True,
    )
    reviewer: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    final_category: Mapped[str | None] = mapped_column(Text)
    final_severity: Mapped[str | None] = mapped_column(Text)
    final_routing: Mapped[str | None] = mapped_column(Text)
    edited_acknowledgement: Mapped[str | None] = mapped_column(Text)
    comments: Mapped[str | None] = mapped_column(Text)
    review_metadata_json: Mapped[dict[str, object]] = mapped_column(
        "review_metadata",
        JSONB,
        server_default="{}",
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
