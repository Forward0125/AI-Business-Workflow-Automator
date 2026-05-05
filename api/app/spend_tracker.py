"""Daily OpenAI spend tracker (in-memory, per process).

Resets at UTC midnight. Used by /research, /workflows/runs and any
other endpoint that calls OpenAI as a hard floor against runaway
costs in the public demo.

Not durable across restarts. For a single-instance deploy that's
acceptable; for multi-instance scale-out, swap to Redis with TTL'd
keys.
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone

from app.logging import get_logger
from app.settings import settings


log = get_logger(__name__)


class SpendTracker:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._date: str = ""
        self._spent_usd: float = 0.0

    def _today(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def _maybe_roll(self) -> None:
        today = self._today()
        if today != self._date:
            if self._date:
                log.info(
                    "spend.day_rolled",
                    previous_date=self._date,
                    previous_total_usd=round(self._spent_usd, 4),
                )
            self._date = today
            self._spent_usd = 0.0

    def remaining(self) -> float:
        with self._lock:
            self._maybe_roll()
            return settings.daily_spend_cap_usd - self._spent_usd

    def under_cap(self) -> bool:
        return self.remaining() > 0.0

    def add(self, usd: float) -> float:
        with self._lock:
            self._maybe_roll()
            self._spent_usd += max(0.0, usd)
            total = self._spent_usd
        if total > settings.daily_spend_cap_usd:
            log.warning(
                "spend.over_cap",
                total_usd=round(total, 4),
                cap_usd=settings.daily_spend_cap_usd,
            )
        return total

    def snapshot(self) -> dict:
        with self._lock:
            self._maybe_roll()
            return {
                "date":      self._date,
                "spent_usd": round(self._spent_usd, 6),
                "cap_usd":   settings.daily_spend_cap_usd,
                "remaining": round(settings.daily_spend_cap_usd - self._spent_usd, 6),
            }


# One tracker per process.
tracker = SpendTracker()


# ─── OpenAI pricing table (USD per 1M tokens, Apr 2026) ──────────


PRICES_USD_PER_1M: dict[str, tuple[float, float]] = {
    "gpt-4o-mini":  (0.15,  0.60),
    "gpt-4o":       (2.50, 10.00),
    "gpt-5-mini":   (0.25,  2.00),
    "gpt-5":        (1.25, 10.00),
}


def calc_cost(model: str, tokens_in: int, tokens_out: int) -> float:
    """Cost in USD for an OpenAI call. Returns 0 for unknown models."""
    in_p, out_p = PRICES_USD_PER_1M.get(model, (0.0, 0.0))
    return (tokens_in * in_p + tokens_out * out_p) / 1_000_000
