"""Stable contracts shared by every Avpilot agent tool."""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, Field


class ToolCitation(BaseModel):
    source_type: str
    source_id: str
    title: str
    quote: str
    chunk_id: str | None = None
    score: float | None = None
    locator: dict[str, object] | None = None
    url: str | None = None


class ToolResult(BaseModel):
    tool_name: str
    content: str
    citations: list[ToolCitation] = Field(default_factory=list)
    metadata: dict[str, object] = Field(default_factory=dict)


@dataclass(slots=True)
class AgentToolContext:
    user_id: uuid.UUID
    knowledge_base_ids: list[uuid.UUID]
    allow_web: bool = False


ToolHandler = Callable[[dict[str, Any]], Awaitable[ToolResult]]


@dataclass(slots=True)
class AgentTool:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: ToolHandler

    def function_schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


@dataclass(slots=True)
class AgentRun:
    results: list[ToolResult] = field(default_factory=list)
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    direct_answer: str | None = None
    mode: str = "native"
    model_usages: list[dict[str, Any]] = field(default_factory=list)
