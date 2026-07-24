from app.application.task_queue import (
    DOCUMENT_TASK,
    enqueue_task,
    task_dedupe_key,
)
from app.celery_app import celery_app
from app.tasks.base import is_retryable, retry_countdown


class RecordingSession:
    def __init__(self) -> None:
        self.added = []

    def add(self, value) -> None:
        self.added.append(value)


def test_outbox_event_contains_stable_dedupe_key_and_payload() -> None:
    import uuid

    session = RecordingSession()
    job_id = uuid.uuid4()
    event = enqueue_task(
        session,  # type: ignore[arg-type]
        task_name=DOCUMENT_TASK,
        queue="ingestion",
        dedupe_key=task_dedupe_key("document", job_id),
        payload={"document_id": "document-1", "job_id": str(job_id)},
    )

    assert session.added == [event]
    assert event.dedupe_key == f"document:{job_id}"
    assert event.payload["job_id"] == str(job_id)
    assert event.status == "pending"


def test_retry_policy_uses_bounded_exponential_backoff() -> None:
    assert [retry_countdown(index) for index in range(6)] == [
        30,
        60,
        120,
        240,
        480,
        600,
    ]
    assert is_retryable(TimeoutError())
    assert not is_retryable(FileNotFoundError())


def test_celery_requires_late_ack_and_worker_loss_rejection() -> None:
    assert celery_app.conf.task_acks_late is True
    assert celery_app.conf.task_reject_on_worker_lost is True
    assert celery_app.conf.worker_prefetch_multiplier == 1
    assert {"ingestion", "memory", "maintenance"} <= {
        queue.name for queue in celery_app.conf.task_queues
    }
