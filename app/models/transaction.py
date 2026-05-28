import uuid
from decimal import Decimal
from datetime import datetime, timezone
from sqlalchemy import String, Numeric, DateTime, Enum as SAEnum, ForeignKey, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    corridor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("corridors.id"), index=True)

    # Idempotency — prevents double processing on retries / duplicate webhooks
    idempotency_key: Mapped[str] = mapped_column(String(255), unique=True, index=True)

    # Collection (source) side
    source_currency: Mapped[str] = mapped_column(String(3))          # "NGN"
    source_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))   # total user pays incl. fee
    platform_fee: Mapped[Decimal] = mapped_column(Numeric(14, 2))    # fee portion
    fee_percentage: Mapped[Decimal] = mapped_column(Numeric(6, 4))   # snapshotted at tx time
    collection_provider: Mapped[str] = mapped_column(String(50))     # "flutterwave"
    collection_method: Mapped[str | None] = mapped_column(
        SAEnum("bank_transfer", "card", "ussd", "mobile_money", name="collection_method_enum"),
        nullable=True,
    )
    collection_reference: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    collection_status: Mapped[str] = mapped_column(
        SAEnum("pending", "confirmed", "failed", name="collection_status_enum"),
        default="pending",
        index=True,
    )

    # FX
    fx_rate: Mapped[Decimal] = mapped_column(Numeric(14, 8))         # target per source unit
    fx_rate_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    # Disbursement (target) side
    target_currency: Mapped[str] = mapped_column(String(3))          # "CNY"
    target_amount: Mapped[Decimal] = mapped_column(Numeric(14, 4))   # what merchant receives
    disbursement_provider: Mapped[str] = mapped_column(String(50))   # "lianlian"
    disbursement_target_type: Mapped[str] = mapped_column(String(50)) # "alipay_qr"
    disbursement_target_data: Mapped[str] = mapped_column(Text)       # QR code content
    disbursement_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    disbursement_status: Mapped[str] = mapped_column(
        SAEnum("pending", "processing", "completed", "failed", name="disbursement_status_enum"),
        default="pending",
        index=True,
    )
    alipay_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Overall status (derived from collection + disbursement statuses)
    status: Mapped[str] = mapped_column(
        SAEnum(
            "pending",
            "collection_initiated",
            "collection_confirmed",
            "disbursement_initiated",
            "disbursement_processing",
            "completed",
            "failed",
            "refund_initiated",
            "refunded",
            name="tx_status_enum",
        ),
        default="pending",
        index=True,
    )
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Refund tracking
    refund_status: Mapped[str | None] = mapped_column(
        SAEnum("none", "initiated", "completed", "failed", name="refund_status_enum"),
        default="none", nullable=True,
    )
    refund_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    refund_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)

    # Flexible extra data (merchant name, note, etc.)
    metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
