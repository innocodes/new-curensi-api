import uuid
import enum
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, ForeignKey
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class SubscriptionTier(str, enum.Enum):
    FREE     = "free"
    PRO      = "pro"
    BUSINESS = "business"


class Subscription(Base):
    __tablename__ = "subscriptions"

    id:                   Mapped[uuid.UUID]      = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id:              Mapped[uuid.UUID]       = mapped_column(ForeignKey("users.id"), nullable=False, unique=True, index=True)
    tier:                 Mapped[str]             = mapped_column(
        SAEnum(SubscriptionTier, name="subscription_tier_enum"),
        default=SubscriptionTier.FREE,
    )
    paystack_customer_id: Mapped[str | None]      = mapped_column(String(255), nullable=True)
    paystack_sub_code:    Mapped[str | None]      = mapped_column(String(255), nullable=True)
    status:               Mapped[str]             = mapped_column(String(50), default="active")
    current_period_end:   Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at:           Mapped[datetime]        = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at:           Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=True,
    )
