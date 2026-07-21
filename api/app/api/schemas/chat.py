"""Conversation persistence and knowledge-grounded streaming chat schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ConversationCreate(BaseModel):
    title: str = Field(default="新对话", min_length=1, max_length=256)
    knowledge_base_ids: list[uuid.UUID] = Field(default_factory=list, max_length=20)


class ConversationUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=256)
    knowledge_base_ids: list[uuid.UUID] | None = Field(default=None, max_length=20)


class ConversationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    knowledge_base_ids: list[uuid.UUID] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class CitationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source_type: str
    source_id: str
    chunk_id: str | None
    title: str
    locator: dict[str, object] | None
    quote: str
    score: float | None


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    conversation_id: uuid.UUID
    role: str
    content: str
    usage: dict[str, object] | None
    citations: list[CitationResponse] = Field(default_factory=list)
    created_at: datetime


class ChatStreamRequest(BaseModel):
    conversation_id: uuid.UUID | None = None
    message: str = Field(min_length=1, max_length=8000)
    knowledge_base_ids: list[uuid.UUID] = Field(default_factory=list, max_length=20)
