import asyncio
import base64
import logging
from datetime import datetime, timezone
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30, name="tasks.parse_image")
def parse_image_task(self, batch_id: str, user_id: str, r2_key: str, source: str):
    """source: 'receipt_scan' | 'screenshot'"""
    asyncio.run(_parse_image_async(self, batch_id, user_id, r2_key, source))


async def _parse_image_async(task, batch_id: str, user_id: str, r2_key: str, source: str):
    from app.core.database import AsyncSessionLocal
    from app.models.ingestion import IngestionBatch, IngestionStatus
    from app.models.financial_transaction import FinancialTransaction
    from app.services.storage_service import fetch_from_r2
    from app.services.ai_parser import extract_from_image
    from app.services.notification_service import send_push_to_user
    from app.services.insights_service import invalidate_user_caches
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(IngestionBatch).where(IngestionBatch.id == batch_id))
        batch = result.scalar_one_or_none()
        if not batch:
            logger.error(f"Batch {batch_id} not found")
            return

        try:
            batch.status = IngestionStatus.PROCESSING
            await db.commit()

            image_bytes = await fetch_from_r2(r2_key)
            image_b64   = base64.b64encode(image_bytes).decode("utf-8")
            # Detect media type from r2_key extension
            ext = r2_key.rsplit(".", 1)[-1].lower()
            media_type_map = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}
            media_type = media_type_map.get(ext, "image/jpeg")

            item = await extract_from_image(image_b64, media_type)

            tx = FinancialTransaction(
                user_id=user_id,
                batch_id=batch_id,
                account_id=batch.account_id,
                date=item.date,
                description=item.merchant,
                amount=item.amount,
                transaction_type=item.type,
                currency=item.currency or batch.currency or "NGN",
                category=item.category_hint,
                source=source,
            )
            db.add(tx)

            batch.status = IngestionStatus.COMPLETED
            batch.transaction_count = 1
            batch.completed_at = datetime.now(timezone.utc)
            await db.commit()

            await invalidate_user_caches(user_id)
            await send_push_to_user(
                user_id=user_id,
                title="Receipt scanned ✅",
                body=f"Transaction of {item.currency} {item.amount:.2f} added.",
                data={"batch_id": batch_id, "type": "image_complete"},
                db=db,
            )

        except Exception as exc:
            batch.status = IngestionStatus.FAILED
            batch.error_message = str(exc)
            await db.commit()

            if task.request.retries < task.max_retries:
                raise task.retry(exc=exc)

            await send_push_to_user(
                user_id=user_id,
                title="Scan failed",
                body="We couldn't read the image. Please try again with a clearer photo.",
                data={"batch_id": batch_id, "type": "image_failed"},
                db=db,
            )
