"""
Rubric canonicalization + content hashing.

The content hash is the reproducibility key: it is computed over a canonical
JSON form of the rubric (criteria + decision config + prompt template version)
with stable key ordering, so identical rubrics always hash identically and a
published version can never silently change.
"""

from __future__ import annotations

import hashlib
import json

from app.api.schemas.task import RubricDraft
from app.core.exceptions import ValidationError


def canonical_rubric(draft: RubricDraft) -> dict:
    """Deterministic, order-stable dict form of a rubric draft."""
    return {
        "prompt_template_version": draft.prompt_template_version,
        "decision_config": {
            "accept_at": float(draft.decision_config.accept_at),
            "review_at": float(draft.decision_config.review_at),
        },
        "criteria": [
            {
                "key": c.key,
                "title": c.title,
                "instructions": c.instructions,
                "type": c.type.value,
                "weight": float(c.weight),
                "gate_policy": c.gate_policy.value if c.gate_policy else None,
                "pass_threshold": c.pass_threshold,
            }
            for c in draft.criteria
        ],
    }


def rubric_hash(draft: RubricDraft) -> str:
    payload = json.dumps(canonical_rubric(draft), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def validate_publishable(draft: RubricDraft) -> None:
    """Ensure a draft is complete enough to publish (raises on problems)."""
    if not draft.criteria:
        raise ValidationError("Cannot publish a rubric with no criteria")
    scored = [c for c in draft.criteria if c.type.value == "scored"]
    if scored and sum(c.weight for c in scored) <= 0:
        raise ValidationError("Scored criteria must have a positive total weight")
    if not scored and not any(c.type.value == "gate" for c in draft.criteria):
        raise ValidationError("Rubric must contain at least one gate or scored criterion")
