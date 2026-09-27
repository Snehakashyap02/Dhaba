import asyncio
import time

from app.load_shedding import LoadShedder


def test_load_shedder_rejects_when_capacity_is_full():
    async def scenario():
        shedder = LoadShedder(
            max_in_flight=1,
            acquire_timeout_seconds=0.01,
        )

        first_started = asyncio.Event()
        release_first = asyncio.Event()

        def first_work():
            first_started.set()

            while not release_first.is_set():
                time.sleep(0.001)

            return "first"

        first_task = asyncio.create_task(
            shedder.try_run(first_work)
        )

        await first_started.wait()

        second_result = await shedder.try_run(
            lambda: "second"
        )

        assert second_result is None

        release_first.set()

        assert await first_task == "first"

    asyncio.run(scenario())