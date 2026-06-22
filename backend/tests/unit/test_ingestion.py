"""Unit tests for ingestion: zip-slip, normalization, excludes, caps."""

from __future__ import annotations

import io
import zipfile
from types import SimpleNamespace

import pytest

from app.core.exceptions import IngestionError
from app.ingestion import normalize as normmod
from app.ingestion.normalize import normalize_items
from app.ingestion.zip import ingest_zip


def make_zip(files: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return buf.getvalue()


def test_zip_basic_normalization():
    data = make_zip({"main.py": "print('hi')\nx = 1\n", "README.md": "# Title"})
    fs = ingest_zip(data, "x.zip")
    assert fs.file_count == 2
    by = fs.by_path()
    assert by["main.py"].language == "python"
    assert by["main.py"].line_count == 3
    assert by["README.md"].language == "markdown"
    assert len(fs.fileset_hash) == 64


def test_zip_slip_blocked():
    data = make_zip({"../evil.txt": "pwned", "ok.py": "x=1"})
    with pytest.raises(IngestionError, match="zip-slip"):
        ingest_zip(data, "x.zip")


def test_excludes_binaries_and_vendored_dirs():
    data = make_zip(
        {
            "app.py": "x = 1",
            "node_modules/dep/index.js": "module.exports = {}",
            "logo.png": "\x89PNG fake",
            "package-lock.json": "{}",
        }
    )
    fs = ingest_zip(data, "x.zip")
    assert {f.path for f in fs.files} == {"app.py"}


def test_common_root_is_stripped():
    data = make_zip({"repo-main/src/app.py": "x=1", "repo-main/README.md": "hi"})
    fs = ingest_zip(data, "x.zip")
    assert {f.path for f in fs.files} == {"src/app.py", "README.md"}


def test_crlf_line_endings_normalized():
    data = make_zip({"a.py": "a = 1\r\nb = 2\r\n"})
    fs = ingest_zip(data, "x.zip")
    f = fs.files[0]
    assert "\r" not in f.content
    assert f.line_count == 3


def test_empty_after_exclusions_rejected():
    data = make_zip({"logo.png": "x", "node_modules/a.js": "y"})
    with pytest.raises(IngestionError):
        ingest_zip(data, "x.zip")


def test_file_count_cap(monkeypatch):
    fake = SimpleNamespace(max_total_mb=10, max_file_bytes=1_000_000, max_file_count=1)
    monkeypatch.setattr(normmod, "get_settings", lambda: fake)
    items = [("a.py", b"x=1"), ("b.py", b"y=2")]
    with pytest.raises(IngestionError, match="files"):
        normalize_items(items, "zip", "x.zip")


def test_fileset_hash_is_content_addressed():
    a = ingest_zip(make_zip({"a.py": "x=1"}), "a.zip")
    b = ingest_zip(make_zip({"a.py": "x=1"}), "b.zip")  # different ref, same content
    c = ingest_zip(make_zip({"a.py": "x=2"}), "c.zip")
    assert a.fileset_hash == b.fileset_hash
    assert a.fileset_hash != c.fileset_hash
