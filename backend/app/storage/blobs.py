"""
Content-addressed blob store.

File contents are stored on disk keyed by their sha256, deduplicating
identical files across submissions. The DB only keeps ``path -> hash`` rows;
the bytes live here and are served to the engine and the Monaco viewer.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from app.settings import get_settings


class BlobStore:
    def __init__(self, root: str | None = None) -> None:
        self.root = Path(root or get_settings().blob_dir)

    def _path_for(self, digest: str) -> Path:
        return self.root / digest[:2] / digest

    def write(self, data: bytes) -> str:
        """Store ``data`` and return its sha256 hex digest (idempotent)."""
        digest = hashlib.sha256(data).hexdigest()
        target = self._path_for(digest)
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            tmp = target.with_suffix(".tmp")
            tmp.write_bytes(data)
            tmp.replace(target)
        return digest

    def read(self, digest: str) -> bytes:
        return self._path_for(digest).read_bytes()

    def read_text(self, digest: str) -> str:
        return self.read(digest).decode("utf-8", errors="replace")

    def exists(self, digest: str) -> bool:
        return self._path_for(digest).exists()
