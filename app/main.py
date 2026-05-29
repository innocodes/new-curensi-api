import os
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from app.core.config import settings
from app.core.database import engine
from app.api import auth, payments, transactions, corridors, webhooks, waitlist

logger = logging.getLogger(__name__)

# App initialized first — before any decorators reference it
app = FastAPI(
    title="Curensi API",
    description="Cross-border merchant payment platform — multi-corridor system",
    version="1.0.0",
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


# Startup event defined AFTER app exists
@app.on_event("startup")
async def startup_event():

    logger.info(f"Starting on PORT: {os.environ.get('PORT', 'NOT SET')}")
    logger.info(f"Environment: {settings.APP_ENV}")
    logger.info(f"DB URL prefix: {settings.async_database_url[:40]}...")
    logger.info(f"Redis URL prefix: {settings.REDIS_URL[:30]}...")

    # Test DB connection
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("Database connection successful")
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        raise

    # Test Redis connection using redis.asyncio
    try:
        import redis.asyncio as aioredis
        redis_client = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True
        )
        await redis_client.ping()
        await redis_client.aclose()
        logger.info("Redis connection successful")
    except Exception as e:
        logger.error(f"Redis connection failed: {e}")
        raise


@app.on_event("shutdown")
async def shutdown_event():
    await engine.dispose()
    logger.info("Database engine disposed cleanly")