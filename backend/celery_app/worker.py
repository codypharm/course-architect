"""Celery application instance and configuration.

This module is the single entry point for all three Fargate services:

  Worker:  celery -A celery_app.worker worker -Q high_priority,generation,retry --loglevel=info
  Beat:    celery -A celery_app.worker beat   --loglevel=info
  Flower:  celery -A celery_app.worker flower --port=5555
"""
import os

from celery import Celery
from dotenv import load_dotenv

load_dotenv()

REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "ai_course_architect",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["celery_app.tasks"],
)

celery_app.conf.update(
    # Queue routing — three queues with different worker pools
    task_routes={
        "queue.tasks.pipeline_start":             {"queue": "high_priority"},
        "queue.tasks.pipeline_resume_validation": {"queue": "high_priority"},
        "queue.tasks.pipeline_resume_curriculum": {"queue": "generation"},
        # pipeline_resume_curriculum overrides queue to "retry" when retry=True
    },

    # Reliability — task is only acknowledged after successful completion
    task_acks_late=True,
    task_reject_on_worker_lost=True,

    # Retry policy
    task_max_retries=3,
    task_retry_backoff=True,

    # Serialisation
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],

    # Result expiry — 1 hour is enough for polling
    result_expires=3600,

    # Timezone
    timezone="UTC",
    enable_utc=True,
)