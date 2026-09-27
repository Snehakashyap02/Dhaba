from app.models import Ticket
from app.refund import calculate_refund


def make_ticket(purchases):
    return Ticket(
        id="TEST",
        received_at="2026-09-01T00:00:00+05:30",
        subject="test",
        body="test",
        purchases=purchases,
        app_opens_since_renewal=0,
    )


def test_duplicate_successful_renewals_are_refundable():
    ticket = make_ticket([
        {
            "id": "p1",
            "type": "renewal",
            "amount_inr": 249,
            "status": "successful",
            "at": "2026-09-05T06:00:00+05:30",
        },
        {
            "id": "p2",
            "type": "renewal",
            "amount_inr": 249,
            "status": "successful",
            "at": "2026-09-05T06:03:00+05:30",
        },
    ])

    result = calculate_refund(ticket)

    assert result.eligible is True
    assert result.amount_inr == 249


def test_failed_then_successful_payment_is_not_duplicate():
    ticket = make_ticket([
        {
            "id": "p1",
            "type": "renewal",
            "amount_inr": 249,
            "status": "failed",
            "at": "2026-09-05T06:00:00+05:30",
        },
        {
            "id": "p2",
            "type": "renewal",
            "amount_inr": 249,
            "status": "successful",
            "at": "2026-09-05T06:03:00+05:30",
        },
    ])

    result = calculate_refund(ticket)

    assert result.eligible is False
    assert result.amount_inr == 0
