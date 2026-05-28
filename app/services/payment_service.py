import uuid
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.corridor import Corridor
from app.models.transaction import Transaction
from app.models.audit_log import AuditLog
from app.core.providers.registry import get_collection_provider
from app.services.fx_service import get_fx_rate, calculate_fee


async def get_corridor(code: str, db: AsyncSession) -> Corridor:
    result = await db.execute(
        select(Corridor).where(Corridor.code == code, Corridor.is_active == True)
    )
    corridor = result.scalar_one_or_none()
    if not corridor:
        raise ValueError(f"Corridor '{code}' is not active")
    return corridor


async def initiate_transaction(
    user_id: uuid.UUID,
    corridor_code: str,
    target_amount: Decimal,
    target_type: str,          # "alipay_qr"
    target_data: str,          # QR code content
    payment_method: str,       # "bank_transfer" | "card" | "ussd"
    metadata: dict,
    db: AsyncSession,
) -> dict:
    corridor = await get_corridor(corridor_code, db)

    collection_provider = get_collection_provider(corridor.collection_provider)

    # Fetch live rate (served from Redis cache if fresh)
    fx_rate = await get_fx_rate(
        corridor.source_currency, corridor.target_currency, collection_provider
    )

    # Calculate amounts
    base_source_amount = (target_amount / fx_rate).quantize(Decimal("0.01"))
    platform_fee = calculate_fee(
        base_source_amount,
        corridor.fee_percentage,
        corridor.fee_flat,
        corridor.min_fee,
        corridor.max_fee,
    )
    total_to_collect = base_source_amount + platform_fee

    # Validate against corridor limits
    if total_to_collect < corridor.min_transaction:
        raise ValueError(f"Minimum transaction is {corridor.source_currency} {corridor.min_transaction}")
    if total_to_collect > corridor.max_transaction:
        raise ValueError(f"Maximum transaction is {corridor.source_currency} {corridor.max_transaction}")

    # Create transaction record first (before calling provider — so we have an ID for the ref)
    tx = Transaction(
        user_id=user_id,
        corridor_id=corridor.id,
        idempotency_key=f"{user_id}-{uuid.uuid4()}",
        source_currency=corridor.source_currency,
        source_amount=total_to_collect,
        platform_fee=platform_fee,
        fee_percentage=corridor.fee_percentage,
        collection_provider=corridor.collection_provider,
        collection_method=payment_method,
        fx_rate=fx_rate,
        fx_rate_timestamp=datetime.now(timezone.utc),
        target_currency=corridor.target_currency,
        target_amount=target_amount,
        disbursement_provider=corridor.disbursement_provider,
        disbursement_target_type=target_type,
        disbursement_target_data=target_data,
        status="pending",
        metadata=metadata,
    )
    db.add(tx)
    await db.flush()  # get tx.id without committing

    # Initiate collection with provider
    result = await collection_provider.initiate_payment(
        amount=total_to_collect,
        currency=corridor.source_currency,
        user_id=str(user_id),
        transaction_ref=str(tx.id),
        payment_method=payment_method,
        metadata={**metadata, "corridor": corridor_code},
    )

    tx.collection_reference = result["reference"]
    tx.status = "collection_initiated"

    # Audit
    db.add(AuditLog(
        transaction_id=tx.id,
        user_id=user_id,
        event="collection_initiated",
        provider=corridor.collection_provider,
        payload=result,
    ))
    await db.commit()

    return {
        "transaction_id": str(tx.id),
        "status": tx.status,
        "payment_instructions": result["payment_instructions"],
        "summary": {
            "target_amount": float(target_amount),
            "target_currency": corridor.target_currency,
            "source_amount": float(total_to_collect),
            "source_currency": corridor.source_currency,
            "platform_fee": float(platform_fee),
            "fx_rate": float(fx_rate),
            "rate_expires_in": 300,
        },
    }


async def create_audit_log(
    transaction_id: uuid.UUID,
    user_id: uuid.UUID,
    event: str,
    provider: str | None,
    payload: dict | None,
    db: AsyncSession,
) -> None:
    db.add(AuditLog(
        transaction_id=transaction_id,
        user_id=user_id,
        event=event,
        provider=provider,
        payload=payload,
    ))
    await db.commit()
