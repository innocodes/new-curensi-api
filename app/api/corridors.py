from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.deps import get_db
from app.models.corridor import Corridor

router = APIRouter(prefix="/corridors", tags=["corridors"])


@router.get("")
async def list_corridors(db: AsyncSession = Depends(get_db)):
    """Return all active corridors with their fee structures. No auth required."""
    result = await db.execute(select(Corridor).where(Corridor.is_active == True))
    corridors = result.scalars().all()
    return [
        {
            "code": c.code,
            "name": c.name,
            "source_country": c.source_country,
            "source_currency": c.source_currency,
            "target_country": c.target_country,
            "target_currency": c.target_currency,
            "supported_methods": c.supported_methods,
            "supported_targets": c.supported_targets,
            "fee_percentage": float(c.fee_percentage),
            "min_transaction": float(c.min_transaction),
            "max_transaction": float(c.max_transaction),
        }
        for c in corridors
    ]
