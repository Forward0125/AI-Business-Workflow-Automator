"""In-memory event broker for live workflow progress.

Same pub/sub primitive as InsightFinder. The API process runs
background jobs with ``asyncio.create_task``; any number of SSE
consumers can subscribe to a run's queue. End-of-stream sentinel
auto-cleanup.

Not durable across process restarts -- a visitor reconnecting mid-run
sees state via DB polling (``GET /workflows/runs/{id}``), not the
event stream.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any


END_EVENT: dict[str, Any] = {"type": "stream.end"}


class JobBroker:
    """Pub/sub for workflow-run events, keyed by run_id."""

    def __init__(self) -> None:
        self._subscribers: dict[int, list[asyncio.Queue]] = defaultdict(list)

    def subscribe(self, run_id: int) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=200)
        self._subscribers[run_id].append(q)
        return q

    def unsubscribe(self, run_id: int, queue: asyncio.Queue) -> None:
        try:
            self._subscribers[run_id].remove(queue)
        except (KeyError, ValueError):
            pass
        if not self._subscribers.get(run_id):
            self._subscribers.pop(run_id, None)

    async def emit(self, run_id: int, event: dict[str, Any]) -> None:
        for q in list(self._subscribers.get(run_id, [])):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                pass  # drop on backpressure rather than block the producer

    async def end(self, run_id: int) -> None:
        await self.emit(run_id, END_EVENT)
        self._subscribers.pop(run_id, None)


# One broker per process.
broker = JobBroker()
