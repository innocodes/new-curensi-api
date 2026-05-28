# CurensiAPI — Python FastAPI Backend

## Stack

- **FastAPI** + Uvicorn + Gunicorn
- **SQLAlchemy 2** (async) + **Alembic** (migrations)
- **PostgreSQL** via **Neon DB** (cloud-hosted, serverless)
- **Redis** — FX rate cache (5 min TTL), Celery broker/backend
- **Celery** — async disbursement, refund, retry, push notification tasks
- **Firebase Admin SDK** — FCM push notifications
- **Pydantic v2** + **pydantic-settings**
- **python-jose** (JWT) + **passlib** (bcrypt)

## Architecture: multi-corridor provider abstraction

Every payment corridor has a **collection provider** and a **disbursement provider**.
Core logic calls provider **interfaces** (`CollectionProvider`, `DisbursementProvider`) — never Flutterwave or LianLian directly. Adding a new corridor = a DB record + optional new provider class.

```
app/
├── core/
│   ├── config.py          # Pydantic Settings from env
│   ├── database.py        # SQLAlchemy engine + Base + session
│   ├── security.py        # JWT, bcrypt
│   ├── deps.py            # FastAPI dependencies (get_db, get_current_user)
│   └── providers/
│       ├── base.py        # CollectionProvider + DisbursementProvider ABCs
│       ├── registry.py    # Maps provider name → instance
│       ├── flutterwave.py # Flutterwave implementation
│       └── lianlian.py    # LianLian implementation
├── api/
│   ├── auth.py            # register, login, refresh, /me, fcm-token
│   ├── payments.py        # /rate, /initiate, /{id}/status
│   ├── transactions.py    # list, detail
│   ├── corridors.py       # list active corridors
│   └── webhooks.py        # Flutterwave + LianLian callbacks
├── services/
│   ├── payment_service.py # Core payment orchestration
│   ├── fx_service.py      # Rate fetch + Redis cache
│   └── notification_service.py  # FCM push
├── tasks/
│   ├── celery_app.py      # Celery config
│   ├── disbursement.py    # CNY disbursement task (max 3 retries)
│   ├── refund.py          # Refund task (max 3 retries)
│   └── notifications.py  # Async push notification task
└── models/
    ├── user.py
    ├── corridor.py        # Corridor config (DB-driven, not hardcoded)
    ├── transaction.py     # Full source+target+collection+disbursement tracking
    └── audit_log.py       # Immutable event log
```

## Transaction lifecycle

```
pending → collection_initiated → collection_confirmed
       → disbursement_initiated → disbursement_processing → completed
                                                          ↘ failed → refund_initiated → refunded
```

## Active corridors (seeded in migration 0001)

| Code  | Source | Collection  | Target | Disbursement | Fee | Min     | Max       |
|-------|--------|-------------|--------|--------------|-----|---------|-----------|
| NG-CN | NGN    | Flutterwave | CNY    | LianLian     | 2%  | ₦5,000  | ₦5,000,000|

## Running locally

```bash
cp .env.example .env   # fill in your Neon DB URL and provider keys
docker compose up      # starts api, worker, beat, flower, redis
```

## Migrations

```bash
# Generate migration after model changes
alembic revision --autogenerate -m "describe change"

# Apply migrations (uses DATABASE_URL_SYNC — psycopg2, not asyncpg)
alembic upgrade head
```

## Deploying to Railway

1. Push repo to GitHub
2. New Railway project → "Deploy from GitHub repo"
3. Add env vars from `.env.example` in Railway dashboard
4. Railway auto-detects `Dockerfile` and `railway.toml`
5. Add a Redis service in Railway (set `REDIS_URL` to the internal URL)
6. Add a second service for the Celery worker with start command:
   `celery -A app.tasks.celery_app worker --loglevel=info`

## Key conventions

- Never call Flutterwave or LianLian directly from API routes — always through the provider interface via `registry.py`
- FX rate is locked at `initiate_transaction` time and stored on the transaction — never recalculated at disbursement
- All webhook handlers check idempotency before processing
- Wallet model is intentionally omitted from v1 — add as optional Phase 2 feature
