import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Request, HTTPException, Depends, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.deps import get_db
from app.core.providers.flutterwave import FlutterwaveProvider
from app.core.providers.lianlian import LianLianProvider
from app.models.transaction import Transaction
from app.models.audit_log import AuditLog
from app.models.user import User
from app.tasks.disbursement import disburse_payment
from app.services.notification_service import send_push

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/flutterwave")
async def flutterwave_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    # Verify signature
    signature = request.headers.get("verif-hash", "")
    if not FlutterwaveProvider.verify_webhook(b"", signature):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    payload = await request.json()

    if payload.get("event") != "charge.completed":
        return {"status": "ignored"}

    data = payload.get("data", {})
    tx_ref = data.get("tx_ref")
    if not tx_ref:
        return {"status": "ignored"}

    # Look up transaction by collection reference
    result = await db.execute(
        select(Transaction).where(Transaction.collection_reference == tx_ref)
    )
    tx = result.scalar_one_or_none()
    if not tx:
        return {"status": "not_found"}

    # Idempotency — skip if already confirmed
    if tx.collection_status == "confirmed":
        return {"status": "already_processed"}

    # Mark collection confirmed
    tx.collection_status = "confirmed"
    tx.status = "collection_confirmed"

    db.add(AuditLog(
        transaction_id=tx.id, user_id=tx.user_id,
        event="collection_confirmed",
        provider="flutterwave",
        payload=data,
    ))
    await db.commit()

    # Notify user that payment received — disbursing now
    user_result = await db.execute(select(User).where(User.id == tx.user_id))
    user = user_result.scalar_one_or_none()
    if user and user.fcm_token:
        send_push(
            fcm_token=user.fcm_token,
            title="Payment received",
            body=f"₦{tx.source_amount:,.0f} received — sending {tx.target_currency} {tx.target_amount} to Alipay now.",
            data={"transaction_id": str(tx.id), "type": "collection_confirmed"},
        )

    # Queue disbursement via Celery
    background_tasks.add_task(disburse_payment.delay, str(tx.id))

    return {"status": "accepted"}


@router.post("/lianlian")
async def lianlian_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    # Verify signature
    body = await request.body()
    signature = request.headers.get("X-LianLian-Signature", "")
    if not LianLianProvider.verify_webhook(body, signature):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    payload = await request.json()
    order_id = payload.get("order_id")
    ll_status = payload.get("status")

    result = await db.execute(
        select(Transaction).where(Transaction.id == uuid.UUID(order_id))
    )
    tx = result.scalar_one_or_none()
    if not tx:
        return {"status": "not_found"}

    db.add(AuditLog(
        transaction_id=tx.id, user_id=tx.user_id,
        event=f"lianlian_{ll_status.lower()}",
        provider="lianlian",
        payload=payload,
    ))

    if ll_status == "SUCCESS":
        tx.disbursement_status = "completed"
        tx.status = "completed"
        tx.alipay_ref = payload.get("alipay_trade_no")
        tx.completed_at = datetime.now(timezone.utc)

        user_result = await db.execute(select(User).where(User.id == tx.user_id))
        user = user_result.scalar_one_or_none()
        if user and user.fcm_token:
            send_push(
                fcm_token=user.fcm_token,
                title="Payment sent ✓",
                body=f"{tx.target_currency} {tx.target_amount} delivered to the merchant.",
                data={"transaction_id": str(tx.id), "type": "payment_completed"},
            )

    elif ll_status == "FAILED":
        tx.disbursement_status = "failed"
        tx.failure_reason = payload.get("fail_reason")
        # Refund will be triggered by the task retry exhaustion flow

    await db.commit()
    return {"status": "accepted"}
