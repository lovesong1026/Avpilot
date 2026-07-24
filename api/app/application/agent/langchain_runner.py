"""LangChain create_agent adapter around Avpilot's user-scoped tool registry."""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable, Sequence
from typing import Any

from langchain.agents import create_agent
from langchain_core.messages import AIMessage
from langchain_core.tools import StructuredTool
from langchain_openai import ChatOpenAI
from openai.types.chat import ChatCompletionMessageParam
from pydantic import BaseModel, Field

from app.application.agent.registry import AgentToolRegistry
from app.application.agent.schemas import AgentRun
from app.shared.config import Settings

EventSink = Callable[[str, dict[str, Any]], Awaitable[None]]


class SearchToolInput(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=8)


class LangChainAgentRunner:
    def __init__(
        self,
        registry: AgentToolRegistry,
        settings: Settings,
        system_prompt: str,
    ) -> None:
        self.registry = registry
        self.settings = settings
        self.system_prompt = system_prompt

    async def run(
        self,
        *,
        question: str,
        history: Sequence[ChatCompletionMessageParam],
        image_context: str,
        on_event: EventSink | None,
    ) -> AgentRun:
        run = AgentRun(mode="langchain_function_calling")
        tools = [
            self._adapt_tool(tool.name, tool.description, run, on_event)
            for tool in self.registry.tools
        ]
        model = ChatOpenAI(
            model=self.settings.bailian_chat_model,
            api_key=self.settings.dashscope_api_key,
            base_url=self.settings.bailian_base_url,
            temperature=0.0,
            timeout=150.0,
            max_retries=2,
        )
        graph = create_agent(model=model, tools=tools, system_prompt=self.system_prompt)
        context = f"\n\n用户附带图片的已有分析：\n{image_context}" if image_context else ""
        messages: list[Any] = [*history[-6:], {"role": "user", "content": question + context}]
        last_answer: str | None = None
        async for update in graph.astream(
            {"messages": messages},
            config={"recursion_limit": max(4, self.settings.agent_max_steps * 2 + 2)},
            stream_mode="updates",
        ):
            for value in update.values():
                if not isinstance(value, dict):
                    continue
                for message in value.get("messages") or []:
                    if isinstance(message, AIMessage) and not message.tool_calls:
                        content = message.content
                        if isinstance(content, str) and content.strip():
                            last_answer = content.strip()
        run.direct_answer = last_answer
        return run

    def _adapt_tool(
        self,
        name: str,
        description: str,
        run: AgentRun,
        on_event: EventSink | None,
    ) -> StructuredTool:
        async def execute(query: str, top_k: int = 5) -> str:
            call_id = f"lc-{uuid.uuid4().hex[:16]}"
            arguments = {"query": query, "top_k": top_k}
            if on_event is not None:
                await on_event(
                    "tool_started",
                    {"tool_call_id": call_id, "name": name, "arguments": arguments},
                )
            result, record = await self.registry.execute(name, arguments)
            record["tool_call_id"] = call_id
            run.results.append(result)
            run.tool_calls.append(record)
            if on_event is not None:
                await on_event(
                    "tool_completed",
                    {
                        "tool_call_id": call_id,
                        "name": name,
                        "status": record["status"],
                        "duration_ms": record["duration_ms"],
                        "hit_count": result.metadata.get("hit_count", 0),
                        "error": record.get("error"),
                    },
                )
            return result.model_dump_json()

        return StructuredTool.from_function(
            coroutine=execute,
            name=name,
            description=description,
            args_schema=SearchToolInput,
        )
