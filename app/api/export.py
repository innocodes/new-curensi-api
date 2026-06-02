from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.deps import get_db, get_current_user
from app.models.user import User
from app.services.export_service import export_to_csv, export_to_excel, export_to_pdf
from app.services.quota_service import check_quota, QuotaExceededException

router = APIRouter(prefix="/export", tags=["Export"])

MIME_TYPES = {
    "csv":   "text/csv",
    "excel": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pdf":   "application/pdf",
}

EXTENSIONS = {"csv": "csv", "excel": "xlsx", "pdf": "pdf"}


class ExportRequest(BaseModel):
    format: str                   # csv | excel | pdf
    date_from: str | None = None  # YYYY-MM-DD
    date_to: str | None = None
    account_id: str | None = None


@router.post("")
async def export_transactions(
    body: ExportRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if body.format not in MIME_TYPES:
        raise HTTPException(status_code=400, detail="format must be 'csv', 'excel', or 'pdf'.")

    try:
        await check_quota(str(current_user.id), "export", db)
    except QuotaExceededException as e:
        raise HTTPException(status_code=402, detail=str(e))

    filters = {
        "date_from":  body.date_from,
        "date_to":    body.date_to,
        "account_id": body.account_id,
    }

    if body.format == "csv":
        data = await export_to_csv(str(current_user.id), filters, db)
    elif body.format == "excel":
        data = await export_to_excel(str(current_user.id), filters, db)
    else:
        data = await export_to_pdf(str(current_user.id), filters, db)

    filename = f"curensi-transactions.{EXTENSIONS[body.format]}"
    return Response(
        content=data,
        media_type=MIME_TYPES[body.format],
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
