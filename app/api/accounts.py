import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.deps import get_db, get_current_user
from app.models.user import User
from app.models.bank_account import BankAccount
from app.schemas.account import BankAccountCreate, BankAccountResponse

router = APIRouter(prefix="/accounts", tags=["Accounts"])


@router.get("", response_model=list[BankAccountResponse])
async def list_accounts(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = (await db.execute(
        select(BankAccount).where(BankAccount.user_id == current_user.id)
    )).scalars().all()
    return [BankAccountResponse.model_validate(a) for a in rows]


@router.post("", response_model=BankAccountResponse, status_code=201)
async def create_account(
    body: BankAccountCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    account = BankAccount(
        user_id=current_user.id,
        bank_name=body.bank_name,
        nickname=body.nickname,
        account_type=body.account_type,
        currency=body.currency,
    )
    db.add(account)
    await db.commit()
    return BankAccountResponse.model_validate(account)


@router.put("/{account_id}", response_model=BankAccountResponse)
async def update_account(
    account_id: str,
    body: BankAccountCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(BankAccount).where(
            BankAccount.id == uuid.UUID(account_id),
            BankAccount.user_id == current_user.id,
        )
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found.")

    account.bank_name    = body.bank_name
    account.nickname     = body.nickname
    account.account_type = body.account_type
    account.currency     = body.currency
    await db.commit()
    return BankAccountResponse.model_validate(account)


@router.delete("/{account_id}", status_code=204)
async def delete_account(
    account_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(BankAccount).where(
            BankAccount.id == uuid.UUID(account_id),
            BankAccount.user_id == current_user.id,
        )
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found.")
    await db.delete(account)
    await db.commit()
