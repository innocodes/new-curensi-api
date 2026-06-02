import asyncio
import logging
from app.tasks.celery_app import celery_app
from app.services.storage_service import FILE_RETENTION_DAYS

logger = logging.getLogger(__name__)


@celery_app.task(name="tasks.cleanup_expired_files")
def cleanup_expired_files():
    """
    Runs daily at 2am via Celery Beat.
    Deletes raw files from R2 older than FILE_RETENTION_DAYS (14 days).
    Only extracted transaction data is retained in PostgreSQL.
    NDPR compliance requirement.
    """
    asyncio.run(_cleanup_async())


async def _cleanup_async():
    from app.core.database import AsyncSessionLocal
    from app.models.ingestion import IngestionBatch
    from app.services.storage_service import delete_from_r2
    from sqlalchemy import select
    from datetime import datetime, timezone, timedelta

    cutoff = datetime.now(timezone.utc) - timedelta(days=FILE_RETENTION_DAYS)

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(IngestionBatch).where(
                IngestionBatch.created_at < cutoff,
                IngestionBatch.r2_key.isnot(None),
                IngestionBatch.r2_deleted_at.is_(None),
            )
        )
        batches = result.scalars().all()

        deleted = 0
        for batch in batches:
            try:
                await delete_from_r2(batch.r2_key)
                batch.r2_key = None
                batch.r2_deleted_at = datetime.now(timezone.utc)
                deleted += 1
            except Exception as e:
                logger.warning(f"Failed to delete R2 file for batch {batch.id}: {e}")

        await db.commit()
        logger.info(f"NDPR cleanup: {deleted}/{len(batches)} files deleted from R2")
