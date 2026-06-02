from pydantic import BaseModel
from datetime import datetime
from decimal import Decimal


class IngestPDFRequest(BaseModel):
    account_id: str | None = None
    currency: str = "NGN"


class IngestImageRequest(BaseModel):
    source: str  # receipt_scan | screenshot
    account_id: str | None = None


class IngestManualRequest(BaseModel):
    amount: Decimal
    transaction_type: str          # credit | debit
    date: str                      # YYYY-MM-DD
    description: str
    category: str | None = None
    account_id: str | None = None
    currency: str = "NGN"
    notes: str | None = None


class IngestionBatchResponse(BaseModel):
    id: str
    source: str
    status: str
    transaction_count: int
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}
