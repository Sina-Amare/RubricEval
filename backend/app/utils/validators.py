"""
Input validation helpers.

Ported from the original ``src/utils/validators.py`` — only the GitHub URL
helpers, which remain relevant for the ingestion layer. Telegram-specific
validators were dropped.
"""

from __future__ import annotations

import re
from typing import Optional
from urllib.parse import urlparse

_USERNAME_RE = re.compile(r"^[a-zA-Z0-9]([a-zA-Z0-9-]{0,37}[a-zA-Z0-9])?$")
_REPO_RE = re.compile(r"^[a-zA-Z0-9._-]{1,100}$")


def validate_github_url(url: str) -> tuple[bool, Optional[str]]:
    """Validate a GitHub repository URL (supports ``/tree/<branch>`` forms)."""
    if not url or not isinstance(url, str):
        return False, "URL is required"
    url = url.strip()
    try:
        parsed = urlparse(url)
    except Exception as exc:  # pragma: no cover - defensive
        return False, f"Invalid URL: {exc}"

    if parsed.scheme not in ("http", "https"):
        return False, "URL must start with http:// or https://"
    if parsed.netloc not in ("github.com", "www.github.com"):
        return False, "URL must be from github.com"

    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) < 2:
        return False, "URL must include username and repository"

    username, repo = parts[0], parts[1]
    if repo.endswith(".git"):
        repo = repo[:-4]
    if not _USERNAME_RE.match(username):
        return False, f"Invalid GitHub username: {username}"
    if not _REPO_RE.match(repo):
        return False, f"Invalid repository name: {repo}"
    return True, None


def extract_github_info(url: str) -> tuple[str, str, Optional[str]]:
    """Return ``(username, repo, branch|None)`` for a GitHub URL."""
    parsed = urlparse(url.strip())
    parts = [p for p in parsed.path.split("/") if p]
    username, repo = parts[0], parts[1]
    if repo.endswith(".git"):
        repo = repo[:-4]
    branch = None
    if len(parts) >= 4 and parts[2] == "tree":
        branch = "/".join(parts[3:])
    return username, repo, branch
