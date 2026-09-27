from .llm import triage_ticket
from .models import Ticket, TriageResponse
from .refund import calculate_refund
from .safety import detect_prompt_injection


def process_ticket(ticket: Ticket) -> TriageResponse:
    injection = detect_prompt_injection(
        f"{ticket.subject}\n{ticket.body}"
    )

    model_result = triage_ticket(ticket)

    refund = calculate_refund(ticket)

    text = f"{ticket.subject} {ticket.body}".lower()

    billing_conflict = (
        ("double charge" in text or "twice" in text)
        and not refund.eligible
    )

    needs_human = (
        injection
        or model_result["confidence"] < 0.80
        or refund.reason.startswith("Possible unauthorized")
        or billing_conflict
    )

    if billing_conflict:
        reply_draft = (
            "We found one successful renewal and one failed payment attempt. "
            "We have not issued a refund because the billing record does not "
            "currently confirm a duplicate successful charge. A support "
            "specialist should review the payment details."
        )
    else:
        reply_draft = model_result["reply_draft"]

    return TriageResponse(
        category=model_result["category"],
        severity=model_result["severity"],
        refund=refund,
        reply_draft=reply_draft,
        needs_human=needs_human,
        confidence=model_result["confidence"],
    )
    
def degraded_ticket_response(ticket: Ticket) -> TriageResponse:
    """
    Safe response used when the service is overloaded.

    Refund logic still runs independently. The model is not called.
    """
    refund = calculate_refund(ticket)

    return TriageResponse(
        category="other",
        severity="medium",
        refund=refund,
        reply_draft=(
            "We’re receiving a high volume of support requests. "
            "A support specialist will review your request and get back to you."
        ),
        needs_human=True,
        confidence=0.0,
    )