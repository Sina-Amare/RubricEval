"""
SQLAlchemy 2.0 ORM models.

Portable across PostgreSQL and SQLite:
  * IDs are 32-char uuid hex strings (no native uuid type required).
  * Enums are stored as VARCHAR via ``native_enum=False`` (+ CHECK).
  * Structured columns use the generic ``JSON`` type.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import (
    CriterionType,
    Decision,
    EvidenceVerification,
    GatePolicy,
    JobState,
    ReviewStatus,
    SourceType,
    Verdict,
)
from app.db.base import Base


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _enum(enum_cls, length: int = 24):
    """A portable, string-backed enum column type."""
    return SAEnum(enum_cls, native_enum=False, length=length, validate_strings=True)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )


# --------------------------------------------------------------------------
# Tasks & rubrics
# --------------------------------------------------------------------------
class Task(Base, TimestampMixin):
    __tablename__ = "task"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    # Editable draft (criteria + decision config) until published into a version.
    draft: Mapped[dict] = mapped_column(JSON, default=dict)
    current_rubric_version_id: Mapped[str | None] = mapped_column(
        String(32),
        ForeignKey(
            "rubric_version.id",
            ondelete="SET NULL",
            use_alter=True,  # break the task <-> rubric_version cycle for PG create/drop
            name="fk_task_current_rubric_version",
        ),
        nullable=True,
    )

    versions: Mapped[list["RubricVersion"]] = relationship(
        back_populates="task",
        foreign_keys="RubricVersion.task_id",
        cascade="all, delete-orphan",
    )


class RubricVersion(Base):
    __tablename__ = "rubric_version"
    __table_args__ = (UniqueConstraint("task_id", "version_number", name="uq_rubric_version"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    task_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("task.id", ondelete="CASCADE"), index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    decision_config: Mapped[dict] = mapped_column(JSON, default=dict)
    prompt_template_version: Mapped[str] = mapped_column(String(50), default="grade@v1")
    is_published: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    task: Mapped["Task"] = relationship(back_populates="versions", foreign_keys=[task_id])
    criteria: Mapped[list["Criterion"]] = relationship(
        back_populates="rubric_version",
        cascade="all, delete-orphan",
        order_by="Criterion.order_index",
    )


class Criterion(Base):
    __tablename__ = "criterion"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    rubric_version_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("rubric_version.id", ondelete="CASCADE"), index=True
    )
    key: Mapped[str] = mapped_column(String(80), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    instructions: Mapped[str] = mapped_column(Text, default="")
    type: Mapped[CriterionType] = mapped_column(_enum(CriterionType))
    weight: Mapped[float] = mapped_column(Float, default=0.0)
    gate_policy: Mapped[GatePolicy | None] = mapped_column(_enum(GatePolicy), nullable=True)
    pass_threshold: Mapped[float | None] = mapped_column(Float, nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, default=0)

    rubric_version: Mapped["RubricVersion"] = relationship(back_populates="criteria")


# --------------------------------------------------------------------------
# Submissions
# --------------------------------------------------------------------------
class Submission(Base):
    __tablename__ = "submission"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    source_type: Mapped[SourceType] = mapped_column(_enum(SourceType))
    source_ref: Mapped[str] = mapped_column(String(500))
    commit_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)
    branch: Mapped[str | None] = mapped_column(String(200), nullable=True)
    fileset_hash: Mapped[str] = mapped_column(String(64), index=True)
    file_count: Mapped[int] = mapped_column(Integer, default=0)
    total_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    files: Mapped[list["SubmissionFile"]] = relationship(
        back_populates="submission", cascade="all, delete-orphan"
    )


class SubmissionFile(Base):
    __tablename__ = "submission_file"
    __table_args__ = (UniqueConstraint("submission_id", "path", name="uq_submission_path"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    submission_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("submission.id", ondelete="CASCADE"), index=True
    )
    path: Mapped[str] = mapped_column(String(1024))
    file_hash: Mapped[str] = mapped_column(String(64), index=True)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    language: Mapped[str | None] = mapped_column(String(40), nullable=True)
    line_count: Mapped[int] = mapped_column(Integer, default=0)

    submission: Mapped["Submission"] = relationship(back_populates="files")


# --------------------------------------------------------------------------
# Reviews
# --------------------------------------------------------------------------
class Review(Base):
    __tablename__ = "review"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    task_id: Mapped[str] = mapped_column(String(32), ForeignKey("task.id"), index=True)
    rubric_version_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("rubric_version.id"), index=True
    )
    submission_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("submission.id"), index=True
    )
    status: Mapped[ReviewStatus] = mapped_column(
        _enum(ReviewStatus), default=ReviewStatus.QUEUED, index=True
    )

    # Reproducibility snapshot
    model_id: Mapped[str] = mapped_column(String(200), default="")
    prompt_template_version: Mapped[str] = mapped_column(String(50), default="")
    rubric_content_hash: Mapped[str] = mapped_column(String(64), default="")
    engine_version: Mapped[str] = mapped_column(String(50), default="")
    idempotency_key: Mapped[str | None] = mapped_column(
        String(64), unique=True, nullable=True, index=True
    )

    # Decision outputs
    decision: Mapped[Decision | None] = mapped_column(_enum(Decision), nullable=True)
    final_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    gate_failed: Mapped[bool] = mapped_column(Boolean, default=False)
    decision_breakdown: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    results: Mapped[list["CriterionResult"]] = relationship(
        back_populates="review", cascade="all, delete-orphan"
    )


class CriterionResult(Base):
    __tablename__ = "criterion_result"
    __table_args__ = (
        UniqueConstraint("review_id", "criterion_id", name="uq_review_criterion"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    review_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("review.id", ondelete="CASCADE"), index=True
    )
    criterion_id: Mapped[str] = mapped_column(String(32), nullable=False)
    criterion_key: Mapped[str] = mapped_column(String(80), nullable=False)
    verdict: Mapped[Verdict] = mapped_column(_enum(Verdict))
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    raw_judgment: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    model_id: Mapped[str] = mapped_column(String(200), default="")
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    attempts: Mapped[int] = mapped_column(Integer, default=1)
    repaired: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    review: Mapped["Review"] = relationship(back_populates="results")
    evidence: Mapped[list["Evidence"]] = relationship(
        back_populates="criterion_result", cascade="all, delete-orphan"
    )


class Evidence(Base):
    __tablename__ = "evidence"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    criterion_result_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("criterion_result.id", ondelete="CASCADE"), index=True
    )
    path: Mapped[str] = mapped_column(String(1024))
    start_line: Mapped[int] = mapped_column(Integer, default=1)
    end_line: Mapped[int] = mapped_column(Integer, default=1)
    quote: Mapped[str] = mapped_column(Text, default="")
    verified: Mapped[EvidenceVerification] = mapped_column(_enum(EvidenceVerification, length=24))
    resolved_file_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    criterion_result: Mapped["CriterionResult"] = relationship(back_populates="evidence")


# --------------------------------------------------------------------------
# BYOK provider configuration
# --------------------------------------------------------------------------
class ProviderConfig(Base, TimestampMixin):
    __tablename__ = "provider_config"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(120))
    provider: Mapped[str] = mapped_column(String(60), default="openrouter")
    model_id: Mapped[str] = mapped_column(String(200))
    key_ciphertext: Mapped[bytes] = mapped_column(default=b"")
    key_fingerprint: Mapped[str] = mapped_column(String(40), default="")
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, index=True)


# --------------------------------------------------------------------------
# Live-evaluation event log (drives SSE + replay)
# --------------------------------------------------------------------------
class ReviewEvent(Base):
    __tablename__ = "review_event"

    # BIGINT on PostgreSQL; INTEGER on SQLite so the rowid autoincrements.
    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    review_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("review.id", ondelete="CASCADE"), index=True
    )
    seq: Mapped[int] = mapped_column(Integer, default=0)
    type: Mapped[str] = mapped_column(String(40))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


# --------------------------------------------------------------------------
# Durable leased job queue
# --------------------------------------------------------------------------
class Job(Base):
    __tablename__ = "job"
    __table_args__ = (
        CheckConstraint("attempts >= 0", name="ck_job_attempts"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    review_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("review.id", ondelete="CASCADE"), unique=True, index=True
    )
    state: Mapped[JobState] = mapped_column(_enum(JobState), default=JobState.QUEUED, index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    lease_owner: Mapped[str | None] = mapped_column(String(80), nullable=True)
    leased_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )
