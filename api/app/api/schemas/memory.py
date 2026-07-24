"""Memory extraction, graph, timeline, and community API schemas."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class MemoryCreate(BaseModel):
    text: str = Field(min_length=2, max_length=20_000)


class MemorySourceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    raw_text: str
    source_type: str
    source_message_id: uuid.UUID | None
    status: str
    graph_source_id: str | None
    graph_stats: dict[str, object] | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class MemoryNode(BaseModel):
    id: str
    kind: Literal["source", "fragment", "statement", "entity"]
    label: str
    properties: dict[str, object] = Field(default_factory=dict)


class MemoryEdge(BaseModel):
    id: str
    source: str
    target: str
    kind: str
    label: str = ""


class MemoryGraphResponse(BaseModel):
    nodes: list[MemoryNode]
    edges: list[MemoryEdge]
    stats: dict[str, int]


class TimelineItem(BaseModel):
    id: str
    statement: str
    event_time: str | None
    subject: str
    predicate: str
    object: str
    source_id: str
    created_at: str | None


class CommunityItem(BaseModel):
    id: str
    name: str
    member_count: int
    members: list[dict[str, str]]
