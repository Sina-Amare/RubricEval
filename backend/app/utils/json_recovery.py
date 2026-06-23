"""
Schema-agnostic JSON recovery for fallible LLM output.

Adapted from the original ``src/utils/json_recovery.py`` but stripped of the
hiring-specific partial-recovery logic. These strategies handle the common
ways a weak/free model mangles JSON: markdown fences, surrounding prose,
trailing commas, and missing commas. The caller validates the recovered
object against its own Pydantic schema.
"""

from __future__ import annotations

import json
import re
from typing import Any, Optional


def extract_json(text: str) -> Optional[dict[str, Any]]:
    """Best-effort extraction of a single JSON object from ``text``.

    Returns the parsed dict, or ``None`` if nothing parseable was found.
    """
    if not text or not text.strip():
        return None

    for strategy in (
        _direct,
        _from_markdown,
        _from_boundaries,
        _fixed_boundaries,
        _balanced,
    ):
        result = strategy(text)
        if isinstance(result, dict):
            return result
    return None


def _balanced(text: str) -> Optional[dict]:
    """Last resort: salvage a TRUNCATED object by closing open brackets in order.

    Walks the text tracking string state + a bracket stack, then appends the
    correct closers in reverse. Safe because the caller validates the result
    against a Pydantic schema, so a mis-recovery just fails validation (-> error
    verdict), never a silent wrong value.
    """
    start = text.find("{")
    if start == -1:
        return None
    s = text[start:]
    stack: list[str] = []
    in_str = esc = False
    for ch in s:
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch in "{[":
            stack.append(ch)
        elif ch == "}" and stack and stack[-1] == "{":
            stack.pop()
        elif ch == "]" and stack and stack[-1] == "[":
            stack.pop()

    body = s + ('"' if in_str else "")
    body = re.sub(r",\s*$", "", body.rstrip())
    closer = "".join("}" if c == "{" else "]" for c in reversed(stack))
    for candidate in (body + closer, _fix_json_string(body + closer)):
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    return None


def _direct(text: str) -> Optional[dict]:
    stripped = text.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            return None
    return None


def _from_markdown(text: str) -> Optional[dict]:
    for pattern in (r"```json\s*(.*?)```", r"```\s*(.*?)```"):
        for match in re.findall(pattern, text, re.DOTALL):
            candidate = match.strip()
            if not candidate.startswith("{"):
                continue
            for attempt in (candidate, _fix_json_string(candidate)):
                try:
                    return json.loads(attempt)
                except json.JSONDecodeError:
                    continue
    return None


def _from_boundaries(text: str) -> Optional[dict]:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end <= start:
        return None
    candidate = text[start : end + 1]
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        return None


def _fixed_boundaries(text: str) -> Optional[dict]:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end <= start:
        return None
    candidate = _fix_json_string(text[start : end + 1])
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        return None


def _fix_json_string(json_str: str) -> str:
    """Repair common, safe-to-fix JSON formatting issues."""
    json_str = json_str.lstrip("﻿")
    # Trailing commas before a closing brace/bracket.
    json_str = re.sub(r",\s*}", "}", json_str)
    json_str = re.sub(r",\s*]", "]", json_str)
    # Missing commas between an object/array end and the next quoted key.
    json_str = re.sub(r"}\s*\"", '},"', json_str)
    json_str = re.sub(r"]\s*\"", '],"', json_str)
    return json_str
