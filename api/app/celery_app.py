"""Celery application and queue policy for durable background work."""

from celery import Celery
from celery.schedules import crontab
from kombu import Exchange, Queue

from app.shared.config import get_settings

settings = get_settings()
task_exchange = Exchange("avpilot", type="direct")

celery_app = Celery(
    "avpilot",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "app.tasks.ingestion",
        "app.tasks.memory",
        "app.tasks.maintenance",
    ],
)
celery_app.conf.update(
    task_queues=(
        Queue("ingestion", task_exchange, routing_key="ingestion"),
        Queue("memory", task_exchange, routing_key="memory"),
        Queue("maintenance", task_exchange, routing_key="maintenance"),
    ),
    task_default_queue="maintenance",
    task_default_exchange="avpilot",
    task_default_exchange_type="direct",
    task_default_routing_key="maintenance",
    task_routes={
        "app.tasks.ingestion.*": {"queue": "ingestion"},
        "app.tasks.memory.*": {"queue": "memory"},
        "app.tasks.maintenance.*": {"queue": "maintenance"},
    },
    task_track_started=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    broker_transport_options={
        "visibility_timeout": settings.celery_visibility_timeout_seconds,
    },
    result_expires=3600,
    timezone="Asia/Shanghai",
    enable_utc=True,
    beat_schedule={
        "recover-task-outbox": {
            "task": "app.tasks.maintenance.recover_task_outbox",
            "schedule": 30.0,
        },
        "recover-stale-ingestions": {
            "task": "app.tasks.maintenance.recover_stale_ingestions",
            "schedule": 60.0,
        },
        "recover-stale-agent-traces": {
            "task": "app.tasks.maintenance.recover_stale_agent_traces",
            "schedule": 60.0,
        },
        "rebuild-memory-communities": {
            "task": "app.tasks.maintenance.rebuild_memory_communities",
            "schedule": crontab(hour=3, minute=0),
        },
    },
)
