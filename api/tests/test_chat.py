import json
import uuid

from app.application.agent.schemas import ToolCitation, ToolResult
from app.application.chat import (
    build_agent_answer_messages,
    build_grounded_messages,
    format_sse,
)
from app.infrastructure.database.models.conversation import Message


def test_format_sse_preserves_chinese_and_event_boundary() -> None:
    value = format_sse("token", {"text": "星航仪"})

    assert value.startswith("event: token\n")
    assert value.endswith("\n\n")
    payload = json.loads(value.split("data: ", 1)[1])
    assert payload == {"text": "星航仪"}


def test_grounded_prompt_numbers_sources_and_keeps_history() -> None:
    history = [
        Message(conversation_id=uuid.uuid4(), role="user", content="上一轮问题"),
        Message(conversation_id=uuid.uuid4(), role="assistant", content="上一轮回答"),
    ]
    hits = [
        {
            "content": "验收代号是猎户座七号。",
            "citation": {"document_title": "项目记录", "page": 3},
        }
    ]

    messages = build_grounded_messages(question="代号是什么？", history=history, hits=hits)

    assert messages[0]["role"] == "system"
    assert "[资料 1] 项目记录，第 3 页" in str(messages[0]["content"])
    assert messages[1]["content"] == "上一轮问题"
    assert messages[-1]["content"] == "代号是什么？"


def test_agent_answer_prompt_unifies_document_memory_and_web_citations() -> None:
    results = [
        ToolResult(
            tool_name="knowledge_search",
            content="完整父块",
            citations=[
                ToolCitation(
                    source_type="document",
                    source_id="doc-1",
                    title="项目记录",
                    quote="猎户座七号",
                    locator={"page": 3},
                )
            ],
        ),
        ToolResult(
            tool_name="web_search",
            content="网页摘要",
            citations=[
                ToolCitation(
                    source_type="web",
                    source_id="https://example.com",
                    title="公开网页",
                    quote="公开事实",
                    url="https://example.com",
                )
            ],
        ),
    ]
    messages = build_agent_answer_messages(
        question="请综合回答",
        history=[],
        results=results,
        direct_answer=None,
        image_urls=[],
    )
    system = str(messages[0]["content"])
    assert "[来源 1][document] 项目记录，第 3 页" in system
    assert "[来源 2][web] 公开网页" in system
    assert "https://example.com" in system


def test_agent_answer_prompt_forbids_fake_number_when_no_citation() -> None:
    messages = build_agent_answer_messages(
        question="我喜欢什么？",
        history=[],
        results=[
            ToolResult(
                tool_name="memory_search",
                content="没有找到相关长期记忆。",
                metadata={"hit_count": 0},
            )
        ],
        direct_answer=None,
        image_urls=[],
    )
    assert "绝对禁止输出 [1]" in str(messages[0]["content"])
