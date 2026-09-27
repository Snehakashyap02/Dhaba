import asyncio
from collections.abc import Callable
from typing import TypeVar


T = TypeVar("T")


class LoadShedder:
    def __init__(
        self,
        max_in_flight: int = 10,
        acquire_timeout_seconds: float = 0.05,
    ):
        self._semaphore = asyncio.Semaphore(max_in_flight)
        self.acquire_timeout_seconds = acquire_timeout_seconds

    async def try_run(self, fn: Callable[[], T]) -> T | None:
        try:
            await asyncio.wait_for(
                self._semaphore.acquire(),
                timeout=self.acquire_timeout_seconds,
            )
        except TimeoutError:
            return None

        try:
            return await asyncio.to_thread(fn)
        finally:
            self._semaphore.release()