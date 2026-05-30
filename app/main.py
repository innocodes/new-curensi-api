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
from app.api import auth, payments, transactions, corridors, webhooks, waitlist

logger = logging.getLogger(__name__)


async def _check_db(retries: int = 5, delay: float = 2.0) -> None:
    """
    Retry DB check to handle Neon cold-start latency.
    Logs failure but never raises — app stays up regardless.
    """
    for attempt in range(1, retries + 1):
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            logger.info("✅ Database connection successful")
            return
        except Exception as e:
            logger.warning(
                f"⚠️ DB check attempt {attempt}/{retries} failed: {e}"
            )
            if attempt < retries:
                await asyncio.sleep(delay)

    # All retries exhausted — log but do NOT raise
    # App stays up; individual requests will surface real DB errors
    logger.error(
        "❌ Database connection failed after all retries — "
        "app will continue but DB requests may fail"
    )


async def _check_redis() -> None:
    """
    Redis check is non-fatal — app works without Redis for non-cached paths.
    """
    try:
        client = aioredis.from_url(
            settings.REDIS_URL,
            decode_responses=True      # encoding param removed — deprecated in redis-py 5.x
        )
        await client.ping()
        await client.aclose()
        logger.info("✅ Redis connection successful")
    except Exception as e:
        # Non-fatal — log and continue
        logger.error(f"❌ Redis connection failed: {e} — caching and tasks may be affected")


# ✅ lifespan replaces deprecated @app.on_event
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info(f"PORT: {os.environ.get('PORT', 'NOT SET')}")
    logger.info(f"Environment: {settings.APP_ENV}")
    logger.info(f"DB: {settings.async_database_url[:40]}...")
    logger.info(f"Redis: {settings.REDIS_URL[:30]}...")

    await _check_db()
    await _check_redis()

    yield  # App runs here

    # Shutdown
    await engine.dispose()
    logger.info("✅ Engine disposed cleanly")


app = FastAPI(
    title="Curensi API",
    description="Cross-border merchant payment platform — multi-corridor system",
    version="1.0.0",
    lifespan=lifespan,                  # ✅ replaces deprecated on_event
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

app.include_router(auth.router,         prefix="/api/v1")
app.include_router(payments.router,     prefix="/api/v1")
app.include_router(transactions.router, prefix="/api/v1")
app.include_router(corridors.router,    prefix="/api/v1")
app.include_router(webhooks.router,     prefix="/api/v1")
app.include_router(waitlist.router,     prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok"}