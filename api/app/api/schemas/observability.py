"""Reader-facing Agent trace and Token observability contracts."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TokenTrendPoint(BaseModel):
    date: str
    input_tokens: int
    output_tokens: int


class DistributionPoint(BaseModel):
    name: str
    value: int


class ObservabilitySummary(BaseModel):
    period_days: int
    traces: int
    failed_traces: int
    success_rate: float
    avg_duration_ms: int
    tool_calls: int
    input_tokens: int
    output_tokens: int
    total_tokens: int
    token_trend: list[TokenTrendPoint] = Field(default_factory=list)
    tool_distribution: list[DistributionPoint] = Field(default_factory=list)


class AgentTraceItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    conversation_id: uuid.UUID
    user_message_id: uuid.UUID
    assistant_message_id: uuid.UUID | None
    status: str
    mode: str | None
    question: str
    started_at: datetime
    finished_at: datetime | None
    duration_ms: int | None
    tool_call_count: int
    citation_count: int
    error_message: str | None


class AgentSpanItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    parent_span_id: uuid.UUID | None
    kind: str
    name: str
    status: str
    started_at: datetime
    finished_at: datetime
    duration_ms: int
    input_summary: dict[str, object] | None
    output_summary: dict[str, object] | None
    error_message: str | None


class ModelUsageItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    operation: str
    provider: str
    model: str
    status: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    duration_ms: int | None
    error_message: str | None


class RetrievalSnapshotItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tool_call_id: str
    tool_name: str
    query: str
    hit_count: int
    duration_ms: int
    status: str
    citations: list[dict[str, object]] | None
    result_metadata: dict[str, object] | None
    top_score: float | None


class AgentTraceDetail(AgentTraceItem):
    spans: list[AgentSpanItem] = Field(default_factory=list)
    model_usages: list[ModelUsageItem] = Field(default_factory=list)
    retrieval_snapshots: list[RetrievalSnapshotItem] = Field(default_factory=list)
