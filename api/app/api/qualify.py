"""POST /qualify/{lead_id} -- BANT scoring on the most-recent research.

Admin/test endpoint for now. The full workflow run (research +
qualify + personalize + mocked actions) ships in step 10.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.logging import get_logger
from app.qualify.run import qualify_lead


log = get_logger(__name__)
router = APIRouter(tags=["qualify"])


class QualifyRequest(BaseModel):
    """Optional override of the default pitch; visible to the LLM."""
    pitch: str | None = Field(default=None, max_length=2000)


class QualifyResponse(BaseModel):
    qualification_id: int
    lead_id:          int
    run_id:           int

    budget_score:    float
    authority_score: float
    need_score:      float
    timing_score:    float
    composite_score: float
    qualified:       bool
    reasoning:       str

    model:      str
    tokens_in:  int
    tokens_out: int
    cost_usd:   float


@router.post("/qualify/{lead_id}", response_model=QualifyResponse)
async def post_qualify(
    lead_id: int, body: QualifyRequest | None = None,
) -> QualifyResponse:
    pitch = body.pitch if body else None
    try:
        r = await qualify_lead(lead_id, pitch=pitch)
    except FileNotFoundError as exc:
        raise HTTPException(409, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc

    s = r.score
    return QualifyResponse(
        qualification_id=r.qualification_id,
        lead_id=r.lead_id,
        run_id=r.run_id,
        budget_score=s.budget,
        authority_score=s.authority,
        need_score=s.need,
        timing_score=s.timing,
        composite_score=s.composite,
        qualified=s.qualified,
        reasoning=s.reasoning,
        model=s.model,
        tokens_in=s.tokens_in,
        tokens_out=s.tokens_out,
        cost_usd=s.cost_usd,
    )
