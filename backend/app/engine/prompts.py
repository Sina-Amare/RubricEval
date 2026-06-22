"""
Grading prompt construction.

The prompt embeds the criterion, a SIGNALS hint line, and the submission files
rendered with 1-based line numbers, then asks for a single JSON judgment. The
exact same format is consumed by both the real LiteLLM client and the offline
``FakeLLM`` (which keys its deterministic judgments off SIGNALS + the numbered
file blocks), so behavior is consistent online and offline.
"""

from __future__ import annotations

import json
import re

PROMPT_TEMPLATE_VERSION = "grade@v1"

_SYSTEM = (
    "You are a strict, fair technical evaluator. You judge ONE criterion at a "
    "time against the provided source files. Base your judgment ONLY on the "
    "files shown. Respond with ONLY a single JSON object — no prose, no "
    "markdown fences. Cite real file paths and line numbers as evidence."
)

_STOPWORDS = {
    "the", "and", "for", "that", "with", "this", "should", "must", "have", "has",
    "are", "is", "be", "a", "an", "of", "to", "in", "on", "or", "it", "its",
    "all", "any", "code", "repository", "repo", "file", "files", "use", "uses",
    "using", "contain", "contains", "implement", "implemented", "implements",
}

_MAX_PROMPT_CHARS = 60_000  # budget for the files block (free-model friendly)


def derive_signals(title: str, instructions: str) -> list[str]:
    """Distinctive terms a grader should look for (also used by FakeLLM)."""
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


def render_files(files: list, budget: int = _MAX_PROMPT_CHARS) -> str:
    """Render files as ``<<<FILE path>>>`` blocks with ``N| line`` numbering."""
    blocks: list[str] = []
    used = 0
    for f in files:
        header = f"<<<FILE {f.path}>>>"
        lines = f.content.split("\n")
        numbered = "\n".join(f"{i}| {ln}" for i, ln in enumerate(lines, start=1))
        block = f"{header}\n{numbered}"
        if used + len(block) > budget:
            remaining = budget - used
            if remaining > len(header) + 50:
                blocks.append(block[:remaining] + "\n... [truncated]")
            break
        blocks.append(block)
        used += len(block)
    return "\n\n".join(blocks)


def build_messages(criterion, files, *, schema: dict) -> list[dict[str, str]]:
    signals = derive_signals(criterion.title, criterion.instructions)
    files_block = render_files(files)
    user = f"""[CRITERION]
key: {criterion.key}
title: {criterion.title}
type: {criterion.type.value}
instructions: {criterion.instructions}
SIGNALS: {", ".join(signals)}

[FILES]
{files_block}

[OUTPUT]
Return a JSON object:
  verdict: "pass" | "fail" | "partial"   (pass = criterion is satisfied)
  score: number 0-100                    (overall quality for this criterion)
  confidence: number 0-1
  rationale: short explanation
  evidence: array of {{ "path", "start_line", "end_line", "quote" }}
JSON schema: {json.dumps(schema)}
"""
    return [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content": user},
    ]
