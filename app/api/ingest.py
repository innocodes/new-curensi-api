import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.core.deps import get_db, get_current_user
from app.models.user import User
from app.models.ingestion import IngestionBatch, IngestionSource
from app.services.quota_service import check_quota, QuotaExceededException
from app.services.storage_service import upload_to_r2, generate_r2_key
from app.schemas.ingest import IngestionBatchResponse, IngestManualRequest

router = APIRouter(prefix="/ingest", tags=["Ingest"])

MAX_PDF_BYTES   = 10 * 1024 * 1024   # 10 MB
MAX_IMAGE_BYTES =  5 * 1024 * 1024   #  5 MB


@router.post("/pdf", status_code=202)
async def ingest_pdf(
    file: UploadFile = File(...),
    account_id: str | None = Form(None),
    currency: str = Form("NGN"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload a PDF bank statement for AI extraction."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    contents = await file.read()
    if len(contents) > MAX_PDF_BYTES:
        raise HTTPException(status_code=400, detail="PDF must be under 10 MB.")

    try:
        await check_quota(str(current_user.id), "pdf_upload", db)
    except QuotaExceededException as e:
        raise HTTPException(status_code=402, detail=str(e))

    r2_key = generate_r2_key(str(current_user.id), "pdf_statement", file.filename)
    await upload_to_r2(contents, r2_key, "application/pdf")

    batch = IngestionBatch(
        user_id=current_user.id,
        account_id=uuid.UUID(account_id) if account_id else None,
        source=IngestionSource.PDF_STATEMENT,
        r2_key=r2_key,
        currency=currency,
    )
    db.add(batch)
    await db.commit()

    # Lazy import — Celery not loaded at startup
    from app.tasks.parse_pdf import parse_pdf_task
    parse_pdf_task.delay(str(batch.id), str(current_user.id), r2_key)

    return {"batch_id": str(batch.id), "status": "pending"}


@router.post("/image", status_code=202)
async def ingest_image(
    file: UploadFile = File(...),
    source: str = Form(...),           # receipt_scan | screenshot
    account_id: str | None = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload a receipt photo or screenshot for AI extraction."""
    if source not in ("receipt_scan", "screenshot"):
        raise HTTPException(status_code=400, detail="source must be 'receipt_scan' or 'screenshot'.")

    allowed_types = {"image/jpeg", "image/png", "image/webp"}
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Only JPEG, PNG, or WebP images are accepted.")

    contents = await file.read()
    if len(contents) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=400, detail="Image must be under 5 MB.")

    try:
        await check_quota(str(current_user.id), "ai_scan", db)
    except QuotaExceededException as e:
        raise HTTPException(status_code=402, detail=str(e))

    ext = (file.filename or "image.jpg").rsplit(".", 1)[-1].lower()
    r2_key = generate_r2_key(str(current_user.id), source, f"image.{ext}")
    await upload_to_r2(contents, r2_key, file.content_type)

    batch = IngestionBatch(
        user_id=current_user.id,
        account_id=uuid.UUID(account_id) if account_id else None,
        source=IngestionSource.RECEIPT_SCAN if source == "receipt_scan" else IngestionSource.SCREENSHOT,
        r2_key=r2_key,
    )
    db.add(batch)
    await db.commit()

    from app.tasks.parse_image import parse_image_task
    parse_image_task.delay(str(batch.id), str(current_user.id), r2_key, source)

    return {"batch_id": str(batch.id), "status": "pending"}


@router.post("/manual", status_code=201)
async def ingest_manual(
    body: IngestManualRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Enter a transaction manually — no file upload, no AI."""
    from app.models.financial_transaction import FinancialTransaction

    tx = FinancialTransaction(
        user_id=current_user.id,
        account_id=uuid.UUID(body.account_id) if body.account_id else None,
        date=body.date,
        description=body.description,
        amount=body.amount,
        transaction_type=body.transaction_type,
        currency=body.currency,
        category=body.category,
        notes=body.notes,
        source="manual",
    )
    db.add(tx)
    await db.commit()

    from app.services.insights_service import invalidate_user_caches
    await invalidate_user_caches(str(current_user.id))

    return {"id": str(tx.id), "status": "created"}


@router.get("/batches")
async def list_batches(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List the user's ingestion batches."""
    from sqlalchemy import func
    total = (await db.execute(
        select(func.count()).select_from(IngestionBatch)
        .where(IngestionBatch.user_id == current_user.id)
    )).scalar_one()

    rows = (await db.execute(
        select(IngestionBatch)
        .where(IngestionBatch.user_id == current_user.id)
        .order_by(desc(IngestionBatch.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )).scalars().all()

    return {
        "items": [IngestionBatchResponse.model_validate(b) for b in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/batches/{batch_id}", response_model=IngestionBatchResponse)
async def get_batch(
    batch_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get status of a single batch — poll this after upload."""
    result = await db.execute(
        select(IngestionBatch).where(
            IngestionBatch.id == uuid.UUID(batch_id),
            IngestionBatch.user_id == current_user.id,
        )
    )
    batch = result.scalar_one_or_none()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found.")
    return IngestionBatchResponse.model_validate(batch)
