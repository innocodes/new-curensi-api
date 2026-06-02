from pydantic import BaseModel
from decimal import Decimal
from datetime import datetime


class BudgetCreate(BaseModel):
    category: str
    monthly_limit: Decimal
    alert_threshold: Decimal = Decimal("80")
    currency: str = "NGN"


class BudgetUpdate(BaseModel):
    category: str | None = None
    monthly_limit: Decimal | None = None
    alert_threshold: Decimal | None = None
    is_active: bool | None = None


class BudgetResponse(BaseModel):
    id: str
    category: str
    monthly_limit: Decimal
    alert_threshold: Decimal
    currency: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class BudgetProgressResponse(BudgetResponse):
    spent_this_month: Decimal
    percent_used: float
    days_remaining: int
    over_budget: bool
