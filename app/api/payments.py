from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel
from app.core.deps import get_db, get_current_user, require_kyc
from app.models.user import User
from app.models.transaction import Transaction
from app.services.payment_service import initiate_transaction
from app.services.fx_service import get_fx_rate, get_rate_response
from app.core.providers.registry import get_collection_provider
import uuid

router = APIRouter(prefix="/payments", tags=["payments"])


class InitiateRequest(BaseModel):
    corridor_code: str = "NG-CN"
    target_amount: Decimal
    target_type: str = "alipay_qr"
    target_data: str                  # QR code content
    payment_method: str = "bank_transfer"
    merchant_name: str | None = None
    note: str | None = None


class RateRequest(BaseModel):
    corridor_code: str = "NG-CN"


@router.get("/rate")
async def get_rate(corridor_code: str = "NG-CN", db: AsyncSession = Depends(get_db)):
    """Return the live FX rate for a corridor — no auth required so Splash screen can show it."""
    from sqlalchemy import select as sa_select
    from app.models.corridor import Corridor

    result = await db.execute(
        sa_select(Corridor).where(Corridor.code == corridor_code, Corridor.is_active == True)
    )
    corridor = result.scalar_one_or_none()
    if not corridor:
        raise HTTPException(status_code=404, detail=f"Corridor '{corridor_code}' not found")

    provider = get_collection_provider(corridor.collection_provider)
    rate = await get_fx_rate(corridor.source_currency, corridor.target_currency, provider)
    return get_rate_response(rate, corridor.fee_percentage)


@router.post("/initiate")
async def initiate(
    body: InitiateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_kyc),
):
    try:
        result = await initiate_transaction(
            user_id=current_user.id,
            corridor_code=body.corridor_code,
            target_amount=body.target_amount,
            target_type=body.target_type,
            target_data=body.target_data,
            payment_method=body.payment_method,
            metadata={
                "merchant_name": body.merchant_name,
                "note": body.note,
                "email": current_user.email,
            },
            db=db,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return result


@router.get("/{transaction_id}/status")
async def payment_status(
    transaction_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Transaction).where(
            Transaction.id == uuid.UUID(transaction_id),
            Transaction.user_id == current_user.id,
        )
    )
    tx = result.scalar_one_or_none()
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")

    return {
        "transaction_id": str(tx.id),
        "status": tx.status,
        "collection_status": tx.collection_status,
        "disbursement_status": tx.disbursement_status,
        "target_amount": float(tx.target_amount),
        "target_currency": tx.target_currency,
        "source_amount": float(tx.source_amount),
        "source_currency": tx.source_currency,
        "platform_fee": float(tx.platform_fee),
        "fx_rate": float(tx.fx_rate),
        "merchant_name": (tx.extra or {}).get("merchant_name"),
        "alipay_ref": tx.alipay_ref,
        "disbursement_reference": tx.disbursement_reference,
        "failure_reason": tx.failure_reason,
        "refund_status": tx.refund_status,
        "created_at": tx.created_at.isoformat(),
        "completed_at": tx.completed_at.isoformat() if tx.completed_at else None,
    }
