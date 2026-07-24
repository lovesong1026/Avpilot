import asyncio
import os
import uuid

import pytest
from sqlalchemy import select

from app.application.task_queue import claim_outbox, enqueue_task
from app.infrastructure.database.models.task import TaskOutbox
from app.infrastructure.database.postgres import close_postgres, get_session_factory

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_INTEGRATION_TESTS") != "1",
        reason="set RUN_INTEGRATION_TESTS=1 to use real infrastructure",
    ),
]


def test_outbox_rollback_and_atomic_claim() -> None:
    async def run() -> None:
        rolled_back_key = f"integration:rollback:{uuid.uuid4()}"
        claimed_key = f"integration:claim:{uuid.uuid4()}"
        async with get_session_factory()() as session:
            enqueue_task(
                session,
                task_name="integration.rollback",
                queue="maintenance",
                dedupe_key=rolled_back_key,
                payload={},
            )
            await session.flush()
            await session.rollback()
            assert (
                await session.scalar(
                    select(TaskOutbox).where(
                        TaskOutbox.dedupe_key == rolled_back_key
                    )
                )
                is None
            )

            event = enqueue_task(
                session,
                task_name="integration.claim",
                queue="maintenance",
                dedupe_key=claimed_key,
                payload={},
            )
            await session.commit()
            await session.refresh(event)
            event_id = str(event.id)

        assert await claim_outbox(event_id) is True
        assert await claim_outbox(event_id) is False

        async with get_session_factory()() as session:
            persisted = await session.get(TaskOutbox, uuid.UUID(event_id))
            assert persisted is not None
            assert persisted.status == "running"
            await session.delete(persisted)
            await session.commit()
        await close_postgres()

    asyncio.run(run())
