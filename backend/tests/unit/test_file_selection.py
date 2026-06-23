"""Unit tests for relevance-driven file selection.

These pin the behavior that makes grading meaningful on large repos: the most
relevant application code is selected first (never starved by migrations / lock
files / docs), selection is bounded (file count + char budget) so we stay under
provider token limits, and the rendered format stays compatible with the
evidence verifier and the offline FakeLLM.
"""

from __future__ import annotations

from app.engine.file_selection import (
    classify,
    render_selected,
    render_tree,
    select_for_criterion,
)
from app.ingestion.normalize import NormalizedFile


def _f(path: str, content: str = "x = 1\n") -> NormalizedFile:
    return NormalizedFile(
        path=path,
        content=content,
        file_hash="h",
        size_bytes=len(content.encode()),
        language=None,
        line_count=content.count("\n") + 1,
    )


# --- classify -------------------------------------------------------------

def test_classify_roles():
    assert classify("app/main.py") == "entrypoint"
    assert classify("app/services/grader.py") == "source"
    assert classify("tests/test_grader.py") == "test"
    assert classify("app/components/Card.test.tsx") == "test"
    assert classify("alembic/versions/001_init.py") == "migration"
    assert classify("README.md") == "doc"
    assert classify("pyproject.toml") == "config"
    assert classify("poetry.lock") == "skip"
    assert classify("logo.svg") == "skip"


# --- selection prioritization (the core bug fix) --------------------------

def test_app_source_beats_migrations_even_when_alphabetically_last():
    """The ScrapeGpt failure mode: migrations sort first, app/ sorts later."""
    files = [
        _f(f"alembic/versions/{i:03d}_m.py", "def upgrade():\n    pass\n" * 50)
        for i in range(15)
    ]
    files.append(_f("app/services/processor.py", "def process(x: int) -> int:\n"))
    files.append(_f("app/main.py", "app = FastAPI()\n"))

    selected = select_for_criterion(
        files, ["process", "service"], files_budget=5000, per_file_cap=2000, max_files=5
    )
    paths = [s.file.path for s in selected]
    # Application code must be selected; migrations must not crowd it out.
    assert "app/services/processor.py" in paths
    assert "app/main.py" in paths
    assert paths[0].startswith("app/")


def test_signal_terms_pull_relevant_files_to_the_top():
    files = [
        _f("app/models.py", "class User:\n    pass\n"),
        _f("tests/test_api.py", "def test_login():\n    assert True\n"),
        _f("app/views.py", "def index():\n    return 1\n"),
    ]
    selected = select_for_criterion(
        files, ["test", "def test_"], files_budget=9000, per_file_cap=3000, max_files=3
    )
    # The test file carries the 'test' signal in both path and content.
    assert selected[0].file.path == "tests/test_api.py"


def test_budget_and_max_files_are_bounded():
    files = [_f(f"app/m{i}.py", "y = 2\n" * 200) for i in range(40)]
    selected = select_for_criterion(
        files, [], files_budget=10000, per_file_cap=1000, max_files=6
    )
    assert len(selected) <= 6
    assert sum(len(s.content) for s in selected) <= 10000


def test_oversized_file_is_head_truncated():
    big = "line\n" * 5000  # ~25k chars
    selected = select_for_criterion(
        [_f("app/big.py", big)], [], files_budget=50000, per_file_cap=2000, max_files=5
    )
    assert selected[0].truncated is True
    assert len(selected[0].content) <= 2000


def test_skip_files_are_never_selected():
    files = [_f("poetry.lock", "a==1\n" * 100), _f("app/core.py", "z = 3\n")]
    selected = select_for_criterion(
        files, [], files_budget=50000, per_file_cap=4000, max_files=5
    )
    paths = [s.file.path for s in selected]
    assert "poetry.lock" not in paths
    assert "app/core.py" in paths


def test_selection_is_deterministic():
    files = [_f(f"app/x{i}.py", "q = 9\n") for i in range(10)]
    a = select_for_criterion(files, ["q"], files_budget=9000, per_file_cap=1000, max_files=4)
    b = select_for_criterion(files, ["q"], files_budget=9000, per_file_cap=1000, max_files=4)
    assert [s.file.path for s in a] == [s.file.path for s in b]


# --- tree -----------------------------------------------------------------

def test_tree_lists_paths_when_small():
    files = [_f("app/a.py"), _f("app/b.py")]
    tree = render_tree(files, budget=4000)
    assert "app/a.py" in tree and "app/b.py" in tree


def test_tree_summarizes_when_large():
    files = [_f(f"app/sub{i}/mod{j}.py") for i in range(20) for j in range(10)]
    tree = render_tree(files, budget=1500)
    assert len(tree) <= 1500
    assert "files across" in tree  # collapsed to a directory summary


# --- render format (FakeLLM + evidence verifier contract) -----------------

def test_render_selected_keeps_markers_and_numbering():
    selected = select_for_criterion(
        [_f("app/x.py", "alpha\nbeta\ngamma\n")],
        [], files_budget=9000, per_file_cap=3000, max_files=1,
    )
    out = render_selected(selected)
    assert "<<<FILE app/x.py>>>" in out
    assert "1| alpha" in out
    assert "2| beta" in out
