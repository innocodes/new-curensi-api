import asyncio
import uuid
from sqlalchemy import select
from app.tasks.celery_app import celery_app
from app.core.database import AsyncSessionLocal
from app.core.providers.registry import get_collection_provider
from app.models.transaction import Transaction
from app.models.audit_log import AuditLog
from app.models.user import User
from app.services.notification_service import send_push


@celery_app.task(bind=True, max_retries=3, default_retry_delay=120)
def initiate_refund(self, transaction_id: str):
    asyncio.run(_refund(self, transaction_id))


async def _refund(task, transaction_id: str):
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Transaction).where(Transaction.id == uuid.UUID(transaction_id))
        )
        tx = result.scalar_one_or_none()
        if not tx or tx.refund_status not in (None, "none"):
            return

        user_result = await db.execute(select(User).where(User.id == tx.user_id))
        user = user_result.scalar_one_or_none()

        tx.refund_status = "initiated"
        tx.status = "refund_initiated"
        db.add(AuditLog(
            transaction_id=tx.id, user_id=tx.user_id,
            event="refund_initiated", provider=tx.collection_provider,
        ))
        await db.commit()

        try:
            provider = get_collection_provider(tx.collection_provider)
            refund = await provider.initiate_refund(
                provider_reference=tx.collection_reference or "",
                amount=tx.source_amount,
                reason=tx.failure_reason or "Payment disbursement failed",
            )

            tx.refund_reference = refund["refund_reference"]
            tx.refund_amount = tx.source_amount
            tx.refund_status = "completed"
            tx.status = "refunded"

            db.add(AuditLog(
                transaction_id=tx.id, user_id=tx.user_id,
                event="refund_completed",
                provider=tx.collection_provider,
                payload=refund,
            ))
            await db.commit()

            if user and user.fcm_token:
                send_push(
                    fcm_token=user.fcm_token,
                    title="Refund initiated",
                    body=f"₦{tx.source_amount:,.2f} is being returned to your account.",
                    data={"transaction_id": transaction_id, "type": "refund_initiated"},
                )

        except Exception as exc:
            if task.request.retries < task.max_retries:
                raise task.retry(exc=exc)

            tx.refund_status = "failed"
            db.add(AuditLog(
                transaction_id=tx.id, user_id=tx.user_id,
                event="refund_failed", payload={"error": str(exc)},
            ))
            await db.commit()
