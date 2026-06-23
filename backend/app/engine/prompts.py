"""
Grading prompt construction.

The prompt gives the grader (1) the criterion, (2) a SIGNALS hint line, (3) a
compact project structure overview, and (4) the files most relevant to *this*
criterion rendered with 1-based line numbers — then asks for a single JSON
judgment. Relevance selection (``file_selection``) means a large repository's
prompt budget is spent on application code, not on whatever sorts first.

The ``<<<FILE path>>>`` / ``N| line`` format and the ``SIGNALS:`` line are a
contract consumed by both the real LiteLLM client and the offline ``FakeLLM``
(which keys its deterministic judgments off them), so behavior stays consistent
online and offline.
"""

from __future__ import annotations

import json
import re

from app.engine.file_selection import (
    render_selected,
    render_tree,
    select_for_criterion,
)
from app.settings import get_settings

PROMPT_TEMPLATE_VERSION = "grade@v2"

_SYSTEM = (
    "You are a strict, fair technical evaluator. You judge ONE criterion at a "
    "time against the provided source files. A PROJECT STRUCTURE overview shows "
    "the whole repository; the FILES section shows the files most relevant to "
    "this criterion in full. Base your judgment ONLY on what is shown, but use "
    "the structure to recognize what kind of project this is. Respond with ONLY "
    "a single JSON object — no prose, no markdown fences. Cite real file paths "
    "and line numbers as evidence."
)

_STOPWORDS = {
    "the", "and", "for", "that", "with", "this", "should", "must", "have", "has",
    "are", "is", "be", "a", "an", "of", "to", "in", "on", "or", "it", "its",
    "all", "any", "code", "repository", "repo", "file", "files", "use", "uses",
    "using", "contain", "contains", "implement", "implemented", "implements",
}


def derive_signals(title: str, instructions: str) -> list[str]:
    """Distinctive terms a grader should look for (also drives file selection)."""
    text = f"{title}\n{instructions}"
    backticked = re.findall(r"`([^`]+)`", text)
    words = re.findall(r"[A-Za-z_][A-Za-z0-9_]{2,}", text)
    signals: list[str] = []
    seen: set[str] = set()
    for term in [*backticked, *words]:
        low = term.lower()
        if low in _STOPWORDS or low in seen:
            continue
        seen.add(low)
        signals.append(term)
    return signals[:12]


def build_messages(criterion, files, *, schema: dict) -> list[dict[str, str]]:
    settings = get_settings()
    signals = derive_signals(criterion.title, criterion.instructions)
    selected = select_for_criterion(
        files,
        signals,
        files_budget=settings.grader_files_budget_chars,
        per_file_cap=settings.grader_per_file_chars,
        max_files=settings.grader_max_files,
    )
    tree = render_tree(files, budget=settings.grader_tree_budget_chars)
    files_block = render_selected(selected)
    shown = ", ".join(sf.file.path for sf in selected) or "(none)"

    user = f"""[CRITERION]
key: {criterion.key}
title: {criterion.title}
type: {criterion.type.value}
instructions: {criterion.instructions}
SIGNALS: {", ".join(signals)}

[PROJECT STRUCTURE]
(full repository layout; only the most relevant files are shown in full below)
{tree}

[FILES]
(the {len(selected)} files most relevant to this criterion: {shown})
{files_block}

[OUTPUT]
Return a JSON object:
  verdict: "pass" | "fail" | "partial"   (pass = criterion is satisfied)
  score: number 0-100                    (overall quality for this criterion)
  confidence: number 0-1
  rationale: short explanation
  evidence: array of {{ "path", "start_line", "end_line", "quote" }}
Only cite files shown in the FILES section. JSON schema: {json.dumps(schema)}
"""
    return [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content": user},
    ]
