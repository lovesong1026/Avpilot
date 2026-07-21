"""Multimodal image library API schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.api.schemas.knowledge import IngestionJobResponse, TagSummary


class ImageAssetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    knowledge_base_id: uuid.UUID
    file_name: str
    mime_type: str
    file_size: int
    description: str | None
    ocr_text: str | None
    objects: list[str] | None
    scene: str | None
    status: str
    error_message: str | None
    content_url: str = ""
    ingestion_job: IngestionJobResponse | None = None
    tags: list[TagSummary] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class ImageSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    knowledge_base_ids: list[uuid.UUID] = Field(default_factory=list, max_length=20)
    top_k: int = Field(default=12, ge=1, le=30)


class ImageSearchHitResponse(BaseModel):
    chunk_id: str
    image_id: uuid.UUID
    file_name: str
    content: str
    score: float


class ImageSearchResponse(BaseModel):
    query: str
    hits: list[ImageSearchHitResponse]
