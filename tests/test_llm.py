import json

from app import llm
from app.models import Ticket


def make_ticket():
    return Ticket(
        id="TEST-LLM",
        received_at="2026-09-01T00:00:00+05:30",
        subject="Test ticket",
        body="Please help with my account.",
        purchases=[],
        app_opens_since_renewal=0,
    )


def valid_output():
    return {
        "category": "account",
        "severity": "medium",
        "reply_draft": "We will help with your account.",
        "confidence": 0.95,
    }


def test_validate_accepts_valid_dict():
    result = llm.validate_model_output(valid_output())

    assert result.category == "account"
    assert result.severity == "medium"
    assert result.confidence == 0.95


def test_validate_accepts_valid_json_string():
    result = llm.validate_model_output(
        json.dumps(valid_output())
    )

    assert result.category == "account"


def test_invalid_category_is_rejected():
    raw = valid_output()
    raw["category"] = "not_a_real_category"

    try:
        llm.validate_model_output(raw)
        assert False, "Expected invalid category to be rejected"
    except ValueError as exc:
        assert "Invalid category" in str(exc)


def test_retry_succeeds_after_first_invalid_response(monkeypatch):
    responses = [
        {
            "category": "made_up_category",
            "severity": "medium",
            "reply_draft": "bad output",
            "confidence": 0.5,
        },
        valid_output(),
    ]

    def fake_model(ticket):
        return responses.pop(0)

    monkeypatch.setattr(
        llm,
        "triage_with_fixture",
        fake_model,
    )

    result = llm.triage_ticket(make_ticket())

    assert result["category"] == "account"
    assert result["confidence"] == 0.95
    assert responses == []


def test_malformed_json_then_valid_json_retries(monkeypatch):
    responses = [
        '{"category": "account", "severity": "medium"',
        json.dumps(valid_output()),
    ]

    def fake_model(ticket):
        return responses.pop(0)

    monkeypatch.setattr(
        llm,
        "triage_with_fixture",
        fake_model,
    )

    result = llm.triage_ticket(make_ticket())

    assert result["category"] == "account"
    assert result["confidence"] == 0.95


def test_two_invalid_responses_degrade_safely(monkeypatch):
    responses = [
        "The ticket looks like an account problem.",
        '{"category": "account"',
    ]

    def fake_model(ticket):
        return responses.pop(0)

    monkeypatch.setattr(
        llm,
        "triage_with_fixture",
        fake_model,
    )

    result = llm.triage_ticket(make_ticket())

    assert result["category"] == "other"
    assert result["severity"] == "medium"
    assert result["confidence"] == 0.0
    assert "support specialist" in result["reply_draft"]