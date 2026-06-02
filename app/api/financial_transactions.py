import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, and_
from app.core.deps import get_db, get_current_user
from app.models.user import User
from app.models.financial_transaction import FinancialTransaction
from app.schemas.financial_transaction import (
    FinancialTransactionResponse,
    TransactionUpdateRequest,
    TransactionListResponse,
)

router = APIRouter(prefix="/financial/transactions", tags=["Transactions"])


@router.get("", response_model=TransactionListResponse)
async def list_transactions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    account_id: str | None = None,
    category: str | None = None,
    transaction_type: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    source: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    filters = [
        FinancialTransaction.user_id == current_user.id,
        FinancialTransaction.is_deleted.is_(False),
    ]
    if account_id:      filters.append(FinancialTransaction.account_id == uuid.UUID(account_id))
    if category:        filters.append(FinancialTransaction.category == category)
    if transaction_type: filters.append(FinancialTransaction.transaction_type == transaction_type)
    if date_from:       filters.append(FinancialTransaction.date >= date_from)
    if date_to:         filters.append(FinancialTransaction.date <= date_to)
    if source:          filters.append(FinancialTransaction.source == source)

    total = (await db.execute(
        select(func.count()).select_from(FinancialTransaction).where(and_(*filters))
    )).scalar_one()

    rows = (await db.execute(
        select(FinancialTransaction)
        .where(and_(*filters))
        .order_by(desc(FinancialTransaction.date), desc(FinancialTransaction.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )).scalars().all()

    return TransactionListResponse(
        items=[FinancialTransactionResponse.model_validate(t) for t in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{tx_id}", response_model=FinancialTransactionResponse)
async def get_transaction(
    tx_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(FinancialTransaction).where(
            FinancialTransaction.id == uuid.UUID(tx_id),
            FinancialTransaction.user_id == current_user.id,
            FinancialTransaction.is_deleted.is_(False),
        )
    )
    tx = result.scalar_one_or_none()
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found.")
    return FinancialTransactionResponse.model_validate(tx)


@router.put("/{tx_id}", response_model=FinancialTransactionResponse)
async def update_transaction(
    tx_id: str,
    body: TransactionUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(FinancialTransaction).where(
            FinancialTransaction.id == uuid.UUID(tx_id),
            FinancialTransaction.user_id == current_user.id,
        )
    )
    tx = result.scalar_one_or_none()
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found.")

    if body.category is not None: tx.category = body.category
    if body.mode is not None:     tx.mode = body.mode
    if body.notes is not None:    tx.notes = body.notes
    await db.commit()
    return FinancialTransactionResponse.model_validate(tx)


@router.delete("/{tx_id}", status_code=204)
async def delete_transaction(
    tx_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(FinancialTransaction).where(
            FinancialTransaction.id == uuid.UUID(tx_id),
            FinancialTransaction.user_id == current_user.id,
        )
    )
    tx = result.scalar_one_or_none()
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found.")
    tx.is_deleted = True
    await db.commit()
