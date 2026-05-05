"""POST /leads -- visitor-triggered lead intake.

Validates and fetches a company URL, writes ``leads`` + ``companies``
rows, returns a small summary. The actual workflow run (research /
qualify / personalize) is kicked off separately in step 8.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.fetch import (
    BlockedHostError,
    FetchError,
    InvalidURLError,
    TooLargeError,
)
from app.ingest.lead import intake_lead, to_summary
from app.logging import get_logger
from app.rate_limit import leads_limiter


log = get_logger(__name__)
router = APIRouter(tags=["leads"])


# ─── Schemas ─────────────────────────────────────────────────────


class CreateLeadBody(BaseModel):
    url: str = Field(..., min_length=4, max_length=2048)


class CreateLeadResponse(BaseModel):
    lead_id:       int
    company_id:    int
    domain:        str
    final_url:     str
    title:         str | None
    description:   str | None
    fetched_bytes: int
    elapsed_ms:    int
    cache_path:    str


# ─── Endpoint ────────────────────────────────────────────────────


@router.post("/leads", response_model=CreateLeadResponse)
async def create_lead(body: CreateLeadBody, request: Request) -> CreateLeadResponse:
    """Validate, fetch, and record a new lead URL."""
    ip = request.client.host if request.client else "unknown"
    ua = request.headers.get("user-agent")

    allowed, _remaining = leads_limiter.check(ip)
    if not allowed:
        raise HTTPException(
            429,
            "rate limit reached -- 5 leads per hour per IP. Try again later.",
        )

    try:
        result = await intake_lead(body.url, ip_address=ip, user_agent=ua)
    except InvalidURLError as exc:
        raise HTTPException(400, f"invalid URL: {exc}") from exc
    except BlockedHostError as exc:
        raise HTTPException(400, f"blocked host: {exc}") from exc
    except TooLargeError as exc:
        raise HTTPException(413, str(exc)) from exc
    except FetchError as exc:
        log.warning("leads.fetch_failed", url=body.url, error=str(exc))
        raise HTTPException(502, f"fetch failed: {exc}") from exc

    return CreateLeadResponse(**to_summary(result))
