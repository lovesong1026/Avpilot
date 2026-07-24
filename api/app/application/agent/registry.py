"""Bounded execution registry for model-selected tools."""

from __future__ import annotations

import asyncio
import time
from typing import Any

from app.application.agent.schemas import AgentTool, ToolResult


class UnknownAgentToolError(ValueError):
    """The model requested a tool that is not registered."""


class AgentToolRegistry:
    def __init__(self, tools: list[AgentTool], *, timeout_seconds: float = 30.0) -> None:
        self._tools = {tool.name: tool for tool in tools}
        self.timeout_seconds = timeout_seconds

    @property
    def schemas(self) -> list[dict[str, Any]]:
        return [tool.function_schema() for tool in self._tools.values()]

    @property
    def names(self) -> list[str]:
        return list(self._tools)

    async def execute(
        self, name: str, arguments: dict[str, Any]
    ) -> tuple[ToolResult, dict[str, Any]]:
        tool = self._tools.get(name)
        if tool is None:
            error = str(UnknownAgentToolError(f"未注册的工具：{name}"))
            return (
                ToolResult(
                    tool_name=name or "unknown",
                    content=f"工具执行失败：{error}",
                    metadata={"error": error},
                ),
                {
                    "name": name,
                    "arguments": arguments,
                    "status": "failed",
                    "duration_ms": 0,
                    "error": error,
                },
            )
        started = time.monotonic()
        try:
            result = await asyncio.wait_for(
                tool.handler(arguments), timeout=self.timeout_seconds
            )
            record = {
                "name": name,
                "arguments": arguments,
                "status": "completed",
                "duration_ms": round((time.monotonic() - started) * 1000),
                "metadata": result.metadata,
            }
            return result, record
        except Exception as exc:
            record = {
                "name": name,
                "arguments": arguments,
                "status": "failed",
                "duration_ms": round((time.monotonic() - started) * 1000),
                "error": str(exc) or type(exc).__name__,
            }
            return (
                ToolResult(
                    tool_name=name,
                    content=f"工具执行失败：{record['error']}",
                    metadata={"error": record["error"]},
                ),
                record,
            )
