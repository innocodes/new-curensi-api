# Import all models so Alembic autogenerate picks them up.
# ── Shared ──────────────────────────────────────────────────────────────────
from app.models.user import User
from app.models.waitlist import WaitlistEntry
from app.models.audit_log import AuditLog

# ── Aggregator ───────────────────────────────────────────────────────────────
from app.models.bank_account import BankAccount
from app.models.ingestion import IngestionBatch, IngestionStatus, IngestionSource
from app.models.financial_transaction import FinancialTransaction, UserMode
from app.models.budget import Budget
from app.models.subscription import Subscription, SubscriptionTier

# ── Payment platform (preserved) ────────────────────────────────────────────
from app.models.transaction import Transaction
from app.models.corridor import Corridor

__all__ = [
    # Shared
    "User", "WaitlistEntry", "AuditLog",
    # Aggregator
    "BankAccount",
    "IngestionBatch", "IngestionStatus", "IngestionSource",
    "FinancialTransaction", "UserMode",
    "Budget",
    "Subscription", "SubscriptionTier",
    # Payment platform
    "Transaction", "Corridor",
]
