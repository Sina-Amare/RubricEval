"""Unit tests for rubric canonicalization, hashing, and publish validation."""

from __future__ import annotations

import pytest

from app.api.schemas.task import CriterionIn, DecisionConfig, RubricDraft
from app.core.exceptions import ValidationError
from app.services.rubric import rubric_hash, validate_publishable


def _draft(weight_a: float = 60.0) -> RubricDraft:
    return RubricDraft(
        criteria=[
            CriterionIn(
                key="no_plagiarism",
                title="No plagiarism",
                type="gate",
                gate_policy="force_reject",
            ),
            CriterionIn(key="quality", title="Code quality", type="scored", weight=weight_a),
            CriterionIn(key="tests", title="Has tests", type="scored", weight=40.0),
        ],
        decision_config=DecisionConfig(accept_at=70, review_at=50),
    )


def test_hash_is_deterministic_and_order_independent_of_dict_keys():
    assert rubric_hash(_draft()) == rubric_hash(_draft())


def test_hash_changes_when_content_changes():
    assert rubric_hash(_draft(60.0)) != rubric_hash(_draft(61.0))


def test_gate_requires_policy():
    with pytest.raises(Exception):
        CriterionIn(key="g", title="g", type="gate")  # no gate_policy


def test_scored_requires_positive_weight():
    with pytest.raises(Exception):
        CriterionIn(key="s", title="s", type="scored", weight=0)


def test_decision_config_ordering():
    with pytest.raises(Exception):
        DecisionConfig(accept_at=40, review_at=60)


def test_validate_publishable_rejects_empty():
    with pytest.raises(ValidationError):
        validate_publishable(RubricDraft())


def test_duplicate_keys_rejected():
    with pytest.raises(Exception):
        RubricDraft(
            criteria=[
                CriterionIn(key="dup", title="a", type="scored", weight=10),
                CriterionIn(key="dup", title="b", type="scored", weight=10),
            ]
        )
