"""DTOs for submissions and file content."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from app.core.enums import SourceType


class GithubSubmitIn(BaseModel):
    github_url: str


class SubmissionFileOut(BaseModel):
    path: str
    language: Optional[str]
    line_count: int
    size_bytes: int


class SubmissionOut(BaseModel):
    id: str
    source_type: SourceType
    source_ref: str
    commit_sha: Optional[str]
    branch: Optional[str]
    file_count: int
    total_bytes: int
    fileset_hash: str
    created_at: datetime
    files: list[SubmissionFileOut] = []


class FileContentOut(BaseModel):
    path: str
    language: Optional[str]
    content: str
