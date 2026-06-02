import uuid
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import String, Numeric, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class BankAccount(Base):
    __tablename__ = "bank_accounts"

    id:           Mapped[uuid.UUID]      = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id:      Mapped[uuid.UUID]      = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    bank_name:    Mapped[str | None]     = mapped_column(String(100), nullable=True)
    nickname:     Mapped[str | None]     = mapped_column(String(100), nullable=True)
    account_type: Mapped[str | None]     = mapped_column(String(50), nullable=True)   # current|savings|business|wallet
    currency:     Mapped[str]            = mapped_column(String(3), default="NGN")
    last_balance: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    last_synced:  Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at:   Mapped[datetime]       = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
