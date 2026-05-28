from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from pydantic import BaseModel, EmailStr
from app.core.deps import get_db, get_current_user
from app.models.waitlist import WaitlistEntry
from app.models.user import User

router = APIRouter(prefix="/waitlist", tags=["waitlist"])


class JoinRequest(BaseModel):
    email: EmailStr
    name: str
    phone: str | None = None


class JoinResponse(BaseModel):
    message: str
    position: int


@router.post("", response_model=JoinResponse, status_code=201)
async def join_waitlist(body: JoinRequest, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(
        select(WaitlistEntry).where(WaitlistEntry.email == body.email.lower())
    )
    if existing.scalar_one_or_none():
        # Return success anyway — don't expose whether email is already registered
        count = (await db.execute(select(func.count()).select_from(WaitlistEntry))).scalar_one()
        return JoinResponse(message="already_registered", position=count)

    entry = WaitlistEntry(
        email=body.email.lower(),
        name=body.name,
        phone=body.phone,
    )
    db.add(entry)
    await db.commit()

    count = (await db.execute(select(func.count()).select_from(WaitlistEntry))).scalar_one()
    return JoinResponse(message="registered", position=count)


@router.get("")
async def list_waitlist(
    page: int = 1,
    page_size: int = 50,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """Admin-only: list all waitlist signups. Requires auth."""
    total = (await db.execute(select(func.count()).select_from(WaitlistEntry))).scalar_one()
    rows = (
        await db.execute(
            select(WaitlistEntry)
            .order_by(desc(WaitlistEntry.created_at))
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()

    return {
        "total": total,
        "items": [
            {
                "id": str(e.id),
                "name": e.name,
                "email": e.email,
                "phone": e.phone,
                "joined_at": e.created_at.isoformat(),
            }
            for e in rows
        ],
    }
