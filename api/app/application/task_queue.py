"""Transactional outbox creation, delivery, and task-state bookkeeping."""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models.knowledge import Document, ImageAsset, IngestionJob
from app.infrastructure.database.models.memory import MemorySource
from app.infrastructure.database.models.task import TaskOutbox
from app.infrastructure.database.postgres import get_session_factory

logger = logging.getLogger(__name__)

DOCUMENT_TASK = "app.tasks.ingestion.ingest_document"
WEB_DOCUMENT_TASK = "app.tasks.ingestion.ingest_web_document"
IMAGE_TASK = "app.tasks.ingestion.ingest_image"
MEMORY_TASK = "app.tasks.memory.extract_memory"
RESEARCH_TASK = "app.tasks.research.run_research"


def task_dedupe_key(kind: str, target_id: uuid.UUID) -> str:
    return f"{kind}:{target_id}"


def enqueue_task(
    session: AsyncSession,
    *,
    task_name: str,
    queue: str,
    dedupe_key: str,
    payload: dict[str, object],
) -> TaskOutbox:
    """Add a task intent to the caller's current PostgreSQL transaction."""
    event = TaskOutbox(
        task_name=task_name,
        queue=queue,
        dedupe_key=dedupe_key,
        payload=payload,
        status="pending",
        dispatch_attempts=0,
        available_at=datetime.now(UTC),
    )
    session.add(event)
    return event


async def dispatch_outbox(dedupe_key: str) -> bool:
    """Best-effort immediate delivery; the beat recovery loop handles failures."""
    async with get_session_factory()() as session:
        event = await session.scalar(select(TaskOutbox).where(TaskOutbox.dedupe_key == dedupe_key))
        if event is None or event.status == "completed":
            return False
        return await _dispatch_event(session, event)


async def dispatch_due_outbox(limit: int = 100) -> int:
    """Redeliver pending/failed events and abandoned dispatch attempts."""
    now = datetime.now(UTC)
    abandoned = now - timedelta(minutes=2)
    async with get_session_factory()() as session:
        rows = list(
            await session.scalars(
                select(TaskOutbox)
                .where(
                    TaskOutbox.available_at <= now,
                    or_(
                        TaskOutbox.status.in_(("pending", "dispatch_failed", "retrying")),
                        (
                            (TaskOutbox.status == "dispatching")
                            & (TaskOutbox.updated_at < abandoned)
                        ),
                    ),
                )
                .order_by(TaskOutbox.available_at.asc())
                .limit(limit)
            )
        )
        delivered = 0
        for event in rows:
            delivered += int(await _dispatch_event(session, event))
        return delivered


async def _dispatch_event(session: AsyncSession, event: TaskOutbox) -> bool:
    from app.celery_app import celery_app

    event.status = "dispatching"
    event.dispatch_attempts += 1
    event.error_message = None
    await session.commit()
    task_id = str(event.id)
    try:
        await asyncio.to_thread(
            celery_app.send_task,
            event.task_name,
            kwargs={**event.payload, "outbox_id": task_id},
            queue=event.queue,
            task_id=task_id,
            retry=False,
        )
    except Exception as exc:
        logger.exception("Could not dispatch task outbox event %s", event.id)
        await session.rollback()
        current = await session.get(TaskOutbox, event.id)
        if current is not None:
            current.status = "dispatch_failed"
            current.error_message = str(exc)[:2000]
            current.available_at = datetime.now(UTC) + timedelta(seconds=30)
            await _mark_dispatch_stage(session, current.payload, "dispatch_failed")
            await session.commit()
        return False
    await session.rollback()
    current = await session.get(TaskOutbox, event.id)
    if current is not None:
        current.status = "dispatched"
        current.celery_task_id = task_id
        current.dispatched_at = datetime.now(UTC)
        current.error_message = None
        await _mark_dispatch_stage(session, current.payload, "queued")
        await session.commit()
    return True


async def claim_outbox(outbox_id: str, *, allow_running: bool = False) -> bool:
    """Atomically prevent concurrent duplicate deliveries from doing work twice."""
    async with get_session_factory()() as session:
        event = await session.scalar(
            select(TaskOutbox).where(TaskOutbox.id == uuid.UUID(outbox_id)).with_for_update()
        )
        if event is None or event.status == "completed":
            return False
        if event.status == "running" and not allow_running:
            return False
        event.status = "running"
        event.error_message = None
        await session.commit()
        return True


async def mark_outbox_completed(outbox_id: str) -> None:
    await _set_outbox_status(outbox_id, "completed", finished=True)


async def mark_outbox_retrying(outbox_id: str, exc: Exception, countdown: int) -> None:
    await _set_outbox_status(
        outbox_id,
        "retrying",
        error=str(exc)[:2000],
        available_at=datetime.now(UTC) + timedelta(seconds=countdown),
    )


async def mark_outbox_failed(outbox_id: str, exc: Exception) -> None:
    await _set_outbox_status(
        outbox_id,
        "failed",
        error=str(exc)[:2000],
        finished=True,
    )


async def _set_outbox_status(
    outbox_id: str,
    status: str,
    *,
    error: str | None = None,
    available_at: datetime | None = None,
    finished: bool = False,
) -> None:
    async with get_session_factory()() as session:
        event = await session.get(TaskOutbox, uuid.UUID(outbox_id))
        if event is None:
            return
        event.status = status
        event.error_message = error
        if available_at is not None:
            event.available_at = available_at
        if finished:
            event.finished_at = datetime.now(UTC)
        if status == "retrying":
            await _mark_retrying_target(session, event.payload)
        await session.commit()


async def prepare_ingestion_retry(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    target_type: str,
    target_id: uuid.UUID,
) -> tuple[IngestionJob, str]:
    """Reset a failed ingestion and its existing outbox for user-triggered retry."""
    statement = (
        select(IngestionJob)
        .where(
            IngestionJob.user_id == user_id,
            IngestionJob.target_type == target_type,
            IngestionJob.target_id == target_id,
        )
        .order_by(IngestionJob.created_at.desc())
        .limit(1)
    )
    job = await session.scalar(statement)
    target = (
        await session.get(Document, target_id)
        if target_type == "document"
        else await session.get(ImageAsset, target_id)
    )
    if job is None or target is None or target.user_id != user_id:
        raise LookupError("处理任务不存在")
    if job.status not in {"failed", "retrying", "pending"}:
        raise ValueError("只有失败或等待中的任务可以重试")
    job.status = "pending"
    job.stage = "queued"
    job.progress = 0.0
    job.error_code = None
    job.error_message = None
    job.attempts = 0
    target.status = "pending"
    target.error_code = None
    target.error_message = None
    key = task_dedupe_key(target_type, job.id)
    event = await session.scalar(select(TaskOutbox).where(TaskOutbox.dedupe_key == key))
    if event is None:
        task_name = (
            WEB_DOCUMENT_TASK
            if target_type == "document"
            and isinstance(target, Document)
            and target.source_type == "web"
            else DOCUMENT_TASK
            if target_type == "document"
            else IMAGE_TASK
        )
        enqueue_task(
            session,
            task_name=task_name,
            queue="ingestion",
            dedupe_key=key,
            payload={
                f"{target_type}_id": str(target_id),
                "job_id": str(job.id),
            },
        )
    else:
        _reset_event(event)
    await session.commit()
    return job, key


async def prepare_memory_retry(
    session: AsyncSession, *, user_id: uuid.UUID, source_id: uuid.UUID
) -> tuple[MemorySource, str]:
    source = await session.get(MemorySource, source_id)
    if source is None or source.user_id != user_id:
        raise LookupError("记忆来源不存在")
    if source.status not in {"failed", "retrying", "pending"}:
        raise ValueError("只有失败或等待中的记忆可以重试")
    source.status = "pending"
    source.error_code = None
    source.error_message = None
    key = task_dedupe_key("memory", source.id)
    event = await session.scalar(select(TaskOutbox).where(TaskOutbox.dedupe_key == key))
    if event is None:
        enqueue_task(
            session,
            task_name=MEMORY_TASK,
            queue="memory",
            dedupe_key=key,
            payload={"source_id": str(source.id)},
        )
    else:
        _reset_event(event)
    await session.commit()
    return source, key


def _reset_event(event: TaskOutbox) -> None:
    event.status = "pending"
    event.available_at = datetime.now(UTC)
    event.finished_at = None
    event.error_message = None


async def _mark_dispatch_stage(
    session: AsyncSession, payload: dict[str, object], stage: str
) -> None:
    job_id = payload.get("job_id")
    if not isinstance(job_id, str):
        return
    job = await session.get(IngestionJob, uuid.UUID(job_id))
    if job is not None and job.status in {"pending", "retrying"}:
        job.stage = stage


async def _mark_retrying_target(session: AsyncSession, payload: dict[str, object]) -> None:
    job_id = payload.get("job_id")
    if isinstance(job_id, str):
        job = await session.get(IngestionJob, uuid.UUID(job_id))
        if job is not None:
            job.status = "retrying"
            job.stage = "retry_wait"
            target = (
                await session.get(Document, job.target_id)
                if job.target_type == "document"
                else await session.get(ImageAsset, job.target_id)
            )
            if target is not None:
                target.status = "pending"
        return
    source_id = payload.get("source_id")
    if isinstance(source_id, str):
        source = await session.get(MemorySource, uuid.UUID(source_id))
        if source is not None:
            source.status = "retrying"
        return
    research_id = payload.get("research_id")
    if isinstance(research_id, str):
        from app.infrastructure.database.models.research import ResearchTask

        task = await session.get(ResearchTask, uuid.UUID(research_id))
        if task is not None:
            task.status = "retrying"
            task.stage = "retry_wait"


async def recover_stale_work() -> int:
    """Reset work abandoned by a dead worker so the outbox can redeliver it."""
    from app.shared.config import get_settings

    settings = get_settings()
    cutoff = datetime.now(UTC) - timedelta(seconds=settings.task_stale_after_seconds)
    keys: list[str] = []
    async with get_session_factory()() as session:
        jobs = list(
            await session.scalars(
                select(IngestionJob).where(
                    IngestionJob.status == "processing",
                    IngestionJob.updated_at < cutoff,
                )
            )
        )
        for job in jobs:
            if job.attempts >= settings.task_max_attempts:
                job.status = "failed"
                job.stage = "failed"
                job.error_code = "TaskStale"
                job.error_message = "后台任务多次失去心跳，已停止自动恢复"
                target = (
                    await session.get(Document, job.target_id)
                    if job.target_type == "document"
                    else await session.get(ImageAsset, job.target_id)
                )
                if target is not None:
                    target.status = "failed"
                    target.error_code = job.error_code
                    target.error_message = job.error_message
                continue
            job.status = "pending"
            job.stage = "recovered"
            target = (
                await session.get(Document, job.target_id)
                if job.target_type == "document"
                else await session.get(ImageAsset, job.target_id)
            )
            if target is not None:
                target.status = "pending"
            key = task_dedupe_key(job.target_type, job.id)
            event = await session.scalar(select(TaskOutbox).where(TaskOutbox.dedupe_key == key))
            if event is not None:
                _reset_event(event)
                keys.append(key)

        sources = list(
            await session.scalars(
                select(MemorySource).where(
                    MemorySource.status == "extracting",
                    MemorySource.updated_at < cutoff,
                )
            )
        )
        for source in sources:
            source.status = "pending"
            source.error_code = "TaskRecovered"
            source.error_message = "检测到 Worker 中断，任务已重新排队"
            key = task_dedupe_key("memory", source.id)
            event = await session.scalar(select(TaskOutbox).where(TaskOutbox.dedupe_key == key))
            if event is not None:
                _reset_event(event)
                keys.append(key)

        from app.infrastructure.database.models.research import ResearchTask

        research_tasks = list(
            await session.scalars(
                select(ResearchTask).where(
                    ResearchTask.status.in_(("planning", "researching", "verifying", "writing")),
                    ResearchTask.updated_at < cutoff,
                )
            )
        )
        for task in research_tasks:
            task.status = "pending"
            task.stage = "recovered"
            task.error_code = "TaskRecovered"
            task.error_message = "检测到 Worker 中断，研究任务已重新排队"
            key = task_dedupe_key("research", task.id)
            event = await session.scalar(select(TaskOutbox).where(TaskOutbox.dedupe_key == key))
            if event is not None:
                _reset_event(event)
                keys.append(key)
        await session.commit()
    for key in keys:
        await dispatch_outbox(key)
    return len(keys)


async def rebuild_all_memory_communities() -> int:
    """Run the existing community rebuild once per user with stored memories."""
    from app.infrastructure.graph.memory_graph import MemoryGraphRepository

    async with get_session_factory()() as session:
        user_ids = list(await session.scalars(select(MemorySource.user_id).distinct()))
    graph = MemoryGraphRepository()
    for user_id in user_ids:
        await graph.rebuild_communities(str(user_id))
    return len(user_ids)
