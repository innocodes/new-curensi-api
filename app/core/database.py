from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import MetaData
from app.core.config import settings

convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=convention)


# Neon drops idle connections after ~5 min — pool_recycle handles that.
# pool_size is small because Neon free tier caps at 100 total connections.
engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=5,
    max_overflow=5,
    pool_pre_ping=True,
    pool_recycle=300,
    echo=not settings.is_production,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_session():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
