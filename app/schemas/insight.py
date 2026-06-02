from pydantic import BaseModel
from typing import Literal


class InsightCard(BaseModel):
    title: str
    body: str
    severity: Literal["info", "warning", "success"]
    category: str | None = None
    amount: float | None = None


class InsightFeedResponse(BaseModel):
    insights: list[InsightCard]
    generated_at: str
    cached: bool = False


class AffordabilityRequest(BaseModel):
    question: str


class AffordabilityResponse(BaseModel):
    answer: str
    data_points: list[str] = []
