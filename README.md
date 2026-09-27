# Dhaba Support Triage

A small FastAPI service for triaging Dhaba support tickets.

The implementation focuses on the parts of the assignment that are safety-
critical in production: stable structured output, a refund decision that is
independent from the model, idempotency, prompt-injection handling, safe
degradation, fixture/replay mode, and basic operational monitoring.

---

## Assignment coverage

### Task 1 — Service

Implemented:

- `POST /triage`
- structured request/response validation with Pydantic
- category and severity enums
- deterministic refund gate
- prompt-injection detection
- `needs_human` routing
- model-output validation
- validate → retry → degrade behavior
- ticket-ID idempotency
- fixture mode without an API key
- sanitized operational logging
- `/health`
- `/metrics`

### Task 2 — Make it not lie

Implemented:

- replay of all 12 supplied tickets
- replay output written to `results.json`
- prompt-injection tests for the two tickets that address the assistant
- ambiguous billing case handling
- human-review routing when the system cannot safely determine an outcome
- dashboard metric: `human_review_rate`

### Task 3 — Backend track

Implemented:

- bounded in-flight triage work
- fast load shedding when capacity is unavailable
- safe degraded response during overload
- PostgreSQL production storage design documented
- request/correlation IDs for debugging
- operational logs that do not contain ticket contents

### Task 4 — AI usage

Documented at the end of this README.

---

# Architecture

The service treats ticket content as untrusted user input.

The model/fixture layer is responsible for classification and drafting a reply.

The model does **not** control refunds.

Refund eligibility and refund amount are calculated separately from structured
billing evidence by deterministic application code.

High-level flow:

```text
                    +----------------------+
                    |      POST /triage    |
                    +----------+-----------+
                               |
                               v
                    +----------------------+
                    | Prompt-injection     |
                    | detection             |
                    +----------+-----------+
                               |
                               v
                    +----------------------+
                    | Model / fixture      |
                    | triage               |
                    +----------+-----------+
                               |
                               v
                    +----------------------+
                    | Parse + validate     |
                    | structured output    |
                    +----------+-----------+
                               |
                 +-------------+-------------+
                 |                           |
              invalid                      valid
                 |                           |
                 v                           v
          retry once                deterministic refund
                 |                           |
                 v                           |
            invalid again                    |
                 |                           |
                 v                           v
          safe degraded              human-review logic
             response                      |
                 |                           |
                 +-------------+-------------+
                               |
                               v
                       Triage response