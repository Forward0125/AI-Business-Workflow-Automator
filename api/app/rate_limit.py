"""In-memory IP rate limiter.

Defensive against the public-demo case where one visitor (or a bot)
could rip through OpenAI credits by spamming /leads. Same pattern as
InsightFinder's app.rate_limit.

Not durable across process restarts. For a single-instance deploy
that's acceptable; for a multi-instance scale-out we'd swap to Redis.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from app.settings import settings


class IPRateLimiter:
    """Sliding-window IP rate limit, thread-safe."""

    def __init__(self, max_events: int, window_seconds: float) -> None:
        self.max_events     = max_events
        self.window_seconds = window_seconds
        self._records: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, ip: str) -> tuple[bool, int]:
        now = time.monotonic()
        cutoff = now - self.window_seconds
        with self._lock:
            q = self._records[ip]
            while q and q[0] < cutoff:
                q.popleft()
            if len(q) >= self.max_events:
                return False, 0
            q.append(now)
            return True, self.max_events - len(q)


# Module-level singletons -- one per protected endpoint.
leads_limiter = IPRateLimiter(
    max_events=settings.workflow_runs_per_hour, window_seconds=3600.0,
)
