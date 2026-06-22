"""Submission ingestion + file browsing endpoints (operator-only)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session, require_operator
from app.api.schemas.submission import (
    FileContentOut,
    GithubSubmitIn,
    SubmissionFileOut,
    SubmissionOut,
)
from app.core.exceptions import IngestionError
from app.db.models import Submission
from app.db.repositories.submissions import SubmissionRepository
from app.services.submissions import ingest_and_store
from app.storage.blobs import BlobStore

router = APIRouter(
    prefix="/submissions", tags=["submissions"], dependencies=[Depends(require_operator)]
)


def _out(sub: Submission) -> SubmissionOut:
    return SubmissionOut(
        id=sub.id,
        source_type=sub.source_type,
        source_ref=sub.source_ref,
        commit_sha=sub.commit_sha,
        branch=sub.branch,
        file_count=sub.file_count,
        total_bytes=sub.total_bytes,
        fileset_hash=sub.fileset_hash,
        created_at=sub.created_at,
        files=[
            SubmissionFileOut(
                path=f.path,
                language=f.language,
                line_count=f.line_count,
                size_bytes=f.size_bytes,
            )
            for f in sorted(sub.files, key=lambda x: x.path)
        ],
    )


@router.post("/github", response_model=SubmissionOut, status_code=201)
async def submit_github(
    body: GithubSubmitIn, session: AsyncSession = Depends(get_session)
) -> SubmissionOut:
    try:
        sub = await ingest_and_store(session, source_type="github", github_url=body.github_url)
    except IngestionError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc
    return _out(sub)


@router.post("/zip", response_model=SubmissionOut, status_code=201)
async def submit_zip(
    file: UploadFile = File(...), session: AsyncSession = Depends(get_session)
) -> SubmissionOut:
    data = await file.read()
    if not data[:2] == b"PK":  # ZIP magic
        raise HTTPException(status_code=400, detail="Uploaded file is not a ZIP archive")
    try:
        sub = await ingest_and_store(
            session,
            source_type="zip",
            zip_bytes=data,
            source_ref=file.filename or "upload.zip",
        )
    except IngestionError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc
    return _out(sub)


@router.get("/{submission_id}", response_model=SubmissionOut)
async def get_submission(
    submission_id: str, session: AsyncSession = Depends(get_session)
) -> SubmissionOut:
    sub = await SubmissionRepository(session).get(submission_id)
    if sub is None:
        raise HTTPException(status_code=404, detail="Submission not found")
    return _out(sub)


@router.get("/{submission_id}/files", response_model=list[SubmissionFileOut])
async def list_files(
    submission_id: str, session: AsyncSession = Depends(get_session)
) -> list[SubmissionFileOut]:
    sub = await SubmissionRepository(session).get(submission_id)
    if sub is None:
        raise HTTPException(status_code=404, detail="Submission not found")
    return [
        SubmissionFileOut(
            path=f.path, language=f.language, line_count=f.line_count, size_bytes=f.size_bytes
        )
        for f in sorted(sub.files, key=lambda x: x.path)
    ]


@router.get("/{submission_id}/files/content", response_model=FileContentOut)
async def file_content(
    submission_id: str, path: str, session: AsyncSession = Depends(get_session)
) -> FileContentOut:
    record = await SubmissionRepository(session).get_file(submission_id, path)
    if record is None:
        raise HTTPException(status_code=404, detail="File not found")
    blobs = BlobStore()
    content = blobs.read_text(record.file_hash) if blobs.exists(record.file_hash) else ""
    return FileContentOut(path=record.path, language=record.language, content=content)
