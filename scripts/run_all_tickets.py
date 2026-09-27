import json
from pathlib import Path

import httpx


BASE_DIR = Path(__file__).resolve().parents[1]
TICKETS_FILE = BASE_DIR / "fixtures" / "dhaba_tickets.json"
RESULTS_FILE = BASE_DIR / "results.json"

API_URL = "http://127.0.0.1:8000/triage"


def main():
    with open(TICKETS_FILE, "r", encoding="utf-8") as file:
        data = json.load(file)

    tickets = data["tickets"]

    results = []

    with httpx.Client(timeout=10.0) as client:
        for ticket in tickets:
            ticket_id = ticket["id"]

            try:
                response = client.post(
                    API_URL,
                    json=ticket,
                )

                response.raise_for_status()

                result = response.json()

                results.append({
                    "ticket_id": ticket_id,
                    "status": "success",
                    "result": result,
                })

                print(
                    f"{ticket_id}: "
                    f"{result['category']} | "
                    f"{result['severity']} | "
                    f"refund={result['refund']['eligible']} | "
                    f"human={result['needs_human']}"
                )

            except Exception as exc:
                results.append({
                    "ticket_id": ticket_id,
                    "status": "error",
                    "error": str(exc),
                })

                print(
                    f"{ticket_id}: ERROR - {exc}"
                )

    with open(
        RESULTS_FILE,
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            results,
            file,
            indent=2,
            ensure_ascii=False,
        )

    print()
    print(f"Processed {len(tickets)} tickets.")
    print(f"Results saved to: {RESULTS_FILE}")


if __name__ == "__main__":
    main()