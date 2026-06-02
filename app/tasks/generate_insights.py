import asyncio
import logging
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="tasks.refresh_user_insights")
def refresh_user_insights(user_id: str):
    """
    Refresh cached insights for a user (Pro and Business tiers only).
    Scheduled via Celery Beat: daily at 6am for eligible users.
    Free tier users get insights on-demand only.
    """
    asyncio.run(_refresh_async(user_id))


async def _refresh_async(user_id: str):
    from app.core.database import AsyncSessionLocal
    from app.models.subscription import Subscription, SubscriptionTier
    from app.services.insights_service import generate_insights_feed, generate_cash_flow_forecast
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Subscription).where(
                Subscription.user_id == user_id,
                Subscription.status == "active",
            )
        )
        sub = result.scalar_one_or_none()
        tier = sub.tier if sub else SubscriptionTier.FREE

        # Only run scheduled refresh for paying users
        if tier == SubscriptionTier.FREE:
            return

        try:
            # Refresh insights (this also updates Redis cache)
            await generate_insights_feed(user_id, db)
            # Refresh forecast cache
            await generate_cash_flow_forecast(user_id, db)
            logger.info(f"Insights refreshed for user {user_id} ({tier.value})")
        except Exception as e:
            logger.error(f"Insight refresh failed for {user_id}: {e}")
