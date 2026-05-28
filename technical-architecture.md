# Technical Architecture Document
## Cross-Border Merchant Payment Platform
### Multi-Corridor Design — v1.0

---

## 1. Product Overview

A mobile-first cross-border payment platform that enables users in emerging markets to pay merchants on platforms like Alipay that would otherwise be inaccessible to them. The platform collects local currency from the user, converts at a live FX rate, and disburses the target currency to the submitted payment destination (e.g. Alipay QR code) via licensed payment partners.

**Initial Corridor:** Nigeria (NGN) → China (CNY) via Alipay
**Architecture Philosophy:** Corridor-agnostic from day one — adding new corridors requires configuration, not code rewrites.

---

## 2. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Mobile App                           │
│                  (React Native CLI)                         │
└─────────────────────────┬───────────────────────────────────┘
                          │ HTTPS / REST
┌─────────────────────────▼───────────────────────────────────┐
│                      API Gateway                            │
│              (FastAPI + Uvicorn + Gunicorn)                  │
│                                                             │
│   ┌─────────┐  ┌──────────┐  ┌──────────┐  ┌───────────┐  │
│   │  Auth   │  │Payments  │  │Webhooks  │  │  Users    │  │
│   │  API    │  │  API     │  │  API     │  │  API      │  │
│   └─────────┘  └──────────┘  └──────────┘  └───────────┘  │
└──────────┬──────────────┬──────────────┬────────────────────┘
           │              │              │
┌──────────▼──────┐ ┌─────▼──────┐ ┌────▼──────────────────┐
│  Provider Layer │ │  Task Queue│ │      Data Layer        │
│  (Abstracted)   │ │  (Celery + │ │  (PostgreSQL + Redis)  │
│                 │ │   Redis)   │ │                        │
│ - Flutterwave   │ │            │ │  - Transactions        │
│ - LianLian      │ │ - Disburse │ │  - Users / KYC         │
│ - M-Pesa (fut.) │ │ - Notify   │ │  - Corridors Config    │
│ - Airwallex     │ │ - Retry    │ │  - FX Rates Cache      │
│   (fut.)        │ │            │ │  - Audit Logs          │
└─────────────────┘ └────────────┘ └────────────────────────┘
```

---

## 3. Tech Stack

| Layer | Technology | Rationale |
|---|---|---|
| **Mobile** | React Native CLI | Full native access for security modules, camera, biometrics |
| **API Framework** | FastAPI | Async-native, auto docs, fast, Pydantic validation |
| **App Server** | Uvicorn + Gunicorn | Production-grade async WSGI |
| **Database** | PostgreSQL | ACID-compliant, essential for financial data integrity |
| **ORM** | SQLAlchemy + Alembic | DB modelling + schema migrations |
| **Task Queue** | Celery + Redis | Async disbursement, retries, notifications |
| **Cache** | Redis | FX rate caching, idempotency key storage |
| **Authentication** | JWT (python-jose) | Stateless user session management |
| **Push Notifications** | Firebase FCM | Payment status alerts to mobile |
| **Config Management** | Pydantic Settings | Secrets and environment variable handling |
| **Collection Provider (NG)** | Flutterwave | CBN-licensed NGN collection |
| **Disbursement Provider (CN)** | LianLian Global | PBOC-licensed CNY/Alipay disbursement |

---

## 4. Multi-Corridor Architecture

### 4.1 Core Design Principle

Every corridor consists of two components:
- **Collection Provider** — collects local currency from the user
- **Disbursement Provider** — delivers target currency to the merchant

These are abstracted behind provider interfaces. The platform's core logic never calls Flutterwave or LianLian directly — it calls the interface, and the interface determines which provider to use based on the corridor.

---

### 4.2 Provider Interface Definitions

```python
# core/providers/base.py

from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Optional

class CollectionProvider(ABC):
    """
    Abstract interface for all NGN/local currency collection providers.
    Every collection integration (Flutterwave, M-Pesa, etc.) must implement this.
    """

    @abstractmethod
    async def initiate_payment(
        self,
        amount: Decimal,
        currency: str,
        user_id: str,
        transaction_ref: str,
        payment_method: str,  # bank_transfer | card | ussd | mobile_money
        metadata: dict
    ) -> dict:
        """Initiate a payment collection. Returns provider reference and payment instructions."""
        pass

    @abstractmethod
    async def verify_payment(
        self,
        provider_reference: str,
        transaction_ref: str
    ) -> dict:
        """Verify a payment's status. Returns status and amount confirmed."""
        pass

    @abstractmethod
    async def initiate_refund(
        self,
        provider_reference: str,
        amount: Decimal,
        reason: str
    ) -> dict:
        """Initiate a refund for a failed or disputed transaction."""
        pass

    @abstractmethod
    async def get_fx_rate(
        self,
        source_currency: str,
        target_currency: str
    ) -> Decimal:
        """Fetch live FX rate for a currency pair."""
        pass


class DisbursementProvider(ABC):
    """
    Abstract interface for all CNY/target currency disbursement providers.
    Every disbursement integration (LianLian, Airwallex, etc.) must implement this.
    """

    @abstractmethod
    async def pay_qr(
        self,
        qr_code: str,
        amount: Decimal,
        currency: str,
        transaction_ref: str,
        metadata: dict
    ) -> dict:
        """Submit payment to a QR code. Returns disbursement reference."""
        pass

    @abstractmethod
    async def check_status(
        self,
        disbursement_reference: str
    ) -> dict:
        """Check the status of a disbursement."""
        pass

    @abstractmethod
    async def supported_payment_types(self) -> list:
        """Return list of supported payment types (alipay_qr, wechat_qr, etc.)"""
        pass
```

---

### 4.3 Provider Implementations

```python
# core/providers/flutterwave.py

class FlutterwaveProvider(CollectionProvider):
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.flutterwave.com/v3"

    async def initiate_payment(self, amount, currency, user_id,
                                transaction_ref, payment_method, metadata):
        # Flutterwave-specific implementation
        ...

    async def verify_payment(self, provider_reference, transaction_ref):
        # Verify via Flutterwave's transaction verify endpoint
        ...

    async def initiate_refund(self, provider_reference, amount, reason):
        # Call Flutterwave's refund endpoint
        ...

    async def get_fx_rate(self, source_currency, target_currency):
        # Call Flutterwave's real-time FX conversion endpoint
        ...


# core/providers/lianlian.py

class LianLianProvider(DisbursementProvider):
    def __init__(self, api_key: str, merchant_id: str):
        self.api_key = api_key
        self.merchant_id = merchant_id
        self.base_url = "https://api.lianlianglobal.com"

    async def pay_qr(self, qr_code, amount, currency,
                     transaction_ref, metadata):
        # LianLian Outbound Bill API implementation
        ...

    async def check_status(self, disbursement_reference):
        # Check disbursement status via LianLian
        ...

    async def supported_payment_types(self):
        return ["alipay_qr", "wechat_qr"]


# Future providers (same interface, different implementation)
# class MpesaProvider(CollectionProvider): ...
# class AirwallexProvider(DisbursementProvider): ...
# class PayPayProvider(DisbursementProvider): ...
```

---

### 4.4 Corridor Configuration

Corridors are stored in the database — not hardcoded. Adding a new corridor is a database entry, not a deployment.

```python
# models/corridor.py

class Corridor(Base):
    __tablename__ = "corridors"

    id                    = Column(UUID, primary_key=True)
    code                  = Column(String, unique=True)  # e.g. "NG-CN"
    name                  = Column(String)               # "Nigeria → China"
    is_active             = Column(Boolean, default=False)

    # Source (collection) side
    source_country        = Column(String)               # "NG"
    source_currency       = Column(String)               # "NGN"
    collection_provider   = Column(String)               # "flutterwave"
    supported_methods     = Column(ARRAY(String))        # ["bank_transfer", "card", "ussd"]

    # Target (disbursement) side
    target_country        = Column(String)               # "CN"
    target_currency       = Column(String)               # "CNY"
    disbursement_provider = Column(String)               # "lianlian"
    supported_targets     = Column(ARRAY(String))        # ["alipay_qr", "wechat_qr"]

    # Fee structure
    fee_type              = Column(String)               # "percentage" | "flat" | "hybrid"
    fee_percentage        = Column(Numeric)              # 2.00
    fee_flat              = Column(Numeric)              # 0.00
    min_fee               = Column(Numeric)              # minimum fee floor
    max_fee               = Column(Numeric)              # maximum fee cap

    # Transaction limits
    min_transaction       = Column(Numeric)              # 5000.00 (NGN)
    max_transaction       = Column(Numeric)              # 5000000.00 (NGN)
    daily_limit           = Column(Numeric)              # per user daily cap

    created_at            = Column(DateTime)
    updated_at            = Column(DateTime)
```

**Corridor Table (Initial Data):**

| Code | Source | Collection | Target | Disbursement | Fee | Min | Max |
|---|---|---|---|---|---|---|---|
| NG-CN | NGN | Flutterwave | CNY | LianLian | 2% | ₦5,000 | ₦5,000,000 |
| GH-CN | GHS | Flutterwave | CNY | LianLian | 2% | GHS 100 | GHS 50,000 |
| KE-CN | KES | M-Pesa | CNY | LianLian | 2.5% | KES 500 | KES 500,000 |
| NG-JP | NGN | Flutterwave | JPY | Airwallex | 2.5% | ₦5,000 | ₦2,000,000 |

---

### 4.5 Provider Registry

```python
# core/providers/registry.py

from core.providers.flutterwave import FlutterwaveProvider
from core.providers.lianlian import LianLianProvider
from core.config import settings

# Registry maps provider name (stored in DB) to instantiated provider
COLLECTION_PROVIDERS = {
    "flutterwave": FlutterwaveProvider(api_key=settings.FLUTTERWAVE_SECRET_KEY),
    # "mpesa": MpesaProvider(consumer_key=settings.MPESA_CONSUMER_KEY),
}

DISBURSEMENT_PROVIDERS = {
    "lianlian": LianLianProvider(
        api_key=settings.LIANLIAN_API_KEY,
        merchant_id=settings.LIANLIAN_MERCHANT_ID
    ),
    # "airwallex": AirwallexProvider(client_id=settings.AIRWALLEX_CLIENT_ID),
}

def get_collection_provider(provider_name: str) -> CollectionProvider:
    provider = COLLECTION_PROVIDERS.get(provider_name)
    if not provider:
        raise ValueError(f"Collection provider '{provider_name}' not found")
    return provider

def get_disbursement_provider(provider_name: str) -> DisbursementProvider:
    provider = DISBURSEMENT_PROVIDERS.get(provider_name)
    if not provider:
        raise ValueError(f"Disbursement provider '{provider_name}' not found")
    return provider
```

---

## 5. Database Schema

### 5.1 Core Models

```python
# models/transaction.py

class Transaction(Base):
    __tablename__ = "transactions"

    id                       = Column(UUID, primary_key=True, default=uuid4)
    user_id                  = Column(UUID, ForeignKey("users.id"))
    corridor_id              = Column(UUID, ForeignKey("corridors.id"))

    # Source (collection) side
    source_currency          = Column(String)       # "NGN"
    source_amount            = Column(Numeric)      # 52000.00
    collection_provider      = Column(String)       # "flutterwave"
    collection_reference     = Column(String)       # Flutterwave tx ref
    collection_method        = Column(String)       # "bank_transfer"
    collection_status        = Column(String)       # pending|confirmed|failed

    # FX
    fx_rate                  = Column(Numeric)      # 0.0052 (NGN/CNY)
    fx_rate_timestamp        = Column(DateTime)     # when rate was fetched
    platform_fee             = Column(Numeric)      # 1040.00 NGN
    fee_percentage           = Column(Numeric)      # 2.00

    # Target (disbursement) side
    target_currency          = Column(String)       # "CNY"
    target_amount            = Column(Numeric)      # 265.00
    disbursement_provider    = Column(String)       # "lianlian"
    disbursement_reference   = Column(String)       # LianLian ref
    disbursement_target_type = Column(String)       # "alipay_qr"
    disbursement_target_data = Column(Text)         # QR code data
    disbursement_status      = Column(String)       # pending|processing|completed|failed

    # Overall status
    status                   = Column(String)       # pending|processing|completed|failed|refunded
    failure_reason           = Column(Text)
    idempotency_key          = Column(String, unique=True)  # prevents double processing

    # Refund tracking
    refund_status            = Column(String)       # none|initiated|completed|failed
    refund_reference         = Column(String)
    refund_amount            = Column(Numeric)

    # Metadata
    metadata                 = Column(JSONB)        # flexible extra data
    created_at               = Column(DateTime, default=datetime.utcnow)
    updated_at               = Column(DateTime, onupdate=datetime.utcnow)
    completed_at             = Column(DateTime)


# models/user.py

class User(Base):
    __tablename__ = "users"

    id               = Column(UUID, primary_key=True, default=uuid4)
    full_name        = Column(String)
    email            = Column(String, unique=True)
    phone            = Column(String, unique=True)
    country          = Column(String)          # "NG", "GH", "KE"
    password_hash    = Column(String)
    is_active        = Column(Boolean, default=True)
    is_verified      = Column(Boolean, default=False)
    kyc_status       = Column(String)          # pending|verified|failed
    wallet_balance   = Column(Numeric, default=0)
    wallet_currency  = Column(String)          # "NGN"
    created_at       = Column(DateTime)


# models/audit_log.py

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id               = Column(UUID, primary_key=True)
    transaction_id   = Column(UUID, ForeignKey("transactions.id"))
    user_id          = Column(UUID, ForeignKey("users.id"))
    event            = Column(String)          # "collection_confirmed", "disbursement_initiated" etc.
    provider         = Column(String)
    payload          = Column(JSONB)           # raw provider response
    created_at       = Column(DateTime)
```

---

## 6. Core Payment Flow

### 6.1 Transaction Lifecycle

```
PENDING
   │
   ▼
COLLECTION_INITIATED  ──── (Flutterwave payment link/VA generated)
   │
   ▼
COLLECTION_CONFIRMED  ──── (Webhook received from Flutterwave)
   │
   ▼
DISBURSEMENT_INITIATED ─── (Celery task fires LianLian API call)
   │
   ├──► DISBURSEMENT_PROCESSING (LianLian processing)
   │           │
   │           ▼
   │    COMPLETED ──────────── (Success — notify user)
   │
   └──► DISBURSEMENT_FAILED
               │
               ├──► RETRY (up to 3 times via Celery)
               │
               └──► REFUND_INITIATED ── REFUND_COMPLETED
```

---

### 6.2 Payment Service

```python
# services/payment_service.py

class PaymentService:

    async def initiate_transaction(
        self,
        user_id: str,
        corridor_code: str,
        target_amount: Decimal,
        target_type: str,
        target_data: str,           # Alipay QR code
        payment_method: str,
        db: AsyncSession
    ) -> dict:

        # 1. Load corridor config from DB
        corridor = await get_corridor(corridor_code, db)

        # 2. Fetch live FX rate
        collection_provider = get_collection_provider(corridor.collection_provider)
        fx_rate = await collection_provider.get_fx_rate(
            corridor.source_currency,
            corridor.target_currency
        )

        # 3. Calculate amounts and fees
        source_amount = target_amount / fx_rate
        platform_fee = self.calculate_fee(source_amount, corridor)
        total_to_collect = source_amount + platform_fee

        # 4. Create transaction record
        transaction = Transaction(
            user_id=user_id,
            corridor_id=corridor.id,
            source_currency=corridor.source_currency,
            source_amount=total_to_collect,
            target_currency=corridor.target_currency,
            target_amount=target_amount,
            fx_rate=fx_rate,
            fx_rate_timestamp=datetime.utcnow(),
            platform_fee=platform_fee,
            collection_provider=corridor.collection_provider,
            collection_method=payment_method,
            disbursement_provider=corridor.disbursement_provider,
            disbursement_target_type=target_type,
            disbursement_target_data=target_data,
            status="pending",
            idempotency_key=f"{user_id}-{uuid4()}"
        )
        db.add(transaction)
        await db.commit()

        # 5. Initiate NGN collection
        payment_instructions = await collection_provider.initiate_payment(
            amount=total_to_collect,
            currency=corridor.source_currency,
            user_id=user_id,
            transaction_ref=str(transaction.id),
            payment_method=payment_method,
            metadata={"corridor": corridor_code}
        )

        transaction.status = "collection_initiated"
        transaction.collection_reference = payment_instructions["reference"]
        await db.commit()

        return {
            "transaction_id": str(transaction.id),
            "payment_instructions": payment_instructions,
            "summary": {
                "target_amount": target_amount,
                "target_currency": corridor.target_currency,
                "source_amount": total_to_collect,
                "source_currency": corridor.source_currency,
                "fx_rate": fx_rate,
                "platform_fee": platform_fee,
                "rate_expires_in": 300  # 5 minutes
            }
        }
```

---

### 6.3 Webhook Handler

```python
# api/webhooks.py

@router.post("/webhooks/flutterwave")
async def flutterwave_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    # 1. Verify webhook signature
    signature = request.headers.get("verif-hash")
    if signature != settings.FLUTTERWAVE_WEBHOOK_SECRET:
        raise HTTPException(status_code=401)

    payload = await request.json()

    # 2. Only process successful charges
    if payload.get("event") != "charge.completed":
        return {"status": "ignored"}

    tx_ref = payload["data"]["tx_ref"]

    # 3. Check idempotency — prevent double processing
    existing = await get_transaction_by_reference(tx_ref, db)
    if existing and existing.collection_status == "confirmed":
        return {"status": "already_processed"}

    # 4. Update collection status
    await update_collection_status(tx_ref, "confirmed", db)

    # 5. Queue CNY disbursement as background task
    background_tasks.add_task(
        disburse_payment.delay,  # Celery task
        transaction_id=existing.id
    )

    return {"status": "accepted"}
```

---

### 6.4 Disbursement Task (Celery)

```python
# tasks/disbursement.py

@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60  # retry after 60 seconds
)
async def disburse_payment(self, transaction_id: str):
    async with get_db_session() as db:
        transaction = await get_transaction(transaction_id, db)

        try:
            # Get the correct disbursement provider for this corridor
            provider = get_disbursement_provider(
                transaction.disbursement_provider
            )

            # Fire the CNY disbursement
            result = await provider.pay_qr(
                qr_code=transaction.disbursement_target_data,
                amount=transaction.target_amount,
                currency=transaction.target_currency,
                transaction_ref=str(transaction.id),
                metadata={"user_id": str(transaction.user_id)}
            )

            # Update transaction
            transaction.disbursement_reference = result["reference"]
            transaction.disbursement_status = "processing"
            transaction.status = "disbursement_initiated"
            await db.commit()

            # Log the event
            await create_audit_log(
                transaction_id=transaction_id,
                event="disbursement_initiated",
                provider=transaction.disbursement_provider,
                payload=result,
                db=db
            )

        except Exception as exc:
            # Retry logic
            if self.request.retries < self.max_retries:
                raise self.retry(exc=exc)
            else:
                # All retries exhausted — initiate refund
                transaction.disbursement_status = "failed"
                transaction.status = "failed"
                transaction.failure_reason = str(exc)
                await db.commit()

                # Queue refund
                await initiate_refund.delay(transaction_id)

                # Notify user
                await send_push_notification.delay(
                    user_id=str(transaction.user_id),
                    title="Payment Failed",
                    body="We couldn't complete your payment. A refund will be processed within 24 hours."
                )
```

---

## 7. Project Structure

```
app/
├── main.py                          # FastAPI app entry point
├── core/
│   ├── config.py                    # Environment variables (Pydantic Settings)
│   ├── security.py                  # JWT, password hashing, 2FA
│   ├── database.py                  # Async DB connection
│   └── providers/
│       ├── base.py                  # Abstract provider interfaces
│       ├── registry.py              # Provider registry & resolver
│       ├── flutterwave.py           # Flutterwave implementation
│       ├── lianlian.py              # LianLian implementation
│       └── (future)/
│           ├── mpesa.py
│           └── airwallex.py
├── api/
│   ├── auth.py                      # Login, signup, refresh token
│   ├── payments.py                  # Initiate, status, history
│   ├── webhooks.py                  # Flutterwave + LianLian webhooks
│   ├── users.py                     # Profile, KYC, wallet
│   └── corridors.py                 # List active corridors & rates
├── services/
│   ├── payment_service.py           # Core payment orchestration
│   ├── fx_service.py                # FX rate fetching + Redis caching
│   ├── refund_service.py            # Refund orchestration
│   ├── wallet_service.py            # Wallet balance management
│   └── notification_service.py     # FCM push notifications
├── models/
│   ├── user.py
│   ├── transaction.py
│   ├── corridor.py
│   ├── audit_log.py
│   └── wallet.py
├── schemas/
│   ├── payment.py                   # Pydantic request/response models
│   ├── user.py
│   └── corridor.py
├── tasks/
│   ├── celery_app.py                # Celery configuration
│   ├── disbursement.py              # CNY disbursement task
│   ├── refund.py                    # Refund task
│   └── notifications.py            # Push notification task
└── migrations/                      # Alembic migrations
    └── versions/
```

---

## 8. FX Rate Caching Strategy

FX rates are fetched from Flutterwave but cached in Redis to avoid hammering the rate API on every transaction initiation:

```python
# services/fx_service.py

RATE_CACHE_TTL = 300  # 5 minutes

async def get_fx_rate(
    source_currency: str,
    target_currency: str,
    provider: CollectionProvider
) -> Decimal:

    cache_key = f"fx_rate:{source_currency}:{target_currency}"

    # Check Redis cache first
    cached = await redis.get(cache_key)
    if cached:
        return Decimal(cached)

    # Fetch live rate from provider
    rate = await provider.get_fx_rate(source_currency, target_currency)

    # Cache for 5 minutes
    await redis.setex(cache_key, RATE_CACHE_TTL, str(rate))

    return rate
```

**Note:** The 5-minute cache TTL means users may see a rate that's up to 5 minutes old. The rate countdown timer on the payment confirmation screen should reflect this. Always store the exact rate used at the time of transaction initiation in the transaction record — never recalculate it at disbursement time.

---

## 9. Security Considerations

| Concern | Implementation |
|---|---|
| **API Authentication** | JWT access tokens (15 min expiry) + refresh tokens (7 days) |
| **Webhook Verification** | Signature verification on all incoming webhooks |
| **Idempotency** | Unique idempotency key per transaction, checked before processing |
| **Rate Limiting** | Per-user and per-IP rate limits on payment endpoints |
| **Data Encryption** | AES-256 encryption for sensitive fields (QR data, ID numbers) |
| **Audit Trail** | Immutable audit log for every state change on every transaction |
| **KYC Gate** | No transaction allowed without verified KYC status |
| **Transaction Limits** | Per-transaction and daily limits enforced at service layer |
| **HTTPS Only** | TLS 1.3 enforced, no HTTP fallback |
| **Secrets Management** | All API keys in environment variables, never in codebase |

---

## 10. Environment Variables

```env
# App
APP_ENV=production
SECRET_KEY=your_jwt_secret_key
ALLOWED_ORIGINS=https://yourapp.com

# Database
DATABASE_URL=postgresql+asyncpg://user:password@host:5432/dbname

# Redis
REDIS_URL=redis://localhost:6379/0

# Flutterwave
FLUTTERWAVE_SECRET_KEY=FLWSECK_TEST-xxx
FLUTTERWAVE_WEBHOOK_SECRET=your_webhook_secret

# LianLian
LIANLIAN_API_KEY=your_lianlian_api_key
LIANLIAN_MERCHANT_ID=your_merchant_id
LIANLIAN_WEBHOOK_SECRET=your_webhook_secret

# Firebase
FIREBASE_SERVICE_ACCOUNT_KEY=path/to/serviceAccountKey.json

# Future providers (commented until needed)
# MPESA_CONSUMER_KEY=
# MPESA_CONSUMER_SECRET=
# AIRWALLEX_CLIENT_ID=
# AIRWALLEX_API_KEY=
```

---

## 11. Corridor Expansion Checklist

When adding a new corridor (e.g. Kenya → China):

- [ ] Implement or confirm collection provider supports source country/currency
- [ ] Implement or confirm disbursement provider supports target currency/payment type
- [ ] Add provider implementation file if new provider (implements base interface)
- [ ] Register provider in `registry.py`
- [ ] Insert new corridor record in `corridors` table
- [ ] Add environment variables for new provider credentials
- [ ] Test full payment flow in sandbox environment
- [ ] Confirm regulatory compliance in source country
- [ ] Update mobile app to surface new corridor in UI
- [ ] Set `is_active = true` in corridor record to go live

**No core application code changes required.**

---

## 12. Roadmap Considerations

| Phase | Corridor | Collection | Disbursement | Status |
|---|---|---|---|---|
| 1 | Nigeria → China | Flutterwave | LianLian | **Build Now** |
| 2 | Ghana → China | Flutterwave | LianLian | Config only |
| 3 | Kenya → China | M-Pesa | LianLian | New provider |
| 4 | Nigeria → Japan | Flutterwave | Airwallex | New provider |
| 5 | Nigeria → India | Flutterwave | Airwallex/Razorpay | New provider |
| 6 | Ethiopia → China | Telebirr | LianLian | New provider |

---
*End of Technical Architecture Document — v1.0*
