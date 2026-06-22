"""Ingest a submission and persist it (blobs + DB), with fileset dedup."""

from __future__ import annotations

import asyncio
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import SourceType
from app.core.exceptions import IngestionError
from app.db.models import Submission, SubmissionFile
from app.db.repositories.submissions import SubmissionRepository
from app.ingestion.github import ingest_github
from app.ingestion.zip import ingest_zip
from app.storage.blobs import BlobStore


async def ingest_and_store(
    session: AsyncSession,
    *,
    source_type: str,
    github_url: Optional[str] = None,
    zip_bytes: Optional[bytes] = None,
    source_ref: Optional[str] = None,
) -> Submission:
    if source_type == "github":
        if not github_url:
            raise IngestionError("github_url is required")
        fileset = await ingest_github(github_url)
    elif source_type == "zip":
        if zip_bytes is None:
            raise IngestionError("zip file is required")
        fileset = await asyncio.to_thread(ingest_zip, zip_bytes, source_ref or "upload.zip")
    else:
        raise IngestionError(f"Unknown source_type: {source_type}")

    repo = SubmissionRepository(session)
    existing = await repo.get_by_fileset_hash(fileset.fileset_hash)
    if existing is not None:
        return existing  # idempotent: identical content -> reuse submission

    blobs = BlobStore()
    for f in fileset.files:
        blobs.write(f.content.encode("utf-8"))

    submission = Submission(
        source_type=SourceType(fileset.source_type),
        source_ref=fileset.source_ref,
        commit_sha=fileset.commit_sha,
        branch=fileset.branch,
        fileset_hash=fileset.fileset_hash,
        file_count=fileset.file_count,
        total_bytes=fileset.total_bytes,
    )
    file_rows = [
        SubmissionFile(
            path=f.path,
            file_hash=f.file_hash,
            size_bytes=f.size_bytes,
            language=f.language,
            line_count=f.line_count,
        )
        for f in fileset.files
    ]
    return await repo.create(submission, file_rows)
