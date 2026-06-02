import uuid
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import String, Numeric, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class Budget(Base):
    __tablename__ = "budgets"

    id:              Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id:         Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    category:        Mapped[str]       = mapped_column(String(100), nullable=False)
    monthly_limit:   Mapped[Decimal]   = mapped_column(Numeric(14, 2), nullable=False)
    alert_threshold: Mapped[Decimal]   = mapped_column(Numeric(5, 2), default=Decimal("80"))  # % of limit
    currency:        Mapped[str]       = mapped_column(String(3), default="NGN")
    is_active:       Mapped[bool]      = mapped_column(Boolean, default=True)
    created_at:      Mapped[datetime]  = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
