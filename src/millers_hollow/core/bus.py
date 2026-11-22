import asyncio
from dataclasses import dataclass


@dataclass(frozen=True)
class Output:
    content: str
    channel: str
    stream: bool = False
    end: bool = False


class OutputBus:
    def __init__(self) -> None:
        self.queues: list[asyncio.Queue[Output]] = []

    def subscribe(self) -> asyncio.Queue[Output]:
        queue: asyncio.Queue[Output] = asyncio.Queue()
        self.queues.append(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[Output]) -> None:
        self.queues.remove(queue)

    def publish(self, output: Output) -> None:
        for queue in self.queues:
            queue.put_nowait(output)

    def close(self) -> None:
        for queue in self.queues:
            queue.shutdown()
