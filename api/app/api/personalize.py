"""POST /personalize/{lead_id} -- draft a personalized outreach email."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.logging import get_logger
from app.personalize.draft import ALLOWED_TONES, DEFAULT_TONE
from app.personalize.run import personalize_lead


log = get_logger(__name__)
router = APIRouter(tags=["personalize"])


class PersonalizeRequest(BaseModel):
    tone:  Literal["technical", "executive", "casual"] = DEFAULT_TONE
    pitch: str | None = Field(default=None, max_length=2000)


class PersonalizeResponse(BaseModel):
    email_draft_id:    int
    lead_id:           int
    run_id:            int

    tone:              str
    subject:           str
    body:              str
    cited_findings:    list[str]
    unknown_citations: list[str]

    model:      str
    tokens_in:  int
    tokens_out: int
    cost_usd:   float


@router.post("/personalize/{lead_id}", response_model=PersonalizeResponse)
async def post_personalize(
    lead_id: int, body: PersonalizeRequest | None = None,
) -> PersonalizeResponse:
    body = body or PersonalizeRequest()

    if body.tone not in ALLOWED_TONES:
        raise HTTPException(400, f"unknown tone: {body.tone!r}")

    try:
        r = await personalize_lead(lead_id, tone=body.tone, pitch=body.pitch)
    except FileNotFoundError as exc:
        raise HTTPException(409, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc

    d = r.draft
    return PersonalizeResponse(
        email_draft_id=r.email_draft_id,
        lead_id=r.lead_id,
        run_id=r.run_id,
        tone=d.tone,
        subject=d.subject,
        body=d.body,
        cited_findings=d.cited_findings,
        unknown_citations=d.unknown_citations,
        model=d.model,
        tokens_in=d.tokens_in,
        tokens_out=d.tokens_out,
        cost_usd=d.cost_usd,
    )
