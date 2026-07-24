"""Reliable Celery entry for long-term memory extraction."""

import uuid

from app.application.memory import process_memory_source
from app.celery_app import celery_app
from app.tasks.base import execute_reliable


@celery_app.task(
    bind=True,
    name="app.tasks.memory.extract_memory",
    max_retries=4,
    soft_time_limit=900,
    time_limit=960,
)
def extract_memory(self, source_id: str, outbox_id: str) -> None:
    execute_reliable(
        self,
        outbox_id=outbox_id,
        operation=lambda: process_memory_source(
            uuid.UUID(source_id), raise_on_failure=True
        ),
    )
