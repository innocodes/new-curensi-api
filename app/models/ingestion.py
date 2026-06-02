import uuid
import enum
from datetime import datetime, timezone
from sqlalchemy import String, Integer, DateTime, Text, ForeignKey
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class IngestionStatus(str, enum.Enum):
    PENDING    = "pending"
    PROCESSING = "processing"
    COMPLETED  = "completed"
    FAILED     = "failed"


class IngestionSource(str, enum.Enum):
    PDF_STATEMENT = "pdf_statement"
    RECEIPT_SCAN  = "receipt_scan"
    SCREENSHOT    = "screenshot"
    WHATSAPP      = "whatsapp"
    MANUAL        = "manual"


class IngestionBatch(Base):
    __tablename__ = "ingestion_batches"

    id:                Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id:           Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    account_id:        Mapped[uuid.UUID | None] = mapped_column(ForeignKey("bank_accounts.id"), nullable=True)

    source:            Mapped[str] = mapped_column(
        SAEnum(IngestionSource, name="ingestion_source_enum"), nullable=False
    )
    status:            Mapped[str] = mapped_column(
        SAEnum(IngestionStatus, name="ingestion_status_enum"),
        default=IngestionStatus.PENDING,
        index=True,
    )

    r2_key:            Mapped[str | None]  = mapped_column(String(500), nullable=True)   # raw file in R2
    r2_deleted_at:     Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)  # NDPR
    currency:          Mapped[str]         = mapped_column(String(3), default="NGN")
    transaction_count: Mapped[int]         = mapped_column(Integer, default=0)
    error_message:     Mapped[str | None]  = mapped_column(Text, nullable=True)

    created_at:        Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )
    completed_at:      Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
