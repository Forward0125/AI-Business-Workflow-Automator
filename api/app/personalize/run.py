"""Personalize orchestrator -- load research + qualification, draft, persist.

Reuses the same workflow_run that research and qualify wrote to, so
the email_drafts row attaches to the same run.

Public entry: ``personalize_lead(lead_id, tone=None, pitch=None)``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from app import db
from app.logging import get_logger
from app.personalize.draft import (
    DEFAULT_TONE,
    EmailDraft,
    Tone,
    draft_email,
)
from app.spend_tracker import tracker as spend_tracker


log = get_logger(__name__)


@dataclass
class PersonalizeRunResult:
    email_draft_id: int
    lead_id:        int
    run_id:         int
    draft:          EmailDraft


# ─── DB ops ──────────────────────────────────────────────────────


async def _load_context(lead_id: int) -> dict | None:
    """Load the latest research + (optional) qualification for a lead."""
    async with db.get_conn() as conn:
        row = await conn.fetchrow(
            """
            SELECT
                rr.run_id  AS run_id,
                rr.payload AS profile,
                q.budget_score, q.authority_score, q.need_score,
                q.timing_score, q.composite_score, q.qualified,
                q.reasoning AS qual_reasoning
            FROM research_results rr
            JOIN workflow_runs wr ON wr.id = rr.run_id
            LEFT JOIN qualifications q ON q.run_id = rr.run_id
            WHERE wr.lead_id = $1
            ORDER BY wr.created_at DESC
            LIMIT 1
            """,
            lead_id,
        )
    if row is None:
        return None
    out = dict(row)
    if isinstance(out["profile"], str):
        out["profile"] = json.loads(out["profile"])
    return out


async def _persist_draft(
    *, run_id: int, draft: EmailDraft,
) -> int:
    """Insert a new email_drafts row. Multiple drafts per run are allowed
    (tone variants, regeneration). Returns the id."""
    async with db.get_conn() as conn:
        return await conn.fetchval(
            """
            INSERT INTO email_drafts (
                run_id, tone, subject, body, cited_findings,
                model, tokens_in, tokens_out, cost_usd
            )
            VALUES ($1, $2, $3, $4, $5::jsonb, $6, $7, $8, $9)
            RETURNING id
            """,
            run_id,
            draft.tone, draft.subject, draft.body,
            json.dumps(draft.cited_findings),
            draft.model, draft.tokens_in, draft.tokens_out, draft.cost_usd,
        )


# ─── Public API ──────────────────────────────────────────────────


async def personalize_lead(
    lead_id: int,
    *,
    tone:    Tone = DEFAULT_TONE,
    pitch:   str | None = None,
) -> PersonalizeRunResult:
    """Draft a personalized email for the latest research on this lead."""
    if not spend_tracker.under_cap():
        raise RuntimeError(
            "daily OpenAI spend cap reached -- service resumes at UTC midnight",
        )

    ctx = await _load_context(lead_id)
    if ctx is None:
        raise FileNotFoundError(
            f"no research for lead {lead_id}; run /research/{lead_id} first",
        )

    qualification: dict | None = None
    if ctx.get("composite_score") is not None:
        qualification = {
            "budget":    ctx["budget_score"],
            "authority": ctx["authority_score"],
            "need":      ctx["need_score"],
            "timing":    ctx["timing_score"],
            "composite": ctx["composite_score"],
            "qualified": ctx["qualified"],
            "reasoning": ctx["qual_reasoning"],
        }

    draft = await draft_email(
        profile=ctx["profile"],
        qualification=qualification,
        pitch=pitch,
        tone=tone,
    )
    spend_tracker.add(draft.cost_usd)

    email_draft_id = await _persist_draft(run_id=ctx["run_id"], draft=draft)

    log.info(
        "personalize.done",
        lead_id=lead_id,
        run_id=ctx["run_id"],
        email_draft_id=email_draft_id,
        tone=draft.tone,
        cited=len(draft.cited_findings),
        unknown=len(draft.unknown_citations),
        cost_usd=round(draft.cost_usd, 6),
    )

    return PersonalizeRunResult(
        email_draft_id=email_draft_id,
        lead_id=lead_id,
        run_id=ctx["run_id"],
        draft=draft,
    )
