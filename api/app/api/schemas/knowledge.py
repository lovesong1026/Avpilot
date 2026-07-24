"""Knowledge-base, document ingestion, and retrieval API schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class KnowledgeBaseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=1024)


class TagSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    color: str
    source: str


class KnowledgeBaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    is_default: bool
    chat_enabled: bool
    document_count: int = 0
    image_count: int = 0
    created_at: datetime
    updated_at: datetime


class IngestionJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: str
    stage: str
    progress: float
    attempts: int
    error_code: str | None
    error_message: str | None
    updated_at: datetime


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    knowledge_base_id: uuid.UUID
    title: str
    source_type: str
    source_url: str | None
    file_name: str | None
    mime_type: str
    file_size: int
    status: str
    chunk_count: int
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    ingestion_job: IngestionJobResponse | None = None
    tags: list[TagSummary] = Field(default_factory=list)


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=20)
    use_rerank: bool = False


class CitationResponse(BaseModel):
    document_id: uuid.UUID
    document_title: str
    file_name: str | None
    page: int | None
    start_char: int | None
    end_char: int | None


class SearchHitResponse(BaseModel):
    chunk_id: str
    content: str
    excerpt: str
    score: float
    citation: CitationResponse


class SearchResponse(BaseModel):
    query: str
    hits: list[SearchHitResponse]


class WebDocumentCreate(BaseModel):
    url: HttpUrl
