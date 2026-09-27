from typing import Literal
from pydantic import BaseModel, Field


Category = Literal[
    "billing",
    "technical",
    "account",
    "cancellation",
    "feature_request",
    "fraud",
    "invoice",
    "pre_sales",
    "other",
]

Severity = Literal[
    "low",
    "medium",
    "high",
    "critical",
]


class Purchase(BaseModel):
    id: str
    type: Literal["trial", "renewal"]
    amount_inr: int
    status: Literal["initiated", "failed", "successful", "renewal"]
    at: str


class Ticket(BaseModel):
    id: str
    received_at: str
    subject: str
    body: str
    purchases: list[Purchase]
    app_opens_since_renewal: int


class RefundDecision(BaseModel):
    eligible: bool
    amount_inr: int = Field(ge=0)
    reason: str


class TriageResponse(BaseModel):
    category: Category
    severity: Severity
    refund: RefundDecision
    reply_draft: str
    needs_human: bool
    confidence: float = Field(ge=0.0, le=1.0)
