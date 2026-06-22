"""
Shared normalization for all ingestion sources.

Both the GitHub and ZIP paths funnel their ``(path, raw_bytes)`` pairs through
``normalize_items`` so they produce an identical ``NormalizedFileSet``. This is
also where caps (count / size), excludes, binary detection, language detection,
and 1-based line counting live, so the grader, evidence verifier, and the
Monaco viewer all agree on the same content and line numbers.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from dataclasses import dataclass, field

from app.core.exceptions import IngestionError
from app.settings import get_settings

# Directories whose contents are never code-under-review.
_EXCLUDE_DIR_PARTS = {
    ".git", ".svn", ".hg", "node_modules", "vendor", "venv", ".venv", "env",
    "__pycache__", "build", "dist", "out", "target", "bin", "obj", ".next",
    ".nuxt", ".cache", "coverage", ".idea", ".vscode", "bower_components",
}
# Lockfiles / generated noise.
_EXCLUDE_NAMES = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock",
    "Thumbs.db", ".DS_Store",
}
_BINARY_EXTS = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".webp", ".pdf", ".mp4", ".mp3",
    ".wav", ".avi", ".zip", ".tar", ".gz", ".rar", ".7z", ".exe", ".dll", ".so",
    ".dylib", ".a", ".o", ".class", ".jar", ".war", ".woff", ".woff2", ".ttf",
    ".eot", ".otf", ".pyc", ".pyo", ".bin", ".parquet", ".h5", ".hdf5", ".svg",
}
_LANGUAGE_MAP = {
    ".py": "python", ".js": "javascript", ".ts": "typescript", ".jsx": "javascript",
    ".tsx": "typescript", ".go": "go", ".java": "java", ".cpp": "cpp", ".c": "c",
    ".cs": "csharp", ".php": "php", ".rb": "ruby", ".rs": "rust", ".kt": "kotlin",
    ".swift": "swift", ".html": "html", ".css": "css", ".scss": "scss",
    ".sass": "sass", ".json": "json", ".yaml": "yaml", ".yml": "yaml",
    ".xml": "xml", ".md": "markdown", ".sql": "sql", ".sh": "bash",
    ".toml": "toml", ".dockerfile": "dockerfile",
}


@dataclass
class NormalizedFile:
    path: str
    content: str
    file_hash: str
    size_bytes: int
    language: str | None
    line_count: int


@dataclass
class NormalizedFileSet:
    source_type: str
    source_ref: str
    files: list[NormalizedFile] = field(default_factory=list)
    commit_sha: str | None = None
    branch: str | None = None
    fileset_hash: str = ""
    total_bytes: int = 0

    @property
    def file_count(self) -> int:
        return len(self.files)

    def by_path(self) -> dict[str, NormalizedFile]:
        return {f.path: f for f in self.files}


def _normalize_path(path: str) -> str:
    return path.replace("\\", "/").lstrip("/")


def should_exclude(rel_path: str) -> bool:
    rel_path = _normalize_path(rel_path)
    parts = rel_path.split("/")
    if any(p in _EXCLUDE_DIR_PARTS for p in parts[:-1]):
        return True
    name = parts[-1]
    if name in _EXCLUDE_NAMES:
        return True
    dot = name.rfind(".")
    ext = name[dot:].lower() if dot != -1 else ""
    return ext in _BINARY_EXTS


def detect_language(path: str) -> str | None:
    name = path.rsplit("/", 1)[-1].lower()
    if name in ("dockerfile", "makefile", "rakefile"):
        return name
    dot = name.rfind(".")
    if dot == -1:
        return None
    return _LANGUAGE_MAP.get(name[dot:])


def _decode(data: bytes) -> str | None:
    if b"\x00" in data[:8192]:  # NUL byte -> treat as binary
        return None
    for enc in ("utf-8", "utf-16", "latin-1"):
        try:
            return data.decode(enc)
        except (UnicodeDecodeError, UnicodeError):
            continue
    return None


def normalize_items(
    items: Iterable[tuple[str, bytes]],
    source_type: str,
    source_ref: str,
    *,
    commit_sha: str | None = None,
    branch: str | None = None,
) -> NormalizedFileSet:
    """Build a ``NormalizedFileSet`` from ``(path, raw_bytes)`` pairs."""
    s = get_settings()
    max_total = s.max_total_mb * 1024 * 1024
    files: list[NormalizedFile] = []
    total = 0

    for raw_path, data in items:
        path = _normalize_path(raw_path)
        if not path or should_exclude(path):
            continue
        if len(data) > s.max_file_bytes:
            continue  # skip oversized single files
        text = _decode(data)
        if text is None or not text.strip():
            continue
        # Normalize line endings so line counts/highlights are stable.
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        encoded = text.encode("utf-8")
        total += len(encoded)
        if total > max_total:
            raise IngestionError(
                f"Submission exceeds the {s.max_total_mb}MB content limit"
            )
        if len(files) >= s.max_file_count:
            raise IngestionError(f"Submission exceeds {s.max_file_count} files")
        files.append(
            NormalizedFile(
                path=path,
                content=text,
                file_hash=hashlib.sha256(encoded).hexdigest(),
                size_bytes=len(encoded),
                language=detect_language(path),
                line_count=text.count("\n") + 1 if text else 0,
            )
        )

    if not files:
        raise IngestionError("No analyzable text files found in submission")

    files.sort(key=lambda f: f.path)
    fingerprint = "\n".join(f"{f.path}:{f.file_hash}" for f in files)
    fileset_hash = hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()
    return NormalizedFileSet(
        source_type=source_type,
        source_ref=source_ref,
        files=files,
        commit_sha=commit_sha,
        branch=branch,
        fileset_hash=fileset_hash,
        total_bytes=total,
    )
