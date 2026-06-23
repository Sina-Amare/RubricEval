"""Unit tests for schema-agnostic JSON recovery (incl. truncated output)."""

from __future__ import annotations

from app.utils.json_recovery import extract_json


def test_direct():
    assert extract_json('{"verdict": "pass", "score": 80}')["score"] == 80


def test_markdown_fenced():
    assert extract_json('```json\n{"verdict": "fail"}\n```')["verdict"] == "fail"


def test_prose_wrapped():
    out = extract_json('Sure! Here it is: {"verdict": "partial", "score": 50} hope it helps')
    assert out["verdict"] == "partial"


def test_trailing_comma():
    assert extract_json('{"verdict": "pass", "score": 70,}')["verdict"] == "pass"


def test_truncated_nested_object_recovered():
    # Free models often cut off mid-output; the balancer should close brackets.
    s = '{"verdict": "pass", "score": 80, "evidence": [{"path": "a.py", "start_line": 1'
    out = extract_json(s)
    assert out is not None
    assert out["verdict"] == "pass"
    assert out["evidence"][0]["path"] == "a.py"


def test_truncated_inside_string_recovered():
    s = '{"verdict": "fail", "rationale": "the repo is missing tests and err'
    out = extract_json(s)
    assert out is not None
    assert out["verdict"] == "fail"


def test_pure_garbage_returns_none():
    assert extract_json("this is not json at all, sorry") is None
    assert extract_json("") is None
