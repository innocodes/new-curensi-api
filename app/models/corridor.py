import uuid
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import String, Boolean, DateTime, Numeric, ARRAY
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class Corridor(Base):
    __tablename__ = "corridors"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(10), unique=True, index=True)  # e.g. "NG-CN"
    name: Mapped[str] = mapped_column(String(100))                           # "Nigeria → China"
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)

    # Collection (source) side
    source_country: Mapped[str] = mapped_column(String(3))          # "NG"
    source_currency: Mapped[str] = mapped_column(String(3))         # "NGN"
    collection_provider: Mapped[str] = mapped_column(String(50))    # "flutterwave"
    supported_methods: Mapped[list[str]] = mapped_column(ARRAY(String))  # ["bank_transfer","card","ussd"]

    # Disbursement (target) side
    target_country: Mapped[str] = mapped_column(String(3))          # "CN"
    target_currency: Mapped[str] = mapped_column(String(3))         # "CNY"
    disbursement_provider: Mapped[str] = mapped_column(String(50))  # "lianlian"
    supported_targets: Mapped[list[str]] = mapped_column(ARRAY(String))  # ["alipay_qr","wechat_qr"]

    # Fee structure
    fee_type: Mapped[str] = mapped_column(String(20), default="percentage")  # percentage|flat|hybrid
    fee_percentage: Mapped[Decimal] = mapped_column(Numeric(6, 4), default=Decimal("2.00"))
    fee_flat: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"))
    min_fee: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"))
    max_fee: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)

    # Transaction limits (in source currency)
    min_transaction: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("5000.00"))
    max_transaction: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("5000000.00"))
    daily_limit: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("5000000.00"))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
