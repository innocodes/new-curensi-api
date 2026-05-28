from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api import auth, payments, transactions, corridors, webhooks, waitlist

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
