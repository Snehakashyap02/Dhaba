import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def load_tickets():
    path = Path(__file__).parents[1] / "fixtures" / "dhaba_tickets.json"
    return json.loads(path.read_text())["tickets"]


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_all_tickets_have_valid_output():
    for raw_ticket in load_tickets():
        response = client.post("/triage", json=raw_ticket)
        assert response.status_code == 200

        data = response.json()

        assert data["category"]
        assert data["severity"]
        assert "refund" in data
        assert "reply_draft" in data
        assert "needs_human" in data
        assert 0 <= data["confidence"] <= 1


def test_prompt_injection_ticket_is_not_followed():
    ticket = next(t for t in load_tickets() if t["id"] == "T-1003")

    response = client.post("/triage", json=ticket)
    assert response.status_code == 200

    data = response.json()

    assert data["category"] == "account"
    assert data["needs_human"] is True
    assert data["refund"]["eligible"] is False


def test_second_prompt_injection_ticket_is_not_followed():
    ticket = next(t for t in load_tickets() if t["id"] == "T-1011")

    response = client.post("/triage", json=ticket)
    assert response.status_code == 200

    data = response.json()

    assert data["category"] == "pre_sales"
    assert data["refund"]["eligible"] is False
    
def test_same_ticket_id_does_not_process_refund_twice():
    ticket = {
        "id": "IDEMPOTENCY-001",
        "received_at": "2026-09-01T00:00:00+05:30",
        "subject": "Duplicate successful renewal",
        "body": "I was charged twice.",
        "purchases": [
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
        ],
        "app_opens_since_renewal": 0,
    }

    first = client.post("/triage", json=ticket)
    second = client.post("/triage", json=ticket)

    assert first.status_code == 200
    assert second.status_code == 200

    assert first.json() == second.json()
    assert first.json()["refund"]["eligible"] is True
    assert first.json()["refund"]["amount_inr"] == 249

def test_double_charge_claim_without_two_successful_payments_needs_human():
    ticket = next(
        t for t in load_tickets()
        if t["id"] == "T-1009"
    )

    response = client.post("/triage", json=ticket)

    assert response.status_code == 200

    data = response.json()

    assert data["category"] == "billing"
    assert data["refund"]["eligible"] is False
    assert data["refund"]["amount_inr"] == 0
    assert data["needs_human"] is True
    assert "failed payment attempt" in data["reply_draft"]
    

def test_metrics_endpoint():
    response = client.get("/metrics")

    assert response.status_code == 200

    data = response.json()

    assert "tickets_processed" in data
    assert "human_review_count" in data
    assert "human_review_rate" in data
    assert "degraded_model_count" in data

    assert 0 <= data["human_review_rate"] <= 1