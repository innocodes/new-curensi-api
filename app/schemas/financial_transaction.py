from pydantic import BaseModel
from datetime import datetime
from decimal import Decimal


class FinancialTransactionResponse(BaseModel):
    id: str
    user_id: str
    batch_id: str | None
    account_id: str | None
    date: str | None
    description: str | None
    amount: Decimal
    transaction_type: str
    balance_after: Decimal | None
    reference: str | None
    currency: str
    category: str | None
    mode: str | None
    notes: str | None
    source: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class TransactionUpdateRequest(BaseModel):
    category: str | None = None
    mode: str | None = None
    notes: str | None = None


class TransactionListResponse(BaseModel):
    items: list[FinancialTransactionResponse]
    total: int
    page: int
    page_size: int
