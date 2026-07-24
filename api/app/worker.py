"""Stable Celery CLI import target: ``celery -A app.worker.celery_app``."""

from app.celery_app import celery_app

__all__ = ["celery_app"]
