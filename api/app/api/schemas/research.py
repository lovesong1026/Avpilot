"""Deep-research request and response contracts."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ResearchCreate(BaseModel):
    question: str = Field(min_length=5, max_length=8000)
    title: str | None = Field(default=None, min_length=1, max_length=256)
    knowledge_base_ids: list[uuid.UUID] = Field(default_factory=list, max_length=20)
    use_memory: bool = True
    allow_web: bool = False
    max_iterations: int = Field(default=2, ge=1, le=3)


class ResearchStepResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    position: int
    question: str
    status: str
    finding: str | None
    evidence_count: int
    started_at: datetime | None
    finished_at: datetime | None
    error_message: str | None


class ResearchEvidenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    step_id: uuid.UUID | None
    source_type: str
    source_id: str
    chunk_id: str | None
    title: str
    quote: str
    url: str | None
    locator: dict[str, object] | None
    score: float | None
    query: str


class ResearchTaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    question: str
    status: str
    stage: str
    progress: float
    allow_web: bool
    use_memory: bool
    knowledge_base_ids: list[str]
    plan: dict[str, object] | None
    verifier_result: dict[str, object] | None
    report_markdown: str | None
    iteration_count: int
    max_iterations: int
    input_tokens: int
    output_tokens: int
    total_tokens: int
    started_at: datetime | None
    finished_at: datetime | None
    error_code: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class ResearchTaskDetail(ResearchTaskResponse):
    steps: list[ResearchStepResponse] = Field(default_factory=list)
    evidence: list[ResearchEvidenceResponse] = Field(default_factory=list)
