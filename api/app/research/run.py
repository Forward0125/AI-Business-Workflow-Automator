"""Research orchestrator -- ties Brave + LLM extraction + DB write.

Public entry: ``research_for_lead(lead_id)``. Looks up the lead,
loads the cached HTML, optionally web-searches, runs the LLM, writes
``research_results`` and updates ``companies`` with the freshly-
extracted name + industry.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from app import db
from app.logging import get_logger
from app.research import brave, extract
from app.settings import PROJECT_ROOT
from app.spend_tracker import tracker as spend_tracker


log = get_logger(__name__)

CACHE_ROOT = PROJECT_ROOT / "data" / "raw"


# ─── Result ──────────────────────────────────────────────────────


@dataclass
class ResearchRunResult:
    research_id:           int
    lead_id:               int
    domain:                str
    payload:               dict
    summary:               str | None
    search_results_count:  int
    fetched_bytes:         int
    model:                 str
    tokens_in:             int
    tokens_out:            int
    cost_usd:              float


# ─── HTML cache resolution ──────────────────────────────────────


def _latest_cached_html(domain: str) -> bytes | None:
    """Pick the most recently written .html in data/raw/<domain>/."""
    folder = CACHE_ROOT / domain
    if not folder.exists():
        return None
    files = sorted(folder.glob("*.html"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        return None
    return files[0].read_bytes()


# ─── DB ops ──────────────────────────────────────────────────────


async def _load_lead(lead_id: int) -> dict | None:
    async with db.get_conn() as conn:
        row = await conn.fetchrow(
            """
            SELECT l.id AS lead_id, l.input_url, l.company_id,
                   c.domain, c.name
            FROM leads l JOIN companies c ON c.id = l.company_id
            WHERE l.id = $1
            """,
            lead_id,
        )
    return dict(row) if row else None


async def _persist_research(
    *,
    lead: dict,
    result: extract.ResearchResult,
    search_count: int,
    fetched_bytes: int,
) -> int:
    """Insert into research_results and update companies. Returns research_id."""
    async with db.get_conn() as conn, conn.transaction():
        # Find or create the workflow_run for this lead. For the
        # admin/test endpoint we create a one-step run keyed to the
        # lead so research_results.run_id has a real reference.
        run_id = await conn.fetchval(
            """
            INSERT INTO workflow_runs (lead_id, status, triggered_by, started_at, finished_at)
            VALUES ($1, 'success', 'research-only', NOW(), NOW())
            RETURNING id
            """,
            lead["lead_id"],
        )

        research_id = await conn.fetchval(
            """
            INSERT INTO research_results (
                run_id, payload, summary,
                search_results_count, fetched_bytes,
                model, tokens_in, tokens_out, cost_usd
            )
            VALUES ($1, $2::jsonb, $3, $4, $5, $6, $7, $8, $9)
            ON CONFLICT (run_id) DO UPDATE SET
                payload              = EXCLUDED.payload,
                summary              = EXCLUDED.summary,
                search_results_count = EXCLUDED.search_results_count,
                fetched_bytes        = EXCLUDED.fetched_bytes,
                model                = EXCLUDED.model,
                tokens_in            = EXCLUDED.tokens_in,
                tokens_out           = EXCLUDED.tokens_out,
                cost_usd             = EXCLUDED.cost_usd
            RETURNING id
            """,
            run_id,
            json.dumps(result.payload),
            result.summary,
            search_count,
            fetched_bytes,
            result.model,
            result.tokens_in,
            result.tokens_out,
            result.cost_usd,
        )

        # Patch companies with the freshly-extracted name + industry.
        await conn.execute(
            """
            UPDATE companies
            SET name       = COALESCE($2, name),
                industry   = COALESCE($3, industry),
                size_estimate = COALESCE($4, size_estimate),
                metadata   = $5::jsonb,
                updated_at = NOW()
            WHERE id = $1
            """,
            lead["company_id"],
            (result.payload.get("headline") or lead.get("name")),
            result.payload.get("industry"),
            result.payload.get("size_estimate"),
            json.dumps({
                "tech_stack":  result.payload.get("tech_stack", []),
                "key_people":  result.payload.get("key_people", []),
                "recent_news": result.payload.get("recent_news", []),
            }),
        )

    return research_id


# ─── Public API ──────────────────────────────────────────────────


async def research_for_lead(lead_id: int) -> ResearchRunResult:
    """Run research for an existing lead. Raises on missing lead or
    missing cached HTML."""
    lead = await _load_lead(lead_id)
    if lead is None:
        raise LookupError(f"lead {lead_id} not found")

    if not spend_tracker.under_cap():
        raise RuntimeError(
            "daily OpenAI spend cap reached -- service resumes at UTC midnight",
        )

    domain = lead["domain"]
    html = _latest_cached_html(domain)
    if html is None:
        raise FileNotFoundError(
            f"no cached HTML for domain {domain!r}; re-run lead intake",
        )

    page_text = extract.html_to_text(html)
    search_hits = await brave.web_search(domain)

    result = await extract.extract_profile(
        domain=domain,
        url=lead["input_url"],
        page_text=page_text,
        search_hits=search_hits,
    )
    spend_tracker.add(result.cost_usd)

    research_id = await _persist_research(
        lead=lead,
        result=result,
        search_count=len(search_hits),
        fetched_bytes=len(html),
    )

    log.info(
        "research.done",
        lead_id=lead_id, research_id=research_id,
        domain=domain, model=result.model,
        tokens_in=result.tokens_in, tokens_out=result.tokens_out,
        cost_usd=round(result.cost_usd, 6),
        search_hits=len(search_hits),
    )

    return ResearchRunResult(
        research_id=research_id,
        lead_id=lead_id,
        domain=domain,
        payload=result.payload,
        summary=result.summary,
        search_results_count=len(search_hits),
        fetched_bytes=len(html),
        model=result.model,
        tokens_in=result.tokens_in,
        tokens_out=result.tokens_out,
        cost_usd=round(result.cost_usd, 6),
    )
