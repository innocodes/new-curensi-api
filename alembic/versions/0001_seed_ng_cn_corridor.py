"""seed NG-CN corridor

Revision ID: 0001
Revises:
Create Date: 2026-05-28
"""
from alembic import op
import uuid

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(f"""
        INSERT INTO corridors (
            id, code, name, is_active,
            source_country, source_currency, collection_provider, supported_methods,
            target_country, target_currency, disbursement_provider, supported_targets,
            fee_type, fee_percentage, fee_flat, min_fee, max_fee,
            min_transaction, max_transaction, daily_limit,
            created_at, updated_at
        ) VALUES (
            '{uuid.uuid4()}', 'NG-CN', 'Nigeria → China', true,
            'NG', 'NGN', 'flutterwave', ARRAY['bank_transfer','card','ussd'],
            'CN', 'CNY', 'lianlian', ARRAY['alipay_qr','wechat_qr'],
            'percentage', 2.00, 0.00, 0.00, NULL,
            5000.00, 5000000.00, 5000000.00,
            now(), now()
        )
        ON CONFLICT (code) DO NOTHING;
    """)


def downgrade() -> None:
    op.execute("DELETE FROM corridors WHERE code = 'NG-CN';")
