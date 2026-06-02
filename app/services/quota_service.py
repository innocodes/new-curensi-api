from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.subscription import Subscription, SubscriptionTier
from app.models.ingestion import IngestionBatch, IngestionSource, IngestionStatus


class QuotaExceededException(Exception):
    def __init__(self, message: str, upgrade_message: str = ""):
        super().__init__(message)
        self.upgrade_message = upgrade_message or message


TIER_QUOTAS: dict[SubscriptionTier, dict] = {
    SubscriptionTier.FREE: {
        "ai_scans_per_month":    3,
        "pdf_uploads_per_month": 1,
        "whatsapp_bot":          False,
        "ai_insights":           False,
        "export":                False,
        "dual_ledger":           False,
        "tax_vault":             False,
    },
    SubscriptionTier.PRO: {
        "ai_scans_per_month":    -1,   # unlimited
        "pdf_uploads_per_month": 5,
        "whatsapp_bot":          True,
        "ai_insights":           True,
        "export":                True,
        "dual_ledger":           False,
        "tax_vault":             False,
    },
    SubscriptionTier.BUSINESS: {
        "ai_scans_per_month":    -1,
        "pdf_uploads_per_month": -1,
        "whatsapp_bot":          True,
        "ai_insights":           True,
        "export":                True,
        "dual_ledger":           True,
        "tax_vault":             True,
    },
}


async def _get_user_tier(user_id: str, db: AsyncSession) -> SubscriptionTier:
    result = await db.execute(
        select(Subscription).where(
            Subscription.user_id == user_id,
            Subscription.status == "active",
        )
    )
    sub = result.scalar_one_or_none()
    return sub.tier if sub else SubscriptionTier.FREE


def _month_start() -> datetime:
    now = datetime.now(timezone.utc)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


async def count_pdf_uploads_this_month(user_id: str, db: AsyncSession) -> int:
    result = await db.execute(
        select(func.count()).select_from(IngestionBatch).where(
            IngestionBatch.user_id == user_id,
            IngestionBatch.source == IngestionSource.PDF_STATEMENT,
            IngestionBatch.created_at >= _month_start(),
        )
    )
    return result.scalar_one()


async def count_ai_scans_this_month(user_id: str, db: AsyncSession) -> int:
    result = await db.execute(
        select(func.count()).select_from(IngestionBatch).where(
            IngestionBatch.user_id == user_id,
            IngestionBatch.source.in_([IngestionSource.RECEIPT_SCAN, IngestionSource.SCREENSHOT]),
            IngestionBatch.created_at >= _month_start(),
        )
    )
    return result.scalar_one()


async def check_quota(user_id: str, feature: str, db: AsyncSession) -> bool:
    """
    Returns True if the user is within quota for the given feature.
    Raises QuotaExceededException if the limit has been reached.
    """
    tier = await _get_user_tier(user_id, db)
    quota = TIER_QUOTAS[tier]

    if feature == "pdf_upload":
        limit = quota["pdf_uploads_per_month"]
        if limit == -1:
            return True
        used = await count_pdf_uploads_this_month(user_id, db)
        if used >= limit:
            raise QuotaExceededException(
                f"PDF upload limit reached ({limit}/month on {tier.value} plan).",
                upgrade_message="Upgrade to Pro for 5 uploads/month, or Business for unlimited.",
            )

    elif feature == "ai_scan":
        limit = quota["ai_scans_per_month"]
        if limit == -1:
            return True
        used = await count_ai_scans_this_month(user_id, db)
        if used >= limit:
            raise QuotaExceededException(
                f"AI scan limit reached ({limit}/month on {tier.value} plan).",
                upgrade_message="Upgrade to Pro for unlimited AI scans.",
            )

    elif feature in quota:
        if not quota[feature]:
            raise QuotaExceededException(
                f"'{feature}' is not available on the {tier.value} plan.",
                upgrade_message="Upgrade your subscription to access this feature.",
            )

    return True
