import asyncio
import os
import uuid

import pytest
from sqlalchemy import select

from app.application.research import (
    create_research_task,
    delete_research_task,
    get_research_task,
)
from app.application.task_queue import task_dedupe_key
from app.infrastructure.database.models.identity import User
from app.infrastructure.database.models.task import TaskOutbox
from app.infrastructure.database.postgres import close_postgres, get_session_factory

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_INTEGRATION_TESTS") != "1",
        reason="set RUN_INTEGRATION_TESTS=1 to use real infrastructure",
    ),
]


def test_research_task_and_outbox_are_created_atomically() -> None:
    async def run() -> None:
        suffix = uuid.uuid4().hex[:12]
        async with get_session_factory()() as session:
            user = User(
                username=f"research-{suffix}",
                email=f"research-{suffix}@example.test",
                password_hash="integration-only",
                display_name="Research Test",
                is_active=True,
            )
            session.add(user)
            await session.commit()
            task, key = await create_research_task(
                session,
                user_id=user.id,
                question="系统分析低空物流无人机的技术路线与主要风险",
                title="低空物流无人机研究",
                knowledge_base_ids=[],
                use_memory=True,
                allow_web=False,
                max_iterations=2,
            )
            event = await session.scalar(select(TaskOutbox).where(TaskOutbox.dedupe_key == key))
            assert event is not None
            assert event.payload == {"research_id": str(task.id)}
            assert key == task_dedupe_key("research", task.id)
            detail = await get_research_task(session, user.id, task.id)
            assert detail is not None
            assert detail[0].status == "pending"
            assert detail[1:] == ([], [])
            task.status = "failed"
            await session.commit()
            assert await delete_research_task(session, user.id, task.id)
            assert (
                await session.scalar(select(TaskOutbox).where(TaskOutbox.dedupe_key == key)) is None
            )
            await session.delete(user)
            await session.commit()
        await close_postgres()

    asyncio.run(run())
