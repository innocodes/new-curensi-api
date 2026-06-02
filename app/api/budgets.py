import uuid
from datetime import datetime, timezone
from calendar import monthrange
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.core.deps import get_db, get_current_user
from app.models.user import User
from app.models.budget import Budget
from app.models.financial_transaction import FinancialTransaction
from app.schemas.budget import BudgetCreate, BudgetUpdate, BudgetResponse, BudgetProgressResponse

router = APIRouter(prefix="/budgets", tags=["Budgets"])


@router.get("", response_model=list[BudgetResponse])
async def list_budgets(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = (await db.execute(
        select(Budget).where(Budget.user_id == current_user.id, Budget.is_active.is_(True))
    )).scalars().all()
    return [BudgetResponse.model_validate(b) for b in rows]


@router.post("", response_model=BudgetResponse, status_code=201)
async def create_budget(
    body: BudgetCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    budget = Budget(
        user_id=current_user.id,
        category=body.category,
        monthly_limit=body.monthly_limit,
        alert_threshold=body.alert_threshold,
        currency=body.currency,
    )
    db.add(budget)
    await db.commit()
    return BudgetResponse.model_validate(budget)


@router.put("/{budget_id}", response_model=BudgetResponse)
async def update_budget(
    budget_id: str,
    body: BudgetUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Budget).where(Budget.id == uuid.UUID(budget_id), Budget.user_id == current_user.id)
    )
    budget = result.scalar_one_or_none()
    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found.")

    if body.category is not None:       budget.category = body.category
    if body.monthly_limit is not None:  budget.monthly_limit = body.monthly_limit
    if body.alert_threshold is not None: budget.alert_threshold = body.alert_threshold
    if body.is_active is not None:      budget.is_active = body.is_active
    await db.commit()
    return BudgetResponse.model_validate(budget)


@router.delete("/{budget_id}", status_code=204)
async def delete_budget(
    budget_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Budget).where(Budget.id == uuid.UUID(budget_id), Budget.user_id == current_user.id)
    )
    budget = result.scalar_one_or_none()
    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found.")
    budget.is_active = False
    await db.commit()


@router.get("/progress", response_model=list[BudgetProgressResponse])
async def budget_progress(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """All active budgets with percent used and days remaining this month."""
    budgets = (await db.execute(
        select(Budget).where(Budget.user_id == current_user.id, Budget.is_active.is_(True))
    )).scalars().all()

    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    days_in_month = monthrange(now.year, now.month)[1]
    days_remaining = days_in_month - now.day + 1

    results = []
    for b in budgets:
        spent_result = await db.execute(
            select(func.sum(FinancialTransaction.amount)).where(
                FinancialTransaction.user_id == current_user.id,
                FinancialTransaction.category == b.category,
                FinancialTransaction.transaction_type == "debit",
                FinancialTransaction.created_at >= month_start,
                FinancialTransaction.is_deleted.is_(False),
            )
        )
        spent = spent_result.scalar_one() or Decimal("0")
        percent = float(spent / b.monthly_limit * 100) if b.monthly_limit else 0.0

        results.append(BudgetProgressResponse(
            **BudgetResponse.model_validate(b).model_dump(),
            spent_this_month=spent,
            percent_used=round(percent, 1),
            days_remaining=days_remaining,
            over_budget=spent > b.monthly_limit,
        ))
    return results
