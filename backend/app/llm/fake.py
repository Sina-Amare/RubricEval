"""
Deterministic offline LLM backend.

``FakeLLM`` parses the SIGNALS hint and the numbered FILE blocks from the
grading prompt and returns a real, schema-valid judgment that cites an actual
file + line when a signal is found. This lets the whole pipeline — including
evidence verification and Monaco line highlighting — run offline and
deterministically in tests and E2E, while still exercising *real* data paths.
"""

from __future__ import annotations

import re
from typing import Any, Optional

from app.interfaces.llm import LLMPort

_FILE_RE = re.compile(r"<<<FILE (?P<path>.+?)>>>\n(?P<body>.*?)(?=\n<<<FILE |\Z)", re.DOTALL)
_LINE_RE = re.compile(r"^(?P<n>\d+)\| (?P<text>.*)$")


def _parse_signals(text: str) -> list[str]:
    for line in text.splitlines():
        if line.startswith("SIGNALS:"):
            return [s.strip() for s in line[len("SIGNALS:"):].split(",") if s.strip()]
    return []


def _parse_files(text: str) -> list[tuple[str, list[tuple[int, str]]]]:
    files: list[tuple[str, list[tuple[int, str]]]] = []
    for m in _FILE_RE.finditer(text):
        path = m.group("path").strip()
        lines: list[tuple[int, str]] = []
        for raw in m.group("body").split("\n"):
            lm = _LINE_RE.match(raw)
            if lm:
                lines.append((int(lm.group("n")), lm.group("text")))
        files.append((path, lines))
    return files


class FakeLLM(LLMPort):
    async def complete_json(
        self,
        messages: list[dict[str, str]],
        *,
        schema: Optional[dict[str, Any]] = None,
        model_id: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> dict[str, Any]:
        text = "\n".join(m.get("content", "") for m in messages)
        signals = _parse_signals(text)
        files = _parse_files(text)

        for term in signals:
            needle = term.lower()
            for path, lines in files:
                for line_no, line_text in lines:
                    if needle in line_text.lower():
                        return {
                            "verdict": "pass",
                            "score": 85.0,
                            "confidence": 0.9,
                            "rationale": f"Found signal '{term}' at {path}:{line_no}.",
                            "evidence": [
                                {
                                    "path": path,
                                    "start_line": line_no,
                                    "end_line": line_no,
                                    "quote": line_text.strip()[:200],
                                }
                            ],
                        }
        return {
            "verdict": "fail",
            "score": 25.0,
            "confidence": 0.7,
            "rationale": "No supporting evidence for this criterion was found.",
            "evidence": [],
        }
