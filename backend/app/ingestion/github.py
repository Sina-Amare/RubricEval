"""
GitHub ingestion.

Fixes the two concurrency bugs from the original adapter: each call uses its
OWN temp directory (no shared mutable state) and the blocking ``clone`` runs in
a worker thread (never on the event loop).
"""

from __future__ import annotations

import asyncio
import os
import shutil
import tempfile
from collections.abc import Iterator

from git import Repo
from git.exc import GitCommandError

from app.core.exceptions import IngestionError
from app.ingestion.normalize import NormalizedFileSet, normalize_items
from app.settings import get_settings
from app.utils.validators import extract_github_info, validate_github_url

_MAX_CLONE_BYTES = 200 * 1024 * 1024  # reject obviously abusive clones


def _clone(clone_url: str, dest: str, branch: str | None) -> str:
    env = {
        **os.environ,
        "GIT_TERMINAL_PROMPT": "0",      # never prompt for credentials
        "GIT_ALLOW_PROTOCOL": "https",   # block ext::/file:: clone exploits
    }
    kwargs = {"depth": 1, "single_branch": True, "env": env}
    if branch:
        kwargs["branch"] = branch
    try:
        repo = Repo.clone_from(clone_url, dest, **kwargs)
    except GitCommandError as exc:
        raise IngestionError(f"Could not clone repository: {exc.stderr or exc}") from exc
    try:
        return repo.head.commit.hexsha[:12]
    except Exception:
        return ""


def _dir_size(path: str) -> int:
    total = 0
    for root, _dirs, files in os.walk(path):
        if ".git" in root.split(os.sep):
            continue
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return total


def _walk(root: str, max_file_bytes: int) -> Iterator[tuple[str, bytes]]:
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d != ".git"]
        for name in filenames:
            full = os.path.join(dirpath, name)
            try:
                if os.path.getsize(full) > max_file_bytes:
                    continue
                with open(full, "rb") as fh:
                    data = fh.read(max_file_bytes + 1)
            except OSError:
                continue
            rel = os.path.relpath(full, root)
            yield rel, data


async def ingest_github(url: str) -> NormalizedFileSet:
    ok, err = validate_github_url(url)
    if not ok:
        raise IngestionError(err or "Invalid GitHub URL")
    s = get_settings()
    username, repo_name, branch = extract_github_info(url)
    clone_url = f"https://github.com/{username}/{repo_name}.git"

    tmp = tempfile.mkdtemp(prefix="ingest_gh_")
    try:
        commit_sha = await asyncio.to_thread(_clone, clone_url, tmp, branch)
        if _dir_size(tmp) > _MAX_CLONE_BYTES:
            raise IngestionError("Repository is too large to analyze")
        # _walk reads from disk; normalize in a thread (CPU-bound for big repos).
        items = list(_walk(tmp, s.max_file_bytes))
        return await asyncio.to_thread(
            normalize_items, items, "github", url, commit_sha=commit_sha, branch=branch
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
