import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class AuditLog(Base):
    """
    Immutable record of every state change on every transaction.
    Rows are never updated or deleted — only inserted.
    """
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    transaction_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("transactions.id"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    event: Mapped[str] = mapped_column(String(100))   # e.g. "collection_confirmed"
    provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # raw provider response
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
