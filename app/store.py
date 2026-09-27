from typing import Any


class TicketStore:
    def __init__(self):
        self.results: dict[str, Any] = {}
        self.processed_count = 0
        self.human_review_count = 0
        self.degraded_count = 0

    def get(self, ticket_id: str):
        return self.results.get(ticket_id)

    def save(self, ticket_id: str, result) -> bool:
        # Idempotency: never count/process the same ticket twice.
        if ticket_id in self.results:
            return False

        self.results[ticket_id] = result
        self.processed_count += 1

        if result.needs_human:
            self.human_review_count += 1

        if result.confidence == 0.0:
            self.degraded_count += 1

        return True

    def metrics(self) -> dict:
        if self.processed_count == 0:
            human_review_rate = 0.0
        else:
            human_review_rate = (
                self.human_review_count / self.processed_count
            )

        return {
            "tickets_processed": self.processed_count,
            "human_review_count": self.human_review_count,
            "human_review_rate": round(human_review_rate, 4),
            "degraded_model_count": self.degraded_count,
        }


store = TicketStore()