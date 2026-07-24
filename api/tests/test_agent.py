import asyncio
from types import SimpleNamespace

from app.application.agent.langchain_runner import LangChainAgentRunner
from app.application.agent.orchestrator import AgentOrchestrator
from app.application.agent.registry import AgentToolRegistry
from app.application.agent.schemas import AgentRun, AgentTool, ToolResult
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


def test_langchain_structured_tool_preserves_avpilot_result_and_events() -> None:
    async def handler(arguments):
        return ToolResult(
            tool_name="memory_search",
            content=f"结果：{arguments['query']}",
            metadata={"hit_count": 1},
        )

    registry = AgentToolRegistry(
        [
            AgentTool(
                name="memory_search",
                description="search memory",
                parameters={"type": "object", "properties": {}},
                handler=handler,
            )
        ]
    )
    runner = LangChainAgentRunner(
        registry,
        Settings(dashscope_api_key="test"),
        "system",
    )
    run = AgentRun()
    events = []

    async def invoke():
        async def sink(event, payload):
            events.append((event, payload))

        tool = runner._adapt_tool("memory_search", "search memory", run, sink)
        return await tool.ainvoke({"query": "航空", "top_k": 3})

    output = asyncio.run(invoke())
    assert '"tool_name":"memory_search"' in output
    assert run.tool_calls[0]["status"] == "completed"
    assert [event for event, _ in events] == ["tool_started", "tool_completed"]


def test_native_agent_delegates_to_langchain_with_tool_lifecycle(monkeypatch) -> None:
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
    gateway = FakeGateway([])
    settings = Settings(
        dashscope_api_key="test",
        agent_mode="native",
        agent_max_steps=2,
    )
    events = []

    async def fake_langchain_run(self, **kwargs):
        sink = kwargs["on_event"]
        await sink(
            "tool_started",
            {
                "tool_call_id": "lc-test",
                "name": "knowledge_search",
                "arguments": {"query": "星航仪"},
            },
        )
        result, record = await self.registry.execute(
            "knowledge_search", {"query": "星航仪"}
        )
        await sink(
            "tool_completed",
            {
                "tool_call_id": "lc-test",
                "name": "knowledge_search",
                "status": record["status"],
            },
        )
        return AgentRun(
            results=[result],
            tool_calls=[record],
            direct_answer="完成",
            mode="langchain_function_calling",
        )

    monkeypatch.setattr(
        "app.application.agent.orchestrator.LangChainAgentRunner.run",
        fake_langchain_run,
    )

    async def run():
        orchestrator = AgentOrchestrator(
            AgentToolRegistry([tool]), gateway, settings=settings  # type: ignore[arg-type]
        )

        async def sink(event, payload):
            events.append((event, payload))

        return await orchestrator.run(question="查找星航仪", on_event=sink)

    result = asyncio.run(run())
    assert result.mode == "langchain_function_calling"
    assert result.direct_answer == "完成"
    assert len(result.results) == 1
    assert [event for event, _ in events] == [
        "agent_started",
        "tool_started",
        "tool_completed",
    ]


def test_auto_mode_falls_back_to_react(monkeypatch) -> None:
    class FallbackGateway:
        calls = 0

        async def chat(self, *_args, **kwargs):
            self.calls += 1
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

    async def unsupported(*_args, **_kwargs):
        raise RuntimeError("tool calling unsupported")

    monkeypatch.setattr(
        "app.application.agent.orchestrator.LangChainAgentRunner.run",
        unsupported,
    )

    async def run():
        orchestrator = AgentOrchestrator(
            AgentToolRegistry([tool]), FallbackGateway(), settings=settings  # type: ignore[arg-type]
        )
        return await orchestrator.run(question="你好")

    result = asyncio.run(run())
    assert result.mode == "react"
    assert result.direct_answer == "降级完成"
