"""Brave Search API wrapper.

Free tier: 2k requests/month, no card required at signup
(api.search.brave.com). When BRAVE_API_KEY is blank we no-op and
return an empty list, so the demo runs without the key -- the
research step degrades gracefully to "homepage only".
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.logging import get_logger
from app.settings import settings


log = get_logger(__name__)


@dataclass
class SearchHit:
    title:       str
    url:         str
    description: str


async def web_search(query: str, *, count: int = 5) -> list[SearchHit]:
    """Run a Brave web search. Empty list if no API key, on error,
    or on any non-200 response -- callers should NOT block on this.

    The free tier rate-limits us to roughly 1 req/sec; for a single
    research call we make one search so we don't bother batching.
    """
    if not settings.brave_api_key:
        return []

    headers = {
        "X-Subscription-Token": settings.brave_api_key,
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
    }
    params = {"q": query, "count": count, "safesearch": "moderate"}

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                "https://api.search.brave.com/res/v1/web/search",
                headers=headers, params=params,
            )
        if resp.status_code != 200:
            log.warning("brave.bad_status", status=resp.status_code)
            return []
        body = resp.json()
    except Exception as exc:
        log.warning("brave.failed", error=str(exc))
        return []

    items = body.get("web", {}).get("results", [])[:count]
    return [
        SearchHit(
            title=h.get("title") or "",
            url=h.get("url") or "",
            description=(h.get("description") or "").replace("<strong>", "").replace("</strong>", ""),
        )
        for h in items
    ]
