from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "curensi",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "app.tasks.disbursement",
        "app.tasks.refund",
        "app.tasks.notifications",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,          # re-queue if worker crashes mid-task
    worker_prefetch_multiplier=1, # one task at a time per worker for financial safety
)
