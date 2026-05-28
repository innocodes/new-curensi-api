"""add waitlist table

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-28
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "waitlist",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("phone", sa.String(30), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_waitlist"),
    )
    op.create_index("ix_waitlist_email",      "waitlist", ["email"],      unique=True)
    op.create_index("ix_waitlist_created_at", "waitlist", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_waitlist_created_at", table_name="waitlist")
    op.drop_index("ix_waitlist_email",      table_name="waitlist")
    op.drop_table("waitlist")
