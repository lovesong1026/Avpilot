import json
import uuid

from app.application.chat import build_grounded_messages, format_sse
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
