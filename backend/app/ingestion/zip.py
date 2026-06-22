"""ZIP ingestion with zip-slip and zip-bomb protection."""

from __future__ import annotations

import io
import os
import zipfile
from collections.abc import Iterator

from app.core.exceptions import IngestionError
from app.ingestion.normalize import NormalizedFileSet, normalize_items
from app.settings import get_settings


def _is_unsafe_member(name: str) -> bool:
    norm = name.replace("\\", "/")
    if norm.startswith("/"):  # absolute path
        return True
    if os.path.isabs(norm):
        return True
    return ".." in norm.split("/")


def _common_root(names: list[str]) -> str:
    """Detect a single top-level folder (e.g. ``repo-main/``) to strip."""
    roots = set()
    for n in names:
        n = n.replace("\\", "/").lstrip("/")
        first = n.split("/", 1)[0]
        roots.add(first)
        if len(roots) > 1:
            return ""
    if len(roots) == 1 and all("/" in n.replace("\\", "/") for n in names):
        return next(iter(roots)) + "/"
    return ""


def ingest_zip(data: bytes, source_ref: str = "upload.zip") -> NormalizedFileSet:
    s = get_settings()
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise IngestionError("Uploaded file is not a valid ZIP archive") from exc

    infos = [i for i in zf.infolist() if not i.is_dir()]
    if not infos:
        raise IngestionError("ZIP archive is empty")

    for info in infos:
        if _is_unsafe_member(info.filename):
            raise IngestionError(f"Unsafe path in archive (zip-slip blocked): {info.filename}")

    # Cheap zip-bomb guards using declared metadata before reading anything.
    if len(infos) > s.max_file_count * 4:
        raise IngestionError(f"ZIP has too many entries (> {s.max_file_count * 4})")
    declared = sum(i.file_size for i in infos)
    if declared > s.max_total_mb * 1024 * 1024 * 20:
        raise IngestionError("ZIP decompresses to too much data (possible zip bomb)")

    root = _common_root([i.filename for i in infos])

    def _items() -> Iterator[tuple[str, bytes]]:
        # Lazy: normalize_items stops early once content caps are hit.
        for info in infos:
            name = info.filename.replace("\\", "/").lstrip("/")
            if root and name.startswith(root):
                name = name[len(root):]
            if not name:
                continue
            with zf.open(info) as fh:
                yield name, fh.read(s.max_file_bytes + 1)

    return normalize_items(_items(), source_type="zip", source_ref=source_ref)
