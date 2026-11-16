import asyncio
import uuid
from collections import defaultdict
from typing import Any


class NotificationBroker:
    """Fan out notifications to live SSE subscribers.

    This is an in-process broker and assumes a single Uvicorn worker, which is
    how the API is currently deployed. If the app is scaled to multiple workers,
    replace this with Redis pub/sub or periodic database polling.
    """

    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
        self._subscribers: dict[uuid.UUID, set[asyncio.Queue]] = defaultdict(set)

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def subscribe(self, user_id: uuid.UUID) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._subscribers[user_id].add(queue)
        return queue

    def unsubscribe(self, user_id: uuid.UUID, queue: asyncio.Queue) -> None:
        subscribers = self._subscribers.get(user_id)
        if subscribers is None:
            return
        subscribers.discard(queue)
        if not subscribers:
            self._subscribers.pop(user_id, None)

    def publish(self, user_id: uuid.UUID, payload: dict[str, Any]) -> None:
        """Publish from any thread; delivery always happens on the event loop."""
        loop = self._loop
        if loop is not None and loop.is_running():
            loop.call_soon_threadsafe(self._dispatch, user_id, payload)
        else:
            self._dispatch(user_id, payload)

    def _dispatch(self, user_id: uuid.UUID, payload: dict[str, Any]) -> None:
        for queue in list(self._subscribers.get(user_id, ())):
            try:
                queue.put_nowait(payload)
            except asyncio.QueueFull:
                # Slow client: drop the live event. The notification is still
                # persisted and will appear when the client reloads its list.
                pass


notification_broker = NotificationBroker()
