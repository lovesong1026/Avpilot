"""Global search, favorites, tags, daily review, and dashboard schemas."""

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.api.schemas.observability import ObservabilitySummary


class GlobalSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=8, ge=1, le=20)
    min_score: float = Field(default=0.25, ge=0.0, le=1.0)


class GlobalSearchHit(BaseModel):
    target_type: Literal["document", "image", "memory"]
    target_id: str
    title: str
    excerpt: str
    score: float
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, object] = Field(default_factory=dict)


class GlobalSearchResponse(BaseModel):
    query: str
    documents: list[GlobalSearchHit]
    images: list[GlobalSearchHit]
    memories: list[GlobalSearchHit]


class FavoriteCreate(BaseModel):
    target_type: Literal["document", "image", "memory", "message"]
    target_id: str = Field(min_length=1, max_length=64)
    snapshot: dict[str, object] | None = None


class FavoriteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    target_type: str
    target_id: str
    snapshot: dict[str, object] | None
    created_at: datetime


class TagCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")


class TagUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=64)
    color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")


class TagManagementResponse(BaseModel):
    id: uuid.UUID
    name: str
    color: str
    source: str
    document_count: int
    image_count: int


class DailyReviewResponse(BaseModel):
    id: uuid.UUID
    review_date: date
    content: str
    stats: dict[str, object]
    created_at: datetime
    updated_at: datetime


class DashboardResponse(BaseModel):
    counts: dict[str, int]
    tag_distribution: list[dict[str, object]]
    memory_trend: list[dict[str, object]]
    community_distribution: list[dict[str, object]]
    observability: ObservabilitySummary
