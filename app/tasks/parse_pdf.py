import asyncio
import logging
from datetime import datetime, timezone
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30, name="tasks.parse_pdf")
def parse_pdf_task(self, batch_id: str, user_id: str, r2_key: str):
    asyncio.run(_parse_pdf_async(self, batch_id, user_id, r2_key))


async def _parse_pdf_async(task, batch_id: str, user_id: str, r2_key: str):
    from app.core.database import AsyncSessionLocal
    from app.models.ingestion import IngestionBatch, IngestionStatus
    from app.models.financial_transaction import FinancialTransaction
    from app.services.storage_service import fetch_from_r2, extract_pdf_text
    from app.services.ai_parser import extract_from_pdf
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

            pdf_bytes = await fetch_from_r2(r2_key)
            pdf_text  = extract_pdf_text(pdf_bytes)
            extracted = await extract_from_pdf(pdf_text)

            transactions = [
                FinancialTransaction(
                    user_id=user_id,
                    batch_id=batch_id,
                    account_id=batch.account_id,
                    date=item.date,
                    description=item.description,
                    amount=item.amount,
                    transaction_type=item.type,
                    balance_after=item.balance_after,
                    reference=item.reference,
                    source="pdf_statement",
                    currency=batch.currency or "NGN",
                )
                for item in extracted
            ]
            db.add_all(transactions)

            batch.status = IngestionStatus.COMPLETED
            batch.transaction_count = len(transactions)
            batch.completed_at = datetime.now(timezone.utc)
            await db.commit()

            await invalidate_user_caches(user_id)
            await send_push_to_user(
                user_id=user_id,
                title="Statement processed ✅",
                body=f"{len(transactions)} transactions extracted from your statement.",
                data={"batch_id": batch_id, "type": "pdf_complete"},
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
                title="Processing failed",
                body="We couldn't read your statement. Please try again or contact support.",
                data={"batch_id": batch_id, "type": "pdf_failed"},
                db=db,
            )
