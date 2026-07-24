"""Reliable Celery entry for multi-stage deep research."""

import uuid

from app.application.research import process_research_task
from app.celery_app import celery_app
from app.tasks.base import execute_reliable


@celery_app.task(
    bind=True,
    name="app.tasks.research.run_research",
    max_retries=3,
    soft_time_limit=2700,
    time_limit=2760,
)
def run_research(self, research_id: str, outbox_id: str) -> None:
    execute_reliable(
        self,
        outbox_id=outbox_id,
        operation=lambda: process_research_task(uuid.UUID(research_id)),
    )
