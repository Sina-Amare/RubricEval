"""Rebuild a NormalizedFileSet from persisted DB rows + blob storage.

The engine runs later (possibly in another process), so it reconstructs the
exact file content the verifier and Monaco need from the content-addressed
blob store rather than re-cloning.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.submissions import SubmissionRepository
from app.ingestion.normalize import NormalizedFile, NormalizedFileSet
from app.storage.blobs import BlobStore


async def load_fileset(
    session: AsyncSession, submission_id: str
) -> Optional[NormalizedFileSet]:
    sub = await SubmissionRepository(session).get(submission_id)
    if sub is None:
        return None
    blobs = BlobStore()
    files: list[NormalizedFile] = []
    for f in sorted(sub.files, key=lambda x: x.path):
        content = blobs.read_text(f.file_hash) if blobs.exists(f.file_hash) else ""
        files.append(
            NormalizedFile(
                path=f.path,
                content=content,
                file_hash=f.file_hash,
                size_bytes=f.size_bytes,
                language=f.language,
                line_count=f.line_count,
            )
        )
    return NormalizedFileSet(
        source_type=sub.source_type.value,
        source_ref=sub.source_ref,
        files=files,
        commit_sha=sub.commit_sha,
        branch=sub.branch,
        fileset_hash=sub.fileset_hash,
        total_bytes=sub.total_bytes,
    )
