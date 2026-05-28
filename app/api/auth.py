from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from pydantic import BaseModel, EmailStr
import re
from app.core.deps import get_db, get_current_user
from app.core.security import hash_password, verify_password, create_access_token, create_refresh_token, decode_token
from app.models.user import User

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    full_name: str
    email: EmailStr
    phone: str
    password: str
    country: str = "NG"


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: dict


class RefreshRequest(BaseModel):
    refresh_token: str


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(
        select(User).where(or_(User.email == body.email, User.phone == body.phone))
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email or phone already registered")

    user = User(
        full_name=body.full_name,
        email=body.email.lower(),
        phone=body.phone,
        country=body.country,
        hashed_password=hash_password(body.password),
    )
    db.add(user)
    await db.commit()

    return TokenResponse(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
        user={"id": str(user.id), "full_name": user.full_name, "email": user.email,
              "kyc_status": user.kyc_status, "tier": user.tier},
    )


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(User).where(or_(User.email == body.email.lower(), User.phone == body.email))
    )
    user = result.scalar_one_or_none()

    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")

    return TokenResponse(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
        user={"id": str(user.id), "full_name": user.full_name, "email": user.email,
              "kyc_status": user.kyc_status, "tier": user.tier},
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    payload = decode_token(body.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    import uuid
    result = await db.execute(select(User).where(User.id == uuid.UUID(payload["sub"])))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found")

    return TokenResponse(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
        user={"id": str(user.id), "full_name": user.full_name, "email": user.email,
              "kyc_status": user.kyc_status, "tier": user.tier},
    )


@router.get("/me")
async def me(current_user: User = Depends(get_current_user)):
    return {
        "id": str(current_user.id),
        "full_name": current_user.full_name,
        "email": current_user.email,
        "phone": current_user.phone,
        "country": current_user.country,
        "kyc_status": current_user.kyc_status,
        "tier": current_user.tier,
    }


@router.patch("/fcm-token")
async def update_fcm_token(
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    current_user.fcm_token = body.get("fcm_token")
    await db.commit()
    return {"ok": True}
