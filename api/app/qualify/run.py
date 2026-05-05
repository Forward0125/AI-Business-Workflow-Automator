"""Qualify orchestrator -- load research, score BANT, persist.

Reuses the workflow_run that the research step created so the
qualifications row attaches to the same run_id (one workflow run
ends up with both research_results and a qualifications row, which
is what the eventual workflow viz wants).

Public entry: ``qualify_lead(lead_id, pitch=None)``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app import db
from app.logging import get_logger
from app.qualify.score import BANTScore, score_bant
from app.spend_tracker import tracker as spend_tracker


log = get_logger(__name__)


@dataclass
class QualifyRunResult:
    qualification_id: int
    lead_id:          int
    run_id:           int
    score:            BANTScore


# ─── DB ops ──────────────────────────────────────────────────────


async def _load_latest_research(lead_id: int) -> dict | None:
    """Return the most recent research_results joined with its run, or None."""
    async with db.get_conn() as conn:
        row = await conn.fetchrow(
            """
            SELECT
                rr.id        AS research_id,
                rr.run_id    AS run_id,
                rr.payload   AS payload,
                rr.summary   AS summary,
                wr.lead_id   AS lead_id,
                wr.created_at
            FROM research_results rr
            JOIN workflow_runs wr ON wr.id = rr.run_id
            WHERE wr.lead_id = $1
            ORDER BY wr.created_at DESC
            LIMIT 1
            """,
            lead_id,
        )
    if row is None:
        return None
    out = dict(row)
    # asyncpg returns JSONB as a Python dict already (after register_vector
    # init? -- not in this case; default behavior is dict for jsonb).
    # Defensive: if it came back as a str, decode.
    if isinstance(out["payload"], str):
        import json
        out["payload"] = json.loads(out["payload"])
    return out


async def _persist_qualification(
    *, run_id: int, score: BANTScore,
) -> int:
    """UPSERT into qualifications by run_id. Returns qualification_id."""
    async with db.get_conn() as conn:
        return await conn.fetchval(
            """
            INSERT INTO qualifications (
                run_id,
                budget_score, authority_score, need_score, timing_score,
                composite_score, qualified, reasoning,
                model, tokens_in, tokens_out, cost_usd
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
            ON CONFLICT (run_id) DO UPDATE SET
                budget_score    = EXCLUDED.budget_score,
                authority_score = EXCLUDED.authority_score,
                need_score      = EXCLUDED.need_score,
                timing_score    = EXCLUDED.timing_score,
                composite_score = EXCLUDED.composite_score,
                qualified       = EXCLUDED.qualified,
                reasoning       = EXCLUDED.reasoning,
                model           = EXCLUDED.model,
                tokens_in       = EXCLUDED.tokens_in,
                tokens_out      = EXCLUDED.tokens_out,
                cost_usd        = EXCLUDED.cost_usd
            RETURNING id
            """,
            run_id,
            score.budget, score.authority, score.need, score.timing,
            score.composite, score.qualified, score.reasoning,
            score.model, score.tokens_in, score.tokens_out, score.cost_usd,
        )


# ─── Public API ──────────────────────────────────────────────────


async def qualify_lead(
    lead_id: int,
    *,
    pitch:   str | None = None,
) -> QualifyRunResult:
    """Score the most-recent research for a lead. Raises on missing data."""
    if not spend_tracker.under_cap():
        raise RuntimeError(
            "daily OpenAI spend cap reached -- service resumes at UTC midnight",
        )

    research = await _load_latest_research(lead_id)
    if research is None:
        raise FileNotFoundError(
            f"no research for lead {lead_id}; run /research/{lead_id} first",
        )

    profile: dict[str, Any] = research["payload"]
    score = await score_bant(profile=profile, pitch=pitch)
    spend_tracker.add(score.cost_usd)

    qualification_id = await _persist_qualification(
        run_id=research["run_id"], score=score,
    )

    log.info(
        "qualify.done",
        lead_id=lead_id,
        run_id=research["run_id"],
        qualification_id=qualification_id,
        composite=score.composite,
        qualified=score.qualified,
        cost_usd=round(score.cost_usd, 6),
    )

    return QualifyRunResult(
        qualification_id=qualification_id,
        lead_id=lead_id,
        run_id=research["run_id"],
        score=score,
    )
