import asyncio
import uuid
from datetime import datetime, timezone
from sqlalchemy import select
from app.tasks.celery_app import celery_app
from app.core.database import AsyncSessionLocal
from app.core.providers.registry import get_disbursement_provider
from app.models.transaction import Transaction
from app.models.audit_log import AuditLog
from app.models.user import User
from app.services.notification_service import send_push


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def disburse_payment(self, transaction_id: str):
    asyncio.run(_disburse(self, transaction_id))


async def _disburse(task, transaction_id: str):
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Transaction).where(Transaction.id == uuid.UUID(transaction_id))
        )
        tx = result.scalar_one_or_none()
        if not tx:
            return

        # Guard against double-disbursement
        if tx.disbursement_status != "pending":
            return

        user_result = await db.execute(select(User).where(User.id == tx.user_id))
        user = user_result.scalar_one_or_none()

        try:
            provider = get_disbursement_provider(tx.disbursement_provider)

            result = await provider.pay_qr(
                qr_code=tx.disbursement_target_data,
                amount=tx.target_amount,
                currency=tx.target_currency,
                transaction_ref=str(tx.id),
                metadata={"user_id": str(tx.user_id), **(tx.extra or {})},
            )

            tx.disbursement_reference = result["disbursement_reference"]
            tx.disbursement_status = "processing"
            tx.status = "disbursement_initiated"

            db.add(AuditLog(
                transaction_id=tx.id, user_id=tx.user_id,
                event="disbursement_initiated",
                provider=tx.disbursement_provider,
                payload=result,
            ))
            await db.commit()

        except Exception as exc:
            if task.request.retries < task.max_retries:
                raise task.retry(exc=exc)

            # All retries exhausted — fail and queue refund
            tx.disbursement_status = "failed"
            tx.status = "failed"
            tx.failure_reason = str(exc)

            db.add(AuditLog(
                transaction_id=tx.id, user_id=tx.user_id,
                event="disbursement_failed",
                provider=tx.disbursement_provider,
                payload={"error": str(exc)},
            ))
            await db.commit()

            initiate_refund.delay(transaction_id)

            if user and user.fcm_token:
                send_push(
                    fcm_token=user.fcm_token,
                    title="Payment failed",
                    body="We couldn't complete your payment. A refund will be processed within 24 hours.",
                    data={"transaction_id": transaction_id, "type": "payment_failed"},
                )
