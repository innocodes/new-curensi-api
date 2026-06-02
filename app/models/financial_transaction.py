import uuid
import enum
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import String, Numeric, DateTime, Text, ForeignKey, Boolean
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class UserMode(str, enum.Enum):
    PERSONAL = "personal"
    BUSINESS = "business"


class FinancialTransaction(Base):
    """
    Aggregator transaction model — stores transactions extracted from
    bank statements, receipts, screenshots, or entered manually.

    Distinct from the payment platform's Transaction model (table: transactions).
    This table: financial_transactions.
    """
    __tablename__ = "financial_transactions"

    id:               Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id:          Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    batch_id:         Mapped[uuid.UUID | None] = mapped_column(ForeignKey("ingestion_batches.id"), nullable=True)
    account_id:       Mapped[uuid.UUID | None] = mapped_column(ForeignKey("bank_accounts.id"), nullable=True)

    # Extracted financial data
    date:             Mapped[str | None]     = mapped_column(String(20), nullable=True)     # "YYYY-MM-DD"
    description:      Mapped[str | None]     = mapped_column(String(500), nullable=True)
    amount:           Mapped[Decimal]        = mapped_column(Numeric(14, 2), nullable=False)
    transaction_type: Mapped[str]            = mapped_column(String(10))                    # credit | debit
    balance_after:    Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    reference:        Mapped[str | None]     = mapped_column(String(255), nullable=True)
    currency:         Mapped[str]            = mapped_column(String(3), default="NGN")

    # User-editable fields
    category:         Mapped[str | None]     = mapped_column(String(100), nullable=True)
    mode:             Mapped[str | None]     = mapped_column(
        SAEnum(UserMode, name="user_mode_enum"), nullable=True
    )
    notes:            Mapped[str | None]     = mapped_column(Text, nullable=True)

    # Source and flags
    source:           Mapped[str | None]     = mapped_column(String(50), nullable=True)     # pdf_statement|receipt_scan|etc.
    is_deleted:       Mapped[bool]           = mapped_column(Boolean, default=False)        # soft delete

    created_at:       Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )
    updated_at:       Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=True,
    )
