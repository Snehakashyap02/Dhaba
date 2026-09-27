import time
import uuid

from fastapi import FastAPI, HTTPException, Request

from .load_shedding import LoadShedder
from .models import Ticket, TriageResponse
from .store import store
from .triage import degraded_ticket_response, process_ticket


app = FastAPI(
    title="Dhaba Support Triage",
    version="0.1.0",
)

load_shedder = LoadShedder(
    max_in_flight=10,
    acquire_timeout_seconds=0.05,
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/metrics")
def metrics():
    return store.metrics()


@app.post("/triage", response_model=TriageResponse)
async def triage(ticket: Ticket, request: Request):
    started_at = time.perf_counter()

    request_id = request.headers.get(
        "X-Request-ID",
        str(uuid.uuid4()),
    )

    existing = store.get(ticket.id)

    if existing is not None:
        duration_ms = round(
            (time.perf_counter() - started_at) * 1000,
            2,
        )

        print(
            f"request_id={request_id} "
            f"path=/triage "
            f"status=200 "
            f"duration_ms={duration_ms} "
            f"degraded=false "
            f"idempotent=true"
        )

        return existing

    try:
        result = await load_shedder.try_run(
            lambda: process_ticket(ticket)
        )

        if result is None:
            result = degraded_ticket_response(ticket)
            store.save(ticket.id, result)

            duration_ms = round(
                (time.perf_counter() - started_at) * 1000,
                2,
            )

            print(
                f"request_id={request_id} "
                f"path=/triage "
                f"status=200 "
                f"duration_ms={duration_ms} "
                f"degraded=true"
            )

            return result

        store.save(ticket.id, result)

        duration_ms = round(
            (time.perf_counter() - started_at) * 1000,
            2,
        )

        print(
            f"request_id={request_id} "
            f"path=/triage "
            f"status=200 "
            f"duration_ms={duration_ms} "
            f"degraded=false"
        )

        return result

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Unable to process ticket safely",
        ) from exc