import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Boolean, DateTime, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    full_name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    phone: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    country: Mapped[str] = mapped_column(String(3), default="NG")   # ISO-3166 alpha-2
    hashed_password: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    kyc_status: Mapped[str] = mapped_column(
        SAEnum("pending", "submitted", "verified", "failed", name="kyc_status_enum"),
        default="pending",
    )
    tier: Mapped[int] = mapped_column(default=1)  # 1 = ₦500k/day, 2 = ₦5M/day
    fcm_token: Mapped[str | None] = mapped_column(String(500), nullable=True)  # Firebase push token
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
