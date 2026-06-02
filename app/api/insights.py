from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.deps import get_db, get_current_user
from app.models.user import User
from app.services import insights_service
from app.services.quota_service import check_quota, QuotaExceededException
from app.schemas.insight import InsightFeedResponse, AffordabilityRequest, AffordabilityResponse
from datetime import datetime, timezone

router = APIRouter(prefix="/insights", tags=["Insights"])


@router.get("", response_model=InsightFeedResponse)
async def get_insights(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return AI-powered insight cards. Cached 1 hour."""
    try:
        await check_quota(str(current_user.id), "ai_insights", db)
    except QuotaExceededException as e:
        raise HTTPException(status_code=402, detail=str(e))

    cards = await insights_service.generate_insights_feed(str(current_user.id), db)
    return InsightFeedResponse(
        insights=cards,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )


@router.get("/summary")
async def get_summary(
    period: str = Query("this_month", enum=["this_month", "last_3_months", "last_6_months"]),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Spending summary — DB aggregation only, no LLM. Cached 6 hours."""
    return await insights_service.get_spending_summary(str(current_user.id), period, db)


@router.get("/forecast")
async def get_forecast(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """30-day cash flow forecast. Pro/Business tier only. Cached 24 hours."""
    try:
        await check_quota(str(current_user.id), "ai_insights", db)
    except QuotaExceededException as e:
        raise HTTPException(status_code=402, detail=str(e))

    return await insights_service.generate_cash_flow_forecast(str(current_user.id), db)


@router.post("/affordability", response_model=AffordabilityResponse)
async def affordability_check(
    body: AffordabilityRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Answer a specific financial question using last 90 days of data."""
    try:
        await check_quota(str(current_user.id), "ai_insights", db)
    except QuotaExceededException as e:
        raise HTTPException(status_code=402, detail=str(e))

    result = await insights_service.generate_affordability_answer(
        str(current_user.id), body.question, db
    )
    return AffordabilityResponse(
        answer=result.get("answer", ""),
        data_points=result.get("data_points", []),
    )
