from pydantic import BaseModel
from datetime import datetime


class SubscriptionResponse(BaseModel):
    id: str
    tier: str
    status: str
    current_period_end: datetime | None

    model_config = {"from_attributes": True}


class UpgradeRequest(BaseModel):
    tier: str        # pro | business
    paystack_auth_code: str | None = None
