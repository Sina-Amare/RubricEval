"""
Evidence verification.

Every citation an LLM produces is checked against the real submitted files:
the path must exist, the line range must be within bounds, and (if a quote is
given) it must actually appear at those lines. Unverifiable citations are kept
but flagged — they are never silently trusted.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.enums import EvidenceVerification
from app.engine.schemas import EvidenceItem
from app.ingestion.normalize import NormalizedFileSet


@dataclass
class VerifiedEvidence:
    path: str
    start_line: int
    end_line: int
    quote: str
    verified: EvidenceVerification
    resolved_file_hash: str | None


def verify_evidence(
    items: list[EvidenceItem], fileset: NormalizedFileSet
) -> list[VerifiedEvidence]:
    by_path = fileset.by_path()
    out: list[VerifiedEvidence] = []
    for e in items:
        f = by_path.get(e.path)
        if f is None:
            out.append(
                VerifiedEvidence(
                    e.path, e.start_line, e.end_line, e.quote,
                    EvidenceVerification.UNVERIFIED_PATH, None,
                )
            )
            continue

        lines = f.content.split("\n")
        n = len(lines)
        if not (1 <= e.start_line <= e.end_line <= n):
            out.append(
                VerifiedEvidence(
                    e.path, e.start_line, e.end_line, e.quote,
                    EvidenceVerification.UNVERIFIED_LINES, f.file_hash,
                )
            )
            continue

        status = EvidenceVerification.VERIFIED
        # Whitespace-tolerant: models reflow indentation/line-wraps when quoting,
        # so compare with all runs of whitespace collapsed to a single space.
        quote = " ".join(e.quote.split())
        if quote:
            snippet = " ".join("\n".join(lines[e.start_line - 1 : e.end_line]).split())
            if quote not in snippet and snippet not in quote:
                status = EvidenceVerification.UNVERIFIED_QUOTE
        out.append(
            VerifiedEvidence(
                e.path, e.start_line, e.end_line, e.quote, status, f.file_hash
            )
        )
    return out
