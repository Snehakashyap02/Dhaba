# Dhaba Support Triage

A small FastAPI service for triaging support tickets for a subscription-based app.

The service classifies incoming tickets, assigns severity, determines whether a deterministic refund rule applies, drafts a support response, identifies cases that need human review, and handles model-output failures safely.

The implementation also includes idempotency, prompt-injection detection, bounded concurrency/load shedding, degraded-mode responses, operational metrics, and fixture/replay mode so the project can run without an external API key.

---

## 1. Project Overview

The service exposes one main endpoint:

```text
POST /triage
```

A ticket is submitted as JSON and the service returns a structured triage result containing:

- `category`
- `severity`
- `refund`
- `reply_draft`
- `needs_human`
- `confidence`

The system is designed around these safety boundaries:

1. Model output is validated before it is used.
2. Invalid model output is retried.
3. If the retry also fails, the system returns a safe degraded response.
4. Refund decisions are made by deterministic application logic rather than allowing the model to freely decide a refund.
5. Processing the same ticket ID twice returns the stored result instead of creating a second stored result.
6. Prompt-injection-like text is detected and causes human review.
7. The service can shed load when bounded in-flight capacity is full.
8. Operational logs contain request metadata rather than ticket contents.

---

## 2. Architecture

```text
                    POST /triage
                         |
                         v
                  FastAPI endpoint
                         |
                         v
                 Check ticket ID
                    /         \\
              existing        new
                 |              |
                 v              v
             return       LoadShedder
             stored          |
             result          v
                       process_ticket()
                             |
              +--------------+--------------+
              |              |              |
              v              v              v
        Injection check   Triage logic   Refund gate
              |              |              |
              +--------------+--------------+
                             |
                             v
                       Final response
                             |
                             v
                    Idempotent store
```

---

## 3. Repository Structure

```text
Dhaba_Triage/
├── app/
│   ├── __init__.py
│   ├── llm.py
│   ├── load_shedding.py
│   ├── main.py
│   ├── models.py
│   ├── refund.py
│   ├── safety.py
│   ├── store.py
│   └── triage.py
│
├── tests/
│   ├── test_llm.py
│   ├── test_load_shedding.py
│   ├── test_refund.py
│   ├── test_safety.py
│   └── test_triage.py
│
├── fixtures/
│   └── dhaba_tickets.json
│
├── scripts/
│   └── run_all_tickets.py
│
├── .env.example
├── .gitignore
├── README.md
├── requirements.txt
└── results.json
```

---

# Task 1 — Triage Endpoint

## 4. API

### `GET /health`

Basic health check.

Example:

```json
{
  "status": "ok"
}
```

### `GET /metrics`

Returns lightweight operational metrics from the in-memory store.

Example shape:

```json
{
  "tickets_processed": 12,
  "human_review_count": 3,
  "human_review_rate": 0.25,
  "degraded_model_count": 0
}
```

The main dashboard metric is:

```text
human_review_rate
```

### `POST /triage`

Accepts a ticket using the assignment's ticket schema and returns the structured triage response.

Example:

```json
{
  "category": "billing",
  "severity": "high",
  "refund": {
    "eligible": false,
    "amount_inr": 0,
    "reason": "No deterministic automatic refund rule applies."
  },
  "reply_draft": "We’ll review the payment details and help with the billing issue.",
  "needs_human": false,
  "confidence": 0.94
}
```

---

## 5. Categories and Severity

Supported categories:

```text
billing
technical
account
cancellation
feature_request
fraud
invoice
pre_sales
other
```

Supported severity levels:

```text
low
medium
high
critical
```

The model-facing result is checked against these allowed values before a final API response is returned.

---

## 6. Model Output Safety

The model-facing classification path does not trust raw model output.

The processing sequence is:

```text
model output
    |
    v
parse
    |
    v
validate
    |
    +---- valid ------> use result
    |
    +---- invalid
             |
             v
           retry
             |
             +---- valid ------> use result
             |
             +---- invalid
                       |
                       v
                 degraded result
```

`app/llm.py` validates:

- JSON/object shape
- category
- severity
- reply text
- confidence range

Confidence must be between `0.0` and `1.0`.

The tests cover valid output, JSON-string parsing, invalid categories, retry behavior, malformed JSON, and safe degradation.

---

## 7. Safe Degraded Behavior

If model processing cannot produce a valid result after retrying, the service returns a valid fallback rather than malformed output:

```json
{
  "category": "other",
  "severity": "medium",
  "reply_draft": "We’ve received your request. A support specialist will review it and get back to you.",
  "needs_human": true,
  "confidence": 0.0
}
```

A confidence of `0.0` is also counted as degraded processing in the metrics store.

---

## 8. Refund Safety

Refund decisions are intentionally separated from model classification.

The model does not freely determine the refund amount. `app/refund.py` contains deterministic application logic.

The current automatic refund rule looks for multiple successful renewal charges for the same amount on the same date.

For example:

```text
₹249 successful renewal
₹249 successful renewal
```

on the same date can produce:

```json
{
  "eligible": true,
  "amount_inr": 249,
  "reason": "Multiple successful renewal charges occurred on the same date."
}
```

A failed payment followed by a successful payment is not treated as two successful charges.

Possible unauthorized/fraud-related payment activity is not automatically refunded and is routed to human review.

---

## 9. Idempotency

The ticket ID is used as the idempotency key.

```text
First request
    |
    v
process ticket
    |
    v
store result
    |
    v
return result

Second request with same ticket ID
    |
    v
find existing result
    |
    v
return stored result
```

This makes repeated calls for an already processed ticket return the existing result instead of creating another stored result.

An automated test covers repeated processing of the same ticket.

For production, the in-memory store would be replaced by durable storage with a uniqueness constraint on ticket ID.

---

## 10. Prompt Injection Handling

Ticket bodies are treated as untrusted input.

The service detects patterns such as requests to:

- ignore previous instructions
- reveal the system prompt
- reveal internal refund rules
- approve a full refund
- act as a system-level instruction

When such content is detected:

```text
needs_human = true
```

The ticket can still be classified, but text inside the ticket does not gain authority over refund logic or application behavior.

---

# Task 2 — Replay and Evaluation

## 11. Run All 12 Tickets

The supplied fixture data can be replayed with:

```powershell
python scripts/run_all_tickets.py
```

The verified replay result is:

```text
T-1001: billing | high | refund=False | human=False
T-1002: technical | high | refund=False | human=False
T-1003: account | medium | refund=False | human=True
T-1004: cancellation | medium | refund=False | human=False
T-1005: billing | high | refund=False | human=False
T-1006: billing | high | refund=False | human=False
T-1007: feature_request | low | refund=False | human=False
T-1008: fraud | critical | refund=False | human=True
T-1009: billing | high | refund=False | human=True
T-1010: invoice | low | refund=False | human=False
T-1011: pre_sales | low | refund=False | human=True
T-1012: billing | high | refund=False | human=False

Processed 12 tickets.
Results saved to: results.json
```

### Replay results table

| Ticket | Category | Severity | Refund | Human review | Assessment |
|---|---|---|---|---|---|
| T-1001 | billing | high | No | No | Consistent with current rules |
| T-1002 | technical | high | No | No | Consistent with current rules |
| T-1003 | account | medium | No | Yes | Consistent with current rules |
| T-1004 | cancellation | medium | No | No | Consistent with current rules |
| T-1005 | billing | high | No | No | Consistent with current rules |
| T-1006 | billing | high | No | No | Consistent with current rules |
| T-1007 | feature_request | low | No | No | Consistent with current rules |
| T-1008 | fraud | critical | No | Yes | Consistent with current rules |
| T-1009 | billing | high | No | Yes | Human review is appropriate because billing evidence is ambiguous |
| T-1010 | invoice | low | No | No | Consistent with current rules |
| T-1011 | pre_sales | low | No | Yes | Injection text triggers human review |
| T-1012 | billing | high | No | No | Consistent with current rules |

---

## 12. Ambiguous Ticket: T-1009

T-1009 contains a "double charge" complaint, but the purchase records show one failed renewal and one successful renewal.

The deterministic refund gate therefore does not identify two successful charges.

The system returns:

```text
category: billing
severity: high
refund: false
needs_human: true
```

The reply explains that there is one successful renewal and one failed payment attempt and that a support specialist should review the billing details.

When the wording and records do not establish the automatic refund condition, the system does not guess. It leaves the refund amount at zero and routes the ticket to human review.

---

## 13. Ticket Text Addressed to the Assistant

### T-1003

T-1003 is an account/order-history issue after a phone change. Its body also contains text presented as a fake system instruction asking the automated support assistant to approve a refund.

The system behavior is:

```text
category: account
severity: medium
refund: false
needs_human: true
```

The injected instruction does not control the refund gate.

### T-1011

T-1011 is a pre-sales question about whether the premium plan works offline. Its body also includes text asking the automated agent to reveal the system prompt and internal refund rules.

The system behavior is:

```text
category: pre_sales
severity: low
refund: false
needs_human: true
```

The application does not reveal internal instructions, and the text in the ticket is treated as untrusted input.

---

## 14. Dashboard Metric

The main operational metric is:

```text
human_review_rate
```

It is calculated as:

```text
tickets requiring human review
--------------------------------
uniquely processed tickets
```

The `/metrics` endpoint also exposes:

- `tickets_processed`
- `human_review_count`
- `human_review_rate`
- `degraded_model_count`

---

# Task 3 — Backend Track

## 15. Outage / 50 Tickets per Second Scenario

During an outage the endpoint may receive approximately 50 tickets per second.

The service uses bounded concurrency and a short acquisition timeout so work does not grow without bound.

Current configuration:

```text
max_in_flight = 10
acquire_timeout_seconds = 0.05
```

When capacity cannot be acquired within the timeout, the request enters degraded mode instead of waiting indefinitely.

---

## 16. What a User Gets During Degradation

The API continues returning the documented response shape.

The degraded response tells the user that the request was received and a support specialist will review it.

Example:

```json
{
  "category": "other",
  "severity": "medium",
  "refund": {
    "eligible": false,
    "amount_inr": 0,
    "reason": "No deterministic automatic refund rule applies."
  },
  "reply_draft": "We’re receiving a high volume of support requests. A support specialist will review your request and get back to you.",
  "needs_human": true,
  "confidence": 0.0
}
```

The goal is to remain responsive and preserve the response contract instead of failing under load.

---

## 17. Storage Design

The take-home implementation uses an in-memory store.

For production, I would use durable storage.

### `tickets`

```text
id                  PRIMARY KEY
received_at
subject
body
created_at
```

### `triage_results`

```text
ticket_id           PRIMARY KEY / UNIQUE
category
severity
refund_eligible
refund_amount_inr
refund_reason
reply_draft
needs_human
confidence
created_at
```

### `processing_events`

```text
id
ticket_id
request_id
status
degraded
duration_ms
created_at
```

The unique constraint on `triage_results.ticket_id` provides a durable idempotency boundary and allows the system to survive process restarts.

---

## 18. One Thing Added for 3am Debugging

The endpoint records a request/correlation ID and request duration without logging ticket contents.

Example normal request:

```text
request_id=... path=/triage status=200 duration_ms=3.03 degraded=false
```

Example idempotent replay:

```text
request_id=... path=/triage status=200 duration_ms=0.59 degraded=false idempotent=true
```

Example degraded request:

```text
request_id=... path=/triage status=200 duration_ms=51.27 degraded=true
```

This provides a starting point for debugging request behavior and latency without putting ticket contents or identifying customer/company information into logs.

---

# Task 4 — AI Usage Disclosure

## Agents Used

ChatGPT was used as a coding and review assistant during the take-home.

## Approximate Share of Code Written With AI Assistance

Approximately 70% of the implementation was produced with AI assistance, with the code then run, tested, reviewed, and adjusted locally.

## Single Best Prompt Used

The most useful scope-control prompt in this work was:

> no dont add anything extra. stick to proj and tell me anything left for the project?

This kept the implementation focused on the assignment rather than adding unrelated features.

## One Thing the Agent Got Wrong

An early implementation treated a billing complaint too broadly. The purchase records showed one failed payment followed by one successful payment, which did not establish a duplicate successful charge. The issue was caught by checking the supplied ticket data and was corrected by keeping the refund decision in deterministic application logic and routing ambiguous billing cases to human review.

## One Hand-Written / Directly Controlled Part

The deterministic refund gate was kept under direct application control. The classification layer can identify the issue and draft the response, but refund eligibility and amount are calculated from purchase records using explicit rules.

---

# 19. Tests

The final verified test run was:

```text
19 passed in 2.77s
```

Command used:

```powershell
python -m pytest -q
```

The test suite covers:

- API health
- valid triage responses
- all supplied ticket fixtures
- prompt-injection detection
- refund rules
- idempotency
- model-output validation
- retry behavior
- safe degradation
- load shedding

---

# 20. Verified Local Run

The API was successfully started with:

```powershell
uvicorn app.main:app --reload
```

The server started successfully on:

```text
http://127.0.0.1:8000
```

The triage endpoint returned HTTP 200 during local replay, and operational logs included request IDs, latency, and degraded-state information without logging ticket contents.

---

# 21. Fixture / Replay Mode

The project can run without an external API key.

Fixture data:

```text
fixtures/dhaba_tickets.json
```

Replay script:

```text
scripts/run_all_tickets.py
```

Replay command:

```powershell
python scripts/run_all_tickets.py
```

Verified output:

```text
Processed 12 tickets.
Results saved to: results.json
```

This provides a deterministic evaluation path for a clean machine.

---

# 22. Local Setup

## Requirements

Python 3.11+ is recommended.

Create a virtual environment:

```powershell
python -m venv venv
```

Activate it:

```powershell
.\venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
pip install -r requirements.txt
```

---

# 23. Run the API

From the project root:

```powershell
uvicorn app.main:app --reload
```

Interactive API documentation:

```text
http://127.0.0.1:8000/docs
```

Endpoints:

```text
GET  /health
GET  /metrics
POST /triage
```

---

# 24. Run Tests

```powershell
python -m pytest -q
```

Verified result:

```text
19 passed in 2.77s
```

---

# 25. Run the 12-Ticket Replay

```powershell
python scripts/run_all_tickets.py
```

Verified result:

```text
T-1001: billing | high | refund=False | human=False
T-1002: technical | high | refund=False | human=False
T-1003: account | medium | refund=False | human=True
T-1004: cancellation | medium | refund=False | human=False
T-1005: billing | high | refund=False | human=False
T-1006: billing | high | refund=False | human=False
T-1007: feature_request | low | refund=False | human=False
T-1008: fraud | critical | refund=False | human=True
T-1009: billing | high | refund=False | human=True
T-1010: invoice | low | refund=False | human=False
T-1011: pre_sales | low | refund=False | human=True
T-1012: billing | high | refund=False | human=False

Processed 12 tickets.
Results saved to: results.json
```

---

# 26. Clean-Machine Run

From a fresh checkout:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m pytest -q
python scripts/run_all_tickets.py
uvicorn app.main:app --reload
```

No API key is required for fixture/replay mode.

---

# 27. Known Limitations

This is a take-home implementation rather than a production deployment.

Current limitations include:

- the result store is in memory
- production persistence would require a database
- the fixture/replay path is deterministic
- load shedding is intentionally simple
- production deployment would require durable idempotency and distributed coordination
- the refund component produces a refund decision; an actual payment/refund execution system is outside the assignment scope
- fixture-mode reply templates are deterministic English templates rather than a live language-aware generation service

---

# 28. Design Decisions

### Why validate model output?

Model-shaped output can be malformed or contain values outside the application's supported schema. Validation keeps the API contract stable.

### Why retry?

A single malformed result should not immediately force degradation if a retry can recover.

### Why degrade?

The API should continue returning a valid response when model processing cannot safely complete.

### Why separate refund logic?

Refunds affect money. The application owns the financial decision boundary instead of allowing generated text to determine the refund.

### Why detect prompt injection?

Ticket bodies are untrusted user input. Instructions inside a ticket should not override system behavior.

### Why use idempotency?

Support requests can be retried. The same ticket ID should not create a second independent processing result.

### Why shed load?

During an outage, unbounded work can cause the service to fail completely. Bounded in-flight processing allows the service to remain responsive and return a safe degraded response instead.

---

# 29. Final Submission Checklist

- [x] `python -m pytest -q` passes
- [x] 19 tests pass
- [x] All 12 tickets replay successfully
- [x] `results.json` generated successfully
- [x] T-1003 prompt-injection behavior documented
- [x] T-1011 prompt-injection behavior documented
- [x] T-1009 ambiguity and human-review behavior documented
- [x] Dashboard metric documented
- [x] Backend load-shedding design documented
- [x] Degraded user behavior documented
- [x] Production storage design documented
- [x] 3am debugging improvement documented
- [x] AI usage disclosure included
- [x] Fixture/replay mode documented
- [x] Clean-machine run instructions included

Do not commit:

```text
.env
venv/
__pycache__/
.pytest_cache/
```

Final Git check:

```powershell
git status
```

Expected final state:

```text
nothing to commit, working tree clean
```

---

# 30. Submission

Submit the GitHub repository link using the repository configured for the assignment and ensure the repository is accessible to the Propel hiring team.

The repository should contain:

```text
README.md
app/
tests/
fixtures/
scripts/
requirements.txt
.gitignore
.env.example
```

Final verified local results:

```text
19 passed in 2.77s
```

and:

```text
Processed 12 tickets.
Results saved to: results.json
```
