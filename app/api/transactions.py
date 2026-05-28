import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from app.core.deps import get_db, get_current_user
from app.models.user import User
from app.models.transaction import Transaction

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.get("")
async def list_transactions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(Transaction).where(Transaction.user_id == current_user.id)
    if status:
        query = query.where(Transaction.status == status)
    query = query.order_by(desc(Transaction.created_at))

    count_q = select(func.count()).select_from(
        select(Transaction.id).where(Transaction.user_id == current_user.id).subquery()
    )
    total = (await db.execute(count_q)).scalar_one()

    offset = (page - 1) * page_size
    rows = (await db.execute(query.offset(offset).limit(page_size))).scalars().all()

    return {
        "items": [_serialize_list(tx) for tx in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/{transaction_id}")
async def get_transaction(
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
    return _serialize_detail(tx)


def _serialize_list(tx: Transaction) -> dict:
    return {
        "id": str(tx.id),
        "merchant_name": (tx.extra or {}).get("merchant_name"),
        "target_amount": float(tx.target_amount),
        "target_currency": tx.target_currency,
        "source_amount": float(tx.source_amount),
        "source_currency": tx.source_currency,
        "status": tx.status,
        "payment_method": tx.collection_method,
        "created_at": tx.created_at.isoformat(),
    }


def _serialize_detail(tx: Transaction) -> dict:
    return {
        **_serialize_list(tx),
        "platform_fee": float(tx.platform_fee),
        "fee_percentage": float(tx.fee_percentage),
        "fx_rate": float(tx.fx_rate),
        "collection_provider": tx.collection_provider,
        "collection_reference": tx.collection_reference,
        "collection_status": tx.collection_status,
        "disbursement_provider": tx.disbursement_provider,
        "disbursement_reference": tx.disbursement_reference,
        "disbursement_status": tx.disbursement_status,
        "alipay_ref": tx.alipay_ref,
        "failure_reason": tx.failure_reason,
        "refund_status": tx.refund_status,
        "refund_reference": tx.refund_reference,
        "completed_at": tx.completed_at.isoformat() if tx.completed_at else None,
        "note": (tx.extra or {}).get("note"),
    }
