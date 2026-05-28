# Import all models so Alembic autogenerate picks them up
from app.models.user import User
from app.models.corridor import Corridor
from app.models.transaction import Transaction
from app.models.audit_log import AuditLog
from app.models.waitlist import WaitlistEntry

__all__ = ["User", "Corridor", "Transaction", "AuditLog", "WaitlistEntry"]
