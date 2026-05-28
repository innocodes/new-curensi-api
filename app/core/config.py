from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_ENV: str = "development"
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # Neon DB
    DATABASE_URL: str        # asyncpg — used by the app
    DATABASE_URL_SYNC: str   # psycopg2 — used by Alembic migrations only

    # Redis / Celery
    REDIS_URL: str = "redis://localhost:6379/0"

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

    # Future providers — optional
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
    def celery_broker_url(self) -> str:
        return self.REDIS_URL

    @property
    def celery_result_backend(self) -> str:
        return self.REDIS_URL


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
