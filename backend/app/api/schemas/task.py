"""DTOs for tasks, rubric drafts, criteria, and published rubric versions."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.enums import CriterionType, GatePolicy


class CriterionIn(BaseModel):
    key: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=200)
    instructions: str = ""
    type: CriterionType
    weight: float = 0.0
    gate_policy: Optional[GatePolicy] = None
    pass_threshold: Optional[float] = None

    @field_validator("key")
    @classmethod
    def _key_slug(cls, v: str) -> str:
        v = v.strip()
        if not all(ch.isalnum() or ch in "_-" for ch in v):
            raise ValueError("key may only contain letters, digits, '_' and '-'")
        return v

    @model_validator(mode="after")
    def _check_type_fields(self) -> "CriterionIn":
        if self.type == CriterionType.GATE:
            if self.gate_policy is None:
                raise ValueError("gate criteria require a gate_policy")
        else:  # scored
            if self.weight <= 0:
                raise ValueError("scored criteria require weight > 0")
        if self.pass_threshold is not None and not (0 <= self.pass_threshold <= 100):
            raise ValueError("pass_threshold must be between 0 and 100")
        return self


class DecisionConfig(BaseModel):
    accept_at: float = 70.0
    review_at: float = 50.0

    @model_validator(mode="after")
    def _ordered(self) -> "DecisionConfig":
        if not (0 <= self.review_at <= self.accept_at <= 100):
            raise ValueError("require 0 <= review_at <= accept_at <= 100")
        return self


class RubricDraft(BaseModel):
    criteria: list[CriterionIn] = Field(default_factory=list)
    decision_config: DecisionConfig = Field(default_factory=DecisionConfig)
    prompt_template_version: str = "grade@v1"

    @model_validator(mode="after")
    def _unique_keys(self) -> "RubricDraft":
        keys = [c.key for c in self.criteria]
        if len(keys) != len(set(keys)):
            raise ValueError("criterion keys must be unique")
        return self


class TaskCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = ""


class TaskUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=200)
    description: Optional[str] = None


class CriterionOut(BaseModel):
    id: str
    key: str
    title: str
    instructions: str
    type: CriterionType
    weight: float
    gate_policy: Optional[GatePolicy]
    pass_threshold: Optional[float]
    order_index: int


class RubricVersionOut(BaseModel):
    id: str
    version_number: int
    content_hash: str
    prompt_template_version: str
    decision_config: DecisionConfig
    criteria: list[CriterionOut]
    created_at: datetime


class TaskOut(BaseModel):
    id: str
    name: str
    description: str
    current_rubric_version_id: Optional[str]
    current_version_number: Optional[int] = None
    draft: RubricDraft
    created_at: datetime
    updated_at: datetime


class PublishResult(BaseModel):
    rubric_version_id: str
    version_number: int
    content_hash: str
