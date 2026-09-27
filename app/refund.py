from .models import Ticket, RefundDecision


def calculate_refund(ticket: Ticket) -> RefundDecision:
    successful_renewals = [
        p for p in ticket.purchases
        if p.type == "renewal" and p.status == "successful"
    ]

    counts = {}

    for purchase in successful_renewals:
        key = (purchase.amount_inr, purchase.at[:10])
        counts[key] = counts.get(key, 0) + 1

    duplicate_amount = 0

    for (amount, _), count in counts.items():
        if count > 1:
            duplicate_amount += amount * (count - 1)

    if duplicate_amount > 0:
        return RefundDecision(
            eligible=True,
            amount_inr=duplicate_amount,
            reason="Multiple successful renewal charges occurred on the same date.",
        )

    body = ticket.body.lower()
    subject = ticket.subject.lower()

    if any(
        keyword in f"{subject} {body}"
        for keyword in ["fraud", "never installed", "unauthorized"]
    ):
        return RefundDecision(
            eligible=False,
            amount_inr=0,
            reason="Possible unauthorized payment requires human review.",
        )

    return RefundDecision(
        eligible=False,
        amount_inr=0,
        reason="No deterministic automatic refund rule applies.",
    )
