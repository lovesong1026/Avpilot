import asyncio
import json
from types import SimpleNamespace

from app.application.agent.orchestrator import AgentOrchestrator
from app.application.agent.registry import AgentToolRegistry
from app.application.agent.schemas import AgentTool, ToolResult
from app.shared.config import Settings


def _completion(*, tool_calls=None, content=None):
    message = SimpleNamespace(
        tool_calls=tool_calls or [],
        content=content,
        model_dump=lambda **_: {
            "role": "assistant",
            "content": content,
            "tool_calls": [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {
                        "name": call.function.name,
                        "arguments": call.function.arguments,
                    },
                }
                for call in (tool_calls or [])
            ],
        },
    )
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def _call(name: str, arguments: dict):
    return SimpleNamespace(
        id="call-1",
        function=SimpleNamespace(name=name, arguments=json.dumps(arguments)),
    )


class FakeGateway:
    def __init__(self, responses):
        self.responses = list(responses)

    async def chat(self, *_args, **_kwargs):
        return self.responses.pop(0)


def test_registry_rejects_unknown_tool_without_crossing_boundary() -> None:
    async def run():
        registry = AgentToolRegistry([])
        result, record = await registry.execute("other_user_search", {"query": "secret"})
        return result, record

    result, record = asyncio.run(run())
    assert record["status"] == "failed"
    assert "未注册" in result.content


def test_native_agent_emits_bounded_tool_lifecycle() -> None:
    async def handler(arguments):
        return ToolResult(
            tool_name="knowledge_search",
            content="资料内容",
            metadata={"query": arguments["query"], "hit_count": 1},
        )

    tool = AgentTool(
        name="knowledge_search",
        description="search",
        parameters={"type": "object", "properties": {"query": {"type": "string"}}},
        handler=handler,
    )
    gateway = FakeGateway(
        [
            _completion(tool_calls=[_call("knowledge_search", {"query": "星航仪"})]),
            _completion(content="完成"),
        ]
    )
    settings = Settings(
        dashscope_api_key="test",
        agent_mode="native",
        agent_max_steps=2,
    )
    events = []

    async def run():
        orchestrator = AgentOrchestrator(
            AgentToolRegistry([tool]), gateway, settings=settings  # type: ignore[arg-type]
        )

        async def sink(event, payload):
            events.append((event, payload))

        return await orchestrator.run(question="查找星航仪", on_event=sink)

    result = asyncio.run(run())
    assert result.mode == "native"
    assert result.direct_answer == "完成"
    assert len(result.results) == 1
    assert [event for event, _ in events] == [
        "agent_started",
        "tool_started",
        "tool_completed",
    ]


def test_auto_mode_falls_back_to_react() -> None:
    class FallbackGateway:
        calls = 0

        async def chat(self, *_args, **kwargs):
            self.calls += 1
            if kwargs.get("tools"):
                raise RuntimeError("tool calling unsupported")
            return _completion(content='{"action":"final","answer":"降级完成"}')

    settings = Settings(dashscope_api_key="test", agent_mode="auto")
    async def noop(_arguments):
        return ToolResult(tool_name="noop", content="")

    tool = AgentTool(
        name="noop",
        description="noop",
        parameters={"type": "object", "properties": {}},
        handler=noop,
    )

    async def run():
        orchestrator = AgentOrchestrator(
            AgentToolRegistry([tool]), FallbackGateway(), settings=settings  # type: ignore[arg-type]
        )
        return await orchestrator.run(question="你好")

    result = asyncio.run(run())
    assert result.mode == "react"
    assert result.direct_answer == "降级完成"
