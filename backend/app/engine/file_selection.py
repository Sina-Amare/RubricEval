"""
Relevance-driven file selection for grading.

A real repository holds far more code than fits in one prompt, and most of it is
irrelevant to any single criterion. The naive approach — render files in path
order until a char budget runs out — spends the whole budget on whatever sorts
first (``alembic/versions/*``, lock files, fixtures) and the grader may never see
a line of application code. That makes verdicts meaningless on large repos.

This module replaces that with one **standard, repo-agnostic, two-stage
mechanism** used for every project:

1.  **Structure first.** A compact project tree (every path, summarized by
    directory when large) is always included, so the grader knows the whole
    project shape even though only a subset of files is shown in full.

2.  **Relevant files only.** Each file is scored for the criterion being graded —
    a structural prior (entrypoints and app/src source rank high; migrations,
    generated code, configs, docs rank low) plus how strongly the criterion's
    signal terms appear in the path and content. The highest-scoring files are
    selected up to a bounded file-count and char budget, with oversized files
    head-truncated so breadth wins over any single giant file.

Selection is deterministic (no LLM call, no randomness), so reviews are
reproducible and we never blow past provider token limits.
"""

from __future__ import annotations

import posixpath
from collections import defaultdict
from dataclasses import dataclass

from app.ingestion.normalize import NormalizedFile

# --- role classification --------------------------------------------------

# Files with no evaluative signal — skipped entirely (ingestion already drops
# binaries and vendored dirs; this catches the text noise that survives).
_SKIP_NAMES = {
    "poetry.lock", "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
    "composer.lock", "cargo.lock", "go.sum", ".gitkeep", ".gitignore",
    ".dockerignore", ".prettierrc", ".editorconfig", "py.typed",
}
_SKIP_EXTS = {
    ".lock", ".map", ".min.js", ".min.css", ".snap", ".csv", ".tsv",
    ".svg", ".lockb",
}

_ENTRYPOINT_NAMES = {
    "main.py", "app.py", "__main__.py", "manage.py", "wsgi.py", "asgi.py",
    "cli.py", "server.py", "bot.py", "run.py", "application.py",
    "index.ts", "index.tsx", "index.js", "server.ts", "app.ts", "main.ts",
    "main.go", "main.rs", "program.cs",
}
_SOURCE_EXTS = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".java", ".rb", ".kt",
    ".kts", ".cs", ".php", ".cpp", ".cc", ".cxx", ".c", ".h", ".hpp", ".scala",
    ".swift", ".m", ".mm", ".vue", ".svelte", ".dart", ".ex", ".exs",
}
_CONFIG_EXTS = {
    ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf", ".env",
    ".example", ".txt", ".properties", ".mako",
}
_DOC_EXTS = {".md", ".rst", ".adoc", ".mdx"}

# Path markers for low-signal files: kept (they still exist in the tree) but
# scored low so application code is always preferred within the budget.
_LOW_SIGNAL_MARKERS = (
    "migrations/", "/migration/", "alembic/versions/", "/fixtures/",
    "/__snapshots__/", "/snapshots/", "/testdata/", "/golden/", "/seeds/",
    "/locale/", "/locales/", "/static/", "/public/",
)
# Directory names that mark genuine source code (boosts relevance).
_SOURCE_DIR_MARKERS = (
    "src/", "app/", "lib/", "libs/", "services/", "service/", "core/",
    "engine/", "api/", "internal/", "pkg/", "domain/", "handlers/", "handler/",
    "controllers/", "controller/", "routers/", "routes/", "models/", "model/",
    "schemas/", "repositories/", "usecases/", "use_cases/", "components/",
    "hooks/", "utils/", "helpers/", "jobs/", "workers/", "tasks/", "db/",
)


@dataclass
class SelectedFile:
    file: NormalizedFile
    content: str       # possibly head-truncated for the prompt
    truncated: bool
    score: float


def _basename(path: str) -> str:
    return path.rsplit("/", 1)[-1].lower()


def _ext(name: str) -> str:
    dot = name.rfind(".")
    return name[dot:] if dot != -1 else ""


def classify(path: str) -> str:
    """One of: skip | entrypoint | test | source | migration | config | doc | other."""
    p = path.lower()
    name = _basename(p)
    ext = _ext(name)
    if name in _SKIP_NAMES or ext in _SKIP_EXTS or name.endswith(".min.js"):
        return "skip"
    if any(marker in p for marker in ("migrations/", "/migration/", "alembic/versions/")):
        return "migration"
    parts = p.split("/")
    is_test = (
        "test" in parts
        or "tests" in parts
        or "__tests__" in parts
        or name.startswith("test_")
        or name.endswith("_test" + ext)
        or ".test." in name
        or ".spec." in name
        or name.endswith("conftest.py")
    )
    if is_test:
        return "test"
    if name in _ENTRYPOINT_NAMES:
        return "entrypoint"
    if ext in _SOURCE_EXTS:
        return "source"
    if ext in _DOC_EXTS:
        return "doc"
    if ext in _CONFIG_EXTS:
        return "config"
    return "other"


def _structural_prior(path: str, role: str) -> float:
    """Role-based base score — how much this file matters before signals."""
    p = path.lower()
    base = {
        "entrypoint": 45.0,
        "source": 22.0,
        "test": 20.0,
        "doc": 4.0,
        "config": 3.0,
        "migration": 0.5,
        "other": 1.5,
    }.get(role, 1.5)
    if role in ("source", "entrypoint", "test") and any(
        m in p for m in _SOURCE_DIR_MARKERS
    ):
        base += 8.0
    if any(m in p for m in _LOW_SIGNAL_MARKERS):
        base -= 30.0
    if _basename(p) in ("readme.md", "readme.rst", "readme"):
        base += 6.0
    # Shallower files (closer to the root of a package) are usually more central.
    depth = path.count("/")
    base -= min(depth, 6) * 0.5
    return base


def _signal_score(file: NormalizedFile, signals: list[str]) -> float:
    """How strongly the criterion's signal terms appear in this file."""
    if not signals:
        return 0.0
    path_l = file.path.lower()
    text_l = (file.content or "").lower()
    score = 0.0
    for term in signals:
        t = term.lower().strip()
        if len(t) < 2:
            continue
        if t in path_l:
            score += 10.0  # a path/name match is a strong relevance hint
        hits = text_l.count(t)
        if hits:
            score += min(hits, 6) * 1.4  # content hits, capped to avoid runaway
    return score


def select_for_criterion(
    files: list[NormalizedFile],
    signals: list[str],
    *,
    files_budget: int,
    per_file_cap: int,
    max_files: int,
) -> list[SelectedFile]:
    """Rank files by relevance to a criterion and select within bounds.

    Returns the chosen files (highest relevance first), each head-truncated to
    ``per_file_cap`` chars, collectively kept under ``files_budget`` chars and
    ``max_files`` files. Deterministic: ties break on path.
    """
    terms = [t.lower().strip() for t in signals if len(t.strip()) >= 2]
    ranked: list[tuple[bool, float, NormalizedFile]] = []
    for f in files:
        role = classify(f.path)
        if role == "skip" or not (f.content or "").strip():
            continue
        score = _structural_prior(f.path, role) + _signal_score(f, signals)
        # A file whose *path* matches a criterion term (e.g. the README for a
        # "has README" gate, test files for a "has tests" check) is the file the
        # criterion is really about — guarantee it leads, so gates never fail
        # just because source files crowded the named file out of the budget.
        named = any(t in f.path.lower() for t in terms)
        ranked.append((named, score, f))
    ranked.sort(key=lambda t: (not t[0], -t[1], t[2].path))

    chosen: list[SelectedFile] = []
    used = 0
    for _named, score, f in ranked:
        if len(chosen) >= max_files:
            break
        content, truncated = f.content, False
        if len(content) > per_file_cap:
            content, truncated = _head(content, per_file_cap), True
        if used + len(content) > files_budget:
            remaining = files_budget - used
            if remaining < 600:  # no meaningful room left for another file
                break
            content, truncated = _head(f.content, remaining), True
        chosen.append(SelectedFile(file=f, content=content, truncated=truncated, score=score))
        used += len(content)
    return chosen


def _head(content: str, cap: int) -> str:
    """First ``cap`` chars, trimmed back to the last full line when sensible."""
    cut = content[:cap]
    nl = cut.rfind("\n")
    return cut[:nl] if nl > cap * 0.5 else cut


def render_tree(files: list[NormalizedFile], *, budget: int) -> str:
    """A compact project structure overview that always fits in ``budget`` chars.

    Lists every path when small; for large repos, collapses to a per-directory
    summary (file count + the languages present) so the grader still sees the
    whole shape of the project without spending the prompt budget on it.
    """
    paths = sorted(f.path for f in files)
    full = "\n".join(paths)
    if len(full) <= budget:
        return full

    by_dir: dict[str, list[str]] = defaultdict(list)
    for p in paths:
        by_dir[posixpath.dirname(p) or "."].append(posixpath.basename(p))

    lines: list[str] = [f"({len(paths)} files across {len(by_dir)} directories)"]
    for d in sorted(by_dir):
        names = by_dir[d]
        exts = sorted({_ext(n) for n in names if "." in n})
        kinds = ", ".join(e for e in exts[:6] if e) or "files"
        lines.append(f"{d}/  — {len(names)} ({kinds})")
    out = "\n".join(lines)
    if len(out) <= budget:
        return out
    return out[: budget - 15].rstrip() + "\n… [truncated]"


def render_selected(selected: list[SelectedFile]) -> str:
    """Render chosen files as ``<<<FILE path>>>`` blocks with ``N| line`` numbers.

    The markers and 1-based numbering are a contract shared with ``FakeLLM`` and
    the evidence verifier — line numbers map to the real file, so cited lines
    resolve correctly in the report (head truncation preserves numbering).
    """
    blocks: list[str] = []
    for sf in selected:
        header = f"<<<FILE {sf.file.path}>>>"
        lines = sf.content.split("\n")
        numbered = "\n".join(f"{i}| {ln}" for i, ln in enumerate(lines, start=1))
        suffix = "\n... [truncated]" if sf.truncated else ""
        blocks.append(f"{header}\n{numbered}{suffix}")
    return "\n\n".join(blocks)
