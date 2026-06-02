from decimal import Decimal
from datetime import datetime, timezone
import redis.asyncio as aioredis
from app.core.providers.base import CollectionProvider
from app.core.config import settings

RATE_CACHE_TTL = 300  # 5 minutes

_redis: aioredis.Redis | None = None


def _get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis


async def get_fx_rate(
    source_currency: str,
    target_currency: str,
    provider: CollectionProvider,
) -> Decimal:
    """
    Returns the live FX rate from Redis cache if fresh, otherwise fetches
    from the collection provider and caches the result for 5 minutes.

    The rate stored in cache and on each transaction is the exact rate used —
    it is never recalculated at disbursement time.
    """
    cache_key = f"fx_rate:{source_currency}:{target_currency}"

    cached = await _get_redis().get(cache_key)
    if cached:
        return Decimal(cached)

    rate = await provider.get_fx_rate(source_currency, target_currency)
    await _get_redis().setex(cache_key, RATE_CACHE_TTL, str(rate))
    return rate


def calculate_fee(source_amount: Decimal, fee_percentage: Decimal, fee_flat: Decimal,
                  min_fee: Decimal, max_fee: Decimal | None) -> Decimal:
    pct_fee = (source_amount * fee_percentage / Decimal("100")).quantize(Decimal("0.01"))
    fee = pct_fee + fee_flat
    fee = max(fee, min_fee)
    if max_fee is not None:
        fee = min(fee, max_fee)
    return fee


async def close_redis() -> None:
    """Close the shared Redis client on shutdown."""
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None


def get_rate_response(rate: Decimal, fee_pct: Decimal) -> dict:
    return {
        "cny_per_ngn": rate,
        "ngn_per_cny": (Decimal("1") / rate).quantize(Decimal("0.01")),
        "fee_pct": fee_pct,
        "fetched_at": datetime.now(timezone.utc),
    }
