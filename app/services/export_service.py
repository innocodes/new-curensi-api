import io
import csv
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.financial_transaction import FinancialTransaction


async def _get_transactions(user_id: str, filters: dict, db: AsyncSession):
    query = select(FinancialTransaction).where(
        FinancialTransaction.user_id == user_id,
        FinancialTransaction.is_deleted.is_(False),
    )
    if filters.get("date_from"):
        query = query.where(FinancialTransaction.date >= filters["date_from"])
    if filters.get("date_to"):
        query = query.where(FinancialTransaction.date <= filters["date_to"])
    if filters.get("account_id"):
        query = query.where(FinancialTransaction.account_id == filters["account_id"])
    result = await db.execute(query.order_by(FinancialTransaction.date.desc()))
    return result.scalars().all()


def _tx_to_row(tx: FinancialTransaction) -> list:
    return [
        tx.date,
        tx.description,
        float(tx.amount),
        tx.transaction_type,
        tx.category or "",
        tx.currency,
        tx.reference or "",
        tx.notes or "",
        tx.source or "",
    ]

HEADERS = ["Date", "Description", "Amount", "Type", "Category", "Currency", "Reference", "Notes", "Source"]


async def export_to_csv(user_id: str, filters: dict, db: AsyncSession) -> bytes:
    txs = await _get_transactions(user_id, filters, db)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(HEADERS)
    for tx in txs:
        writer.writerow(_tx_to_row(tx))
    return buf.getvalue().encode("utf-8")


async def export_to_excel(user_id: str, filters: dict, db: AsyncSession) -> bytes:
    import openpyxl
    txs = await _get_transactions(user_id, filters, db)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Transactions"
    ws.append(HEADERS)
    for tx in txs:
        ws.append(_tx_to_row(tx))
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


async def export_to_pdf(user_id: str, filters: dict, db: AsyncSession) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet

    txs = await _get_transactions(user_id, filters, db)
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4)
    styles = getSampleStyleSheet()

    data = [HEADERS] + [_tx_to_row(tx) for tx in txs]
    table = Table(data)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0B5A3D")),
        ("TEXTCOLOR",  (0, 0), (-1, 0), colors.white),
        ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",   (0, 0), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8F5EA")]),
        ("GRID",       (0, 0), (-1, -1), 0.5, colors.HexColor("#E5DFC9")),
    ]))

    doc.build([
        Paragraph("Curensi — Transaction Export", styles["Title"]),
        Paragraph(f"Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}", styles["Normal"]),
        table,
    ])
    return buf.getvalue()
