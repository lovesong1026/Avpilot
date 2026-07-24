"""Periodic recovery and maintenance jobs."""

from app.application.task_queue import (
    dispatch_due_outbox,
    rebuild_all_memory_communities,
    recover_stale_work,
)
from app.celery_app import celery_app
from app.tasks.runtime import run_async


@celery_app.task(name="app.tasks.maintenance.recover_task_outbox")
def recover_task_outbox() -> int:
    return run_async(dispatch_due_outbox)


@celery_app.task(name="app.tasks.maintenance.recover_stale_ingestions")
def recover_stale_ingestions() -> int:
    return run_async(recover_stale_work)


@celery_app.task(
    name="app.tasks.maintenance.rebuild_memory_communities",
    soft_time_limit=1800,
    time_limit=1860,
)
def rebuild_memory_communities() -> int:
    return run_async(rebuild_all_memory_communities)
