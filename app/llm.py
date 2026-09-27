import json
from typing import Any
from pydantic import BaseModel, Field, ValidationError

from .models import Ticket


class ModelTriageOutput(BaseModel):
    category: str
    severity: str
    reply_draft: str
    confidence: float = Field(ge=0.0, le=1.0)


VALID_CATEGORIES = {
    "billing",
    "technical",
    "account",
    "cancellation",
    "feature_request",
    "fraud",
    "invoice",
    "pre_sales",
    "other",
}

VALID_SEVERITIES = {
    "low",
    "medium",
    "high",
    "critical",
}


def validate_model_output(raw_output: Any) -> ModelTriageOutput:
    """
    Parse and validate model output.

    Accepts:
    - Python dict
    - JSON string
    - JSON wrapped in a simple Markdown code fence

    Rejects:
    - prose
    - malformed JSON
    - truncated JSON
    - invalid categories
    - invalid severities
    - invalid confidence values
    """

    if isinstance(raw_output, str):
        raw_output = raw_output.strip()

        if raw_output.startswith("```") and raw_output.endswith("```"):
            lines = raw_output.splitlines()

            if lines and lines[0].strip().lower() in {
                "```",
                "```json",
            }:
                lines = lines[1:]

            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]

            raw_output = "\n".join(lines).strip()

        raw_output = json.loads(raw_output)

    if not isinstance(raw_output, dict):
        raise TypeError("Model output must be a JSON object.")

    result = ModelTriageOutput.model_validate(raw_output)

    if result.category not in VALID_CATEGORIES:
        raise ValueError(
            f"Invalid category returned by model: {result.category}"
        )

    if result.severity not in VALID_SEVERITIES:
        raise ValueError(
            f"Invalid severity returned by model: {result.severity}"
        )

    return result


def triage_with_fixture(ticket: Ticket) -> dict:
    text = f"{ticket.subject} {ticket.body}".lower()

    if any(
        x in text
        for x in ["fraud", "never installed", "unauthorized"]
    ):
        category = "fraud"
        severity = "critical"
        reply = (
            "We’re sorry about this. We’ll have a support specialist review "
            "the payment activity and help resolve the issue."
        )
        confidence = 0.98

    elif "invoice" in text or "gst invoice" in text:
        category = "invoice"
        severity = "low"
        reply = "We’ll help with your GST invoice request."
        confidence = 0.98

    elif "feature" in text or "add marathi" in text:
        category = "feature_request"
        severity = "low"
        reply = (
            "Thanks for the suggestion. We’ll pass your language request "
            "to the product team."
        )
        confidence = 0.97

    elif "crash" in text or "closes immediately" in text:
        category = "technical"
        severity = "high"
        reply = (
            "Sorry about the crash. We’ll help investigate the issue "
            "on your device."
        )
        confidence = 0.98

    elif "order history" in text or "changed my phone" in text:
        category = "account"
        severity = "medium"
        reply = (
            "We’ll help investigate your missing order history "
            "after the device change."
        )
        confidence = 0.94

    elif "cancel" in text:
        category = "cancellation"
        severity = "medium"
        reply = "We can help with cancelling your subscription."
        confidence = 0.99

    elif "not activate" in text or "free version" in text:
        category = "billing"
        severity = "high"
        reply = (
            "We’ll check the payment and subscription activation status."
        )
        confidence = 0.96

    elif "double charge" in text or "twice" in text:
        category = "billing"
        severity = "high"
        reply = (
            "We’ll verify the duplicate charge and help resolve it."
        )
        confidence = 0.98

    elif (
        "premium" in text
        or "subscribe" in text
        or "offline" in text
    ):
        category = "pre_sales"
        severity = "low"
        reply = (
            "Premium availability and offline support depend on "
            "the current product capabilities."
        )
        confidence = 0.90

    elif (
        "refund" in text
        or "charged" in text
        or "paisa kat" in text
    ):
        category = "billing"
        severity = "high"
        reply = (
            "We’ll review the payment details and help with the "
            "billing issue."
        )
        confidence = 0.94

    else:
        category = "other"
        severity = "medium"
        reply = (
            "We’ll review your request and help resolve the issue."
        )
        confidence = 0.70

    return {
        "category": category,
        "severity": severity,
        "reply_draft": reply,
        "confidence": confidence,
    }


def degraded_response() -> dict:
    return {
        "category": "other",
        "severity": "medium",
        "reply_draft": (
            "We’ve received your request. A support specialist "
            "will review it and get back to you."
        ),
        "confidence": 0.0,
    }


def triage_ticket(ticket: Ticket) -> dict:
    for attempt in range(2):
        try:
            raw_output = triage_with_fixture(ticket)
            validated = validate_model_output(raw_output)

            return validated.model_dump()

        except (ValidationError, ValueError, TypeError):
            if attempt == 0:
                continue

            return degraded_response()

    return degraded_response()