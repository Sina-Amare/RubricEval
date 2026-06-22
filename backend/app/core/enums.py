"""
Domain enumerations.

All enums use plain string values so they map cleanly to non-native (string-backed)
DB columns on both PostgreSQL and SQLite, and serialize directly to JSON.
"""

from __future__ import annotations

from enum import Enum


class StrEnum(str, Enum):
    """A str-valued Enum whose `str()` is its value (portable across py311+)."""

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.value


class CriterionType(StrEnum):
    """Whether a criterion gates the decision or contributes a weighted score."""

    GATE = "gate"
    SCORED = "scored"


class GatePolicy(StrEnum):
    """How a gate criterion affects the final decision when it does not pass."""

    MUST_PASS = "must_pass"        # failing -> REJECT
    FORCE_REJECT = "force_reject"  # a kill-switch criterion; failing -> REJECT


class Verdict(StrEnum):
    """Per-criterion judgment produced by the grader."""

    PASS = "pass"
    FAIL = "fail"
    PARTIAL = "partial"
    ERROR = "error"  # grading itself failed (never silently treated as pass)


class Decision(StrEnum):
    """Final, deterministic outcome of a review."""

    ACCEPT = "accept"
    REVIEW = "review"
    REJECT = "reject"


class ReviewStatus(StrEnum):
    """Lifecycle of a review run."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class JobState(StrEnum):
    """Lifecycle of a durable queue job."""

    QUEUED = "queued"
    LEASED = "leased"
    DONE = "done"
    FAILED = "failed"


class SourceType(StrEnum):
    """Where a submission's files came from."""

    GITHUB = "github"
    ZIP = "zip"


class EvidenceVerification(StrEnum):
    """Result of verifying a cited piece of evidence against the real files."""

    VERIFIED = "verified"
    UNVERIFIED_PATH = "unverified_path"      # file path does not exist
    UNVERIFIED_LINES = "unverified_lines"    # line range out of bounds
    UNVERIFIED_QUOTE = "unverified_quote"    # quote not found at cited lines
