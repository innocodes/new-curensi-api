from functools import lru_cache
import re
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ── App ────────────────────────────────────────────────────────────
    APP_ENV: str = "development"
    SECRET_KEY: str
    ALLOWED_ORIGINS: str = "http://localhost:3000"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # ── Database ────────────────────────────────────────────────────────
    DATABASE_URL: str
    DATABASE_URL_SYNC: str

    # ── Redis ───────────────────────────────────────────────────────────
    REDIS_URL: str

    # ── File Storage (Cloudflare R2) ────────────────────────────────────
    R2_ACCOUNT_ID: str = ""
    R2_ACCESS_KEY_ID: str = ""
    R2_SECRET_ACCESS_KEY: str = ""
    R2_BUCKET_NAME: str = "curensi-documents"
    R2_PUBLIC_URL: str = ""

    # ── AI Providers ────────────────────────────────────────────────────
    ANTHROPIC_API_KEY: str = ""
    OPENAI_API_KEY: str = ""

    # ── Communications ──────────────────────────────────────────────────
    TERMII_API_KEY: str = ""
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_WHATSAPP_NUMBER: str = ""

    # ── KYC ─────────────────────────────────────────────────────────────
    DOJAH_APP_ID: str = ""
    DOJAH_API_KEY: str = ""

    # ── Subscriptions ────────────────────────────────────────────────────
    PAYSTACK_SECRET_KEY: str = ""
    PAYSTACK_WEBHOOK_SECRET: str = ""

    # ── Firebase ────────────────────────────────────────────────────────
    FIREBASE_SERVICE_ACCOUNT_KEY: str = "{}"

    # ── Payment Platform (preserved, feature-flagged) ───────────────────
    FLUTTERWAVE_SECRET_KEY: str = ""
    FLUTTERWAVE_WEBHOOK_SECRET: str = ""
    FLUTTERWAVE_BASE_URL: str = "https://api.flutterwave.com/v3"
    LIANLIAN_APP_ID: str = ""
    LIANLIAN_MERCHANT_ID: str = ""
    LIANLIAN_API_KEY: str = ""
    LIANLIAN_WEBHOOK_SECRET: str = ""
    LIANLIAN_BASE_URL: str = "https://sandbox.lianlianpay.com"
    MPESA_CONSUMER_KEY: str = ""
    MPESA_CONSUMER_SECRET: str = ""
    AIRWALLEX_CLIENT_ID: str = ""
    AIRWALLEX_API_KEY: str = ""

    # ── Feature Flags ────────────────────────────────────────────────────
    # Aggregator — active
    ENABLE_AGGREGATOR: bool = True
    ENABLE_AI_INSIGHTS: bool = True
    ENABLE_WHATSAPP_BOT: bool = False       # Phase 2 — pending Twilio/Meta approval
    ENABLE_SUBSCRIPTIONS: bool = False      # Phase 2 — pending Paystack setup

    # Payment platform — preserved, off until CBN licensed
    ENABLE_PAYMENTS: bool = False
    ENABLE_CORRIDORS: bool = False
    ENABLE_PAYMENT_WEBHOOKS: bool = False

    # ── Computed Properties ──────────────────────────────────────────────
    @property
    def origins(self) -> list[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",")]

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    @property
    def async_database_url(self) -> str:
        """
        Normalizes DATABASE_URL for asyncpg + Neon SSL.
        asyncpg does NOT accept 'sslmode' or 'channel_binding' — strip them
        and replace with the asyncpg-compatible 'ssl=require'.
        """
        url = self.DATABASE_URL
        url = url.replace("postgres://", "postgresql+asyncpg://")
        url = url.replace("postgresql://", "postgresql+asyncpg://")
        url = re.sub(r"[&?]sslmode=[^&]*", "", url)
        url = re.sub(r"[&?]channel_binding=[^&]*", "", url)
        if "neon.tech" in url:
            separator = "&" if "?" in url else "?"
            url += f"{separator}ssl=require"
        return url

    @property
    def sync_database_url(self) -> str:
        """Normalizes DATABASE_URL_SYNC for psycopg2 (Alembic only)."""
        url = self.DATABASE_URL_SYNC
        url = url.replace("postgres://", "postgresql+psycopg2://")
        url = url.replace("postgresql://", "postgresql+psycopg2://")
        return url

    @property
    def celery_broker_url(self) -> str:
        return self.REDIS_URL

    @property
    def celery_result_backend(self) -> str:
        return self.REDIS_URL


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
