import asyncio
import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.application.agent.schemas import AgentRun
from app.application.observability import (
    complete_agent_trace,
    create_agent_trace,
    observability_summary,
)
from app.infrastructure.database.models.conversation import Conversation, Message
from app.infrastructure.database.models.identity import User
from app.infrastructure.database.postgres import close_postgres, get_session_factory

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_INTEGRATION_TESTS") != "1",
        reason="set RUN_INTEGRATION_TESTS=1 to use real infrastructure",
    ),
]


def test_trace_and_token_summary_round_trip() -> None:
    async def run() -> None:
        suffix = uuid.uuid4().hex[:12]
        now = datetime.now(UTC)
        async with get_session_factory()() as session:
            user = User(
                username=f"trace-{suffix}",
                email=f"trace-{suffix}@example.test",
                password_hash="integration-only",
                display_name="Trace Test",
                is_active=True,
            )
            session.add(user)
            await session.flush()
            conversation = Conversation(user_id=user.id, title="Trace integration")
            session.add(conversation)
            await session.flush()
            user_message = Message(
                conversation_id=conversation.id,
                role="user",
                content="测试 Trace",
            )
            session.add(user_message)
            await session.commit()
            await session.refresh(user_message)
            trace = await create_agent_trace(
                session,
                user_id=user.id,
                conversation_id=conversation.id,
                user_message_id=user_message.id,
                question=user_message.content,
                started_at=now,
            )
            assistant = Message(
                conversation_id=conversation.id,
                role="assistant",
                content="Trace 已记录。",
            )
            session.add(assistant)
            await session.commit()
            await session.refresh(assistant)
            await complete_agent_trace(
                session,
                trace=trace,
                assistant_message_id=assistant.id,
                run=AgentRun(mode="integration"),
                citations=[],
                final_usage={
                    "prompt_tokens": 12,
                    "completion_tokens": 5,
                    "total_tokens": 17,
                },
                answer_model="integration-model",
                trace_started=now,
                agent_started=now,
                agent_finished=now + timedelta(milliseconds=20),
                answer_started=now + timedelta(milliseconds=20),
                finished_at=now + timedelta(milliseconds=50),
                tool_spans=[],
            )
            summary = await observability_summary(session, user.id, days=1)
            assert summary["traces"] == 1
            assert summary["total_tokens"] == 17
            assert summary["success_rate"] == 1.0
            await session.delete(user)
            await session.commit()
        await close_postgres()

    asyncio.run(run())
