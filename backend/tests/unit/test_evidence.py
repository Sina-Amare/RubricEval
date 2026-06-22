"""Unit tests for evidence verification against real file content."""

from __future__ import annotations

from app.core.enums import EvidenceVerification as EV
from app.engine.evidence import verify_evidence
from app.engine.schemas import EvidenceItem
from app.ingestion.normalize import NormalizedFile, NormalizedFileSet


def _fileset() -> NormalizedFileSet:
    f = NormalizedFile(
        path="a.py",
        content="line one\nline two\nline three",
        file_hash="h1",
        size_bytes=0,
        language="python",
        line_count=3,
    )
    return NormalizedFileSet(source_type="zip", source_ref="x", files=[f])


def _verify(item: EvidenceItem) -> EV:
    return verify_evidence([item], _fileset())[0].verified


def test_verified_when_path_lines_quote_match():
    assert _verify(EvidenceItem(path="a.py", start_line=2, end_line=2, quote="line two")) == EV.VERIFIED


def test_verified_with_empty_quote_when_lines_ok():
    assert _verify(EvidenceItem(path="a.py", start_line=1, end_line=3, quote="")) == EV.VERIFIED


def test_unverified_path():
    assert _verify(EvidenceItem(path="missing.py", start_line=1, end_line=1)) == EV.UNVERIFIED_PATH


def test_unverified_lines_out_of_bounds():
    assert _verify(EvidenceItem(path="a.py", start_line=5, end_line=6)) == EV.UNVERIFIED_LINES


def test_unverified_quote_not_present():
    assert _verify(EvidenceItem(path="a.py", start_line=1, end_line=1, quote="nope")) == EV.UNVERIFIED_QUOTE
