from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_ENV: str = "development"
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # Neon DB
    DATABASE_URL: str
    DATABASE_URL_SYNC: str

    # Redis / Celery
    # ✅ No localhost default — forces explicit config in all environments
    REDIS_URL: str

    # Flutterwave
    FLUTTERWAVE_SECRET_KEY: str = ""
    FLUTTERWAVE_WEBHOOK_SECRET: str = ""
    FLUTTERWAVE_BASE_URL: str = "https://api.flutterwave.com/v3"

    # LianLian
    LIANLIAN_APP_ID: str = ""
    LIANLIAN_MERCHANT_ID: str = ""
    LIANLIAN_API_KEY: str = ""
    LIANLIAN_WEBHOOK_SECRET: str = ""
    LIANLIAN_BASE_URL: str = "https://sandbox.lianlianpay.com"

    # Firebase
    FIREBASE_SERVICE_ACCOUNT_KEY: str = "{}"

    # CORS
    ALLOWED_ORIGINS: str = "http://localhost:3000"

    # Future providers
    MPESA_CONSUMER_KEY: str = ""
    MPESA_CONSUMER_SECRET: str = ""
    AIRWALLEX_CLIENT_ID: str = ""
    AIRWALLEX_API_KEY: str = ""

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
        Always use this property in the app — never DATABASE_URL directly.

        Key difference from psycopg2:
          asyncpg does NOT accept 'sslmode' or 'channel_binding' as query params.
          It uses 'ssl=require' instead. Strip the libpq params and add the
          asyncpg-compatible one.
        """
        import re
        url = self.DATABASE_URL

        # Normalize driver prefix
        url = url.replace("postgres://", "postgresql+asyncpg://")
        url = url.replace("postgresql://", "postgresql+asyncpg://")

        # Strip libpq-only params that asyncpg rejects with TypeError
        url = re.sub(r"[&?]sslmode=[^&]*", "", url)
        url = re.sub(r"[&?]channel_binding=[^&]*", "", url)

        # Add asyncpg-compatible SSL param
        separator = "&" if "?" in url else "?"
        url += f"{separator}ssl=require"

        return url

    @property
    def sync_database_url(self) -> str:
        """
        Normalizes DATABASE_URL_SYNC for psycopg2 (Alembic only).
        Always use this in alembic/env.py — never DATABASE_URL_SYNC directly.
        """
        url = self.DATABASE_URL_SYNC

        # Normalize driver prefix for psycopg2
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