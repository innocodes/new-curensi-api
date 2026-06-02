import os
import logging
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
import redis.asyncio as aioredis
from app.core.config import settings
from app.core.database import engine

# ── Always-active routers ────────────────────────────────────────────
from app.api import auth, waitlist, users

# ── Aggregator routers (conditional) ────────────────────────────────
if settings.ENABLE_AGGREGATOR:
    from app.api import ingest, insights, budgets, accounts, financial_transactions, export

if settings.ENABLE_WHATSAPP_BOT:
    from app.api import whatsapp  # Phase 2

if settings.ENABLE_SUBSCRIPTIONS:
    from app.api import subscriptions  # Phase 2

# ── Payment platform routers (preserved, flagged off) ────────────────
if settings.ENABLE_PAYMENTS:
    from app.api import payments, corridors

if settings.ENABLE_PAYMENT_WEBHOOKS:
    from app.api import payment_webhooks

logger = logging.getLogger(__name__)


async def _check_db(retries: int = 5, delay: float = 2.0) -> None:
    """Retry DB check to handle Neon cold-start. Logs failure, never raises."""
    for attempt in range(1, retries + 1):
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            logger.info("✅ Database connection successful")
            return
        except Exception as e:
            logger.warning(f"⚠️  DB check attempt {attempt}/{retries} failed: {e}")
            if attempt < retries:
                await asyncio.sleep(delay)
    logger.error("❌ DB connection failed after retries — requests may fail")


async def _check_redis() -> None:
    """Redis check is non-fatal — caching degrades gracefully without it."""
    try:
        client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        await client.ping()
        await client.aclose()
        logger.info("✅ Redis connection successful")
    except Exception as e:
        logger.error(f"❌ Redis connection failed: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──────────────────────────────────────────────────────
    logger.info(f"PORT: {os.environ.get('PORT', 'NOT SET')}")
    logger.info(f"Environment: {settings.APP_ENV}")
    logger.info(
        f"Feature flags — "
        f"AGGREGATOR={settings.ENABLE_AGGREGATOR} | "
        f"AI_INSIGHTS={settings.ENABLE_AI_INSIGHTS} | "
        f"PAYMENTS={settings.ENABLE_PAYMENTS} | "
        f"WHATSAPP={settings.ENABLE_WHATSAPP_BOT} | "
        f"SUBSCRIPTIONS={settings.ENABLE_SUBSCRIPTIONS}"
    )

    await _check_db()
    await _check_redis()

    yield

    # ── Shutdown ─────────────────────────────────────────────────────
    from app.services.fx_service import close_redis
    await close_redis()
    await engine.dispose()
    logger.info("✅ Shutdown complete")


app = FastAPI(
    title="Curensi AI API",
    description="Financial aggregator + cross-border payment platform",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs" if not settings.is_production else None,
    redoc_url="/redoc" if not settings.is_production else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Always register ───────────────────────────────────────────────────
app.include_router(auth.router,     prefix="/api/v1", tags=["Auth"])
app.include_router(waitlist.router, prefix="/api/v1", tags=["Waitlist"])
app.include_router(users.router,    prefix="/api/v1", tags=["Users"])

# ── Aggregator ────────────────────────────────────────────────────────
if settings.ENABLE_AGGREGATOR:
    app.include_router(ingest.router,                 prefix="/api/v1", tags=["Ingest"])
    app.include_router(insights.router,               prefix="/api/v1", tags=["Insights"])
    app.include_router(budgets.router,                prefix="/api/v1", tags=["Budgets"])
    app.include_router(accounts.router,               prefix="/api/v1", tags=["Accounts"])
    app.include_router(financial_transactions.router, prefix="/api/v1", tags=["Transactions"])
    app.include_router(export.router,                 prefix="/api/v1", tags=["Export"])

if settings.ENABLE_WHATSAPP_BOT:
    app.include_router(whatsapp.router,      prefix="/api/v1", tags=["WhatsApp"])

if settings.ENABLE_SUBSCRIPTIONS:
    app.include_router(subscriptions.router, prefix="/api/v1", tags=["Subscriptions"])

# ── Payment platform (preserved, flagged off) ─────────────────────────
if settings.ENABLE_PAYMENTS:
    app.include_router(payments.router,  prefix="/api/v1", tags=["Payments"])
    app.include_router(corridors.router, prefix="/api/v1", tags=["Corridors"])

if settings.ENABLE_PAYMENT_WEBHOOKS:
    app.include_router(payment_webhooks.router, prefix="/api/v1", tags=["Payment Webhooks"])


@app.get("/health", tags=["Health"])
async def health():
    return {
        "status": "ok",
        "aggregator": settings.ENABLE_AGGREGATOR,
        "payments": settings.ENABLE_PAYMENTS,
    }
