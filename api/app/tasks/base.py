"""Shared retry policy and lifecycle helpers for Celery tasks."""

from celery import Task

from app.application.task_queue import (
    claim_outbox,
    mark_outbox_completed,
    mark_outbox_failed,
    mark_outbox_retrying,
)
from app.tasks.runtime import run_async

NON_RETRYABLE_ERRORS = {
    "DocumentParseError",
    "InvalidImageError",
    "InvalidUploadError",
    "InvalidImageUploadError",
    "UnsafeWebUrlError",
    "FileNotFoundError",
}


def retry_countdown(retries: int) -> int:
    return min(600, 30 * (2**retries))


def is_retryable(exc: Exception) -> bool:
    return type(exc).__name__ not in NON_RETRYABLE_ERRORS


def execute_reliable(
    task: Task,
    *,
    outbox_id: str,
    operation,
) -> None:
    delivery_info = task.request.delivery_info or {}
    redelivered = bool(delivery_info.get("redelivered"))
    if not run_async(lambda: claim_outbox(outbox_id, allow_running=redelivered)):
        return
    try:
        run_async(operation)
    except Exception as exc:
        retries = int(task.request.retries)
        if is_retryable(exc) and retries < int(task.max_retries or 0):
            countdown = retry_countdown(retries)
            run_async(lambda error=exc: mark_outbox_retrying(outbox_id, error, countdown))
            raise task.retry(exc=exc, countdown=countdown) from exc
        run_async(lambda error=exc: mark_outbox_failed(outbox_id, error))
        raise
    run_async(lambda: mark_outbox_completed(outbox_id))
