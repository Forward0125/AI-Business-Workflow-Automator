"""End-to-end workflow orchestrator.

Runs the 8-step DAG (fetch -> web_search -> research -> qualify ->
personalize -> crm -> calendar -> email) for a single lead, updating
``workflow_runs`` + ``workflow_steps`` rows and emitting SSE events
through the in-memory ``JobBroker``.

Public entry: ``start_pipeline(url, ...)`` returns a run_id IMMEDIATELY
and spawns the actual work as ``asyncio.create_task``. The HTTP layer
returns that run_id so the visitor can subscribe to the SSE stream
right away.

For step-9 admin endpoints we kept simpler "run only one stage"
modules (``research/run.py``, ``qualify/run.py``, ``personalize/run.py``).
This module bypasses those and uses the LOWER-LEVEL building blocks
(``research.extract``, ``qualify.score``, ``personalize.draft``) so
state and persistence stay under the orchestrator's control.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable

from app import db
from app.actions import mocked
from app.alerts import emit_alert
from app.fetch import FetchError
from app.ingest.lead import intake_lead
from app.jobs import broker
from app.logging import get_logger
from app.personalize.draft import DEFAULT_TONE, Tone, draft_email
from app.qualify.score import score_bant
from app.research import brave, extract
from app.runs import state
from app.settings import PROJECT_ROOT
from app.spend_tracker import tracker as spend_tracker


log = get_logger(__name__)

CACHE_ROOT = PROJECT_ROOT / "data" / "raw"


# ─── Step runner helper ─────────────────────────────────────────


async def _run_step(
    run_id:  int,
    name:    str,
    work:    Callable[[], Awaitable[tuple[Any, dict[str, Any]]]],
) -> Any:
    """Run a single pipeline step.

    ``work`` is a 0-arg async callable returning ``(result, metadata)``.
    The ``metadata`` dict gets persisted on the step row and broadcast
    in the SSE step.completed event. Any exception fails the step and
    is re-raised to the caller.
    """
    await state.start_step(run_id, name)
    await broker.emit(run_id, {"type": "step.started", "step": name})

    try:
        result, meta = await work()
    except Exception as exc:
        await state.fail_step(run_id, name, str(exc))
        await broker.emit(run_id, {
            "type": "step.failed", "step": name, "error": str(exc),
        })
        raise

    await state.complete_step(run_id, name, meta)
    await broker.emit(run_id, {
        "type": "step.completed", "step": name, **meta,
    })
    return result


# ─── Persistence helpers ────────────────────────────────────────


async def _persist_research(
    *, run_id: int, result: extract.ResearchResult,
    search_count: int, fetched_bytes: int,
) -> None:
    async with db.get_conn() as conn:
        await conn.execute(
            """
            INSERT INTO research_results (
                run_id, payload, summary,
                search_results_count, fetched_bytes,
                model, tokens_in, tokens_out, cost_usd
            )
            VALUES ($1, $2::jsonb, $3, $4, $5, $6, $7, $8, $9)
            """,
            run_id,
            json.dumps(result.payload),
            result.summary,
            search_count,
            fetched_bytes,
            result.model, result.tokens_in, result.tokens_out, result.cost_usd,
        )


async def _persist_qualification(*, run_id: int, score) -> None:
    async with db.get_conn() as conn:
        await conn.execute(
            """
            INSERT INTO qualifications (
                run_id,
                budget_score, authority_score, need_score, timing_score,
                composite_score, qualified, reasoning,
                model, tokens_in, tokens_out, cost_usd
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
            """,
            run_id,
            score.budget, score.authority, score.need, score.timing,
            score.composite, score.qualified, score.reasoning,
            score.model, score.tokens_in, score.tokens_out, score.cost_usd,
        )


async def _persist_email_draft(*, run_id: int, draft) -> int:
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
            run_id, draft.tone, draft.subject, draft.body,
            json.dumps(draft.cited_findings),
            draft.model, draft.tokens_in, draft.tokens_out, draft.cost_usd,
        )


def _latest_cached_html(domain: str) -> bytes | None:
    folder = CACHE_ROOT / domain
    if not folder.exists():
        return None
    files = sorted(folder.glob("*.html"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        return None
    return files[0].read_bytes()


# ─── The pipeline body ──────────────────────────────────────────


async def _execute(
    run_id: int,
    *,
    url:    str,
    tone:   Tone,
    pitch:  str | None,
    ip:     str | None,
    ua:     str | None,
) -> None:
    """The actual pipeline. Called as a background task."""
    await broker.emit(run_id, {
        "type": "run.started", "run_id": run_id, "url": url, "tone": tone,
    })

    total_cost = 0.0
    total_tokens_in = 0
    total_tokens_out = 0

    # ─── 1. Fetch ─────────────────────────────────────────────
    async def _fetch_step():
        try:
            r = await intake_lead(url, ip_address=ip, user_agent=ua)
        except FetchError as exc:
            raise RuntimeError(f"fetch failed: {exc}") from exc
        return r, {
            "lead_id":       r.lead_id,
            "domain":        r.domain,
            "fetched_bytes": r.fetched_bytes,
            "elapsed_ms":    r.elapsed_ms,
            "title":         (r.title or "")[:120],
        }

    lead_result = await _run_step(run_id, "fetch", _fetch_step)
    await state.set_lead_id(run_id, lead_result.lead_id)

    # ─── 2. Web search (no-op when BRAVE_API_KEY blank) ───────
    async def _search_step():
        hits = await brave.web_search(lead_result.domain)
        return hits, {"hits": len(hits), "domain": lead_result.domain}

    search_hits = await _run_step(run_id, "web_search", _search_step)

    # ─── 3. Research extraction ───────────────────────────────
    async def _research_step():
        if not spend_tracker.under_cap():
            raise RuntimeError("daily OpenAI spend cap reached")
        html = _latest_cached_html(lead_result.domain)
        if html is None:
            raise RuntimeError(f"missing cached html for {lead_result.domain}")
        page_text = extract.html_to_text(html)
        r = await extract.extract_profile(
            domain=lead_result.domain,
            url=lead_result.final_url,
            page_text=page_text,
            search_hits=search_hits,
        )
        spend_tracker.add(r.cost_usd)
        await _persist_research(
            run_id=run_id, result=r,
            search_count=len(search_hits),
            fetched_bytes=lead_result.fetched_bytes,
        )
        return r, {
            "industry":     r.payload.get("industry"),
            "size":         r.payload.get("size_estimate"),
            "headline":     (r.payload.get("headline") or "")[:200],
            "summary":      r.payload.get("summary"),
            "tech_stack":   r.payload.get("tech_stack", []),
            "key_people":   r.payload.get("key_people", []),
            "recent_news":  r.payload.get("recent_news", []),
            "tokens_in":    r.tokens_in,
            "tokens_out":   r.tokens_out,
            "cost_usd":     round(r.cost_usd, 6),
        }

    research_result = await _run_step(run_id, "research", _research_step)
    total_cost += research_result.cost_usd
    total_tokens_in  += research_result.tokens_in
    total_tokens_out += research_result.tokens_out

    # ─── 4. Qualify (BANT) ─────────────────────────────────────
    async def _qualify_step():
        if not spend_tracker.under_cap():
            raise RuntimeError("daily OpenAI spend cap reached")
        s = await score_bant(profile=research_result.payload, pitch=pitch)
        spend_tracker.add(s.cost_usd)
        await _persist_qualification(run_id=run_id, score=s)
        return s, {
            "composite":  s.composite,
            "qualified":  s.qualified,
            "budget":     s.budget,
            "authority":  s.authority,
            "need":       s.need,
            "timing":     s.timing,
            "tokens_in":  s.tokens_in,
            "tokens_out": s.tokens_out,
            "cost_usd":   round(s.cost_usd, 6),
        }

    qualification = await _run_step(run_id, "qualify", _qualify_step)
    total_cost += qualification.cost_usd
    total_tokens_in  += qualification.tokens_in
    total_tokens_out += qualification.tokens_out

    # Surface notably low-fit leads to the dashboard's alert feed --
    # the rep would want to skim these for "is this even worth a touch?".
    if qualification.composite < 0.30:
        await emit_alert(
            severity="info",
            title=f"Low-fit lead detected (composite {qualification.composite:.2f})",
            body=f"{lead_result.domain} -- {qualification.reasoning[:300]}",
            source="qualify",
            metadata={"run_id": run_id, "lead_id": lead_result.lead_id},
        )

    # ─── 5. Personalize ───────────────────────────────────────
    qual_for_prompt = {
        "budget":    qualification.budget,
        "authority": qualification.authority,
        "need":      qualification.need,
        "timing":    qualification.timing,
        "composite": qualification.composite,
        "qualified": qualification.qualified,
        "reasoning": qualification.reasoning,
    }

    async def _personalize_step():
        if not spend_tracker.under_cap():
            raise RuntimeError("daily OpenAI spend cap reached")
        d = await draft_email(
            profile=research_result.payload,
            qualification=qual_for_prompt,
            pitch=pitch,
            tone=tone,
        )
        spend_tracker.add(d.cost_usd)
        draft_id = await _persist_email_draft(run_id=run_id, draft=d)
        return d, {
            "email_draft_id":    draft_id,
            "tone":              d.tone,
            "subject":           d.subject,
            "body":              d.body,
            "cited_findings":    d.cited_findings,
            "unknown_citations": d.unknown_citations,
            "tokens_in":         d.tokens_in,
            "tokens_out":        d.tokens_out,
            "cost_usd":          round(d.cost_usd, 6),
        }

    email_draft = await _run_step(run_id, "personalize", _personalize_step)
    total_cost += email_draft.cost_usd
    total_tokens_in  += email_draft.tokens_in
    total_tokens_out += email_draft.tokens_out

    # ─── 6. CRM (mocked) ──────────────────────────────────────
    async def _crm_step():
        result = await mocked.crm_update(
            company_id=lead_result.company_id,
            domain=lead_result.domain,
            qualified=qualification.qualified,
            composite=qualification.composite,
            industry=research_result.payload.get("industry"),
            size_estimate=research_result.payload.get("size_estimate"),
        )
        await mocked.persist(run_id, result)
        return result, {
            "duration_ms": result.duration_ms,
            "platform":    result.payload.get("platform"),
            "deal_stage":  result.payload.get("deal_stage"),
            "score":       result.payload.get("score"),
            "payload":     result.payload,
        }

    await _run_step(run_id, "crm", _crm_step)

    # ─── 7. Calendar (mocked) ─────────────────────────────────
    async def _calendar_step():
        result = await mocked.calendar_book(
            domain=lead_result.domain,
            primary_contact=None,
        )
        await mocked.persist(run_id, result)
        return result, {
            "duration_ms":  result.duration_ms,
            "platform":     result.payload.get("platform"),
            "scheduled_at": result.payload.get("scheduled_at"),
            "payload":      result.payload,
        }

    await _run_step(run_id, "calendar", _calendar_step)

    # ─── 8. Email (mocked) ────────────────────────────────────
    async def _email_step():
        result = await mocked.email_send(
            domain=lead_result.domain,
            primary_contact=None,
            subject=email_draft.subject,
            body_preview=email_draft.body,
        )
        await mocked.persist(run_id, result)
        return result, {
            "duration_ms":  result.duration_ms,
            "platform":     result.payload.get("platform"),
            "scheduled_at": result.payload.get("scheduled_at"),
            "message_id":   result.payload.get("message_id"),
            "payload":      result.payload,
        }

    await _run_step(run_id, "email", _email_step)

    # ─── Done ─────────────────────────────────────────────────
    await state.complete_run(
        run_id,
        total_cost_usd=round(total_cost, 6),
        total_tokens_in=total_tokens_in,
        total_tokens_out=total_tokens_out,
    )
    await broker.emit(run_id, {
        "type":             "run.completed",
        "run_id":           run_id,
        "lead_id":          lead_result.lead_id,
        "qualified":        qualification.qualified,
        "composite":        qualification.composite,
        "email_subject":    email_draft.subject,
        "total_cost_usd":   round(total_cost, 6),
        "total_tokens_in":  total_tokens_in,
        "total_tokens_out": total_tokens_out,
    })


# ─── Public API ──────────────────────────────────────────────────


async def start_pipeline(
    *,
    url:   str,
    tone:  Tone = DEFAULT_TONE,
    pitch: str | None = None,
    ip:    str | None = None,
    ua:    str | None = None,
    triggered_by: str = "visitor",
) -> int:
    """Create a workflow_run, spawn the work as a background task,
    return run_id immediately."""
    run_id = await state.create_run(triggered_by=triggered_by, ip_address=ip)

    async def _bg() -> None:
        try:
            await _execute(run_id, url=url, tone=tone, pitch=pitch, ip=ip, ua=ua)
        except Exception as exc:
            log.error("pipeline.failed", run_id=run_id, error=str(exc))
            await state.fail_run(run_id, str(exc))
            await broker.emit(run_id, {
                "type": "run.failed", "run_id": run_id, "error": str(exc),
            })
            await emit_alert(
                severity="error",
                title=f"Workflow run #{run_id} failed",
                body=str(exc)[:500],
                source="pipeline",
                metadata={"run_id": run_id, "url": url},
            )
        finally:
            await broker.end(run_id)

    asyncio.create_task(_bg())
    return run_id
