from celery import Celery
from celery.schedules import crontab
from app.core.config import settings

celery_app = Celery(
    "curensi",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        # Aggregator tasks
        "app.tasks.parse_pdf",
        "app.tasks.parse_image",
        "app.tasks.generate_insights",
        "app.tasks.cleanup",
        # Shared
        "app.tasks.notifications",
        # Payment platform (preserved — imported even when flagged off,
        # but only dispatched when ENABLE_PAYMENTS=True)
        "app.tasks.disbursement",
        "app.tasks.refund",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,           # re-queue if worker crashes mid-task
    worker_prefetch_multiplier=1,  # one task at a time per worker for financial safety

    # ── Celery Beat schedule ──────────────────────────────────────────
    beat_schedule={
        # NDPR compliance: delete raw R2 files older than 14 days — daily at 2am
        "cleanup-expired-files": {
            "task": "tasks.cleanup_expired_files",
            "schedule": crontab(hour=2, minute=0),
        },
        # Pro/Business insight refresh — daily at 6am
        # Individual user tasks are dispatched by this scheduled task
        "refresh-insights-trigger": {
            "task": "tasks.refresh_insights_for_eligible_users",
            "schedule": crontab(hour=6, minute=0),
        },
    },
)
