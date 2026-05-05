"""POST /research/{lead_id} -- run the LLM research extraction.

Admin / test endpoint for now. The full workflow run (research +
qualify + personalize + mocked actions) ships in step 10.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.logging import get_logger
from app.research.run import research_for_lead


log = get_logger(__name__)
router = APIRouter(tags=["research"])


class ResearchResponse(BaseModel):
    research_id:           int
    lead_id:               int
    domain:                str
    payload:               dict[str, Any]
    summary:               str | None
    search_results_count:  int
    fetched_bytes:         int
    model:                 str
    tokens_in:             int
    tokens_out:            int
    cost_usd:              float


@router.post("/research/{lead_id}", response_model=ResearchResponse)
async def post_research(lead_id: int) -> ResearchResponse:
    try:
        r = await research_for_lead(lead_id)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(409, str(exc)) from exc
    except RuntimeError as exc:
        # spend cap reached
        raise HTTPException(503, str(exc)) from exc

    return ResearchResponse(
        research_id=r.research_id, lead_id=r.lead_id, domain=r.domain,
        payload=r.payload, summary=r.summary,
        search_results_count=r.search_results_count,
        fetched_bytes=r.fetched_bytes,
        model=r.model, tokens_in=r.tokens_in, tokens_out=r.tokens_out,
        cost_usd=r.cost_usd,
    )
