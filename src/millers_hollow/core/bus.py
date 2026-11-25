import asyncio
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Output:
    content: str
    channel: str
    stream: bool = False
    end: bool = False


class OutputBus:
    def __init__(self) -> None:
        self.subscribers: dict[asyncio.Queue[Output], asyncio.Task[None]] = {}

    def restart(self) -> None:
        pass

    def subscribe(
        self, consumer: Callable[[asyncio.Queue[Output]], Coroutine[Any, Any, None]]
    ) -> asyncio.Queue[Output]:
        queue = asyncio.Queue[Output]()
        task = asyncio.create_task(consumer(queue))
        self.subscribers[queue] = task
        return queue

    async def unsubscribe(self, queue: asyncio.Queue[Output]) -> None:
        task = self.subscribers.pop(queue)
        queue.shutdown()
        await task

    def publish(self, output: Output) -> None:
        for queue in self.subscribers:
            queue.put_nowait(output)

    async def close(self) -> None:
        subscribers = self.subscribers.copy()
        self.subscribers.clear()
        for queue in subscribers:
            queue.shutdown()
        await asyncio.gather(*subscribers.values())
