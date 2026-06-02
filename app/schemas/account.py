from pydantic import BaseModel
from decimal import Decimal
from datetime import datetime


class BankAccountCreate(BaseModel):
    bank_name: str | None = None
    nickname: str | None = None
    account_type: str | None = None   # current | savings | business | wallet
    currency: str = "NGN"


class BankAccountResponse(BaseModel):
    id: str
    bank_name: str | None
    nickname: str | None
    account_type: str | None
    currency: str
    last_balance: Decimal | None
    last_synced: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}
