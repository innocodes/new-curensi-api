import json
import logging
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import anthropic
import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from app.core.config import settings
from app.models.financial_transaction import FinancialTransaction
from app.schemas.insight import InsightCard

logger = logging.getLogger(__name__)

client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

INSIGHTS_CACHE_TTL   = 3600        # 1 hour
SUMMARY_CACHE_TTL    = 21_600      # 6 hours
FORECAST_CACHE_TTL   = 86_400      # 24 hours

_redis: aioredis.Redis | None = None


def _get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis


async def _get_recent_transactions(user_id: str, days: int, db: AsyncSession) -> list[dict]:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    result = await db.execute(
        select(FinancialTransaction).where(
            FinancialTransaction.user_id == user_id,
            FinancialTransaction.created_at >= since,
            FinancialTransaction.is_deleted.is_(False),
        ).order_by(FinancialTransaction.created_at.desc()).limit(200)
    )
    txs = result.scalars().all()
    return [
        {
            "date": t.date,
            "description": t.description,
            "amount": float(t.amount),
            "type": t.transaction_type,
            "category": t.category,
        }
        for t in txs
    ]


async def generate_insights_feed(user_id: str, db: AsyncSession) -> list[InsightCard]:
    """
    Generate AI-powered insight cards for the user.
    Uses Claude Haiku. Cached in Redis for 1 hour.
    """
    cache_key = f"insights:{user_id}"
    try:
        cached = await _get_redis().get(cache_key)
        if cached:
            data = json.loads(cached)
            return [InsightCard(**item) for item in data]
    except Exception:
        pass

    txs = await _get_recent_transactions(user_id, 30, db)
    if not txs:
        return []

    prompt = f"""
You are a financial advisor AI. Analyse these transactions from the last 30 days and
return 3-5 actionable insight cards as a JSON array.

Transactions:
{json.dumps(txs, indent=2)}

Return ONLY a JSON array, no markdown:
[
  {{
    "title": "short title",
    "body": "1-2 sentences of actionable insight",
    "severity": "info" | "warning" | "success",
    "category": "category name or null",
    "amount": number or null
  }}
]
"""

    response = await client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}]
    )
    raw = response.content[0].text.strip()

    try:
        data = json.loads(raw)
        cards = [InsightCard(**item) for item in data]
        await _get_redis().setex(cache_key, INSIGHTS_CACHE_TTL, json.dumps([c.model_dump() for c in cards]))
        return cards
    except Exception as e:
        logger.warning(f"Insights parse failed: {e}")
        return []


async def generate_affordability_answer(user_id: str, question: str, db: AsyncSession) -> dict:
    """
    Answer a specific affordability question using last 90 days of transactions.
    Uses Claude Haiku. Not cached — answers are question-specific.
    """
    txs = await _get_recent_transactions(user_id, 90, db)

    prompt = f"""
You are a personal finance assistant. Based on the user's last 90 days of financial data,
answer their question clearly and concisely. Be specific where possible.

Financial data:
{json.dumps(txs[:100], indent=2)}

User's question: {question}

Return ONLY a JSON object:
{{
  "answer": "your answer here",
  "data_points": ["specific fact 1", "specific fact 2"]
}}
"""

    response = await client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}]
    )
    raw = response.content[0].text.strip()

    try:
        return json.loads(raw)
    except Exception:
        return {"answer": response.content[0].text.strip(), "data_points": []}


async def get_spending_summary(user_id: str, period: str, db: AsyncSession) -> dict:
    """
    Pure DB aggregation — no LLM call. Cached in Redis for 6 hours.
    period: this_month | last_3_months | last_6_months
    """
    cache_key = f"summary:{user_id}:{period}"
    try:
        cached = await _get_redis().get(cache_key)
        if cached:
            return json.loads(cached)
    except Exception:
        pass

    days_map = {"this_month": 30, "last_3_months": 90, "last_6_months": 180}
    days = days_map.get(period, 30)
    since = datetime.now(timezone.utc) - timedelta(days=days)

    result = await db.execute(
        select(
            FinancialTransaction.transaction_type,
            FinancialTransaction.category,
            func.sum(FinancialTransaction.amount).label("total"),
            func.count().label("count"),
        ).where(
            FinancialTransaction.user_id == user_id,
            FinancialTransaction.created_at >= since,
            FinancialTransaction.is_deleted.is_(False),
        ).group_by(
            FinancialTransaction.transaction_type,
            FinancialTransaction.category,
        )
    )
    rows = result.all()

    total_in  = sum(float(r.total) for r in rows if r.transaction_type == "credit")
    total_out = sum(float(r.total) for r in rows if r.transaction_type == "debit")
    by_category = {}
    for r in rows:
        if r.transaction_type == "debit":
            cat = r.category or "Uncategorised"
            by_category[cat] = by_category.get(cat, 0) + float(r.total)

    summary = {
        "period": period,
        "total_income": total_in,
        "total_spending": total_out,
        "net": total_in - total_out,
        "by_category": dict(sorted(by_category.items(), key=lambda x: x[1], reverse=True)),
    }

    try:
        await _get_redis().setex(cache_key, SUMMARY_CACHE_TTL, json.dumps(summary))
    except Exception:
        pass

    return summary


async def generate_cash_flow_forecast(user_id: str, db: AsyncSession) -> dict:
    """
    30-day cash flow forecast using Claude Haiku.
    Cached in Redis for 24 hours.
    """
    cache_key = f"forecast:{user_id}"
    try:
        cached = await _get_redis().get(cache_key)
        if cached:
            return json.loads(cached)
    except Exception:
        pass

    txs = await _get_recent_transactions(user_id, 90, db)
    if not txs:
        return {"forecast": [], "summary": "Not enough data for a forecast yet."}

    prompt = f"""
You are a financial forecasting AI. Based on 90 days of transaction history,
predict the user's cash flow for the next 30 days.

Historical transactions:
{json.dumps(txs[:150], indent=2)}

Return ONLY a JSON object:
{{
  "predicted_income": number,
  "predicted_spending": number,
  "predicted_net": number,
  "confidence": "low" | "medium" | "high",
  "summary": "1-2 sentence plain-language summary",
  "alerts": ["alert 1 if any", "alert 2 if any"]
}}
"""

    response = await client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}]
    )
    raw = response.content[0].text.strip()

    try:
        result = json.loads(raw)
        await _get_redis().setex(cache_key, FORECAST_CACHE_TTL, json.dumps(result))
        return result
    except Exception as e:
        logger.warning(f"Forecast parse failed: {e}")
        return {"summary": "Forecast unavailable at this time.", "alerts": []}


async def invalidate_user_caches(user_id: str) -> None:
    """Invalidate all cached insights/summaries when new transactions arrive."""
    try:
        redis = _get_redis()
        keys = [
            f"insights:{user_id}",
            f"summary:{user_id}:this_month",
            f"summary:{user_id}:last_3_months",
            f"summary:{user_id}:last_6_months",
            f"forecast:{user_id}",
        ]
        await redis.delete(*keys)
    except Exception:
        pass
