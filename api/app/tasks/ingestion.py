"""Reliable Celery entries for document, web, and image ingestion."""

import uuid

from app.application.images import process_image
from app.application.knowledge import process_document, process_web_document
from app.celery_app import celery_app
from app.tasks.base import execute_reliable


@celery_app.task(
    bind=True,
    name="app.tasks.ingestion.ingest_document",
    max_retries=4,
    soft_time_limit=1200,
    time_limit=1260,
)
def ingest_document(self, document_id: str, job_id: str, outbox_id: str) -> None:
    execute_reliable(
        self,
        outbox_id=outbox_id,
        operation=lambda: process_document(
            uuid.UUID(document_id), uuid.UUID(job_id), raise_on_failure=True
        ),
    )


@celery_app.task(
    bind=True,
    name="app.tasks.ingestion.ingest_web_document",
    max_retries=4,
    soft_time_limit=1200,
    time_limit=1260,
)
def ingest_web_document(self, document_id: str, job_id: str, outbox_id: str) -> None:
    execute_reliable(
        self,
        outbox_id=outbox_id,
        operation=lambda: process_web_document(
            uuid.UUID(document_id), uuid.UUID(job_id), raise_on_failure=True
        ),
    )


@celery_app.task(
    bind=True,
    name="app.tasks.ingestion.ingest_image",
    max_retries=4,
    soft_time_limit=900,
    time_limit=960,
)
def ingest_image(self, image_id: str, job_id: str, outbox_id: str) -> None:
    execute_reliable(
        self,
        outbox_id=outbox_id,
        operation=lambda: process_image(
            uuid.UUID(image_id), uuid.UUID(job_id), raise_on_failure=True
        ),
    )
